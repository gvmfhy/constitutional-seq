"""Transcript selection module for choosing canonical transcripts."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import requests

from .models import RetrievedSequence

logger = logging.getLogger(__name__)


class SelectionMethod(Enum):
    """Methods used for transcript selection."""
    
    REFSEQ_SELECT = "RefSeq Select"
    UNIPROT_CANONICAL = "UniProt Canonical"
    LONGEST_CDS = "Longest CDS"
    MOST_RECENT_VERSION = "Most Recent Version"
    USER_OVERRIDE = "User Override"
    DEFAULT = "Default (First Available)"


@dataclass
class TranscriptSelection:
    """Represents a selected transcript with rationale."""
    
    transcript: RetrievedSequence
    method: SelectionMethod
    confidence: float
    rationale: str
    warnings: List[str]
    alternatives_count: int


class TranscriptSelector:
    """Selects canonical transcripts using hierarchical criteria."""
    
    UNIPROT_BASE_URL = "https://rest.uniprot.org/uniprotkb"
    
    def __init__(self, uniprot_enabled: bool = True, prefer_longest: bool = True):
        """Initialize the transcript selector.
        
        Args:
            uniprot_enabled: Whether to use UniProt for canonical validation
            prefer_longest: Whether to prefer longest CDS when other criteria equal
        """
        self.uniprot_enabled = uniprot_enabled
        self.prefer_longest = prefer_longest
        
        # Setup session for API requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NCBI-GenBank-Tool/1.0'
        })
    
    def select_canonical(
        self,
        transcripts: List[RetrievedSequence],
        gene_symbol: str,
        gene_id: str,
        user_preference: Optional[str] = None
    ) -> Optional[TranscriptSelection]:
        """Select the canonical transcript from a list.
        
        Uses hierarchical selection:
        1. User override (if provided)
        2. RefSeq Select designation
        3. UniProt canonical annotation
        4. Longest CDS
        5. Most recent version
        
        Args:
            transcripts: List of transcript sequences
            gene_symbol: Official gene symbol
            gene_id: NCBI Gene ID
            user_preference: Optional user-specified accession
            
        Returns:
            Selected transcript with metadata or None
        """
        if not transcripts:
            logger.warning(f"No transcripts provided for {gene_symbol}")
            return None
        
        warnings = []
        
        # 1. Check user preference first
        if user_preference:
            selected = self._find_by_accession(transcripts, user_preference)
            if selected:
                return TranscriptSelection(
                    transcript=selected,
                    method=SelectionMethod.USER_OVERRIDE,
                    confidence=1.0,
                    rationale=f"User specified transcript {user_preference}",
                    warnings=warnings,
                    alternatives_count=len(transcripts) - 1
                )
            else:
                warnings.append(f"User preference {user_preference} not found")
        
        # 2. Check for RefSeq Select
        refseq_select = self._find_refseq_select(transcripts)
        if refseq_select:
            logger.info(f"Found RefSeq Select transcript: {refseq_select.full_accession}")
            return TranscriptSelection(
                transcript=refseq_select,
                method=SelectionMethod.REFSEQ_SELECT,
                confidence=0.95,
                rationale="NCBI RefSeq Select designation (curated representative)",
                warnings=warnings,
                alternatives_count=len(transcripts) - 1
            )
        
        # 3. Check UniProt canonical
        if self.uniprot_enabled:
            uniprot_canonical = self._find_uniprot_canonical(
                transcripts, gene_symbol, gene_id
            )
            if uniprot_canonical:
                logger.info(f"Found UniProt canonical: {uniprot_canonical.full_accession}")
                return TranscriptSelection(
                    transcript=uniprot_canonical,
                    method=SelectionMethod.UNIPROT_CANONICAL,
                    confidence=0.9,
                    rationale="UniProt canonical transcript annotation",
                    warnings=warnings,
                    alternatives_count=len(transcripts) - 1
                )
        
        # 4. Select longest CDS
        if self.prefer_longest:
            longest = self._find_longest_cds(transcripts)
            if longest:
                # Check if multiple transcripts have same length
                same_length = [t for t in transcripts if t.cds_length == longest.cds_length]
                if len(same_length) > 1:
                    warnings.append(f"{len(same_length)} transcripts with equal CDS length")
                    # Use most recent version as tiebreaker
                    longest = self._find_most_recent(same_length)
                    return TranscriptSelection(
                        transcript=longest,
                        method=SelectionMethod.MOST_RECENT_VERSION,
                        confidence=0.7,
                        rationale=f"Most recent version among {len(same_length)} equal-length transcripts",
                        warnings=warnings,
                        alternatives_count=len(transcripts) - 1
                    )
                
                return TranscriptSelection(
                    transcript=longest,
                    method=SelectionMethod.LONGEST_CDS,
                    confidence=0.8,
                    rationale=f"Longest CDS ({longest.cds_length} bp)",
                    warnings=warnings,
                    alternatives_count=len(transcripts) - 1
                )
        
        # 5. Fall back to most recent version
        most_recent = self._find_most_recent(transcripts)
        if most_recent:
            warnings.append("No clear canonical transcript identified")
            return TranscriptSelection(
                transcript=most_recent,
                method=SelectionMethod.MOST_RECENT_VERSION,
                confidence=0.6,
                rationale="Most recent transcript version",
                warnings=warnings,
                alternatives_count=len(transcripts) - 1
            )
        
        # 6. Last resort - take first
        warnings.append("Using first available transcript")
        return TranscriptSelection(
            transcript=transcripts[0],
            method=SelectionMethod.DEFAULT,
            confidence=0.5,
            rationale="First available transcript (no selection criteria met)",
            warnings=warnings,
            alternatives_count=len(transcripts) - 1
        )
    
    def _find_by_accession(
        self,
        transcripts: List[RetrievedSequence],
        accession: str
    ) -> Optional[RetrievedSequence]:
        """Find transcript by accession number."""
        # Handle with or without version
        for transcript in transcripts:
            if transcript.accession == accession or transcript.full_accession == accession:
                return transcript
        return None
    
    def _find_refseq_select(
        self,
        transcripts: List[RetrievedSequence]
    ) -> Optional[RetrievedSequence]:
        """Find RefSeq Select transcript."""
        for transcript in transcripts:
            if transcript.refseq_select:
                return transcript
        return None
    
    def _find_uniprot_canonical(
        self,
        transcripts: List[RetrievedSequence],
        gene_symbol: str,
        gene_id: str
    ) -> Optional[RetrievedSequence]:
        """Find UniProt canonical transcript.
        
        Queries UniProt to get the canonical transcript accession.
        """
        try:
            # Query UniProt for gene
            params = {
                'query': f'gene:{gene_symbol} AND organism_id:9606 AND reviewed:true',
                'format': 'json',
                'fields': 'xref_refseq',
                'size': 1
            }
            
            response = self.session.get(
                f"{self.UNIPROT_BASE_URL}/search",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            if not results:
                logger.debug(f"No UniProt entry found for {gene_symbol}")
                return None
            
            # Extract RefSeq cross-references
            entry = results[0]
            refseq_refs = []
            
            for xref in entry.get('uniProtKBCrossReferences', []):
                if xref.get('database') == 'RefSeq':
                    ref_id = xref.get('id', '')
                    if ref_id.startswith('NM_'):  # mRNA transcript
                        refseq_refs.append(ref_id.split('.')[0])  # Remove version
            
            if not refseq_refs:
                logger.debug(f"No RefSeq cross-references in UniProt for {gene_symbol}")
                return None
            
            # Find matching transcript
            # UniProt typically lists canonical first
            canonical_accession = refseq_refs[0]
            
            for transcript in transcripts:
                if transcript.accession == canonical_accession:
                    logger.info(f"Matched UniProt canonical: {transcript.full_accession}")
                    return transcript
            
            logger.debug(f"UniProt canonical {canonical_accession} not in transcript list")
            return None
            
        except Exception as e:
            logger.error(f"Failed to query UniProt for {gene_symbol}: {e}")
            return None
    
    def _find_longest_cds(
        self,
        transcripts: List[RetrievedSequence]
    ) -> Optional[RetrievedSequence]:
        """Find transcript with longest CDS."""
        if not transcripts:
            return None
        
        return max(transcripts, key=lambda t: t.cds_length)
    
    def _find_most_recent(
        self,
        transcripts: List[RetrievedSequence]
    ) -> Optional[RetrievedSequence]:
        """Find most recent transcript version."""
        if not transcripts:
            return None
        
        # Sort by version number (descending)
        sorted_transcripts = sorted(
            transcripts,
            key=lambda t: t.version,
            reverse=True
        )
        
        return sorted_transcripts[0]
    
    def generate_selection_report(
        self,
        selections: Dict[str, TranscriptSelection]
    ) -> str:
        """Generate a report of transcript selections.
        
        Args:
            selections: Dictionary of gene symbol to selection
            
        Returns:
            Formatted report string
        """
        report_lines = [
            "Transcript Selection Report",
            "=" * 80,
            ""
        ]
        
        # Summary statistics
        total = len(selections)
        by_method = {}
        
        for gene, selection in selections.items():
            method = selection.method.value
            by_method[method] = by_method.get(method, 0) + 1
        
        report_lines.extend([
            f"Total genes processed: {total}",
            "",
            "Selection methods used:",
        ])
        
        for method, count in sorted(by_method.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total) * 100
            report_lines.append(f"  {method}: {count} ({percentage:.1f}%)")
        
        report_lines.extend(["", "Genes requiring manual review:"])
        
        # List genes with warnings
        genes_with_warnings = [
            (gene, sel) for gene, sel in selections.items()
            if sel.warnings or sel.confidence < 0.7
        ]
        
        if genes_with_warnings:
            for gene, selection in sorted(genes_with_warnings):
                report_lines.append(f"\n{gene}:")
                report_lines.append(f"  Selected: {selection.transcript.full_accession}")
                report_lines.append(f"  Method: {selection.method.value}")
                report_lines.append(f"  Confidence: {selection.confidence:.2f}")
                
                if selection.warnings:
                    report_lines.append("  Warnings:")
                    for warning in selection.warnings:
                        report_lines.append(f"    - {warning}")
        else:
            report_lines.append("  None")
        
        return "\n".join(report_lines)