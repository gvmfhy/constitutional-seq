"""Tests for input parsing module."""

import json
import tempfile
from pathlib import Path

import pytest

from genbank_tool.input_parser import InputParser


class TestInputParser:
    """Test cases for input parsing."""
    
    @pytest.fixture
    def parser(self):
        """Create an InputParser instance."""
        return InputParser()
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_parse_text_file(self, parser, temp_dir):
        """Test parsing plain text file."""
        # Create test file
        test_file = temp_dir / "genes.txt"
        test_file.write_text("TP53\nBRCA1\nEGFR\n# Comment line\nVEGFA")
        
        genes = parser.parse_file(test_file)
        
        assert genes == ["TP53", "BRCA1", "EGFR", "VEGFA"]
        assert parser.last_format == "text"
    
    def test_parse_text_file_with_commas(self, parser, temp_dir):
        """Test parsing text file with comma-separated values."""
        test_file = temp_dir / "genes.txt"
        test_file.write_text("TP53, BRCA1, EGFR\nVEGFA, KRAS")
        
        genes = parser.parse_file(test_file)
        
        assert genes == ["TP53", "BRCA1", "EGFR", "VEGFA", "KRAS"]
    
    def test_parse_csv_file_with_header(self, parser, temp_dir):
        """Test parsing CSV file with header."""
        test_file = temp_dir / "genes.csv"
        content = "Gene Symbol,Description,Type\nTP53,Tumor protein p53,TSG\nBRCA1,Breast cancer 1,TSG\nEGFR,Epidermal growth factor receptor,ONC"
        test_file.write_text(content)
        
        genes = parser.parse_file(test_file)
        
        assert genes == ["TP53", "BRCA1", "EGFR"]
        assert parser.last_format == "csv"
        assert parser.last_delimiter == ","
    
    def test_parse_csv_file_no_header(self, parser, temp_dir):
        """Test parsing CSV file without header."""
        test_file = temp_dir / "genes.csv"
        content = "TP53,BRCA1,EGFR\nVEGFA,KRAS,MYC"
        test_file.write_text(content)
        
        genes = parser.parse_file(test_file)
        
        assert genes == ["TP53", "BRCA1", "EGFR", "VEGFA", "KRAS", "MYC"]
    
    def test_parse_tsv_file(self, parser, temp_dir):
        """Test parsing TSV file."""
        test_file = temp_dir / "genes.tsv"
        content = "Gene\tDescription\nTP53\tTumor protein p53\nBRCA1\tBreast cancer 1"
        test_file.write_text(content)
        
        genes = parser.parse_file(test_file)
        
        assert genes == ["TP53", "BRCA1"]
        assert parser.last_delimiter == "\t"
    
    def test_parse_json_file_list(self, parser, temp_dir):
        """Test parsing JSON file with list format."""
        test_file = temp_dir / "genes.json"
        data = ["TP53", "BRCA1", "EGFR"]
        test_file.write_text(json.dumps(data))
        
        genes = parser.parse_file(test_file)
        
        assert genes == ["TP53", "BRCA1", "EGFR"]
        assert parser.last_format == "json"
    
    def test_parse_json_file_objects(self, parser, temp_dir):
        """Test parsing JSON file with object format."""
        test_file = temp_dir / "genes.json"
        data = [
            {"gene": "TP53", "description": "Tumor protein p53"},
            {"symbol": "BRCA1", "description": "Breast cancer 1"},
            {"gene_symbol": "EGFR", "description": "EGFR"}
        ]
        test_file.write_text(json.dumps(data))
        
        genes = parser.parse_file(test_file)
        
        assert genes == ["TP53", "BRCA1", "EGFR"]
    
    def test_parse_json_file_dict(self, parser, temp_dir):
        """Test parsing JSON file with dictionary format."""
        test_file = temp_dir / "genes.json"
        data = {
            "genes": ["TP53", "BRCA1", "EGFR"],
            "metadata": {"source": "test"}
        }
        test_file.write_text(json.dumps(data))
        
        genes = parser.parse_file(test_file)
        
        assert genes == ["TP53", "BRCA1", "EGFR"]
    
    def test_encoding_detection(self, parser, temp_dir):
        """Test encoding detection."""
        # UTF-8 with BOM
        test_file = temp_dir / "genes_bom.txt"
        test_file.write_bytes("\ufeffTP53\nBRCA1".encode('utf-8-sig'))
        
        genes = parser.parse_file(test_file)
        assert genes == ["TP53", "BRCA1"]
        assert parser.last_encoding == "utf-8-sig"
        
        # Latin-1
        test_file_latin = temp_dir / "genes_latin.txt"
        test_file_latin.write_bytes("TP53\nBRCA1\nGène".encode('latin-1'))
        
        genes = parser.parse_file(test_file_latin)
        assert "TP53" in genes
        assert parser.last_encoding == "latin-1"
    
    def test_delimiter_detection(self, parser, temp_dir):
        """Test delimiter detection."""
        # Semicolon delimiter
        test_file = temp_dir / "genes_semicolon.csv"
        test_file.write_text("Gene;Type\nTP53;TSG\nBRCA1;TSG")
        
        genes = parser.parse_file(test_file)
        assert genes == ["TP53", "BRCA1"]
        assert parser.last_delimiter == ";"
        
        # Pipe delimiter
        test_file_pipe = temp_dir / "genes_pipe.csv"
        test_file_pipe.write_text("Gene|Type\nEGFR|ONC\nKRAS|ONC")
        
        genes = parser.parse_file(test_file_pipe)
        assert genes == ["EGFR", "KRAS"]
        assert parser.last_delimiter == "|"
    
    def test_auto_detect_format(self, parser, temp_dir):
        """Test auto-detection of file format."""
        # File without extension
        test_file = temp_dir / "genes"
        test_file.write_text("Gene,Type\nTP53,TSG\nBRCA1,TSG")
        
        genes = parser.parse_file(test_file)
        assert genes == ["TP53", "BRCA1"]
        assert parser.last_format == "csv"
    
    def test_empty_file(self, parser, temp_dir):
        """Test parsing empty file."""
        test_file = temp_dir / "empty.txt"
        test_file.write_text("")
        
        genes = parser.parse_file(test_file)
        assert genes == []
    
    def test_file_not_found(self, parser):
        """Test handling of non-existent file."""
        with pytest.raises(FileNotFoundError):
            parser.parse_file("non_existent_file.txt")
    
    def test_find_gene_column(self, parser):
        """Test gene column detection."""
        # Test various header formats
        assert parser._find_gene_column(["Gene Symbol", "Description"]) == 0
        assert parser._find_gene_column(["ID", "Gene", "Type"]) == 1
        assert parser._find_gene_column(["Name", "HUGO Symbol"]) == 1
        assert parser._find_gene_column(["A", "B", "C"]) is None
        assert parser._find_gene_column([]) is None
    
    def test_get_format_info(self, parser, temp_dir):
        """Test format info retrieval."""
        test_file = temp_dir / "genes.csv"
        test_file.write_text("Gene,Type\nTP53,TSG")
        
        parser.parse_file(test_file)
        info = parser.get_format_info()
        
        assert info['format'] == 'csv'
        assert info['delimiter'] == ','
        assert info['encoding'] in ['utf-8', 'utf-8-sig']
    
    @pytest.mark.skipif(True, reason="Excel parsing requires pandas or openpyxl")
    def test_parse_excel_file(self, parser, temp_dir):
        """Test parsing Excel file (requires pandas or openpyxl)."""
        # This test would require creating an actual Excel file
        # Skipped by default as it requires external dependencies
        pass