"""MANE database loader - downloads and parses the official MANE summary."""

import gzip
import logging
from pathlib import Path
from typing import Dict, Optional
from urllib.request import urlretrieve

logger = logging.getLogger(__name__)


class MANEDatabase:
    """Loads and caches the official MANE transcript database."""
    
    MANE_URL = "https://ftp.ncbi.nlm.nih.gov/refseq/MANE/MANE_human/current/MANE.GRCh38.v1.4.summary.txt.gz"
    CACHE_DIR = Path("cache/mane_database")
    
    def __init__(self):
        """Initialize MANE database."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.mane_data = {}
        self._load_database()
    
    def _load_database(self) -> None:
        """Download and parse MANE summary file."""
        cache_file = self.CACHE_DIR / "mane_summary.txt.gz"
        
        # Download if not cached
        if not cache_file.exists():
            logger.info("Downloading MANE database...")
            try:
                urlretrieve(self.MANE_URL, cache_file)
                logger.info("MANE database downloaded successfully")
            except Exception as e:
                logger.error(f"Failed to download MANE database: {e}")
                return
        
        # Parse the file
        try:
            with gzip.open(cache_file, 'rt') as f:
                # Skip header
                header = f.readline().strip().split('\t')
                
                for line in f:
                    fields = line.strip().split('\t')
                    if len(fields) >= 10:
                        # Parse MANE entry
                        gene_symbol = fields[3]
                        refseq_nuc = fields[5]  # RefSeq transcript (NM_)
                        ensembl_nuc = fields[7]  # Ensembl transcript (ENST)
                        mane_type = fields[9]  # MANE status column
                        
                        if gene_symbol not in self.mane_data:
                            self.mane_data[gene_symbol] = {}
                        
                        if mane_type == "MANE Select":
                            self.mane_data[gene_symbol]['select'] = {
                                'refseq': refseq_nuc,
                                'ensembl': ensembl_nuc
                            }
                        elif mane_type == "MANE Plus Clinical":
                            if 'plus_clinical' not in self.mane_data[gene_symbol]:
                                self.mane_data[gene_symbol]['plus_clinical'] = []
                            self.mane_data[gene_symbol]['plus_clinical'].append({
                                'refseq': refseq_nuc,
                                'ensembl': ensembl_nuc
                            })
            
            logger.info(f"Loaded MANE data for {len(self.mane_data)} genes")
            
        except Exception as e:
            logger.error(f"Failed to parse MANE database: {e}")
    
    def get_mane_select(self, gene_symbol: str) -> Optional[Dict[str, str]]:
        """Get MANE Select transcript for a gene.
        
        Args:
            gene_symbol: HGNC gene symbol
            
        Returns:
            Dict with 'refseq' and 'ensembl' accessions or None
        """
        gene_data = self.mane_data.get(gene_symbol, {})
        return gene_data.get('select')
    
    def get_mane_plus_clinical(self, gene_symbol: str) -> list:
        """Get MANE Plus Clinical transcripts for a gene.
        
        Args:
            gene_symbol: HGNC gene symbol
            
        Returns:
            List of dicts with 'refseq' and 'ensembl' accessions
        """
        gene_data = self.mane_data.get(gene_symbol, {})
        return gene_data.get('plus_clinical', [])
    
    def has_mane(self, gene_symbol: str) -> bool:
        """Check if a gene has any MANE annotation."""
        return gene_symbol in self.mane_data