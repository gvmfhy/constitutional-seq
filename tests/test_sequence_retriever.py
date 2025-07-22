"""Tests for the sequence retriever module."""

import json
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation

from genbank_tool.sequence_retriever import SequenceRetriever, RetrievedSequence


class TestSequenceRetriever:
    """Test cases for SequenceRetriever class."""
    
    @pytest.fixture
    def retriever(self, tmp_path):
        """Create a SequenceRetriever instance with temp cache directory."""
        retriever = SequenceRetriever(email="test@example.com", cache_enabled=True)
        retriever.CACHE_DIR = tmp_path / "cache"
        retriever.CACHE_DIR.mkdir(exist_ok=True)
        return retriever
    
    @pytest.fixture
    def mock_genbank_record(self):
        """Create a mock GenBank record with CDS."""
        # Create a sequence
        sequence = Seq("ATGTCGAAATAG")  # 12 bp, starts with ATG, ends with TAG
        
        # Create a record
        record = SeqRecord(
            sequence,
            id="NM_001025077.3",
            name="NM_001025077",
            description="Homo sapiens vascular endothelial growth factor A (VEGFA), transcript variant 1, mRNA"
        )
        
        # Add gene feature
        gene_feature = SeqFeature(
            FeatureLocation(0, 12),
            type="gene",
            qualifiers={
                'gene': ['VEGFA'],
                'db_xref': ['GeneID:7422']
            }
        )
        
        # Add CDS feature
        cds_feature = SeqFeature(
            FeatureLocation(0, 12),
            type="CDS",
            qualifiers={
                'protein_id': ['NP_001020298.2'],
                'product': ['vascular endothelial growth factor A'],
                'translation': ['MSK*'],
                'gene': ['VEGFA']
            }
        )
        
        record.features = [gene_feature, cds_feature]
        record.annotations = {'comment': 'This is a RefSeq Select transcript'}
        
        return record
    
    @pytest.fixture  
    def mock_search_result(self):
        """Mock Entrez search result."""
        return {
            'IdList': ['123456789', '987654321'],
            'Count': '2'
        }
    
    def test_retrieved_sequence_full_accession(self):
        """Test full accession property."""
        seq = RetrievedSequence(
            gene_symbol="VEGFA",
            gene_id="7422",
            accession="NM_001025077",
            version="3",
            description="Test",
            genbank_url="http://test.com",
            cds_sequence="ATG",
            cds_length=3
        )
        
        assert seq.full_accession == "NM_001025077.3"
    
    def test_extract_cds_features(self, retriever, mock_genbank_record):
        """Test CDS feature extraction."""
        cds_features = retriever._extract_cds_features(mock_genbank_record)
        
        assert len(cds_features) == 1
        assert cds_features[0]['sequence'] == "ATGTCGAAATAG"
        assert cds_features[0]['length'] == 12
        assert cds_features[0]['protein_id'] == 'NP_001020298.2'
        assert cds_features[0]['has_start_codon'] == True
        assert cds_features[0]['has_stop_codon'] == True
    
    def test_is_refseq_select(self, retriever, mock_genbank_record):
        """Test RefSeq Select detection."""
        assert retriever._is_refseq_select(mock_genbank_record) == True
        
        # Test without RefSeq Select
        mock_genbank_record.annotations = {'comment': 'Regular transcript'}
        assert retriever._is_refseq_select(mock_genbank_record) == False
    
    def test_extract_transcript_variant(self, retriever):
        """Test transcript variant extraction."""
        # Test with variant in description
        record = SeqRecord(
            Seq("ATG"),
            description="Gene X, transcript variant 2, mRNA"
        )
        assert retriever._extract_transcript_variant(record) == "2"
        
        # Test with isoform
        record.description = "Gene Y, isoform alpha, mRNA"
        assert retriever._extract_transcript_variant(record) == "alpha"
        
        # Test without variant
        record.description = "Gene Z mRNA"
        assert retriever._extract_transcript_variant(record) is None
    
    @patch('Bio.Entrez.esearch')
    @patch('Bio.Entrez.efetch')
    def test_retrieve_by_gene_id(self, mock_efetch, mock_esearch, retriever, 
                                  mock_search_result, mock_genbank_record):
        """Test retrieving sequences by gene ID."""
        # Mock search results
        mock_search_handle = MagicMock()
        mock_search_handle.read.return_value = str(mock_search_result).encode()
        mock_esearch.return_value = mock_search_handle
        
        # Mock Entrez.read for search
        with patch('Bio.Entrez.read', return_value=mock_search_result):
            # Mock fetch results
            mock_fetch_handle = MagicMock()
            mock_efetch.return_value = mock_fetch_handle
            
            # Mock SeqIO.parse
            with patch('Bio.SeqIO.parse', return_value=[mock_genbank_record]):
                sequences = retriever.retrieve_by_gene_id("VEGFA", "7422")
        
        assert len(sequences) == 1
        seq = sequences[0]
        
        assert seq.gene_symbol == "VEGFA"
        assert seq.gene_id == "7422"
        assert seq.accession == "NM_001025077"
        assert seq.version == "3"
        assert seq.cds_sequence == "ATGTCGAAATAG"
        assert seq.cds_length == 12
        assert seq.refseq_select == True
    
    @patch('Bio.Entrez.efetch')
    def test_retrieve_by_accession(self, mock_efetch, retriever, mock_genbank_record):
        """Test retrieving a specific sequence by accession."""
        # Mock fetch results
        mock_handle = MagicMock()
        mock_efetch.return_value = mock_handle
        
        # Mock SeqIO.parse
        with patch('Bio.SeqIO.parse', return_value=[mock_genbank_record]):
            seq = retriever.retrieve_by_accession("NM_001025077")
        
        assert seq is not None
        assert seq.accession == "NM_001025077"
        assert seq.gene_symbol == "VEGFA"
        assert seq.cds_sequence == "ATGTCGAAATAG"
    
    @patch('Bio.Entrez.esearch')
    def test_empty_search_results(self, mock_esearch, retriever):
        """Test handling of empty search results."""
        # Mock empty search
        mock_handle = MagicMock()
        mock_esearch.return_value = mock_handle
        
        with patch('Bio.Entrez.read', return_value={'IdList': []}):
            sequences = retriever.retrieve_by_gene_id("NOTREAL", "99999")
        
        assert sequences == []
    
    def test_caching(self, retriever, tmp_path):
        """Test caching functionality."""
        # Create cache data
        cache_data = {
            'timestamp': time.time(),
            'gene_id': '7422',
            'sequences': [
                {
                    'gene_symbol': 'VEGFA',
                    'gene_id': '7422',
                    'accession': 'NM_001025077',
                    'version': '3',
                    'description': 'Test sequence',
                    'genbank_url': 'http://test.com',
                    'cds_sequence': 'ATGTAG',
                    'cds_length': 6,
                    'protein_id': 'NP_001020298.2',
                    'transcript_variant': '1',
                    'refseq_select': True,
                    'retrieval_timestamp': '2024-01-01 00:00:00'
                }
            ]
        }
        
        # Save to cache
        cache_path = retriever._get_cache_path('7422')
        with open(cache_path, 'w') as f:
            json.dump(cache_data, f)
        
        # Load from cache
        cached = retriever._load_from_cache('7422')
        
        assert cached is not None
        assert len(cached) == 1
        assert cached[0]['gene_symbol'] == 'VEGFA'
    
    def test_cache_expiration(self, retriever, tmp_path):
        """Test cache expiration."""
        # Create old cache entry (8 days old)
        cache_data = {
            'timestamp': time.time() - (8 * 24 * 3600),
            'gene_id': '7422',
            'sequences': [{'gene_symbol': 'VEGFA'}]
        }
        
        cache_path = retriever._get_cache_path('7422')
        with open(cache_path, 'w') as f:
            json.dump(cache_data, f)
        
        # Try to load expired cache
        cached = retriever._load_from_cache('7422')
        
        assert cached is None
    
    def test_rate_limiting(self, retriever):
        """Test rate limiting."""
        import time
        
        # Make two requests
        start_time = time.time()
        retriever._rate_limit()
        retriever._rate_limit()
        elapsed = time.time() - start_time
        
        # Should take at least 1/3 second
        assert elapsed >= (1.0 / retriever.RATE_LIMIT)
    
    @patch('Bio.Entrez.esearch')
    def test_error_handling(self, mock_esearch, retriever):
        """Test error handling."""
        # Test search error
        mock_esearch.side_effect = Exception("Network error")
        
        sequences = retriever.retrieve_by_gene_id("VEGFA", "7422")
        assert sequences == []
    
    def test_multiple_cds_features(self, retriever):
        """Test handling records with multiple CDS features."""
        # Create record with multiple CDS
        sequence = Seq("ATGTCGAAATAGATGAAATAG")  # 21 bp
        record = SeqRecord(sequence, id="NM_TEST.1")
        
        # Add two CDS features
        cds1 = SeqFeature(
            FeatureLocation(0, 12),
            type="CDS",
            qualifiers={'protein_id': ['NP_001.1']}
        )
        
        cds2 = SeqFeature(
            FeatureLocation(9, 21),  # Longer CDS
            type="CDS", 
            qualifiers={'protein_id': ['NP_002.1']}
        )
        
        record.features = [cds1, cds2]
        
        cds_features = retriever._extract_cds_features(record)
        
        assert len(cds_features) == 2
        # Should have extracted both
        assert cds_features[0]['length'] == 12
        assert cds_features[1]['length'] == 12