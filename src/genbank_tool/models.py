"""Data models for the NCBI GenBank tool."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RetrievedSequence:
    """Represents a retrieved CDS sequence with metadata."""
    
    gene_symbol: str
    gene_id: str
    accession: str
    version: str
    description: str
    genbank_url: str
    cds_sequence: str
    cds_length: int
    protein_id: Optional[str] = None
    transcript_variant: Optional[str] = None
    refseq_select: bool = False
    retrieval_timestamp: str = ""
    full_gene_name: Optional[str] = None  # Full descriptive name from UniProt/NCBI
    gene_url: Optional[str] = None  # URL to gene page (NCBI Gene or UniProt)
    isoform: Optional[str] = None  # Isoform identifier if applicable
    
    @property
    def full_accession(self) -> str:
        """Get full accession with version."""
        return f"{self.accession}.{self.version}"