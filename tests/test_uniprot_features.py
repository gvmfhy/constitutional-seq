"""Tests for UniProt features module."""

import json
from unittest.mock import Mock, patch, MagicMock

import pytest

from genbank_tool.uniprot_features import (
    UniProtFeatureRetriever,
    ProteinFeatures,
    ProteinDomain,
    PostTranslationalModification,
    ProteinVariant,
    ProteinIsoform,
    DiseaseAssociation,
    DrugTarget,
    PathwayInvolvement,
    ProteinExpression
)


class TestUniProtFeatureRetriever:
    """Test cases for UniProt feature retrieval."""
    
    @pytest.fixture
    def retriever(self):
        """Create a UniProt feature retriever."""
        return UniProtFeatureRetriever(cache_enabled=False)
    
    @pytest.fixture
    def mock_uniprot_entry(self):
        """Create a mock UniProt entry."""
        return {
            'primaryAccession': 'P04637',
            'organism': {'scientificName': 'Homo sapiens', 'taxonId': 9606},
            'proteinDescription': {
                'recommendedName': {
                    'fullName': {'value': 'Cellular tumor antigen p53'}
                }
            },
            'sequence': {'length': 393},
            'features': [
                {
                    'type': 'Domain',
                    'description': 'DNA-binding domain',
                    'location': {'start': {'value': 102}, 'end': {'value': 292}}
                },
                {
                    'type': 'Modified residue',
                    'description': 'Phosphoserine',
                    'location': {'start': {'value': 15}, 'end': {'value': 15}}
                }
            ],
            'comments': [
                {
                    'commentType': 'FUNCTION',
                    'texts': [{'value': 'Acts as a tumor suppressor'}]
                },
                {
                    'commentType': 'SUBCELLULAR LOCATION',
                    'subcellularLocations': [
                        {'location': {'value': 'Nucleus'}}
                    ]
                },
                {
                    'commentType': 'DISEASE',
                    'disease': {
                        'name': 'Li-Fraumeni syndrome',
                        'diseaseId': 'DI-00001'
                    },
                    'texts': [{'value': 'Associated with cancer predisposition'}]
                }
            ],
            'uniProtKBCrossReferences': [
                {
                    'database': 'Pfam',
                    'id': 'PF00870',
                    'properties': [
                        {'key': 'EntryName', 'value': 'P53'},
                        {'key': 'Description', 'value': 'P53 DNA-binding domain'}
                    ]
                },
                {
                    'database': 'KEGG',
                    'id': 'hsa:7157',
                    'properties': [
                        {'key': 'PathwayName', 'value': 'p53 signaling pathway'}
                    ]
                },
                {
                    'database': 'GO',
                    'id': 'GO:0006915',
                    'properties': [
                        {'key': 'GoTerm', 'value': 'P:apoptotic process'}
                    ]
                }
            ]
        }
    
    def test_initialization(self, retriever):
        """Test retriever initialization."""
        assert retriever.cache_enabled == False
        assert retriever.session is not None
    
    def test_extract_protein_name(self, retriever, mock_uniprot_entry):
        """Test protein name extraction."""
        name = retriever._extract_protein_name(mock_uniprot_entry)
        assert name == 'Cellular tumor antigen p53'
    
    def test_extract_protein_name_fallback(self, retriever):
        """Test protein name extraction with fallback."""
        entry = {
            'proteinDescription': {
                'submittedName': [
                    {'fullName': {'value': 'Test protein'}}
                ]
            }
        }
        name = retriever._extract_protein_name(entry)
        assert name == 'Test protein'
    
    def test_extract_domains(self, retriever, mock_uniprot_entry):
        """Test domain extraction."""
        domains = retriever._extract_domains(mock_uniprot_entry)
        
        # Check Pfam domain
        pfam_domains = [d for d in domains if d.database == 'Pfam']
        assert len(pfam_domains) == 1
        assert pfam_domains[0].name == 'P53'
        assert pfam_domains[0].identifier == 'PF00870'
        
        # Check UniProt domain
        uniprot_domains = [d for d in domains if d.database == 'UniProt']
        assert len(uniprot_domains) == 1
        assert uniprot_domains[0].name == 'DNA-binding domain'
        assert uniprot_domains[0].start == 102
        assert uniprot_domains[0].end == 292
    
    def test_extract_ptms(self, retriever, mock_uniprot_entry):
        """Test PTM extraction."""
        ptms = retriever._extract_ptms(mock_uniprot_entry)
        assert len(ptms) == 1
        assert ptms[0].type == 'Modified residue'
        assert ptms[0].position == 15
        assert ptms[0].description == 'Phosphoserine'
    
    def test_extract_diseases(self, retriever, mock_uniprot_entry):
        """Test disease extraction."""
        diseases = retriever._extract_diseases(mock_uniprot_entry)
        assert len(diseases) == 1
        assert diseases[0].disease_name == 'Li-Fraumeni syndrome'
        assert diseases[0].disease_id == 'DI-00001'
        assert 'cancer predisposition' in diseases[0].involvement
    
    def test_extract_pathways(self, retriever, mock_uniprot_entry):
        """Test pathway extraction."""
        pathways = retriever._extract_pathways(mock_uniprot_entry)
        assert len(pathways) == 1
        assert pathways[0].database == 'KEGG'
        assert pathways[0].pathway_id == 'hsa:7157'
        assert pathways[0].pathway_name == 'p53 signaling pathway'
    
    def test_extract_go_terms(self, retriever, mock_uniprot_entry):
        """Test GO term extraction."""
        go_terms = retriever._extract_go_terms(mock_uniprot_entry)
        assert go_terms is not None
        assert 'biological_process' in go_terms
        assert 'apoptotic process' in go_terms['biological_process']
    
    def test_extract_function(self, retriever, mock_uniprot_entry):
        """Test function extraction."""
        function = retriever._extract_function(mock_uniprot_entry)
        assert function == 'Acts as a tumor suppressor'
    
    def test_extract_subcellular_location(self, retriever, mock_uniprot_entry):
        """Test subcellular location extraction."""
        locations = retriever._extract_subcellular_location(mock_uniprot_entry)
        assert locations == ['Nucleus']
    
    @patch('genbank_tool.uniprot_features.requests.Session')
    def test_get_protein_features(self, mock_session_class, retriever, mock_uniprot_entry):
        """Test complete protein feature retrieval."""
        # Setup mock
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'results': [mock_uniprot_entry]}
        mock_session.get.return_value = mock_response
        
        # Reinitialize retriever to use mocked session
        retriever = UniProtFeatureRetriever(cache_enabled=False)
        retriever.session = mock_session
        
        # Get features
        features = retriever.get_protein_features('TP53')
        
        assert features is not None
        assert features.uniprot_id == 'P04637'
        assert features.gene_symbol == 'TP53'
        assert features.protein_name == 'Cellular tumor antigen p53'
        assert features.sequence_length == 393
        assert len(features.domains) > 0
        assert len(features.ptms) > 0
        assert len(features.diseases) > 0
        assert len(features.pathways) > 0
        assert features.function_description == 'Acts as a tumor suppressor'
        assert features.subcellular_location == ['Nucleus']
    
    @patch('genbank_tool.uniprot_features.requests.Session')
    def test_get_protein_features_not_found(self, mock_session_class, retriever):
        """Test protein feature retrieval when not found."""
        # Setup mock
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'results': []}
        mock_session.get.return_value = mock_response
        
        # Reinitialize retriever to use mocked session
        retriever = UniProtFeatureRetriever(cache_enabled=False)
        retriever.session = mock_session
        
        # Get features
        features = retriever.get_protein_features('INVALID_GENE')
        assert features is None
    
    @patch('genbank_tool.uniprot_features.requests.Session')
    def test_extract_variants(self, mock_session_class, retriever):
        """Test variant extraction."""
        # Setup mock
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'features': [
                {
                    'type': 'VARIANT',
                    'begin': 72,
                    'wildType': 'R',
                    'alternativeSequence': 'C',
                    'consequenceType': 'missense',
                    'clinicalSignificance': 'Pathogenic',
                    'association': [{'name': 'Li-Fraumeni syndrome'}],
                    'xrefs': {'dbSNP': ['rs28934578']},
                    'frequency': 0.0001
                }
            ]
        }
        mock_session.get.return_value = mock_response
        
        # Reinitialize retriever to use mocked session
        retriever = UniProtFeatureRetriever(cache_enabled=False)
        retriever.session = mock_session
        
        # Get variants
        variants = retriever._extract_variants('P04637')
        
        assert len(variants) == 1
        assert variants[0].position == 72
        assert variants[0].original == 'R'
        assert variants[0].variant == 'C'
        assert variants[0].type == 'missense'
        assert variants[0].clinical_significance == 'Pathogenic'
        assert variants[0].disease_association == 'Li-Fraumeni syndrome'
        assert variants[0].dbsnp_id == 'rs28934578'
        assert variants[0].frequency == 0.0001
    
    @patch('genbank_tool.uniprot_features.requests.Session')
    def test_analyze_isoforms(self, mock_session_class, retriever, mock_uniprot_entry):
        """Test isoform analysis."""
        # Add isoform data to mock entry
        mock_uniprot_entry['comments'].append({
            'commentType': 'ALTERNATIVE PRODUCTS',
            'isoforms': [
                {
                    'isoformIds': ['P04637-1'],
                    'name': {'value': 'Isoform 1'}
                },
                {
                    'isoformIds': ['P04637-2'],
                    'name': {'value': 'Isoform 2'}
                }
            ]
        })
        
        # Setup mock
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'results': [mock_uniprot_entry]}
        mock_session.get.return_value = mock_response
        
        # Reinitialize retriever to use mocked session
        retriever = UniProtFeatureRetriever(cache_enabled=False)
        retriever.session = mock_session
        
        # Analyze isoforms
        analysis = retriever.analyze_isoforms('TP53')
        
        assert analysis['gene'] == 'TP53'
        assert analysis['canonical_id'] == 'P04637'
        assert analysis['total_isoforms'] == 2
        assert len(analysis['isoforms']) == 2
    
    @patch('genbank_tool.uniprot_features.requests.Session')
    def test_get_clinical_data(self, mock_session_class, retriever, mock_uniprot_entry):
        """Test clinical data retrieval."""
        # Setup mock
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'results': [mock_uniprot_entry]}
        mock_session.get.return_value = mock_response
        
        # Mock variant response
        mock_variant_response = Mock()
        mock_variant_response.status_code = 200
        mock_variant_response.json.return_value = {
            'features': [
                {
                    'type': 'VARIANT',
                    'begin': 72,
                    'wildType': 'R',
                    'alternativeSequence': 'C',
                    'consequenceType': 'missense',
                    'clinicalSignificance': 'Pathogenic'
                },
                {
                    'type': 'VARIANT',
                    'begin': 100,
                    'wildType': 'A',
                    'alternativeSequence': 'T',
                    'consequenceType': 'missense',
                    'clinicalSignificance': 'Benign'
                }
            ]
        }
        
        # Configure mock to return different responses
        mock_session.get.side_effect = [mock_response, mock_variant_response]
        
        # Reinitialize retriever to use mocked session
        retriever = UniProtFeatureRetriever(cache_enabled=False)
        retriever.session = mock_session
        
        # Get clinical data
        clinical_data = retriever.get_clinical_data('TP53')
        
        assert clinical_data['gene'] == 'TP53'
        assert len(clinical_data['diseases']) == 1
        assert len(clinical_data['pathogenic_variants']) == 1
        assert len(clinical_data['benign_variants']) == 1


class TestProteinDataClasses:
    """Test protein feature data classes."""
    
    def test_protein_domain(self):
        """Test ProteinDomain dataclass."""
        domain = ProteinDomain(
            name='P53',
            database='Pfam',
            identifier='PF00870',
            start=102,
            end=292,
            description='P53 DNA-binding domain'
        )
        assert domain.name == 'P53'
        assert domain.database == 'Pfam'
        assert domain.start == 102
        assert domain.end == 292
    
    def test_ptm(self):
        """Test PostTranslationalModification dataclass."""
        ptm = PostTranslationalModification(
            type='phosphorylation',
            position=15,
            residue='S',
            description='Phosphoserine'
        )
        assert ptm.type == 'phosphorylation'
        assert ptm.position == 15
        assert ptm.residue == 'S'
    
    def test_protein_variant(self):
        """Test ProteinVariant dataclass."""
        variant = ProteinVariant(
            position=72,
            original='R',
            variant='C',
            type='missense',
            clinical_significance='Pathogenic'
        )
        assert variant.position == 72
        assert variant.original == 'R'
        assert variant.variant == 'C'
        assert variant.clinical_significance == 'Pathogenic'
    
    def test_protein_features(self):
        """Test ProteinFeatures dataclass."""
        features = ProteinFeatures(
            uniprot_id='P04637',
            gene_symbol='TP53',
            protein_name='Cellular tumor antigen p53',
            sequence_length=393,
            domains=[],
            ptms=[],
            variants=[],
            isoforms=[],
            diseases=[],
            drug_targets=[],
            pathways=[],
            expression=[]
        )
        assert features.uniprot_id == 'P04637'
        assert features.gene_symbol == 'TP53'
        assert features.sequence_length == 393