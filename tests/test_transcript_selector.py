"""Tests for transcript selection module."""

from unittest.mock import Mock, patch

import pytest

from genbank_tool.models import RetrievedSequence
from genbank_tool.transcript_selector import (
    SelectionMethod,
    TranscriptSelection,
    TranscriptSelector,
)


class TestTranscriptSelector:
    """Test cases for transcript selection."""
    
    @pytest.fixture
    def selector(self):
        """Create a TranscriptSelector instance."""
        return TranscriptSelector(uniprot_enabled=True, prefer_longest=True)
    
    def _create_sequence(self, accession, version, cds_length, refseq_select=False, 
                        gene_symbol="TEST", gene_id="12345", description="Test transcript"):
        """Helper to create RetrievedSequence with proper fields."""
        cds_seq = "ATG" + "CGT" * ((cds_length - 6) // 3) + "TAA"
        return RetrievedSequence(
            gene_symbol=gene_symbol,
            gene_id=gene_id,
            accession=accession,
            version=version,
            description=description,
            genbank_url=f"https://www.ncbi.nlm.nih.gov/nuccore/{accession}.{version}",
            cds_sequence=cds_seq,
            cds_length=cds_length,
            refseq_select=refseq_select
        )
    
    @pytest.fixture
    def mock_transcripts(self):
        """Create mock transcript data."""
        return [
            RetrievedSequence(
                gene_symbol="TEST1",
                gene_id="12345",
                accession="NM_001234",
                version=1,
                description="Transcript 1",
                genbank_url="https://www.ncbi.nlm.nih.gov/nuccore/NM_001234.1",
                cds_sequence="ATG" + "CGT" * 300 + "TAA",  # 909 bp
                cds_length=909,
                refseq_select=False
            ),
            RetrievedSequence(
                gene_symbol="TEST1",
                gene_id="12345",
                accession="NM_001234",
                version=2,
                description="Transcript 2",
                genbank_url="https://www.ncbi.nlm.nih.gov/nuccore/NM_001234.2",
                cds_sequence="ATG" + "CGT" * 400 + "TAA",  # 1209 bp
                cds_length=1209,
                refseq_select=False
            ),
            RetrievedSequence(
                gene_symbol="TEST1",
                gene_id="12345",
                accession="NM_001235",
                version=1,
                description="Transcript 3 - RefSeq Select",
                genbank_url="https://www.ncbi.nlm.nih.gov/nuccore/NM_001235.1",
                cds_sequence="ATG" + "CGT" * 250 + "TAA",  # 759 bp
                cds_length=759,
                refseq_select=True
            ),
            RetrievedSequence(
                gene_symbol="TEST1",
                gene_id="12345",
                accession="NM_001236",
                version=1,
                description="Transcript 4",
                genbank_url="https://www.ncbi.nlm.nih.gov/nuccore/NM_001236.1",
                cds_sequence="ATG" + "CGT" * 350 + "TAA",  # 1059 bp
                cds_length=1059,
                refseq_select=False
            ),
        ]
    
    def test_select_with_refseq_select(self, selector, mock_transcripts):
        """Test that RefSeq Select takes highest priority."""
        result = selector.select_canonical(
            mock_transcripts,
            gene_symbol="TEST1",
            gene_id="12345"
        )
        
        assert result is not None
        assert result.transcript.accession == "NM_001235"
        assert result.method == SelectionMethod.REFSEQ_SELECT
        assert result.confidence == 0.95
        assert "RefSeq Select" in result.rationale
        assert result.alternatives_count == 3
    
    def test_select_with_user_preference(self, selector, mock_transcripts):
        """Test that user preference overrides all other criteria."""
        result = selector.select_canonical(
            mock_transcripts,
            gene_symbol="TEST1",
            gene_id="12345",
            user_preference="NM_001236"
        )
        
        assert result is not None
        assert result.transcript.accession == "NM_001236"
        assert result.method == SelectionMethod.USER_OVERRIDE
        assert result.confidence == 1.0
        assert "User specified" in result.rationale
    
    def test_select_with_invalid_user_preference(self, selector, mock_transcripts):
        """Test handling of invalid user preference."""
        result = selector.select_canonical(
            mock_transcripts,
            gene_symbol="TEST1",
            gene_id="12345",
            user_preference="NM_999999"
        )
        
        # Should fall back to RefSeq Select
        assert result.transcript.accession == "NM_001235"
        assert result.method == SelectionMethod.REFSEQ_SELECT
        assert "User preference NM_999999 not found" in result.warnings
    
    def test_select_longest_cds(self, selector):
        """Test longest CDS selection when no RefSeq Select."""
        transcripts = [
            self._create_sequence("NM_001234", 1, 309, description="Short transcript"),
            self._create_sequence("NM_001235", 1, 1509, description="Long transcript"),
        ]
        
        result = selector.select_canonical(
            transcripts,
            gene_symbol="TEST2",
            gene_id="12346"
        )
        
        assert result.transcript.accession == "NM_001235"
        assert result.method == SelectionMethod.LONGEST_CDS
        assert result.confidence == 0.8
        assert "1509 bp" in result.rationale
    
    def test_select_with_equal_length_transcripts(self, selector):
        """Test selection when multiple transcripts have equal length."""
        transcripts = [
            self._create_sequence("NM_001234", 1, 909, description="Transcript v1"),
            self._create_sequence("NM_001234", 3, 909, description="Transcript v3"),
            self._create_sequence("NM_001234", 2, 909, description="Transcript v2"),
        ]
        
        result = selector.select_canonical(
            transcripts,
            gene_symbol="TEST3",
            gene_id="12347"
        )
        
        # Should select version 3 (most recent)
        assert result.transcript.version == 3
        assert result.method == SelectionMethod.MOST_RECENT_VERSION
        assert result.confidence == 0.7
        assert "3 transcripts with equal CDS length" in result.warnings
    
    def test_select_with_uniprot_canonical(self, selector, mock_transcripts):
        """Test UniProt canonical selection."""
        # Remove RefSeq Select to test UniProt
        for t in mock_transcripts:
            t.refseq_select = False
        
        # Mock UniProt response
        with patch.object(selector.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                'results': [{
                    'uniProtKBCrossReferences': [
                        {'database': 'RefSeq', 'id': 'NM_001236.1'},
                        {'database': 'RefSeq', 'id': 'NM_001234.2'},
                    ]
                }]
            }
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            result = selector.select_canonical(
                mock_transcripts,
                gene_symbol="TEST4",
                gene_id="12348"
            )
            
            assert result.transcript.accession == "NM_001236"
            assert result.method == SelectionMethod.UNIPROT_CANONICAL
            assert result.confidence == 0.9
            assert "UniProt canonical" in result.rationale
    
    def test_select_empty_list(self, selector):
        """Test handling of empty transcript list."""
        result = selector.select_canonical(
            [],
            gene_symbol="TEST5",
            gene_id="12349"
        )
        
        assert result is None
    
    def test_select_single_transcript(self, selector):
        """Test selection with only one transcript."""
        transcripts = [
            self._create_sequence("NM_001234", 1, 9, description="Only transcript")
        ]
        
        result = selector.select_canonical(
            transcripts,
            gene_symbol="TEST6",
            gene_id="12350"
        )
        
        assert result.transcript.accession == "NM_001234"
        assert result.alternatives_count == 0
    
    def test_select_without_uniprot(self, mock_transcripts):
        """Test selection with UniProt disabled."""
        selector = TranscriptSelector(uniprot_enabled=False, prefer_longest=True)
        
        # Remove RefSeq Select
        for t in mock_transcripts:
            t.refseq_select = False
        
        result = selector.select_canonical(
            mock_transcripts,
            gene_symbol="TEST7",
            gene_id="12351"
        )
        
        # Should select longest (NM_001234 v2 with 1209 bp)
        assert result.transcript.accession == "NM_001234"
        assert result.transcript.version == 2
        assert result.method == SelectionMethod.LONGEST_CDS
    
    def test_uniprot_error_handling(self, selector, mock_transcripts):
        """Test handling of UniProt API errors."""
        # Remove RefSeq Select
        for t in mock_transcripts:
            t.refseq_select = False
        
        with patch.object(selector.session, 'get') as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            result = selector.select_canonical(
                mock_transcripts,
                gene_symbol="TEST8",
                gene_id="12352"
            )
            
            # Should fall back to longest CDS
            assert result.method == SelectionMethod.LONGEST_CDS
    
    def test_generate_selection_report(self, selector):
        """Test report generation."""
        selections = {
            "GENE1": TranscriptSelection(
                transcript=Mock(full_accession="NM_001234.1"),
                method=SelectionMethod.REFSEQ_SELECT,
                confidence=0.95,
                rationale="RefSeq Select",
                warnings=[],
                alternatives_count=3
            ),
            "GENE2": TranscriptSelection(
                transcript=Mock(full_accession="NM_001235.1"),
                method=SelectionMethod.LONGEST_CDS,
                confidence=0.8,
                rationale="Longest CDS",
                warnings=[],
                alternatives_count=2
            ),
            "GENE3": TranscriptSelection(
                transcript=Mock(full_accession="NM_001236.1"),
                method=SelectionMethod.DEFAULT,
                confidence=0.5,
                rationale="Default",
                warnings=["No clear canonical transcript"],
                alternatives_count=5
            ),
        }
        
        report = selector.generate_selection_report(selections)
        
        assert "Total genes processed: 3" in report
        assert "RefSeq Select: 1 (33.3%)" in report
        assert "Longest CDS: 1 (33.3%)" in report
        assert "GENE3" in report  # Gene with warnings
        assert "No clear canonical transcript" in report
    
    def test_find_by_accession_with_version(self, selector):
        """Test finding transcript by full accession with version."""
        transcripts = [
            self._create_sequence("NM_001234", 2, 9, description="Test")
        ]
        
        # Test with version
        found = selector._find_by_accession(transcripts, "NM_001234.2")
        assert found is not None
        assert found.accession == "NM_001234"
        
        # Test without version
        found = selector._find_by_accession(transcripts, "NM_001234")
        assert found is not None
        assert found.accession == "NM_001234"
        
        # Test not found
        found = selector._find_by_accession(transcripts, "NM_999999")
        assert found is None