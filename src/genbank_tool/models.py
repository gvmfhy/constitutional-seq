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
    
    @property
    def full_accession(self) -> str:
        """Get full accession with version."""
        return f"{self.accession}.{self.version}"