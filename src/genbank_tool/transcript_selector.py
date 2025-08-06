"""Transcript selection module for choosing canonical transcripts."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import requests

from .models import RetrievedSequence
from .mane_selector import MANESelector
from .mane_database import MANEDatabase

logger = logging.getLogger(__name__)


class SelectionMethod(Enum):
    """Methods used for transcript selection."""
    
    MANE_SELECT = "MANE Select"
    MANE_PLUS_CLINICAL = "MANE Plus Clinical"
    REFSEQ_SELECT = "RefSeq Select"
    LONGEST_CDS = "Longest CDS (Arbitrary)"
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
    
    def __init__(self, uniprot_enabled: bool = True, prefer_longest: bool = True, 
                 mane_enabled: bool = True, api_key: Optional[str] = None):
        """Initialize the transcript selector.
        
        Args:
            uniprot_enabled: Whether to use UniProt for canonical validation
            prefer_longest: Whether to prefer longest CDS when other criteria equal
            mane_enabled: Whether to use MANE Select (highest priority)
            api_key: NCBI API key for MANE queries
        """
        self.uniprot_enabled = uniprot_enabled
        self.prefer_longest = prefer_longest
        self.mane_enabled = mane_enabled
        
        # Initialize MANE selector and database if enabled
        self.mane_selector = MANESelector(api_key=api_key) if mane_enabled else None
        self.mane_database = MANEDatabase() if mane_enabled else None
        
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
        2. MANE Select (highest confidence)
        3. MANE Plus Clinical
        4. RefSeq Select designation
        5. UniProt canonical annotation
        6. Longest CDS
        7. Most recent version
        
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
        
        # 2. Check for MANE Select (highest priority for therapeutic use)
        if self.mane_enabled and self.mane_database:
            # Try MANE Select first
            mane_select = self.mane_database.get_mane_select(gene_symbol)
            if mane_select:
                # Find matching transcript in our list
                mane_match = self._find_by_accession(
                    transcripts, 
                    mane_select['refseq'].split('.')[0]
                )
                if mane_match:
                    logger.info(f"Found MANE Select transcript: {mane_match.full_accession}")
                    return TranscriptSelection(
                        transcript=mane_match,
                        method=SelectionMethod.MANE_SELECT,
                        confidence=1.0,
                        rationale="MANE Select - NCBI/EBI consensus for therapeutic use",
                        warnings=warnings,
                        alternatives_count=len(transcripts) - 1
                    )
                else:
                    warnings.append(f"MANE Select {mane_select['refseq']} not in retrieved set")
            
            # Try MANE Plus Clinical
            mane_plus = self.mane_database.get_mane_plus_clinical(gene_symbol)
            for mane_clinical in mane_plus:
                mane_match = self._find_by_accession(
                    transcripts,
                    mane_clinical['refseq'].split('.')[0]
                )
                if mane_match:
                    logger.info(f"Found MANE Plus Clinical transcript: {mane_match.full_accession}")
                    return TranscriptSelection(
                        transcript=mane_match,
                        method=SelectionMethod.MANE_PLUS_CLINICAL,
                        confidence=0.98,
                        rationale="MANE Plus Clinical - Additional clinically relevant transcript",
                        warnings=warnings,
                        alternatives_count=len(transcripts) - 1
                    )
            
            if mane_plus:
                warnings.append(f"MANE Plus Clinical transcripts not in retrieved set")
        
        # 3. Check for RefSeq Select
        refseq_select = self._find_refseq_select(transcripts)
        if refseq_select:
            logger.info(f"Found RefSeq Select transcript: {refseq_select.full_accession}")
            return TranscriptSelection(
                transcript=refseq_select,
                method=SelectionMethod.REFSEQ_SELECT,
                confidence=0.95,
                rationale="NCBI RefSeq Select - manually curated representative transcript",
                warnings=warnings,
                alternatives_count=len(transcripts) - 1
            )
        
        # 4. Skip UniProt canonical check - removed due to unreliable proxy method
        # The "longest ATG transcript" heuristic has no scientific basis for canonical selection
        # Better to proceed directly to longest CDS as an explicit algorithmic choice
        
        # 5. Select longest CDS (with preference for ATG start)
        if self.prefer_longest:
            longest_overall = self._find_longest_cds(transcripts)
            longest_atg = self._find_longest_atg_cds(transcripts)
            
            # If we have both, decide which to use
            if longest_overall and longest_atg:
                # Check if the longest overall starts with ATG
                if self._has_standard_start_codon(longest_overall):
                    # Longest is also ATG-starting, use it
                    longest = longest_overall
                else:
                    # Longest starts with non-ATG, add warning and prefer ATG version
                    start_codon = longest_overall.cds_sequence[:3].upper()
                    warnings.append(f"Longest CDS starts with {start_codon} (non-standard); selected ATG-starting alternative")
                    longest = longest_atg
                    
                    return TranscriptSelection(
                        transcript=longest,
                        method=SelectionMethod.LONGEST_CDS,
                        confidence=0.65,  # Lower confidence due to non-standard start codon issue
                        rationale=f"Longest ATG-starting CDS ({longest.cds_length} bp), avoided {start_codon} start",
                        warnings=warnings,
                        alternatives_count=len(transcripts) - 1
                    )
            elif longest_overall:
                # Only non-ATG longest available
                if not self._has_standard_start_codon(longest_overall):
                    start_codon = longest_overall.cds_sequence[:3].upper()
                    warnings.append(f"Selected transcript starts with {start_codon} instead of ATG")
                longest = longest_overall
            elif longest_atg:
                # Only ATG version available
                longest = longest_atg
            else:
                # No transcripts found
                longest = None
            
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
                        confidence=0.60,  # Lower confidence for algorithmic tiebreaker
                        rationale=f"Most recent version among {len(same_length)} equal-length transcripts",
                        warnings=warnings,
                        alternatives_count=len(transcripts) - 1
                    )
                
                # Confidence based on whether it has standard start codon
                confidence = 0.50 if self._has_standard_start_codon(longest) else 0.40
                return TranscriptSelection(
                    transcript=longest,
                    method=SelectionMethod.LONGEST_CDS,
                    confidence=confidence,
                    rationale=f"Longest CDS ({longest.cds_length} bp) - arbitrary algorithmic fallback, no biological basis",
                    warnings=warnings + ["No curated transcript found; using arbitrary length-based selection"],
                    alternatives_count=len(transcripts) - 1
                )
        
        # 6. Fall back to most recent version
        most_recent = self._find_most_recent(transcripts)
        if most_recent:
            warnings.append("No clear canonical transcript identified")
            return TranscriptSelection(
                transcript=most_recent,
                method=SelectionMethod.MOST_RECENT_VERSION,
                confidence=0.50,  # Low confidence for fallback method
                rationale="Most recent transcript version - last resort algorithmic selection",
                warnings=warnings,
                alternatives_count=len(transcripts) - 1
            )
        
        # 7. Last resort - take first
        warnings.append("Using first available transcript - manual review required")
        return TranscriptSelection(
            transcript=transcripts[0],
            method=SelectionMethod.DEFAULT,
            confidence=0.40,  # Very low confidence for arbitrary selection
            rationale="First available transcript (no reliable selection criteria met)",
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
        
        For now, this is simplified to just use the longest transcript
        as a placeholder since proper UniProt canonical detection requires
        complex protein-to-mRNA mapping that often fails.
        """
        # Simplified approach: assume longest transcript is canonical
        # This is a reasonable heuristic since UniProt canonical detection
        # is complex and error-prone due to protein->mRNA mapping issues
        
        if not transcripts:
            return None
            
        # Find longest CDS that starts with ATG (most likely to be canonical)
        atg_transcripts = [t for t in transcripts 
                          if t.cds_sequence and t.cds_sequence.upper().startswith('ATG')]
        
        if atg_transcripts:
            longest = max(atg_transcripts, key=lambda t: t.cds_length)
            logger.info(f"Selected longest ATG transcript as UniProt canonical proxy: {longest.full_accession}")
            return longest
        
        # Fall back to overall longest if no ATG transcripts
        longest = max(transcripts, key=lambda t: t.cds_length)
        logger.info(f"Selected longest transcript as UniProt canonical proxy: {longest.full_accession}")
        return longest
    
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
    
    def _has_standard_start_codon(self, transcript: RetrievedSequence) -> bool:
        """Check if transcript starts with standard ATG codon."""
        if not transcript.cds_sequence:
            return False
        return transcript.cds_sequence.upper().startswith('ATG')
    
    def _find_longest_atg_cds(
        self,
        transcripts: List[RetrievedSequence]
    ) -> Optional[RetrievedSequence]:
        """Find transcript with longest CDS that starts with ATG."""
        atg_transcripts = [t for t in transcripts if self._has_standard_start_codon(t)]
        if not atg_transcripts:
            return None
        
        return max(atg_transcripts, key=lambda t: t.cds_length)
    
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