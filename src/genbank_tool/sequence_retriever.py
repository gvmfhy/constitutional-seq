"""Sequence retrieval module for NCBI GenBank tool."""

import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import requests
from Bio import Entrez, SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import RetrievedSequence
from .transcript_selector import TranscriptSelector, TranscriptSelection

logger = logging.getLogger(__name__)


class SequenceRetriever:
    """Retrieves CDS sequences from NCBI RefSeq database."""
    
    NCBI_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    GENBANK_URL_TEMPLATE = "https://www.ncbi.nlm.nih.gov/nuccore/{accession}"
    RATE_LIMIT = 3  # requests per second for non-API key users
    CACHE_DIR = Path("cache/sequences")
    
    def __init__(self, api_key: Optional[str] = None, email: Optional[str] = None, 
                 cache_enabled: bool = True, enable_selection: bool = True):
        """Initialize the sequence retriever.
        
        Args:
            api_key: Optional NCBI API key for increased rate limits
            email: Email for NCBI Entrez (required by NCBI guidelines)
            cache_enabled: Whether to use local caching
            enable_selection: Whether to enable transcript selection
        """
        self.api_key = api_key
        self.email = email or "user@example.com"
        self.cache_enabled = cache_enabled
        self.enable_selection = enable_selection
        
        # Set up Biopython Entrez
        Entrez.email = self.email
        if api_key:
            Entrez.api_key = api_key
        
        if self.cache_enabled:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Setup session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,  # Exponential backoff
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        
        # Rate limiting
        self.last_request_time = 0
        self.rate_limit = 10 if api_key else self.RATE_LIMIT
        
        # Initialize transcript selector if enabled
        if self.enable_selection:
            self.selector = TranscriptSelector(
                uniprot_enabled=True, 
                prefer_longest=True,
                mane_enabled=True,
                api_key=api_key
            )
    
    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        min_interval = 1.0 / self.rate_limit
        
        if time_since_last < min_interval:
            time.sleep(min_interval - time_since_last)
        
        self.last_request_time = time.time()
    
    def _get_cache_path(self, gene_id: str) -> Path:
        """Get cache file path for a gene ID."""
        return self.CACHE_DIR / f"gene_{gene_id}_sequences.json"
    
    def _load_from_cache(self, gene_id: str) -> Optional[List[Dict]]:
        """Load sequences from cache if available."""
        if not self.cache_enabled:
            return None
            
        cache_path = self._get_cache_path(gene_id)
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    data = json.load(f)
                # Check if cache is less than 7 days old
                if time.time() - data['timestamp'] < 7 * 24 * 3600:
                    logger.debug(f"Cache hit for gene ID: {gene_id}")
                    return data['sequences']
            except Exception as e:
                logger.warning(f"Failed to load cache for gene {gene_id}: {e}")
        
        return None
    
    def _save_to_cache(self, gene_id: str, sequences: List[Dict]) -> None:
        """Save sequences to cache."""
        if not self.cache_enabled:
            return
            
        cache_path = self._get_cache_path(gene_id)
        try:
            with open(cache_path, 'w') as f:
                json.dump({
                    'timestamp': time.time(),
                    'gene_id': gene_id,
                    'sequences': sequences
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache for gene {gene_id}: {e}")
    
    def _search_refseq_transcripts(self, gene_id: str) -> List[str]:
        """Search for RefSeq transcripts for a gene.
        
        Args:
            gene_id: NCBI Gene ID
            
        Returns:
            List of RefSeq accession numbers
        """
        # Build search query for RefSeq mRNA transcripts
        query = f"{gene_id}[Gene ID] AND refseq[filter] AND mRNA[filter]"
        
        self._rate_limit()
        
        try:
            handle = Entrez.esearch(
                db="nuccore",
                term=query,
                retmax=50,  # Get up to 50 transcripts
                sort="relevance"
            )
            record = Entrez.read(handle)
            handle.close()
            
            transcript_ids = record.get("IdList", [])
            logger.info(f"Found {len(transcript_ids)} RefSeq transcripts for gene {gene_id}")
            
            return transcript_ids
            
        except Exception as e:
            logger.error(f"Failed to search RefSeq transcripts for gene {gene_id}: {e}")
            return []
    
    def _fetch_genbank_records(self, accession_ids: List[str]) -> List[SeqRecord]:
        """Fetch GenBank records for accession IDs.
        
        Args:
            accession_ids: List of NCBI accession IDs
            
        Returns:
            List of SeqRecord objects
        """
        if not accession_ids:
            return []
        
        self._rate_limit()
        
        try:
            handle = Entrez.efetch(
                db="nuccore",
                id=accession_ids,
                rettype="gb",
                retmode="text"
            )
            
            records = list(SeqIO.parse(handle, "genbank"))
            handle.close()
            
            logger.info(f"Fetched {len(records)} GenBank records")
            return records
            
        except Exception as e:
            logger.error(f"Failed to fetch GenBank records: {e}")
            return []
    
    def _extract_cds_features(self, record: SeqRecord) -> List[Dict]:
        """Extract CDS features from a GenBank record.
        
        Args:
            record: BioPython SeqRecord object
            
        Returns:
            List of CDS feature dictionaries
        """
        cds_features = []
        
        for feature in record.features:
            if feature.type == "CDS":
                # Extract CDS sequence
                try:
                    cds_seq = feature.extract(record.seq)
                    
                    # Get qualifiers
                    qualifiers = feature.qualifiers
                    
                    cds_info = {
                        'sequence': str(cds_seq),
                        'length': len(cds_seq),
                        'protein_id': qualifiers.get('protein_id', [''])[0],
                        'product': qualifiers.get('product', [''])[0],
                        'translation': qualifiers.get('translation', [''])[0],
                        'gene': qualifiers.get('gene', [''])[0],
                        'note': qualifiers.get('note', [''])[0],
                        'location': str(feature.location)
                    }
                    
                    # Check if it's a complete CDS
                    if len(cds_seq) % 3 == 0 and len(cds_seq) >= 3:
                        if str(cds_seq[:3]).upper() in ['ATG', 'CTG', 'GTG']:
                            cds_info['has_start_codon'] = True
                        if str(cds_seq[-3:]).upper() in ['TAA', 'TAG', 'TGA']:
                            cds_info['has_stop_codon'] = True
                    
                    cds_features.append(cds_info)
                    
                except Exception as e:
                    logger.warning(f"Failed to extract CDS from {record.id}: {e}")
        
        return cds_features
    
    def _is_refseq_select(self, record: SeqRecord) -> bool:
        """Check if a record is RefSeq Select.
        
        Args:
            record: BioPython SeqRecord object
            
        Returns:
            True if RefSeq Select
        """
        # Check keywords field (primary location for RefSeq Select designation)
        if 'keywords' in record.annotations:
            keywords = record.annotations['keywords']
            for keyword in keywords:
                if 'RefSeq Select' in keyword or 'MANE Select' in keyword:
                    return True
        
        # Check comments for RefSeq Select designation
        if 'comment' in record.annotations:
            comment = record.annotations['comment'].upper()
            if 'REFSEQ SELECT' in comment or 'MANE SELECT' in comment:
                return True
        
        # Check in feature qualifiers
        for feature in record.features:
            if feature.type == "source":
                notes = feature.qualifiers.get('note', [])
                for note in notes:
                    if 'RefSeq Select' in note or 'MANE Select' in note:
                        return True
        
        return False
    
    def _extract_transcript_variant(self, record: SeqRecord) -> Optional[str]:
        """Extract transcript variant information.
        
        Args:
            record: BioPython SeqRecord object
            
        Returns:
            Transcript variant string or None
        """
        # Try to extract from definition
        definition = record.description
        
        # Common patterns for transcript variants
        patterns = [
            r'transcript variant (\w+)',
            r'variant (\d+)',
            r'isoform (\w+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, definition, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _get_gene_url(self, gene_id: str, resolved_gene=None) -> Optional[str]:
        """Generate URL to gene page based on source."""
        if resolved_gene and hasattr(resolved_gene, 'source') and resolved_gene.source == "UniProt":
            # For UniProt-resolved genes, link to UniProt
            return f"https://www.uniprot.org/uniprotkb?query=gene:{resolved_gene.official_symbol}+AND+organism_id:9606"
        else:
            # Default to NCBI Gene
            return f"https://www.ncbi.nlm.nih.gov/gene/{gene_id}"
    
    def _extract_isoform_info(self, record) -> Optional[str]:
        """Extract isoform information from GenBank record."""
        # Look for isoform info in description
        description = record.description.lower()
        
        # Pattern for isoform X1, X2, etc.
        isoform_match = re.search(r'isoform\s+([X\d]+)', description, re.IGNORECASE)
        if isoform_match:
            return f"isoform {isoform_match.group(1)}"
        
        # Pattern for variant 1, 2, etc.
        variant_match = re.search(r'variant\s+(\d+)', description, re.IGNORECASE)
        if variant_match:
            return f"variant {variant_match.group(1)}"
        
        # Check qualifiers for isoform info
        for feature in record.features:
            if feature.type == "CDS":
                if 'note' in feature.qualifiers:
                    for note in feature.qualifiers['note']:
                        if 'isoform' in note.lower():
                            return note
        
        return None
    
    def retrieve_by_gene_id(self, gene_symbol: str, gene_id: str, 
                           resolved_gene=None) -> List[RetrievedSequence]:
        """Retrieve all CDS sequences for a gene.
        
        Args:
            gene_symbol: Official gene symbol
            gene_id: NCBI Gene ID
            resolved_gene: Optional ResolvedGene object with full gene info
            
        Returns:
            List of retrieved sequences
        """
        logger.info(f"Retrieving sequences for {gene_symbol} (Gene ID: {gene_id})")
        
        # Check cache first
        cached = self._load_from_cache(gene_id)
        if cached is not None:
            # Convert cached data to RetrievedSequence objects
            sequences = []
            for seq_data in cached:
                # Ensure new fields are populated if missing (for old cache entries)
                if 'full_gene_name' not in seq_data:
                    seq_data['full_gene_name'] = resolved_gene.description if resolved_gene and hasattr(resolved_gene, 'description') else None
                if 'gene_url' not in seq_data:
                    seq_data['gene_url'] = self._get_gene_url(gene_id, resolved_gene)
                if 'isoform' not in seq_data:
                    seq_data['isoform'] = None
                sequences.append(RetrievedSequence(**seq_data))
            return sequences
        
        # Search for RefSeq transcripts
        transcript_ids = self._search_refseq_transcripts(gene_id)
        
        if not transcript_ids:
            logger.warning(f"No RefSeq transcripts found for {gene_symbol}")
            return []
        
        # Fetch GenBank records
        records = self._fetch_genbank_records(transcript_ids)
        
        if not records:
            logger.warning(f"Failed to fetch GenBank records for {gene_symbol}")
            return []
        
        # Extract CDS sequences
        sequences = []
        
        for record in records:
            # Extract CDS features
            cds_features = self._extract_cds_features(record)
            
            if not cds_features:
                logger.debug(f"No CDS found in {record.id}")
                continue
            
            # Usually there's one main CDS per mRNA transcript
            # Take the longest one if multiple
            main_cds = max(cds_features, key=lambda x: x['length'])
            
            # Parse accession and version
            accession_parts = record.id.split('.')
            accession = accession_parts[0]
            version = accession_parts[1] if len(accession_parts) > 1 else "1"
            
            # Create RetrievedSequence object
            seq = RetrievedSequence(
                gene_symbol=gene_symbol,
                gene_id=gene_id,
                accession=accession,
                version=version,
                description=record.description,
                genbank_url=self.GENBANK_URL_TEMPLATE.format(accession=record.id),
                cds_sequence=main_cds['sequence'],
                cds_length=main_cds['length'],
                protein_id=main_cds.get('protein_id'),
                transcript_variant=self._extract_transcript_variant(record),
                refseq_select=self._is_refseq_select(record),
                retrieval_timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                full_gene_name=resolved_gene.description if resolved_gene and hasattr(resolved_gene, 'description') else None,
                gene_url=self._get_gene_url(gene_id, resolved_gene),
                isoform=self._extract_isoform_info(record)
            )
            
            sequences.append(seq)
            
            logger.debug(f"Retrieved {seq.full_accession}: {seq.cds_length} bp CDS")
        
        # Sort by RefSeq Select status and then by length
        sequences.sort(key=lambda x: (x.refseq_select, x.cds_length), reverse=True)
        
        # Cache the results
        if sequences:
            cache_data = [
                {
                    'gene_symbol': s.gene_symbol,
                    'gene_id': s.gene_id,
                    'accession': s.accession,
                    'version': s.version,
                    'description': s.description,
                    'genbank_url': s.genbank_url,
                    'cds_sequence': s.cds_sequence,
                    'cds_length': s.cds_length,
                    'protein_id': s.protein_id,
                    'transcript_variant': s.transcript_variant,
                    'refseq_select': s.refseq_select,
                    'retrieval_timestamp': s.retrieval_timestamp,
                    'full_gene_name': s.full_gene_name,
                    'gene_url': s.gene_url,
                    'isoform': s.isoform
                }
                for s in sequences
            ]
            self._save_to_cache(gene_id, cache_data)
        
        logger.info(f"Retrieved {len(sequences)} sequences for {gene_symbol}")
        
        return sequences
    
    def get_canonical_transcript(
        self,
        gene_symbol: str,
        gene_id: str,
        user_preference: Optional[str] = None,
        resolved_gene=None
    ) -> Optional[TranscriptSelection]:
        """Retrieve and select the canonical transcript for a gene.
        
        Args:
            gene_symbol: Official gene symbol
            gene_id: NCBI Gene ID
            user_preference: Optional user-specified accession
            
        Returns:
            Selected canonical transcript or None
        """
        if not self.enable_selection:
            raise RuntimeError("Transcript selection is not enabled")
        
        # Get all transcripts
        transcripts = self.retrieve_by_gene_id(gene_symbol, gene_id, resolved_gene)
        
        if not transcripts:
            logger.warning(f"No transcripts found for {gene_symbol}")
            return None
        
        # Select canonical
        selection = self.selector.select_canonical(
            transcripts,
            gene_symbol,
            gene_id,
            user_preference
        )
        
        if selection:
            logger.info(
                f"Selected {selection.transcript.full_accession} for {gene_symbol} "
                f"using {selection.method.value} (confidence: {selection.confidence:.2f})"
            )
            
            if selection.warnings:
                for warning in selection.warnings:
                    logger.warning(f"  {warning}")
        
        return selection
    
    def retrieve_by_accession(self, accession: str) -> Optional[RetrievedSequence]:
        """Retrieve a specific sequence by accession number.
        
        Args:
            accession: RefSeq accession number (e.g., NM_001025077)
            
        Returns:
            Retrieved sequence or None
        """
        logger.info(f"Retrieving sequence for accession: {accession}")
        
        # Fetch the record
        records = self._fetch_genbank_records([accession])
        
        if not records:
            logger.error(f"Failed to fetch record for {accession}")
            return None
        
        record = records[0]
        
        # Extract CDS
        cds_features = self._extract_cds_features(record)
        
        if not cds_features:
            logger.error(f"No CDS found in {accession}")
            return None
        
        # Take the main CDS
        main_cds = max(cds_features, key=lambda x: x['length'])
        
        # Parse accession and version
        accession_parts = record.id.split('.')
        acc_base = accession_parts[0]
        version = accession_parts[1] if len(accession_parts) > 1 else "1"
        
        # Extract gene info from features
        gene_symbol = ""
        gene_id = ""
        
        for feature in record.features:
            if feature.type == "gene":
                gene_symbol = feature.qualifiers.get('gene', [''])[0]
                db_xrefs = feature.qualifiers.get('db_xref', [])
                for xref in db_xrefs:
                    if xref.startswith('GeneID:'):
                        gene_id = xref.split(':')[1]
                break
        
        # Create RetrievedSequence
        seq = RetrievedSequence(
            gene_symbol=gene_symbol,
            gene_id=gene_id,
            accession=acc_base,
            version=version,
            description=record.description,
            genbank_url=self.GENBANK_URL_TEMPLATE.format(accession=record.id),
            cds_sequence=main_cds['sequence'],
            cds_length=main_cds['length'],
            protein_id=main_cds.get('protein_id'),
            transcript_variant=self._extract_transcript_variant(record),
            refseq_select=self._is_refseq_select(record),
            retrieval_timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            full_gene_name=None,  # TODO: Get from resolved gene
            gene_url=None,  # TODO: Get from resolved gene
            isoform=self._extract_isoform_info(record)
        )
        
        return seq