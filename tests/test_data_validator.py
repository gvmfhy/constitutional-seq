"""Tests for data validation module."""

from unittest.mock import Mock, patch

import pytest

from genbank_tool.data_validator import (
    DataValidator,
    ValidationFlag,
    ValidationIssue,
    ValidationLevel,
    ValidationResult,
)
from genbank_tool.models import RetrievedSequence


class TestDataValidator:
    """Test cases for data validation."""
    
    @pytest.fixture
    def validator(self):
        """Create a DataValidator instance."""
        return DataValidator(validate_cross_refs=True, strict_mode=False)
    
    @pytest.fixture
    def valid_sequence(self):
        """Create a valid test sequence."""
        return RetrievedSequence(
            gene_symbol="TEST1",
            gene_id="12345",
            accession="NM_001234",
            version="1",
            description="Test transcript",
            genbank_url="https://www.ncbi.nlm.nih.gov/nuccore/NM_001234.1",
            cds_sequence="ATGGCGGCGGCGGCGTAA",  # Valid CDS with start and stop
            cds_length=18,
            refseq_select=False
        )
    
    def test_validate_complete_sequence(self, validator, valid_sequence):
        """Test validation of a complete, valid sequence."""
        result = validator.validate_sequence(valid_sequence)
        
        assert result.is_valid is True
        assert len(result.issues) == 0
        assert result.confidence_score == 1.0
    
    def test_validate_no_start_codon(self, validator):
        """Test detection of missing start codon."""
        sequence = RetrievedSequence(
            gene_symbol="TEST1",
            gene_id="12345",
            accession="NM_001234",
            version="1",
            description="Test",
            genbank_url="https://test.com",
            cds_sequence="GGGGCGGCGGCGTAA",  # No ATG start
            cds_length=15
        )
        
        result = validator.validate_sequence(sequence)
        
        assert result.is_valid is True  # Warning only in non-strict mode
        assert len(result.issues) == 1
        assert result.issues[0].flag == ValidationFlag.NO_START_CODON
        assert result.issues[0].level == ValidationLevel.WARNING
        assert result.confidence_score < 1.0
    
    def test_validate_no_stop_codon(self, validator):
        """Test detection of missing stop codon."""
        sequence = RetrievedSequence(
            gene_symbol="TEST1",
            gene_id="12345",
            accession="NM_001234",
            version="1",
            description="Test",
            genbank_url="https://test.com",
            cds_sequence="ATGGCGGCGGCGGCG",  # No stop codon
            cds_length=15
        )
        
        result = validator.validate_sequence(sequence)
        
        assert len(result.issues) == 1
        assert result.issues[0].flag == ValidationFlag.NO_STOP_CODON
        assert result.issues[0].level == ValidationLevel.WARNING
    
    def test_validate_incomplete_codon(self, validator):
        """Test detection of incomplete codon (not multiple of 3)."""
        sequence = RetrievedSequence(
            gene_symbol="TEST1",
            gene_id="12345",
            accession="NM_001234",
            version="1",
            description="Test",
            genbank_url="https://test.com",
            cds_sequence="ATGGCGGCGGCGTAAG",  # 16 bp, not multiple of 3
            cds_length=16
        )
        
        result = validator.validate_sequence(sequence)
        
        assert result.is_valid is False  # Error level
        assert any(issue.flag == ValidationFlag.INCOMPLETE_CODON for issue in result.issues)
        assert any(issue.level == ValidationLevel.ERROR for issue in result.issues)
    
    def test_validate_internal_stop_codons(self, validator):
        """Test detection of internal stop codons."""
        sequence = RetrievedSequence(
            gene_symbol="TEST1",
            gene_id="12345",
            accession="NM_001234",
            version="1",
            description="Test",
            genbank_url="https://test.com",
            cds_sequence="ATGTAGGCGGCGTAA",  # TAG is internal stop
            cds_length=15
        )
        
        result = validator.validate_sequence(sequence)
        
        assert result.is_valid is False
        internal_stop_issue = next(
            issue for issue in result.issues 
            if issue.flag == ValidationFlag.MULTIPLE_STOP_CODONS
        )
        assert internal_stop_issue.level == ValidationLevel.ERROR
        assert internal_stop_issue.details['stop_positions'] == [(3, 'TAG')]
    
    def test_check_deprecated_entry(self, validator):
        """Test detection of deprecated entries."""
        sequence = RetrievedSequence(
            gene_symbol="TEST1",
            gene_id="12345",
            accession="NM_001234",
            version="1",
            description="This entry has been deprecated",
            genbank_url="https://test.com",
            cds_sequence="ATGGCGGCGGCGTAA",
            cds_length=15
        )
        
        result = validator.validate_sequence(sequence)
        
        assert any(issue.flag == ValidationFlag.DEPRECATED_ENTRY for issue in result.issues)
        assert any(issue.level == ValidationLevel.WARNING for issue in result.issues)
    
    def test_check_withdrawn_entry(self, validator):
        """Test detection of withdrawn entries."""
        sequence = RetrievedSequence(
            gene_symbol="TEST1",
            gene_id="12345",
            accession="NM_001234",
            version="1",
            description="This record has been withdrawn",
            genbank_url="https://test.com",
            cds_sequence="ATGGCGGCGGCGTAA",
            cds_length=15
        )
        
        result = validator.validate_sequence(sequence)
        
        assert result.is_valid is False  # Critical issue
        assert any(issue.flag == ValidationFlag.WITHDRAWN_ENTRY for issue in result.issues)
        assert any(issue.level == ValidationLevel.CRITICAL for issue in result.issues)
    
    def test_validate_against_uniprot_success(self, validator, valid_sequence):
        """Test successful UniProt validation."""
        with patch.object(validator.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                'results': [{
                    'primaryAccession': 'P12345',
                    'sequence': {'length': 5, 'checksum': 'abc123'},  # 5 AA = 15 nt
                    'uniProtKBCrossReferences': [
                        {'database': 'RefSeq', 'id': 'NM_001234.1'}
                    ]
                }]
            }
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = validator.validate_sequence(valid_sequence, 'TEST1')
            
            assert 'uniprot' in result.cross_references
            assert result.cross_references['uniprot']['accession'] == 'P12345'
            assert result.confidence_score >= 0.9  # May be reduced by other factors
    
    def test_validate_against_uniprot_no_entry(self, validator, valid_sequence):
        """Test UniProt validation with no entry found."""
        with patch.object(validator.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {'results': []}
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = validator.validate_sequence(valid_sequence, 'TEST1')
            
            assert any(issue.flag == ValidationFlag.NO_UNIPROT_ENTRY for issue in result.issues)
    
    def test_validate_against_ensembl_success(self, validator, valid_sequence):
        """Test successful Ensembl validation."""
        with patch.object(validator.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                'id': 'ENSG00000123456',
                'biotype': 'protein_coding',
                'description': 'Test gene'
            }
            mock_response.raise_for_status = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            result = validator.validate_sequence(valid_sequence, 'TEST1')
            
            assert 'ensembl' in result.cross_references
            assert result.cross_references['ensembl']['gene_id'] == 'ENSG00000123456'
    
    def test_confidence_calculation(self, validator):
        """Test confidence score calculation."""
        # Create sequence with multiple issues
        sequence = RetrievedSequence(
            gene_symbol="TEST1",
            gene_id="12345",
            accession="NM_001234",
            version="1",
            description="Test",
            genbank_url="https://test.com",
            cds_sequence="GGGGCGGCGGCG",  # No start, no stop, incomplete
            cds_length=12
        )
        
        result = validator.validate_sequence(sequence)
        
        # Should have warnings that reduce confidence
        assert result.confidence_score < 1.0
        assert result.confidence_score > 0.5  # Not too low for just warnings
    
    def test_strict_mode(self):
        """Test strict mode validation."""
        validator = DataValidator(validate_cross_refs=False, strict_mode=True)
        
        sequence = RetrievedSequence(
            gene_symbol="TEST1",
            gene_id="12345",
            accession="NM_001234",
            version="1",
            description="Test",
            genbank_url="https://test.com",
            cds_sequence="GGGGCGGCGGCGTAA",  # No start codon (warning)
            cds_length=15
        )
        
        result = validator.validate_sequence(sequence)
        
        assert result.is_valid is False  # In strict mode, warnings invalidate
    
    def test_batch_validation(self, validator, valid_sequence):
        """Test batch validation."""
        sequences = [
            (valid_sequence, 'TEST1'),
            (valid_sequence, 'TEST2')
        ]
        
        results = validator.validate_batch(sequences)
        
        assert len(results) == 2
        assert all(isinstance(r, ValidationResult) for r in results)
    
    def test_validation_report(self, validator):
        """Test report generation."""
        # Create results with various issues
        results = []
        
        # Valid sequence
        valid_seq = RetrievedSequence(
            gene_symbol="GOOD",
            gene_id="1",
            accession="NM_000001",
            version="1",
            description="Good sequence",
            genbank_url="https://test.com",
            cds_sequence="ATGGCGTAA",
            cds_length=9
        )
        results.append(validator.validate_sequence(valid_seq))
        
        # Invalid sequence
        invalid_seq = RetrievedSequence(
            gene_symbol="BAD",
            gene_id="2",
            accession="NM_000002",
            version="1",
            description="Bad sequence",
            genbank_url="https://test.com",
            cds_sequence="ATGTAGTAA",  # Internal stop
            cds_length=9
        )
        results.append(validator.validate_sequence(invalid_seq))
        
        report = validator.generate_validation_report(results)
        
        assert "Total sequences validated: 2" in report
        assert "Valid sequences: 1 (50.0%)" in report
        assert "Multiple in-frame stop codons" in report
        assert "NM_000002.1" in report