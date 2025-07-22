"""Tests for the gene resolver module."""

import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from genbank_tool.gene_resolver import GeneResolver, ResolvedGene


class TestGeneResolver:
    """Test cases for GeneResolver class."""
    
    @pytest.fixture
    def resolver(self, tmp_path):
        """Create a GeneResolver instance with temp cache directory."""
        resolver = GeneResolver(cache_enabled=True)
        resolver.CACHE_DIR = tmp_path / "cache"
        resolver.CACHE_DIR.mkdir(exist_ok=True)
        return resolver
    
    @pytest.fixture
    def mock_search_response(self):
        """Mock NCBI search response."""
        return {
            'esearchresult': {
                'idlist': ['7422', '7423']  # VEGFA and VEGFB gene IDs
            }
        }
    
    @pytest.fixture
    def mock_summary_response(self):
        """Mock NCBI summary response."""
        return {
            'result': {
                '7422': {
                    'uid': '7422',
                    'name': 'VEGFA',
                    'description': 'vascular endothelial growth factor A',
                    'otheraliases': 'VEGF, VPF, VEGF-A, MVCD1',
                    'organism': 'Homo sapiens'
                },
                '7423': {
                    'uid': '7423',
                    'name': 'VEGFB',
                    'description': 'vascular endothelial growth factor B',
                    'otheraliases': 'VEGF-B, VRF',
                    'organism': 'Homo sapiens'
                }
            }
        }
    
    def test_normalize_gene_name(self, resolver):
        """Test gene name normalization."""
        assert resolver._normalize_gene_name("VEGF") == "VEGF"
        assert resolver._normalize_gene_name(" VEGF ") == "VEGF"
        assert resolver._normalize_gene_name("VEGF_A") == "VEGFA"
        assert resolver._normalize_gene_name("VEGF-A") == "VEGFA"
        assert resolver._normalize_gene_name("  VEGF   A  ") == "VEGF A"
    
    def test_calculate_confidence(self, resolver):
        """Test confidence score calculation."""
        gene = {
            'name': 'VEGFA',
            'description': 'vascular endothelial growth factor A',
            'otheraliases': 'VEGF, VPF, VEGF-A'
        }
        
        # Exact match
        assert resolver._calculate_confidence('VEGFA', gene) == 1.0
        assert resolver._calculate_confidence('vegfa', gene) == 1.0
        
        # Alias match
        assert resolver._calculate_confidence('VEGF', gene) == 0.9
        assert resolver._calculate_confidence('VPF', gene) == 0.9
        
        # Description match
        gene_desc_only = {'name': 'OTHER', 'description': 'something VEGF related'}
        assert resolver._calculate_confidence('VEGF', gene_desc_only) == 0.7
        
        # Partial match
        assert resolver._calculate_confidence('VEG', gene) == 0.6
    
    @patch('requests.Session.get')
    def test_resolve_vegf_to_vegfa(self, mock_get, resolver, mock_search_response, mock_summary_response):
        """Test resolving VEGF to VEGFA."""
        # Setup mock responses
        mock_responses = [
            Mock(json=lambda: mock_search_response, status_code=200),
            Mock(json=lambda: mock_summary_response, status_code=200)
        ]
        mock_get.side_effect = mock_responses
        
        # Test resolution
        result = resolver.resolve('VEGF')
        
        assert result is not None
        assert result.input_name == 'VEGF'
        assert result.official_symbol == 'VEGFA'
        assert result.gene_id == '7422'
        assert 'VEGF' in result.aliases
        assert result.confidence == 0.9  # Alias match
    
    @patch('requests.Session.get')
    def test_resolve_exact_match(self, mock_get, resolver, mock_search_response, mock_summary_response):
        """Test resolving exact gene symbol."""
        mock_responses = [
            Mock(json=lambda: mock_search_response, status_code=200),
            Mock(json=lambda: mock_summary_response, status_code=200)
        ]
        mock_get.side_effect = mock_responses
        
        result = resolver.resolve('VEGFA')
        
        assert result is not None
        assert result.official_symbol == 'VEGFA'
        assert result.confidence == 1.0  # Exact match
    
    @patch('requests.Session.get')
    def test_resolve_not_found(self, mock_get, resolver):
        """Test resolving non-existent gene."""
        mock_response = Mock(
            json=lambda: {'esearchresult': {'idlist': []}},
            status_code=200
        )
        mock_get.return_value = mock_response
        
        result = resolver.resolve('NOTAREALGENE')
        
        assert result is None
    
    @patch('requests.Session.get')
    def test_resolve_batch(self, mock_get, resolver, mock_search_response, mock_summary_response):
        """Test batch resolution."""
        # Mock different responses for different genes
        mock_responses = [
            # First gene - VEGF
            Mock(json=lambda: mock_search_response, status_code=200),
            Mock(json=lambda: mock_summary_response, status_code=200),
            # Second gene - TP53
            Mock(json=lambda: {'esearchresult': {'idlist': ['7157']}}, status_code=200),
            Mock(json=lambda: {
                'result': {
                    '7157': {
                        'uid': '7157',
                        'name': 'TP53',
                        'description': 'tumor protein p53',
                        'otheraliases': 'p53, LFS1',
                        'organism': 'Homo sapiens'
                    }
                }
            }, status_code=200),
            # Third gene - not found
            Mock(json=lambda: {'esearchresult': {'idlist': []}}, status_code=200),
        ]
        mock_get.side_effect = mock_responses
        
        genes = ['VEGF', 'TP53', 'NOTREAL']
        results = resolver.resolve_batch(genes)
        
        assert len(results) == 3
        assert results['VEGF'].official_symbol == 'VEGFA'
        assert results['TP53'].official_symbol == 'TP53'
        assert results['NOTREAL'] is None
    
    def test_caching(self, resolver, tmp_path):
        """Test caching functionality."""
        # Create a cache entry
        cache_data = {
            'timestamp': 1234567890,
            'query': 'VEGF',
            'result': [
                {
                    'uid': '7422',
                    'name': 'VEGFA',
                    'description': 'vascular endothelial growth factor A',
                    'otheraliases': 'VEGF, VPF'
                }
            ]
        }
        
        cache_path = resolver._get_cache_path('VEGF')
        with open(cache_path, 'w') as f:
            json.dump(cache_data, f)
        
        # Load from cache
        with patch('time.time', return_value=1234567900):  # 10 seconds later
            cached = resolver._load_from_cache('VEGF')
        
        assert cached is not None
        assert cached[0]['name'] == 'VEGFA'
    
    def test_cache_expiration(self, resolver, tmp_path):
        """Test cache expiration."""
        # Create an old cache entry
        cache_data = {
            'timestamp': 1234567890,
            'query': 'VEGF',
            'result': [{'name': 'VEGFA'}]
        }
        
        cache_path = resolver._get_cache_path('VEGF')
        with open(cache_path, 'w') as f:
            json.dump(cache_data, f)
        
        # Try to load expired cache (31 days later)
        with patch('time.time', return_value=1234567890 + 31 * 24 * 3600):
            cached = resolver._load_from_cache('VEGF')
        
        assert cached is None
    
    @patch('requests.Session.get')
    def test_rate_limiting(self, mock_get, resolver):
        """Test rate limiting behavior."""
        mock_get.return_value = Mock(
            json=lambda: {'esearchresult': {'idlist': []}},
            status_code=200
        )
        
        import time
        
        # Make two quick requests
        start_time = time.time()
        resolver._search_gene('GENE1')
        resolver._search_gene('GENE2')
        elapsed = time.time() - start_time
        
        # Should take at least 1/3 second due to rate limiting
        assert elapsed >= (1.0 / resolver.RATE_LIMIT)
    
    def test_error_handling(self, resolver):
        """Test error handling."""
        # Test with both NCBI and UniProt failing
        with patch.object(resolver, '_search_gene') as mock_ncbi:
            mock_ncbi.side_effect = Exception("Network error")
            
            with patch.object(resolver, '_search_uniprot') as mock_uniprot:
                mock_uniprot.side_effect = Exception("UniProt error")
                
                result = resolver.resolve('VEGF')
                assert result is None
        
        # Test with both sources returning empty results
        with patch.object(resolver, '_search_gene') as mock_ncbi:
            mock_ncbi.return_value = []
            
            with patch.object(resolver, '_search_uniprot') as mock_uniprot:
                mock_uniprot.return_value = []
                
                result = resolver.resolve('VEGF')
                assert result is None
    
    def test_disambiguation(self, resolver):
        """Test disambiguation reasoning."""
        with patch.object(resolver, '_search_gene') as mock_search:
            # Mock two very similar genes
            mock_search.return_value = [
                {
                    'uid': '1',
                    'name': 'GENE1',
                    'description': 'test gene 1',
                    'otheraliases': 'TEST'
                },
                {
                    'uid': '2', 
                    'name': 'GENE2',
                    'description': 'test gene 2',
                    'otheraliases': 'TEST'
                }
            ]
            
            result = resolver.resolve('TEST')
            
            assert result is not None
            assert result.disambiguation_reason is not None
            assert 'Selected over' in result.disambiguation_reason