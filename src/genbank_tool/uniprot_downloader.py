"""Download and parse UniProt ID mapping files for canonical transcript mapping.

This module downloads the UniProt human ID mapping file to get comprehensive
canonical transcript mappings for all human genes.
"""

import gzip
import json
import logging
import requests
from pathlib import Path
from typing import Dict, Optional, Set
from datetime import datetime, timedelta
from io import StringIO

logger = logging.getLogger(__name__)


class UniProtIDMapper:
    """Downloads and parses UniProt ID mapping to get canonical transcripts."""
    
    # UniProt FTP URLs for ID mapping files
    UNIPROT_ID_MAPPING_URL = "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/idmapping/by_organism/HUMAN_9606_idmapping_selected.tab.gz"
    UNIPROT_FASTA_URL = "https://rest.uniprot.org/uniprotkb/stream?query=organism_id:9606+AND+reviewed:true&format=fasta&fields=accession,gene_primary,xref_refseq"
    
    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the UniProt ID mapper.
        
        Args:
            cache_dir: Directory to store downloaded files and parsed mappings
        """
        self.cache_dir = cache_dir or Path.home() / ".genbank_cache" / "uniprot"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.mapping_file = self.cache_dir / "HUMAN_9606_idmapping_selected.tab.gz"
        self.parsed_cache = self.cache_dir / "canonical_mapping_full.json"
        self.gene_to_transcript: Dict[str, str] = {}
    
    def download_mapping_file(self, force: bool = False) -> bool:
        """Download the UniProt ID mapping file if needed.
        
        Args:
            force: Force re-download even if file exists
            
        Returns:
            True if download successful or file exists
        """
        # Check if file exists and is recent (less than 30 days old)
        if not force and self.mapping_file.exists():
            file_age = datetime.now() - datetime.fromtimestamp(self.mapping_file.stat().st_mtime)
            if file_age < timedelta(days=30):
                logger.info(f"Using existing mapping file (age: {file_age.days} days)")
                return True
        
        logger.info("Downloading UniProt ID mapping file (~50MB)...")
        try:
            response = requests.get(self.UNIPROT_ID_MAPPING_URL, stream=True)
            response.raise_for_status()
            
            # Download in chunks
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(self.mapping_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and downloaded % (1024 * 1024 * 10) < 8192:  # Log every 10MB
                            progress = (downloaded / total_size) * 100
                            logger.info(f"Download progress: {progress:.1f}% ({downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB)")
            
            logger.info("Download complete!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download UniProt mapping file: {e}")
            return False
    
    def parse_mapping_file(self) -> Dict[str, str]:
        """Parse the UniProt ID mapping file to extract gene to transcript mappings.
        
        Returns:
            Dictionary mapping gene symbols to RefSeq transcript IDs
        """
        # Check if we have a recent parsed cache
        if self.parsed_cache.exists():
            try:
                with open(self.parsed_cache, 'r') as f:
                    data = json.load(f)
                    cache_date = data.get('date', 'unknown')
                    self.gene_to_transcript = data.get('mapping', {})
                    if self.gene_to_transcript:
                        logger.info(f"Loaded {len(self.gene_to_transcript)} gene mappings from cache (date: {cache_date})")
                        return self.gene_to_transcript
            except Exception as e:
                logger.warning(f"Failed to load parsed cache: {e}")
        
        if not self.mapping_file.exists():
            logger.error("Mapping file not found. Please download first.")
            return {}
        
        logger.info("Parsing UniProt ID mapping file...")
        gene_to_uniprot: Dict[str, str] = {}  # Gene symbol -> UniProt ID
        uniprot_to_refseq: Dict[str, Set[str]] = {}  # UniProt ID -> RefSeq transcripts
        
        try:
            with gzip.open(self.mapping_file, 'rt') as f:
                # Skip header if present
                header = f.readline().strip()
                logger.debug(f"Header: {header}")
                
                # Expected columns (tab-separated):
                # 0. UniProtKB-AC (e.g., P04637)
                # 1. UniProtKB-ID (e.g., P53_HUMAN)
                # 2. GeneID (EntrezGene)
                # 3. RefSeq (protein and mRNA, semicolon-separated)
                # 4. GI
                # 5. PDB
                # 6. GO
                # ...more columns...
                
                processed = 0
                for line in f:
                    if processed % 10000 == 0:
                        logger.debug(f"Processed {processed} entries...")
                    processed += 1
                    
                    parts = line.strip().split('\t')
                    if len(parts) < 4:
                        continue
                    
                    uniprot_id = parts[0]    # UniProt accession (P04637)
                    uniprot_name = parts[1]   # UniProt ID (P53_HUMAN)
                    refseq_field = parts[3] if len(parts) > 3 else ""  # RefSeq
                    
                    if not uniprot_name or not refseq_field:
                        continue
                    
                    # Extract gene symbol from UniProt ID (P53_HUMAN -> P53)
                    gene_symbol = uniprot_name.split('_')[0] if '_' in uniprot_name else ""
                    if not gene_symbol:
                        continue
                    
                    # Parse RefSeq entries - we get proteins (NP_) not mRNA (NM_)
                    proteins = [t.strip() for t in refseq_field.split(';') 
                               if t.strip().startswith('NP_')]
                    
                    if proteins:
                        # Store the first (canonical) protein for this gene
                        # We'll need to map NP_ to NM_ separately
                        if gene_symbol not in gene_to_uniprot:
                            gene_to_uniprot[gene_symbol] = uniprot_id
                            # Store the canonical protein (first one listed)
                            uniprot_to_refseq[uniprot_id] = [proteins[0]]
            
            # Now create gene to canonical transcript mapping
            # UniProt lists the canonical transcript first
            for gene, uniprot_id in gene_to_uniprot.items():
                transcripts = uniprot_to_refseq.get(uniprot_id, [])
                if transcripts:
                    # Take the first transcript as canonical
                    canonical = transcripts[0].split('.')[0]  # Remove version
                    self.gene_to_transcript[gene] = canonical
            
            logger.info(f"Parsed {len(self.gene_to_transcript)} gene to transcript mappings")
            
            # Save to cache
            self._save_parsed_cache()
            
            return self.gene_to_transcript
            
        except Exception as e:
            logger.error(f"Failed to parse mapping file: {e}")
            return {}
    
    def _save_parsed_cache(self) -> None:
        """Save the parsed mappings to a JSON cache file."""
        try:
            data = {
                'mapping': self.gene_to_transcript,
                'date': datetime.now().isoformat(),
                'count': len(self.gene_to_transcript),
                'source': 'UniProt ID mapping file'
            }
            with open(self.parsed_cache, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self.gene_to_transcript)} mappings to cache")
        except Exception as e:
            logger.warning(f"Failed to save parsed cache: {e}")
    
    def map_protein_to_mrna(self, protein_accession: str) -> Optional[str]:
        """Map a protein accession (NP_) to its mRNA transcript (NM_) via NCBI.
        
        Args:
            protein_accession: RefSeq protein accession (e.g., NP_000537.3)
            
        Returns:
            RefSeq mRNA accession (e.g., NM_000546) or None
        """
        try:
            import requests
            import re
            
            # Remove version if present
            protein_id = protein_accession.split('.')[0]
            
            # Query NCBI for the protein record
            response = requests.get(
                'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi',
                params={
                    'db': 'protein',
                    'id': protein_accession,
                    'rettype': 'gb',
                    'retmode': 'text'
                },
                timeout=10
            )
            
            if response.status_code != 200:
                return None
            
            # Look for the mRNA reference in the GenBank record
            # It's typically in DBSOURCE or /coded_by qualifier
            text = response.text
            
            # Try DBSOURCE line first (most reliable)
            dbsource_match = re.search(r'DBSOURCE\s+REFSEQ:\s+accession\s+(NM_\d+)', text)
            if dbsource_match:
                return dbsource_match.group(1)
            
            # Try /coded_by qualifier
            coded_by_match = re.search(r'/coded_by="(NM_\d+)', text)
            if coded_by_match:
                return coded_by_match.group(1)
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to map {protein_accession} to mRNA: {e}")
            return None
    
    def get_canonical_transcript(self, gene_symbol: str, map_to_mrna: bool = False) -> Optional[str]:
        """Get the canonical transcript for a gene.
        
        Args:
            gene_symbol: HGNC gene symbol
            map_to_mrna: If True, map protein to mRNA via NCBI
            
        Returns:
            RefSeq transcript ID (NM_) or protein ID (NP_) depending on map_to_mrna
        """
        # Try exact match first
        result = self.gene_to_transcript.get(gene_symbol)
        
        # Try uppercase
        if not result:
            gene_upper = gene_symbol.upper()
            result = self.gene_to_transcript.get(gene_upper)
        
        # If we have a protein and want mRNA, map it
        if result and map_to_mrna and result.startswith('NP_'):
            mrna = self.map_protein_to_mrna(result)
            if mrna:
                # Cache the mRNA for future use
                self.gene_to_transcript[gene_symbol] = mrna
                self._save_parsed_cache()
                return mrna
            else:
                logger.warning(f"Failed to map {result} to mRNA for {gene_symbol}")
                return None
        
        return result
    
    def update_and_get_mapping(self) -> Dict[str, str]:
        """Download (if needed), parse, and return the full mapping.
        
        Returns:
            Dictionary mapping gene symbols to canonical transcripts
        """
        # Try to load from cache first
        if self.gene_to_transcript:
            return self.gene_to_transcript
        
        # Download if needed
        if self.download_mapping_file():
            # Parse the file
            return self.parse_mapping_file()
        
        return {}