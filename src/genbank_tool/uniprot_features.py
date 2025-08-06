"""Enhanced UniProt integration for protein feature retrieval."""

import json
import logging
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class ProteinDomain:
    """Represents a protein domain annotation."""
    name: str
    database: str  # Pfam, InterPro, etc.
    identifier: str
    start: int
    end: int
    description: Optional[str] = None
    e_value: Optional[float] = None


@dataclass
class PostTranslationalModification:
    """Represents a post-translational modification."""
    type: str  # phosphorylation, acetylation, etc.
    position: int
    residue: str
    description: Optional[str] = None
    evidence: Optional[str] = None


@dataclass
class ProteinVariant:
    """Represents a protein variant/mutation."""
    position: int
    original: str
    variant: str
    type: str  # missense, nonsense, etc.
    consequence: Optional[str] = None
    clinical_significance: Optional[str] = None
    disease_association: Optional[str] = None
    dbsnp_id: Optional[str] = None
    frequency: Optional[float] = None


@dataclass
class ProteinIsoform:
    """Represents a protein isoform."""
    isoform_id: str
    name: str
    sequence_length: int
    differences: str
    refseq_ids: List[str]
    note: Optional[str] = None


@dataclass
class DiseaseAssociation:
    """Represents a disease association."""
    disease_name: str
    disease_id: str  # OMIM, etc.
    involvement: str
    evidence: str
    mutations: List[str]


@dataclass
class DrugTarget:
    """Represents drug target information."""
    drug_name: str
    drug_id: str  # DrugBank ID
    mechanism: str
    status: str  # approved, experimental, etc.


@dataclass
class PathwayInvolvement:
    """Represents pathway involvement."""
    pathway_name: str
    pathway_id: str  # KEGG, Reactome, etc.
    database: str
    role: Optional[str] = None


@dataclass
class ProteinExpression:
    """Represents tissue/cell expression data."""
    tissue: str
    level: str  # high, medium, low
    cell_type: Optional[str] = None
    evidence: Optional[str] = None


@dataclass
class ProteinFeatures:
    """Complete protein feature set from UniProt."""
    uniprot_id: str
    gene_symbol: str
    protein_name: str
    sequence_length: int
    
    # Structural features
    domains: List[ProteinDomain]
    ptms: List[PostTranslationalModification]
    
    # Variants
    variants: List[ProteinVariant]
    isoforms: List[ProteinIsoform]
    
    # Clinical data
    diseases: List[DiseaseAssociation]
    drug_targets: List[DrugTarget]
    
    # Functional data
    pathways: List[PathwayInvolvement]
    expression: List[ProteinExpression]
    
    # Additional annotations
    function_description: Optional[str] = None
    subcellular_location: Optional[List[str]] = None
    protein_families: Optional[List[str]] = None
    go_terms: Optional[Dict[str, List[str]]] = None  # biological_process, molecular_function, cellular_component


class UniProtFeatureRetriever:
    """Retrieves comprehensive protein features from UniProt."""
    
    UNIPROT_BASE_URL = "https://rest.uniprot.org/uniprotkb"
    UNIPROT_VARIATION_URL = "https://www.ebi.ac.uk/proteins/api/variation"
    
    def __init__(self, cache_enabled: bool = True):
        """Initialize UniProt feature retriever.
        
        Args:
            cache_enabled: Whether to use local caching
        """
        self.cache_enabled = cache_enabled
        
        # Setup session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
    
    def get_protein_features(self, gene_symbol: str) -> Optional[ProteinFeatures]:
        """
        Retrieve comprehensive protein features for a gene.
        
        Args:
            gene_symbol: Gene symbol to query
            
        Returns:
            ProteinFeatures object with all annotations
        """
        try:
            # First, get the UniProt entry
            uniprot_entry = self._get_uniprot_entry(gene_symbol)
            if not uniprot_entry:
                logger.warning(f"No UniProt entry found for {gene_symbol}")
                return None
            
            uniprot_id = uniprot_entry['primaryAccession']
            
            # Extract various features
            features = ProteinFeatures(
                uniprot_id=uniprot_id,
                gene_symbol=gene_symbol,
                protein_name=self._extract_protein_name(uniprot_entry),
                sequence_length=uniprot_entry.get('sequence', {}).get('length', 0),
                domains=self._extract_domains(uniprot_entry),
                ptms=self._extract_ptms(uniprot_entry),
                variants=self._extract_variants(uniprot_id),
                isoforms=self._extract_isoforms(uniprot_entry),
                diseases=self._extract_diseases(uniprot_entry),
                drug_targets=self._extract_drug_targets(uniprot_entry),
                pathways=self._extract_pathways(uniprot_entry),
                expression=self._extract_expression(uniprot_entry),
                function_description=self._extract_function(uniprot_entry),
                subcellular_location=self._extract_subcellular_location(uniprot_entry),
                protein_families=self._extract_protein_families(uniprot_entry),
                go_terms=self._extract_go_terms(uniprot_entry)
            )
            
            return features
            
        except Exception as e:
            logger.error(f"Failed to retrieve features for {gene_symbol}: {e}")
            return None
    
    def _get_uniprot_entry(self, gene_symbol: str) -> Optional[Dict]:
        """Get UniProt entry for a gene."""
        params = {
            'query': f'gene:{gene_symbol} AND organism_id:9606 AND reviewed:true',
            'format': 'json',
            'size': 1
        }
        
        response = self.session.get(
            f"{self.UNIPROT_BASE_URL}/search",
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('results'):
                return data['results'][0]
        
        return None
    
    def _extract_protein_name(self, entry: Dict) -> str:
        """Extract protein name from UniProt entry."""
        protein = entry.get('proteinDescription', {})
        recommended = protein.get('recommendedName', {})
        if recommended:
            return recommended.get('fullName', {}).get('value', '')
        
        # Fallback to submitted name
        submitted = protein.get('submittedName', [])
        if submitted:
            return submitted[0].get('fullName', {}).get('value', '')
        
        return ''
    
    def _extract_domains(self, entry: Dict) -> List[ProteinDomain]:
        """Extract protein domain annotations."""
        domains = []
        
        # Extract from cross-references
        for xref in entry.get('uniProtKBCrossReferences', []):
            if xref.get('database') in ['Pfam', 'InterPro', 'SMART', 'PROSITE']:
                # Get feature positions if available
                properties = {p['key']: p['value'] for p in xref.get('properties', [])}
                
                domain = ProteinDomain(
                    name=properties.get('EntryName', xref.get('id', '')),
                    database=xref['database'],
                    identifier=xref['id'],
                    start=0,  # Would need additional API call for exact positions
                    end=0,
                    description=properties.get('Description', '')
                )
                domains.append(domain)
        
        # Extract from features
        for feature in entry.get('features', []):
            if feature.get('type') == 'Domain':
                location = feature.get('location', {})
                domain = ProteinDomain(
                    name=feature.get('description', ''),
                    database='UniProt',
                    identifier=feature.get('featureId', ''),
                    start=location.get('start', {}).get('value', 0),
                    end=location.get('end', {}).get('value', 0),
                    description=feature.get('description', '')
                )
                domains.append(domain)
        
        return domains
    
    def _extract_ptms(self, entry: Dict) -> List[PostTranslationalModification]:
        """Extract post-translational modifications."""
        ptms = []
        
        for feature in entry.get('features', []):
            if feature.get('type') in ['Modified residue', 'Glycosylation site', 
                                       'Disulfide bond', 'Cross-link']:
                location = feature.get('location', {})
                position = location.get('start', {}).get('value', 0)
                
                ptm = PostTranslationalModification(
                    type=feature['type'],
                    position=position,
                    residue='',  # Would need sequence to get this
                    description=feature.get('description', ''),
                    evidence=self._get_evidence_string(feature.get('evidences', []))
                )
                ptms.append(ptm)
        
        return ptms
    
    def _extract_variants(self, uniprot_id: str) -> List[ProteinVariant]:
        """Extract protein variants from UniProt variation API."""
        variants = []
        
        try:
            response = self.session.get(
                f"{self.UNIPROT_VARIATION_URL}/{uniprot_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                for feature in data.get('features', []):
                    if feature.get('type') == 'VARIANT':
                        variant = ProteinVariant(
                            position=feature.get('begin', 0),
                            original=feature.get('wildType', ''),
                            variant=feature.get('alternativeSequence', ''),
                            type=feature.get('consequenceType', ''),
                            consequence=feature.get('consequence', ''),
                            clinical_significance=feature.get('clinicalSignificance', ''),
                            disease_association=feature.get('association', [{}])[0].get('name') if feature.get('association') else None,
                            dbsnp_id=feature.get('xrefs', {}).get('dbSNP', [''])[0],
                            frequency=feature.get('frequency')
                        )
                        variants.append(variant)
        
        except Exception as e:
            logger.warning(f"Failed to retrieve variants for {uniprot_id}: {e}")
        
        return variants
    
    def _extract_isoforms(self, entry: Dict) -> List[ProteinIsoform]:
        """Extract protein isoforms."""
        isoforms = []
        
        for comment in entry.get('comments', []):
            if comment.get('commentType') == 'ALTERNATIVE PRODUCTS':
                for isoform_data in comment.get('isoforms', []):
                    isoform = ProteinIsoform(
                        isoform_id=isoform_data.get('isoformIds', [''])[0],
                        name=isoform_data.get('name', {}).get('value', ''),
                        sequence_length=0,  # Would need additional query
                        differences='',  # Would need to parse
                        refseq_ids=[],  # Would need cross-reference lookup
                        note=isoform_data.get('note', {}).get('texts', [{}])[0].get('value') if isoform_data.get('note') else None
                    )
                    isoforms.append(isoform)
        
        return isoforms
    
    def _extract_diseases(self, entry: Dict) -> List[DiseaseAssociation]:
        """Extract disease associations."""
        diseases = []
        
        for comment in entry.get('comments', []):
            if comment.get('commentType') == 'DISEASE':
                disease_data = comment.get('disease', {})
                disease = DiseaseAssociation(
                    disease_name=disease_data.get('name', ''),
                    disease_id=disease_data.get('diseaseId', ''),
                    involvement=comment.get('texts', [{}])[0].get('value', '') if comment.get('texts') else '',
                    evidence=self._get_evidence_string(comment.get('evidences', [])),
                    mutations=[]  # Would need to parse from text
                )
                diseases.append(disease)
        
        return diseases
    
    def _extract_drug_targets(self, entry: Dict) -> List[DrugTarget]:
        """Extract drug target information."""
        drug_targets = []
        
        # Check DrugBank cross-references
        for xref in entry.get('uniProtKBCrossReferences', []):
            if xref.get('database') == 'DrugBank':
                properties = {p['key']: p['value'] for p in xref.get('properties', [])}
                
                drug = DrugTarget(
                    drug_name=properties.get('GenericName', ''),
                    drug_id=xref['id'],
                    mechanism='',  # Would need DrugBank API
                    status=''  # Would need DrugBank API
                )
                drug_targets.append(drug)
        
        return drug_targets
    
    def _extract_pathways(self, entry: Dict) -> List[PathwayInvolvement]:
        """Extract pathway involvement."""
        pathways = []
        
        # Check pathway cross-references
        for xref in entry.get('uniProtKBCrossReferences', []):
            if xref.get('database') in ['KEGG', 'Reactome', 'BioCyc']:
                properties = {p['key']: p['value'] for p in xref.get('properties', [])}
                
                pathway = PathwayInvolvement(
                    pathway_name=properties.get('PathwayName', ''),
                    pathway_id=xref['id'],
                    database=xref['database'],
                    role=None
                )
                pathways.append(pathway)
        
        return pathways
    
    def _extract_expression(self, entry: Dict) -> List[ProteinExpression]:
        """Extract expression data."""
        expression = []
        
        for comment in entry.get('comments', []):
            if comment.get('commentType') == 'TISSUE SPECIFICITY':
                # Parse tissue specificity text
                text = comment.get('texts', [{}])[0].get('value', '') if comment.get('texts') else ''
                # This would need more sophisticated parsing
                expression.append(ProteinExpression(
                    tissue='Various',  # Would need to parse
                    level='Unknown',
                    cell_type=None,
                    evidence=text
                ))
        
        return expression
    
    def _extract_function(self, entry: Dict) -> Optional[str]:
        """Extract protein function description."""
        for comment in entry.get('comments', []):
            if comment.get('commentType') == 'FUNCTION':
                texts = comment.get('texts', [])
                if texts:
                    return texts[0].get('value', '')
        return None
    
    def _extract_subcellular_location(self, entry: Dict) -> Optional[List[str]]:
        """Extract subcellular location."""
        locations = []
        
        for comment in entry.get('comments', []):
            if comment.get('commentType') == 'SUBCELLULAR LOCATION':
                for location in comment.get('subcellularLocations', []):
                    loc = location.get('location', {}).get('value', '')
                    if loc:
                        locations.append(loc)
        
        return locations if locations else None
    
    def _extract_protein_families(self, entry: Dict) -> Optional[List[str]]:
        """Extract protein family information."""
        families = []
        
        for comment in entry.get('comments', []):
            if comment.get('commentType') == 'SIMILARITY':
                text = comment.get('texts', [{}])[0].get('value', '') if comment.get('texts') else ''
                if text:
                    families.append(text)
        
        return families if families else None
    
    def _extract_go_terms(self, entry: Dict) -> Optional[Dict[str, List[str]]]:
        """Extract GO term annotations."""
        go_terms = {
            'biological_process': [],
            'molecular_function': [],
            'cellular_component': []
        }
        
        for xref in entry.get('uniProtKBCrossReferences', []):
            if xref.get('database') == 'GO':
                properties = {p['key']: p['value'] for p in xref.get('properties', [])}
                term = properties.get('GoTerm', '')
                
                if term.startswith('P:'):
                    go_terms['biological_process'].append(term[2:])
                elif term.startswith('F:'):
                    go_terms['molecular_function'].append(term[2:])
                elif term.startswith('C:'):
                    go_terms['cellular_component'].append(term[2:])
        
        # Only return if we have terms
        if any(go_terms.values()):
            return go_terms
        return None
    
    def _get_evidence_string(self, evidences: List[Dict]) -> str:
        """Format evidence information."""
        evidence_codes = []
        for evidence in evidences:
            code = evidence.get('evidenceCode', '')
            if code:
                evidence_codes.append(code)
        return ', '.join(evidence_codes) if evidence_codes else ''
    
    def analyze_isoforms(self, gene_symbol: str) -> Dict[str, Any]:
        """
        Analyze all isoforms for a gene and compare differences.
        
        Args:
            gene_symbol: Gene symbol to analyze
            
        Returns:
            Dictionary with isoform comparison data
        """
        features = self.get_protein_features(gene_symbol)
        if not features:
            return {}
        
        analysis = {
            'gene': gene_symbol,
            'canonical_id': features.uniprot_id,
            'total_isoforms': len(features.isoforms),
            'isoforms': []
        }
        
        for isoform in features.isoforms:
            isoform_data = {
                'id': isoform.isoform_id,
                'name': isoform.name,
                'differences': isoform.differences,
                'refseq_mapping': isoform.refseq_ids
            }
            analysis['isoforms'].append(isoform_data)
        
        return analysis
    
    def get_clinical_data(self, gene_symbol: str) -> Dict[str, Any]:
        """
        Retrieve clinical significance data for a gene.
        
        Args:
            gene_symbol: Gene symbol to query
            
        Returns:
            Dictionary with clinical data
        """
        features = self.get_protein_features(gene_symbol)
        if not features:
            return {}
        
        clinical_data = {
            'gene': gene_symbol,
            'diseases': [asdict(d) for d in features.diseases],
            'drug_targets': [asdict(d) for d in features.drug_targets],
            'pathogenic_variants': [],
            'benign_variants': []
        }
        
        # Classify variants by clinical significance
        for variant in features.variants:
            if variant.clinical_significance:
                if 'pathogenic' in variant.clinical_significance.lower():
                    clinical_data['pathogenic_variants'].append(asdict(variant))
                elif 'benign' in variant.clinical_significance.lower():
                    clinical_data['benign_variants'].append(asdict(variant))
        
        return clinical_data