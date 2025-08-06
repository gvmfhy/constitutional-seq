"""Data validation and cross-reference module for sequence quality assurance."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import RetrievedSequence

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Validation severity levels."""
    
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationFlag(Enum):
    """Types of validation issues."""
    
    # Sequence completeness
    NO_START_CODON = "No start codon (ATG)"
    NO_STOP_CODON = "No stop codon (TAA/TAG/TGA)"
    MULTIPLE_STOP_CODONS = "Multiple in-frame stop codons"
    INCOMPLETE_CODON = "Sequence length not multiple of 3"
    
    # Cross-reference issues
    UNIPROT_MISMATCH = "UniProt sequence mismatch"
    ENSEMBL_MISMATCH = "Ensembl sequence mismatch"
    NO_UNIPROT_ENTRY = "No UniProt entry found"
    NO_ENSEMBL_ENTRY = "No Ensembl entry found"
    
    # Database status
    DEPRECATED_ENTRY = "Entry marked as deprecated"
    WITHDRAWN_ENTRY = "Entry withdrawn from database"
    SUPPRESSED_ENTRY = "Entry suppressed"
    
    # Annotation conflicts
    LENGTH_DISCREPANCY = "CDS length differs between databases"
    ANNOTATION_CONFLICT = "Conflicting annotations"
    VERSION_OUTDATED = "Newer version available"


@dataclass
class ValidationIssue:
    """Represents a single validation issue."""
    
    flag: ValidationFlag
    level: ValidationLevel
    message: str
    details: Optional[Dict] = None


@dataclass
class ValidationResult:
    """Complete validation result for a sequence."""
    
    sequence: RetrievedSequence
    is_valid: bool
    confidence_score: float
    issues: List[ValidationIssue]
    cross_references: Dict[str, Dict]
    
    @property
    def has_errors(self) -> bool:
        """Check if validation has any errors."""
        return any(issue.level == ValidationLevel.ERROR for issue in self.issues)
    
    @property
    def has_critical_issues(self) -> bool:
        """Check if validation has critical issues."""
        return any(issue.level == ValidationLevel.CRITICAL for issue in self.issues)


class DataValidator:
    """Validates sequence data against multiple databases."""
    
    UNIPROT_BASE_URL = "https://rest.uniprot.org/uniprotkb"
    ENSEMBL_BASE_URL = "https://rest.ensembl.org"
    
    def __init__(self, validate_cross_refs: bool = True, strict_mode: bool = False):
        """Initialize the data validator.
        
        Args:
            validate_cross_refs: Whether to validate against external databases
            strict_mode: If True, warnings are treated as errors
        """
        self.validate_cross_refs = validate_cross_refs
        self.strict_mode = strict_mode
        
        # Setup session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.headers.update({
            'User-Agent': 'NCBI-GenBank-Tool/1.0'
        })
    
    def validate_sequence(
        self,
        sequence: RetrievedSequence,
        gene_symbol: Optional[str] = None
    ) -> ValidationResult:
        """Validate a single sequence.
        
        Args:
            sequence: The sequence to validate
            gene_symbol: Optional gene symbol for cross-reference
            
        Returns:
            ValidationResult with all findings
        """
        issues = []
        cross_refs = {}
        
        # 1. Validate sequence completeness
        completeness_issues = self._validate_completeness(sequence)
        issues.extend(completeness_issues)
        
        # 2. Check for deprecated/withdrawn status
        status_issues = self._check_entry_status(sequence)
        issues.extend(status_issues)
        
        # 3. Cross-reference validation if enabled
        if self.validate_cross_refs and gene_symbol:
            # UniProt validation
            uniprot_result = self._validate_against_uniprot(sequence, gene_symbol)
            if uniprot_result:
                cross_refs['uniprot'] = uniprot_result['data']
                issues.extend(uniprot_result['issues'])
            
            # Ensembl validation
            ensembl_result = self._validate_against_ensembl(sequence, gene_symbol)
            if ensembl_result:
                cross_refs['ensembl'] = ensembl_result['data']
                issues.extend(ensembl_result['issues'])
        
        # 4. Calculate confidence score
        confidence = self._calculate_confidence(issues, cross_refs)
        
        # 5. Determine overall validity
        is_valid = self._determine_validity(issues)
        
        return ValidationResult(
            sequence=sequence,
            is_valid=is_valid,
            confidence_score=confidence,
            issues=issues,
            cross_references=cross_refs
        )
    
    def _validate_completeness(self, sequence: RetrievedSequence) -> List[ValidationIssue]:
        """Check sequence completeness (start/stop codons, length)."""
        issues = []
        cds = sequence.cds_sequence.upper()
        
        # Check start codon
        if not cds.startswith('ATG'):
            issues.append(ValidationIssue(
                flag=ValidationFlag.NO_START_CODON,
                level=ValidationLevel.WARNING,
                message=f"CDS does not start with ATG (found: {cds[:3]})",
                details={'start_codon': cds[:3] if len(cds) >= 3 else cds}
            ))
        
        # Check stop codon
        stop_codons = ['TAA', 'TAG', 'TGA']
        if len(cds) >= 3:
            last_codon = cds[-3:]
            if last_codon not in stop_codons:
                issues.append(ValidationIssue(
                    flag=ValidationFlag.NO_STOP_CODON,
                    level=ValidationLevel.WARNING,
                    message=f"CDS does not end with stop codon (found: {last_codon})",
                    details={'end_codon': last_codon}
                ))
        
        # Check length is multiple of 3
        if len(cds) % 3 != 0:
            issues.append(ValidationIssue(
                flag=ValidationFlag.INCOMPLETE_CODON,
                level=ValidationLevel.ERROR,
                message=f"CDS length ({len(cds)}) is not a multiple of 3",
                details={'length': len(cds), 'remainder': len(cds) % 3}
            ))
        
        # Check for internal stop codons
        if len(cds) > 3:
            # Check every codon except the last one
            internal_stops = []
            for i in range(0, len(cds) - 3, 3):
                codon = cds[i:i+3]
                if codon in stop_codons:
                    internal_stops.append((i, codon))
            
            if internal_stops:
                issues.append(ValidationIssue(
                    flag=ValidationFlag.MULTIPLE_STOP_CODONS,
                    level=ValidationLevel.ERROR,
                    message=f"Found {len(internal_stops)} internal stop codon(s)",
                    details={'stop_positions': internal_stops}
                ))
        
        return issues
    
    def _check_entry_status(self, sequence: RetrievedSequence) -> List[ValidationIssue]:
        """Check if entry is deprecated or withdrawn."""
        issues = []
        
        # Check description for status keywords
        desc_lower = sequence.description.lower()
        
        if 'deprecated' in desc_lower:
            issues.append(ValidationIssue(
                flag=ValidationFlag.DEPRECATED_ENTRY,
                level=ValidationLevel.WARNING,
                message="Entry appears to be deprecated",
                details={'description': sequence.description}
            ))
        
        if 'withdrawn' in desc_lower:
            issues.append(ValidationIssue(
                flag=ValidationFlag.WITHDRAWN_ENTRY,
                level=ValidationLevel.CRITICAL,
                message="Entry has been withdrawn",
                details={'description': sequence.description}
            ))
        
        if 'suppressed' in desc_lower:
            issues.append(ValidationIssue(
                flag=ValidationFlag.SUPPRESSED_ENTRY,
                level=ValidationLevel.ERROR,
                message="Entry has been suppressed",
                details={'description': sequence.description}
            ))
        
        return issues
    
    def _validate_against_uniprot(
        self,
        sequence: RetrievedSequence,
        gene_symbol: str
    ) -> Optional[Dict]:
        """Validate sequence against UniProt database."""
        try:
            # Search for UniProt entry
            params = {
                'query': f'gene:{gene_symbol} AND organism_id:9606 AND reviewed:true',
                'format': 'json',
                'fields': 'accession,gene_names,sequence,xref_refseq',
                'size': 1
            }
            
            response = self.session.get(
                f"{self.UNIPROT_BASE_URL}/search",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            if not data.get('results'):
                return {
                    'data': {},
                    'issues': [ValidationIssue(
                        flag=ValidationFlag.NO_UNIPROT_ENTRY,
                        level=ValidationLevel.INFO,
                        message=f"No UniProt entry found for {gene_symbol}"
                    )]
                }
            
            uniprot_entry = data['results'][0]
            issues = []
            
            # Extract UniProt data
            uniprot_data = {
                'accession': uniprot_entry.get('primaryAccession'),
                'sequence_length': uniprot_entry.get('sequence', {}).get('length', 0) * 3,  # Convert AA to nucleotides
                'sequence_checksum': uniprot_entry.get('sequence', {}).get('checksum'),
            }
            
            # Check if our RefSeq is in UniProt cross-references
            refseq_refs = []
            for xref in uniprot_entry.get('uniProtKBCrossReferences', []):
                if xref.get('database') == 'RefSeq' and xref.get('id', '').startswith('NM_'):
                    refseq_refs.append(xref.get('id'))
            
            uniprot_data['refseq_cross_refs'] = refseq_refs
            
            # Validate
            if sequence.full_accession not in refseq_refs and sequence.accession not in [r.split('.')[0] for r in refseq_refs]:
                issues.append(ValidationIssue(
                    flag=ValidationFlag.ANNOTATION_CONFLICT,
                    level=ValidationLevel.INFO,
                    message=f"RefSeq {sequence.full_accession} not in UniProt cross-references",
                    details={'uniprot_refs': refseq_refs}
                ))
            
            # Check sequence length (approximate due to UTRs)
            if abs(uniprot_data['sequence_length'] - sequence.cds_length) > 100:
                issues.append(ValidationIssue(
                    flag=ValidationFlag.LENGTH_DISCREPANCY,
                    level=ValidationLevel.INFO,
                    message=f"CDS length differs from UniProt protein length",
                    details={
                        'refseq_cds': sequence.cds_length,
                        'uniprot_cds_estimate': uniprot_data['sequence_length']
                    }
                ))
            
            return {'data': uniprot_data, 'issues': issues}
            
        except Exception as e:
            logger.error(f"UniProt validation failed: {e}")
            return None
    
    def _validate_against_ensembl(
        self,
        sequence: RetrievedSequence,
        gene_symbol: str
    ) -> Optional[Dict]:
        """Validate sequence against Ensembl database."""
        try:
            # Search for Ensembl gene
            response = self.session.get(
                f"{self.ENSEMBL_BASE_URL}/lookup/symbol/homo_sapiens/{gene_symbol}",
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 404:
                return {
                    'data': {},
                    'issues': [ValidationIssue(
                        flag=ValidationFlag.NO_ENSEMBL_ENTRY,
                        level=ValidationLevel.INFO,
                        message=f"No Ensembl entry found for {gene_symbol}"
                    )]
                }
            
            response.raise_for_status()
            gene_data = response.json()
            
            ensembl_data = {
                'gene_id': gene_data.get('id'),
                'biotype': gene_data.get('biotype'),
                'description': gene_data.get('description')
            }
            
            issues = []
            
            # Check biotype
            if gene_data.get('biotype') != 'protein_coding':
                issues.append(ValidationIssue(
                    flag=ValidationFlag.ANNOTATION_CONFLICT,
                    level=ValidationLevel.WARNING,
                    message=f"Ensembl biotype is '{gene_data.get('biotype')}', not 'protein_coding'",
                    details={'biotype': gene_data.get('biotype')}
                ))
            
            return {'data': ensembl_data, 'issues': issues}
            
        except Exception as e:
            logger.error(f"Ensembl validation failed: {e}")
            return None
    
    def _calculate_confidence(
        self,
        issues: List[ValidationIssue],
        cross_refs: Dict[str, Dict]
    ) -> float:
        """Calculate confidence score based on validation results."""
        confidence = 1.0
        
        # Deduct for issues based on severity
        for issue in issues:
            if issue.level == ValidationLevel.CRITICAL:
                confidence -= 0.3
            elif issue.level == ValidationLevel.ERROR:
                confidence -= 0.2
            elif issue.level == ValidationLevel.WARNING:
                confidence -= 0.1
            elif issue.level == ValidationLevel.INFO:
                confidence -= 0.05
        
        # Boost for successful cross-references
        if cross_refs.get('uniprot', {}).get('data'):
            confidence += 0.1
        if cross_refs.get('ensembl', {}).get('data'):
            confidence += 0.05
        
        # Ensure within bounds
        return max(0.0, min(1.0, confidence))
    
    def _determine_validity(self, issues: List[ValidationIssue]) -> bool:
        """Determine if sequence is valid based on issues."""
        if self.strict_mode:
            # In strict mode, any warning or higher invalidates
            return not any(
                issue.level in [ValidationLevel.WARNING, ValidationLevel.ERROR, ValidationLevel.CRITICAL]
                for issue in issues
            )
        else:
            # In normal mode, only errors and critical issues invalidate
            return not any(
                issue.level in [ValidationLevel.ERROR, ValidationLevel.CRITICAL]
                for issue in issues
            )
    
    def validate_batch(
        self,
        sequences: List[Tuple[RetrievedSequence, str]]
    ) -> List[ValidationResult]:
        """Validate multiple sequences.
        
        Args:
            sequences: List of (sequence, gene_symbol) tuples
            
        Returns:
            List of validation results
        """
        results = []
        
        for sequence, gene_symbol in sequences:
            logger.info(f"Validating {sequence.full_accession} for {gene_symbol}")
            result = self.validate_sequence(sequence, gene_symbol)
            results.append(result)
        
        return results
    
    def generate_validation_report(self, results: List[ValidationResult]) -> str:
        """Generate a summary report of validation results."""
        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        with_issues = sum(1 for r in results if r.issues)
        
        report_lines = [
            "Sequence Validation Report",
            "=" * 80,
            f"Total sequences validated: {total}",
            f"Valid sequences: {valid} ({valid/total*100:.1f}%)",
            f"Sequences with issues: {with_issues} ({with_issues/total*100:.1f}%)",
            ""
        ]
        
        # Summary by issue type
        issue_counts = {}
        for result in results:
            for issue in result.issues:
                key = (issue.flag.value, issue.level.value)
                issue_counts[key] = issue_counts.get(key, 0) + 1
        
        if issue_counts:
            report_lines.append("Issues by type:")
            for (flag, level), count in sorted(issue_counts.items()):
                report_lines.append(f"  [{level.upper()}] {flag}: {count}")
        
        # Detailed issues for invalid sequences
        invalid_results = [r for r in results if not r.is_valid]
        if invalid_results:
            report_lines.extend(["", "Invalid sequences:"])
            for result in invalid_results:
                report_lines.append(f"\n{result.sequence.full_accession}:")
                for issue in result.issues:
                    if issue.level in [ValidationLevel.ERROR, ValidationLevel.CRITICAL]:
                        report_lines.append(f"  [{issue.level.value}] {issue.message}")
        
        return "\n".join(report_lines)