"""Tests for UniProt integration in gene resolver."""

import json
from unittest.mock import Mock, patch, MagicMock

import pytest

from genbank_tool.gene_resolver import GeneResolver, ResolvedGene


class TestGeneResolverUniProt:
    """Test cases for UniProt integration."""
    
    @pytest.fixture
    def resolver(self, tmp_path):
        """Create a GeneResolver instance with temp cache directory."""
        resolver = GeneResolver(cache_enabled=True)
        resolver.CACHE_DIR = tmp_path / "cache"
        resolver.CACHE_DIR.mkdir(exist_ok=True)
        return resolver
    
    @pytest.fixture
    def mock_ncbi_low_confidence(self):
        """Mock NCBI response with low confidence match."""
        return [
            {
                'uid': '7040',
                'name': 'TGFB1',
                'description': 'transforming growth factor beta 1',
                'otheraliases': ''
            }
        ]
    
    @pytest.fixture
    def mock_uniprot_pax6_response(self):
        """Mock UniProt response for PAX6."""
        return {
            'results': [
                {
                    'primaryAccession': 'P26367',
                    'genes': [
                        {
                            'geneName': {'value': 'PAX6'},
                            'synonyms': [{'value': 'AN2'}]
                        }
                    ],
                    'proteinDescription': {
                        'recommendedName': {
                            'fullName': {'value': 'Paired box protein Pax-6'}
                        }
                    },
                    'uniProtKBCrossReferences': [
                        {
                            'database': 'GeneID',
                            'id': '5080'
                        }
                    ]
                }
            ]
        }
    
    def test_pax6_resolution(self, resolver):
        """Test PAX6 resolution with UniProt fallback."""
        with patch.object(resolver, '_search_gene') as mock_ncbi:
            # NCBI returns wrong gene with low confidence
            mock_ncbi.return_value = [
                {
                    'uid': '7040',
                    'name': 'TGFB1',
                    'description': 'transforming growth factor beta 1',
                    'otheraliases': ''
                }
            ]
            
            with patch.object(resolver, '_search_uniprot') as mock_uniprot:
                # UniProt returns correct PAX6
                mock_uniprot.return_value = [
                    {
                        'primaryAccession': 'P26367',
                        'genes': [
                            {
                                'geneName': {'value': 'PAX6'},
                                'synonyms': [{'value': 'AN2'}]
                            }
                        ],
                        'proteinDescription': {
                            'recommendedName': {
                                'fullName': {'value': 'Paired box protein Pax-6'}
                            }
                        },
                        'uniProtKBCrossReferences': [
                            {
                                'database': 'GeneID',
                                'id': '5080'
                            }
                        ]
                    }
                ]
                
                result = resolver.resolve('PAX6')
                
                assert result is not None
                assert result.official_symbol == 'PAX6'
                assert result.gene_id == '5080'
                assert result.source == 'UniProt'
                assert result.confidence == 0.95  # Exact match in UniProt
    
    def test_ncbi_high_confidence_no_uniprot(self, resolver):
        """Test that high confidence NCBI results don't trigger UniProt."""
        with patch.object(resolver, '_search_gene') as mock_ncbi:
            # NCBI returns high confidence match
            mock_ncbi.return_value = [
                {
                    'uid': '7157',
                    'name': 'TP53',
                    'description': 'tumor protein p53',
                    'otheraliases': 'p53, LFS1'
                }
            ]
            
            with patch.object(resolver, '_search_uniprot') as mock_uniprot:
                result = resolver.resolve('TP53')
                
                # Should not call UniProt
                mock_uniprot.assert_not_called()
                
                assert result is not None
                assert result.official_symbol == 'TP53'
                assert result.source == 'NCBI'
                assert result.confidence == 1.0
    
    def test_extract_gene_id_from_uniprot(self, resolver):
        """Test extracting NCBI Gene ID from UniProt entry."""
        entry = {
            'uniProtKBCrossReferences': [
                {'database': 'RefSeq', 'id': 'NP_000660.1'},
                {'database': 'GeneID', 'id': '5080'},
                {'database': 'HGNC', 'id': 'HGNC:8620'}
            ]
        }
        
        gene_id = resolver._extract_gene_id_from_uniprot(entry)
        assert gene_id == '5080'
    
    def test_parse_uniprot_gene_names(self, resolver):
        """Test parsing gene names from UniProt entry."""
        entry = {
            'genes': [
                {
                    'geneName': {'value': 'PAX6'},
                    'synonyms': [
                        {'value': 'AN2'},
                        {'value': 'MGDA'}
                    ]
                }
            ]
        }
        
        primary, aliases = resolver._parse_uniprot_gene_names(entry)
        
        assert primary == 'PAX6'
        assert aliases == ['AN2', 'MGDA']
    
    def test_calculate_uniprot_confidence(self, resolver):
        """Test UniProt confidence scoring."""
        entry = {
            'genes': [
                {
                    'geneName': {'value': 'PAX6'},
                    'synonyms': [{'value': 'AN2'}]
                }
            ]
        }
        
        # Exact match
        assert resolver._calculate_uniprot_confidence('PAX6', entry) == 0.95
        assert resolver._calculate_uniprot_confidence('pax6', entry) == 0.95
        
        # Alias match
        assert resolver._calculate_uniprot_confidence('AN2', entry) == 0.85
        
        # Partial match
        assert resolver._calculate_uniprot_confidence('PAX', entry) == 0.7
        
        # Low match
        assert resolver._calculate_uniprot_confidence('RANDOM', entry) == 0.5
    
    def test_both_sources_conflict(self, resolver):
        """Test when NCBI and UniProt give different results."""
        with patch.object(resolver, '_search_gene') as mock_ncbi:
            # NCBI returns low confidence match
            mock_ncbi.return_value = [
                {
                    'uid': '7040',
                    'name': 'TGFB1',
                    'description': 'transforming growth factor beta 1',
                    'otheraliases': ''
                }
            ]
            
            with patch.object(resolver, '_search_uniprot') as mock_uniprot:
                # UniProt returns different gene
                mock_uniprot.return_value = [
                    {
                        'primaryAccession': 'P26367',
                        'genes': [{'geneName': {'value': 'PAX6'}}],
                        'uniProtKBCrossReferences': [
                            {'database': 'GeneID', 'id': '5080'}
                        ]
                    }
                ]
                
                result = resolver.resolve('TESTGENE')
                
                # UniProt should have lower confidence (0.5) for TESTGENE->PAX6
                # but NCBI also has 0.5 for TESTGENE->TGFB1
                # In this case, we keep NCBI but note the UniProt alternative
                assert result.source == 'NCBI'
                assert result.official_symbol == 'TGFB1'
                assert 'UniProt suggests PAX6' in result.disambiguation_reason
    
    def test_uniprot_no_gene_id(self, resolver):
        """Test handling UniProt entries without NCBI Gene ID."""
        with patch.object(resolver, '_search_gene') as mock_ncbi:
            mock_ncbi.return_value = []  # No NCBI results
            
            with patch.object(resolver, '_search_uniprot') as mock_uniprot:
                # UniProt entry without Gene ID
                mock_uniprot.return_value = [
                    {
                        'primaryAccession': 'P12345',
                        'genes': [{'geneName': {'value': 'TESTGENE'}}],
                        'uniProtKBCrossReferences': []  # No Gene ID
                    }
                ]
                
                result = resolver.resolve('TESTGENE')
                
                # Should return None as we need Gene ID
                assert result is None
    
    @patch('requests.Session.get')
    def test_uniprot_rate_limiting(self, mock_get, resolver):
        """Test UniProt rate limiting."""
        mock_get.return_value = Mock(
            json=lambda: {'results': []},
            status_code=200
        )
        
        import time
        
        # Make two quick UniProt requests
        start_time = time.time()
        resolver._search_uniprot('GENE1')
        resolver._search_uniprot('GENE2')
        elapsed = time.time() - start_time
        
        # Should respect UniProt rate limit
        assert elapsed >= (1.0 / resolver.UNIPROT_RATE_LIMIT)
    
    def test_uniprot_cache(self, resolver, tmp_path):
        """Test UniProt results caching."""
        with patch.object(resolver, 'session') as mock_session:
            # Mock UniProt response
            mock_response = Mock()
            mock_response.json.return_value = {
                'results': [
                    {
                        'primaryAccession': 'P26367',
                        'genes': [{'geneName': {'value': 'PAX6'}}]
                    }
                ]
            }
            mock_session.get.return_value = mock_response
            
            # First call - should hit API
            result1 = resolver._search_uniprot('PAX6')
            assert mock_session.get.call_count == 1
            
            # Second call - should use cache
            result2 = resolver._search_uniprot('PAX6')
            assert mock_session.get.call_count == 1  # No additional call
            
            assert result1 == result2