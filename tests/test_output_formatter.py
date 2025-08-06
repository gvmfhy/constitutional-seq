"""Tests for output formatting module."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from genbank_tool.models import RetrievedSequence
from genbank_tool.output_formatter import OutputFormatter
from genbank_tool.transcript_selector import TranscriptSelection, SelectionMethod
from genbank_tool.data_validator import (
    ValidationFlag, ValidationIssue, ValidationLevel, ValidationResult
)


class TestOutputFormatter:
    """Test cases for output formatting."""
    
    @pytest.fixture
    def formatter(self):
        """Create an OutputFormatter instance."""
        return OutputFormatter(include_audit_trail=True)
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def sample_sequence(self):
        """Create a sample sequence."""
        return RetrievedSequence(
            gene_symbol="TP53",
            gene_id="7157",
            accession="NM_000546",
            version="6",
            description="Tumor protein p53",
            genbank_url="https://www.ncbi.nlm.nih.gov/nuccore/NM_000546.6",
            cds_sequence="ATGGAGGAGCCGCAGTAA",
            cds_length=18,
            refseq_select=True
        )
    
    @pytest.fixture
    def sample_selection(self, sample_sequence):
        """Create a sample selection result."""
        return TranscriptSelection(
            transcript=sample_sequence,
            method=SelectionMethod.REFSEQ_SELECT,
            confidence=0.95,
            rationale="Selected as RefSeq Select transcript",
            warnings=["Multiple transcripts with equal length"],
            alternatives_count=4
        )
    
    @pytest.fixture
    def sample_validation(self, sample_sequence):
        """Create a sample validation result."""
        issues = [
            ValidationIssue(
                flag=ValidationFlag.NO_UNIPROT_ENTRY,
                level=ValidationLevel.INFO,
                message="No UniProt entry found",
                details={}
            )
        ]
        return ValidationResult(
            sequence=sample_sequence,
            is_valid=True,
            confidence_score=0.90,
            issues=issues,
            cross_references={'ensembl': {'gene_id': 'ENSG00000141510'}}
        )
    
    def test_format_sequence_result_success(self, formatter, sample_sequence, 
                                          sample_selection, sample_validation):
        """Test formatting a successful result."""
        result = formatter.format_sequence_result(
            input_name="p53",
            sequence=sample_sequence,
            selection=sample_selection,
            validation=sample_validation
        )
        
        assert result['Input Name'] == "p53"
        assert result['Official Symbol'] == "TP53"
        assert result['Gene ID'] == "7157"
        assert result['RefSeq Accession'] == "NM_000546.6"
        assert result['GenBank URL'] == "https://www.ncbi.nlm.nih.gov/nuccore/NM_000546.6"
        assert result['CDS Length'] == "18"
        assert result['CDS Sequence'] == "ATGGAGGAGCCGCAGTAA"
        assert result['Selection Method'] == "RefSeq Select"
        assert result['Confidence Score'] == "0.95"
        assert result['Warnings'] == "Multiple transcripts with equal length"
        assert result['Validation Status'] == "Valid"
        assert result['Validation Confidence'] == "0.90"
        assert "[info] No UniProt entry found" in result['Validation Issues']
        assert result['Error'] == ""
    
    def test_format_sequence_result_error(self, formatter):
        """Test formatting an error result."""
        result = formatter.format_sequence_result(
            input_name="INVALID_GENE",
            error="Gene not found in database"
        )
        
        assert result['Input Name'] == "INVALID_GENE"
        assert result['Official Symbol'] == ""
        assert result['Error'] == "Gene not found in database"
        assert all(result[col] == "" for col in formatter.COLUMNS 
                  if col not in ['Input Name', 'Error'])
    
    def test_write_tsv_with_bom(self, formatter, temp_dir, sample_sequence):
        """Test writing TSV file with UTF-8 BOM."""
        output_file = temp_dir / "output.tsv"
        
        results = [
            formatter.format_sequence_result("p53", sample_sequence),
            formatter.format_sequence_result("INVALID", error="Not found")
        ]
        
        formatter.format_results(results, output_file, format='tsv', excel_compatible=True)
        
        # Check file exists
        assert output_file.exists()
        
        # Check BOM
        with open(output_file, 'rb') as f:
            bom = f.read(3)
            assert bom == b'\xef\xbb\xbf'  # UTF-8 BOM
        
        # Check content
        content = output_file.read_text(encoding='utf-8-sig')
        lines = content.strip().split('\n')
        assert len(lines) == 3  # Header + 2 data rows
        assert lines[0].startswith("Input Name\t")
        # Check that the key data is present (input name, official symbol, gene ID)
        assert "p53\tTP53" in lines[1]
        assert "7157" in lines[1]
        assert "INVALID" in lines[2]
    
    def test_write_csv(self, formatter, temp_dir, sample_sequence):
        """Test writing CSV file."""
        output_file = temp_dir / "output.csv"
        
        results = [formatter.format_sequence_result("TP53", sample_sequence)]
        formatter.format_results(results, output_file, format='csv', excel_compatible=False)
        
        content = output_file.read_text()
        # Check that headers include required columns
        assert "Input Name" in content
        assert "Official Symbol" in content
        assert "Gene ID" in content
        # Check data content
        assert "TP53,TP53" in content
        assert "7157" in content
    
    def test_write_json(self, formatter, temp_dir, sample_sequence):
        """Test writing JSON file."""
        output_file = temp_dir / "output.json"
        
        results = [formatter.format_sequence_result("TP53", sample_sequence)]
        formatter.format_results(results, output_file, format='json')
        
        with open(output_file) as f:
            data = json.load(f)
        
        assert 'metadata' in data
        assert 'results' in data
        assert data['metadata']['total_entries'] == 1
        assert data['metadata']['columns'] == formatter.COLUMNS
        assert len(data['results']) == 1
        assert data['results'][0]['Official Symbol'] == 'TP53'
    
    def test_audit_trail_generation(self, formatter, temp_dir, sample_sequence):
        """Test audit trail generation."""
        output_file = temp_dir / "output.tsv"
        
        # Process multiple results
        results = []
        for gene in ["TP53", "BRCA1", "INVALID"]:
            if gene == "INVALID":
                result = formatter.format_sequence_result(gene, error="Not found")
            else:
                result = formatter.format_sequence_result(gene, sample_sequence)
            results.append(result)
        
        formatter.format_results(results, output_file)
        
        # Check audit file
        audit_file = output_file.with_suffix('.audit.json')
        assert audit_file.exists()
        
        with open(audit_file) as f:
            audit_data = json.load(f)
        
        assert audit_data['statistics']['total_processed'] == 3
        assert audit_data['statistics']['successful'] == 2
        assert audit_data['statistics']['failed'] == 1
        assert audit_data['statistics']['success_rate'] == "66.7%"
        assert 'database_versions' in audit_data
        assert len(audit_data['entries']) == 3
    
    def test_statistics(self, formatter, sample_sequence):
        """Test statistics tracking."""
        # Process some results
        formatter.format_sequence_result("TP53", sample_sequence)
        formatter.format_sequence_result("INVALID", error="Not found")
        
        stats = formatter.get_statistics()
        
        assert stats['total_processed'] == 2
        assert stats['successful'] == 1
        assert stats['failed'] == 1
        assert 'duration' in stats
    
    def test_column_headers(self, formatter):
        """Test that all expected columns are present."""
        expected_columns = [
            "Input Name", "Official Symbol", "Full Gene Name", "Gene ID", 
            "Gene URL", "RefSeq Accession", "GenBank URL", "Isoform",
            "CDS Length", "CDS Sequence", "Selection Method",
            "Confidence Score", "Warnings", "Validation Status",
            "Validation Confidence", "Validation Issues", "Error"
        ]
        
        assert formatter.COLUMNS == expected_columns
    
    def test_format_validation_issues(self, formatter, sample_sequence):
        """Test formatting of validation issues."""
        issues = [
            ValidationIssue(
                flag=ValidationFlag.NO_START_CODON,
                level=ValidationLevel.WARNING,
                message="Missing start codon",
                details={}
            ),
            ValidationIssue(
                flag=ValidationFlag.MULTIPLE_STOP_CODONS,
                level=ValidationLevel.ERROR,
                message="Internal stop codon found",
                details={'stop_positions': [(9, 'TAG')]}
            )
        ]
        
        validation = ValidationResult(
            sequence=sample_sequence,
            is_valid=False,
            confidence_score=0.60,
            issues=issues,
            cross_references={}
        )
        
        result = formatter.format_sequence_result(
            input_name="TEST",
            validation=validation
        )
        
        assert result['Validation Status'] == 'Invalid'
        assert result['Validation Confidence'] == '0.60'
        assert '[warning] Missing start codon' in result['Validation Issues']
        assert '[error] Internal stop codon found' in result['Validation Issues']
    
    def test_empty_results(self, formatter, temp_dir):
        """Test handling empty results."""
        output_file = temp_dir / "empty.tsv"
        formatter.format_results([], output_file)
        
        # Read without BOM
        content = output_file.read_text(encoding='utf-8-sig')
        lines = content.strip().split('\n')
        assert len(lines) == 1  # Just header
        assert lines[0].startswith("Input Name\t")
    
    @pytest.mark.skipif(True, reason="Excel output requires openpyxl")
    def test_write_excel(self, formatter, temp_dir, sample_sequence):
        """Test writing Excel file (requires openpyxl)."""
        # This test would require openpyxl to be installed
        # Skipped by default
        pass