"""MANE Select integration for therapeutic-grade transcript selection.

MANE (Matched Annotation from NCBI and EMBL-EBI) provides consensus
transcript selections that are ideal for therapeutic development.
"""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class MANETranscript:
    """Represents a MANE-selected transcript with therapeutic-relevant data."""
    
    gene_symbol: str
    gene_id: str
    refseq_accession: str  # NM_XXXXXX.X
    ensembl_accession: str  # ENST000000XXXXX.X
    mane_type: str  # "MANE Select" or "MANE Plus Clinical"
    
    # Sequences
    cds_sequence: str
    five_utr: Optional[str] = None
    three_utr: Optional[str] = None
    
    # Metadata
    protein_accession: Optional[str] = None  # NP_XXXXXX.X
    transcript_length: Optional[int] = None
    cds_start: Optional[int] = None
    cds_end: Optional[int] = None
    
    # Quality metrics
    has_complete_cds: bool = True
    has_canonical_start: bool = True  # ATG
    has_canonical_stop: bool = True   # TAA, TAG, or TGA
    
    @property
    def full_mrna_sequence(self) -> str:
        """Get complete mRNA sequence (5'UTR + CDS + 3'UTR)."""
        parts = []
        if self.five_utr:
            parts.append(self.five_utr)
        parts.append(self.cds_sequence)
        if self.three_utr:
            parts.append(self.three_utr)
        return ''.join(parts)


class MANESelector:
    """Retrieves MANE Select transcripts for therapeutic applications."""
    
    # NCBI Datasets API v2
    DATASETS_BASE = "https://api.ncbi.nlm.nih.gov/datasets/v2alpha"
    
    # Fallback: NCBI E-utilities
    EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    # Cache configuration
    CACHE_DIR = Path("cache/mane_transcripts")
    CACHE_EXPIRY = 30 * 24 * 3600  # 30 days
    
    def __init__(self, api_key: Optional[str] = None, cache_enabled: bool = True):
        """Initialize MANE selector.
        
        Args:
            api_key: NCBI API key for increased rate limits
            cache_enabled: Whether to cache MANE results
        """
        self.api_key = api_key
        self.cache_enabled = cache_enabled
        
        # Create cache directory
        if cache_enabled:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Setup session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        
        # Rate limiting
        self.last_request_time = 0
        self.rate_limit = 10 if api_key else 3  # requests per second
    
    def get_mane_transcript(self, gene_symbol: str) -> Optional[MANETranscript]:
        """Get MANE Select transcript for a gene.
        
        Args:
            gene_symbol: HGNC gene symbol (e.g., "CFTR", "TP53")
            
        Returns:
            MANETranscript object or None if no MANE selection exists
        """
        # Check cache first
        cached = self._load_from_cache(gene_symbol)
        if cached:
            return cached
        
        # Try NCBI Datasets API first (preferred)
        mane = self._get_from_datasets_api(gene_symbol)
        
        # Fallback to E-utilities if needed
        if not mane:
            mane = self._get_from_eutils(gene_symbol)
        
        # Cache successful result
        if mane and self.cache_enabled:
            self._save_to_cache(gene_symbol, mane)
        
        return mane
    
    def _get_from_datasets_api(self, gene_symbol: str) -> Optional[MANETranscript]:
        """Retrieve MANE transcript using NCBI Datasets API v2."""
        try:
            # Rate limiting
            self._rate_limit()
            
            # Build request URL
            url = f"{self.DATASETS_BASE}/gene/symbol/{quote(gene_symbol)}/taxon/9606"
            
            headers = {
                'Accept': 'application/json',
            }
            
            if self.api_key:
                headers['api-key'] = self.api_key
            
            response = self.session.get(url, headers=headers, timeout=30)
            
            if response.status_code == 404:
                logger.info(f"No gene found for symbol: {gene_symbol}")
                return None
            
            response.raise_for_status()
            data = response.json()
            
            # Parse gene data
            genes = data.get('genes', [])
            if not genes:
                logger.warning(f"No gene data found for: {gene_symbol}")
                return None
            
            gene_data = genes[0]  # Take first match
            gene_id = str(gene_data.get('gene_id', ''))
            
            # Look for MANE transcript
            transcripts = gene_data.get('transcripts', [])
            
            for transcript in transcripts:
                # Check if this is MANE Select
                if transcript.get('mane_select'):
                    return self._parse_mane_transcript(
                        gene_symbol, 
                        gene_id,
                        transcript,
                        'MANE Select'
                    )
            
            # Check for MANE Plus Clinical
            for transcript in transcripts:
                if transcript.get('mane_plus_clinical'):
                    return self._parse_mane_transcript(
                        gene_symbol,
                        gene_id, 
                        transcript,
                        'MANE Plus Clinical'
                    )
            
            logger.info(f"No MANE transcript found for: {gene_symbol}")
            return None
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch from Datasets API: {e}")
            return None
    
    def _get_from_eutils(self, gene_symbol: str) -> Optional[MANETranscript]:
        """Fallback method using NCBI E-utilities."""
        try:
            # First, get gene ID
            gene_id = self._get_gene_id_eutils(gene_symbol)
            if not gene_id:
                return None
            
            # Rate limiting
            self._rate_limit()
            
            # Fetch gene record with MANE info
            params = {
                'db': 'gene',
                'id': gene_id,
                'retmode': 'xml'
            }
            
            if self.api_key:
                params['api_key'] = self.api_key
            
            response = self.session.get(
                f"{self.EUTILS_BASE}/efetch.fcgi",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            # Parse XML for MANE accession
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.text)
            
            # Look for MANE_Select in the XML
            for elem in root.iter():
                if elem.tag == 'Gene-commentary_label' and 'MANE' in elem.text:
                    # Found MANE annotation
                    accession = self._extract_mane_accession(elem)
                    if accession:
                        # Now fetch the actual sequence
                        return self._fetch_sequence_data(
                            gene_symbol,
                            gene_id,
                            accession,
                            'MANE Select'
                        )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch from E-utilities: {e}")
            return None
    
    def _get_gene_id_eutils(self, gene_symbol: str) -> Optional[str]:
        """Get NCBI Gene ID using E-utilities."""
        try:
            self._rate_limit()
            
            params = {
                'db': 'gene',
                'term': f'{gene_symbol}[sym] AND human[organism]',
                'retmode': 'json'
            }
            
            if self.api_key:
                params['api_key'] = self.api_key
            
            response = self.session.get(
                f"{self.EUTILS_BASE}/esearch.fcgi",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            id_list = data.get('esearchresult', {}).get('idlist', [])
            
            if id_list:
                return id_list[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get gene ID: {e}")
            return None
    
    def _fetch_sequence_data(
        self, 
        gene_symbol: str,
        gene_id: str,
        refseq_accession: str,
        mane_type: str
    ) -> Optional[MANETranscript]:
        """Fetch actual sequence data for a MANE transcript."""
        try:
            self._rate_limit()
            
            # Fetch from NCBI Nucleotide database
            params = {
                'db': 'nuccore',
                'id': refseq_accession,
                'rettype': 'gbwithparts',
                'retmode': 'json'
            }
            
            if self.api_key:
                params['api_key'] = self.api_key
            
            response = self.session.get(
                f"{self.EUTILS_BASE}/efetch.fcgi",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            # Parse GenBank format for sequences
            gb_data = response.json()
            
            # Extract CDS and UTRs
            cds_seq, five_utr, three_utr = self._extract_sequences_from_genbank(gb_data)
            
            if not cds_seq:
                logger.warning(f"No CDS found for {refseq_accession}")
                return None
            
            # Validate CDS
            has_atg = cds_seq.upper().startswith('ATG')
            has_stop = cds_seq.upper()[-3:] in ['TAA', 'TAG', 'TGA']
            
            return MANETranscript(
                gene_symbol=gene_symbol,
                gene_id=gene_id,
                refseq_accession=refseq_accession,
                ensembl_accession='',  # Would need separate lookup
                mane_type=mane_type,
                cds_sequence=cds_seq,
                five_utr=five_utr,
                three_utr=three_utr,
                has_canonical_start=has_atg,
                has_canonical_stop=has_stop
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch sequence data: {e}")
            return None
    
    def _parse_mane_transcript(
        self,
        gene_symbol: str,
        gene_id: str,
        transcript_data: Dict,
        mane_type: str
    ) -> MANETranscript:
        """Parse MANE transcript from Datasets API response."""
        refseq_acc = transcript_data.get('accession_version', '')
        ensembl_acc = transcript_data.get('ensembl_transcript', '')
        
        # Get sequence data
        cds_data = transcript_data.get('cds', {})
        cds_seq = cds_data.get('sequence', '')
        
        # Get UTRs if available
        five_utr = transcript_data.get('5_utr', {}).get('sequence')
        three_utr = transcript_data.get('3_utr', {}).get('sequence')
        
        # Validate CDS
        has_atg = cds_seq.upper().startswith('ATG')
        has_stop = cds_seq.upper()[-3:] in ['TAA', 'TAG', 'TGA']
        
        return MANETranscript(
            gene_symbol=gene_symbol,
            gene_id=gene_id,
            refseq_accession=refseq_acc,
            ensembl_accession=ensembl_acc,
            mane_type=mane_type,
            cds_sequence=cds_seq,
            five_utr=five_utr,
            three_utr=three_utr,
            protein_accession=transcript_data.get('protein_accession'),
            transcript_length=transcript_data.get('length'),
            cds_start=cds_data.get('start'),
            cds_end=cds_data.get('end'),
            has_canonical_start=has_atg,
            has_canonical_stop=has_stop,
            has_complete_cds=bool(cds_seq)
        )
    
    def _extract_sequences_from_genbank(self, gb_data: Dict) -> Tuple[str, Optional[str], Optional[str]]:
        """Extract CDS and UTR sequences from GenBank JSON."""
        # This is a simplified version - would need proper GenBank parsing
        # In practice, would use Bio.SeqIO for robust parsing
        cds = ''
        five_utr = None
        three_utr = None
        
        # Extract from features
        features = gb_data.get('features', [])
        sequence = gb_data.get('sequence', '')
        
        for feature in features:
            if feature.get('type') == 'CDS':
                location = feature.get('location', '')
                # Parse location to extract sequence
                # This is simplified - real implementation would handle complex locations
                start, end = self._parse_location(location)
                if start and end:
                    cds = sequence[start-1:end]
            
            elif feature.get('type') == '5UTR':
                location = feature.get('location', '')
                start, end = self._parse_location(location)
                if start and end:
                    five_utr = sequence[start-1:end]
            
            elif feature.get('type') == '3UTR':
                location = feature.get('location', '')
                start, end = self._parse_location(location)
                if start and end:
                    three_utr = sequence[start-1:end]
        
        return cds, five_utr, three_utr
    
    def _parse_location(self, location: str) -> Tuple[Optional[int], Optional[int]]:
        """Parse GenBank location string."""
        # Simplified parsing - handle basic cases like "100..500"
        import re
        match = re.search(r'(\d+)\.\.(\d+)', location)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None, None
    
    def _extract_mane_accession(self, elem) -> Optional[str]:
        """Extract MANE accession from XML element."""
        # Look for RefSeq accession in sibling elements
        parent = elem.getparent()
        if parent is not None:
            for sibling in parent:
                if sibling.tag == 'Gene-commentary_accession':
                    return sibling.text
        return None
    
    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        min_interval = 1.0 / self.rate_limit
        
        if time_since_last < min_interval:
            time.sleep(min_interval - time_since_last)
        
        self.last_request_time = time.time()
    
    def _load_from_cache(self, gene_symbol: str) -> Optional[MANETranscript]:
        """Load MANE transcript from cache."""
        if not self.cache_enabled:
            return None
        
        cache_file = self.CACHE_DIR / f"{gene_symbol.lower()}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                
                # Check expiry
                if time.time() - data['timestamp'] < self.CACHE_EXPIRY:
                    transcript_data = data['transcript']
                    return MANETranscript(**transcript_data)
                    
            except Exception as e:
                logger.warning(f"Failed to load cache for {gene_symbol}: {e}")
        
        return None
    
    def _save_to_cache(self, gene_symbol: str, transcript: MANETranscript) -> None:
        """Save MANE transcript to cache."""
        if not self.cache_enabled:
            return
        
        cache_file = self.CACHE_DIR / f"{gene_symbol.lower()}.json"
        
        try:
            with open(cache_file, 'w') as f:
                json.dump({
                    'timestamp': time.time(),
                    'gene_symbol': gene_symbol,
                    'transcript': {
                        'gene_symbol': transcript.gene_symbol,
                        'gene_id': transcript.gene_id,
                        'refseq_accession': transcript.refseq_accession,
                        'ensembl_accession': transcript.ensembl_accession,
                        'mane_type': transcript.mane_type,
                        'cds_sequence': transcript.cds_sequence,
                        'five_utr': transcript.five_utr,
                        'three_utr': transcript.three_utr,
                        'protein_accession': transcript.protein_accession,
                        'transcript_length': transcript.transcript_length,
                        'cds_start': transcript.cds_start,
                        'cds_end': transcript.cds_end,
                        'has_complete_cds': transcript.has_complete_cds,
                        'has_canonical_start': transcript.has_canonical_start,
                        'has_canonical_stop': transcript.has_canonical_stop
                    }
                }, f, indent=2)
                
        except Exception as e:
            logger.warning(f"Failed to save cache for {gene_symbol}: {e}")
    
    def get_mane_status(self, gene_symbol: str) -> Dict[str, any]:
        """Get comprehensive MANE status for a gene.
        
        Returns information about MANE availability and alternatives.
        """
        mane = self.get_mane_transcript(gene_symbol)
        
        if mane:
            return {
                'has_mane': True,
                'mane_type': mane.mane_type,
                'refseq_accession': mane.refseq_accession,
                'ensembl_accession': mane.ensembl_accession,
                'has_complete_cds': mane.has_complete_cds,
                'has_canonical_start': mane.has_canonical_start,
                'has_canonical_stop': mane.has_canonical_stop,
                'cds_length': len(mane.cds_sequence),
                'has_utrs': bool(mane.five_utr and mane.three_utr)
            }
        else:
            return {
                'has_mane': False,
                'mane_type': None,
                'recommendation': 'Use RefSeq Select or longest CDS as fallback'
            }