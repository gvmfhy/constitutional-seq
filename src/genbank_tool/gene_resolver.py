"""Gene name resolution module for NCBI GenBank tool."""

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class ResolvedGene:
    """Represents a resolved gene with its official information."""
    
    input_name: str
    official_symbol: str
    gene_id: str
    description: str
    aliases: List[str]
    confidence: float
    disambiguation_reason: Optional[str] = None
    source: str = "NCBI"  # NCBI, UniProt, or Combined


class GeneResolver:
    """Resolves gene names to official symbols using NCBI Gene and UniProt databases."""
    
    NCBI_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    UNIPROT_BASE_URL = "https://rest.uniprot.org/uniprotkb/search"
    RATE_LIMIT = 3  # requests per second for non-API key users
    UNIPROT_RATE_LIMIT = 10  # UniProt allows 10 requests per second
    CACHE_DIR = Path("cache/gene_resolution")
    CONFIDENCE_THRESHOLD = 0.8  # Threshold for triggering UniProt fallback (increased for better accuracy)
    
    def __init__(self, api_key: Optional[str] = None, cache_enabled: bool = True):
        """Initialize the gene resolver.
        
        Args:
            api_key: Optional NCBI API key for increased rate limits
            cache_enabled: Whether to use local caching
        """
        self.api_key = api_key
        self.cache_enabled = cache_enabled
        
        if self.cache_enabled:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Setup session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        
        # Rate limiting
        self.last_request_time = 0
        self.last_uniprot_request_time = 0
        self.rate_limit = 10 if api_key else self.RATE_LIMIT
        
    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        min_interval = 1.0 / self.rate_limit
        
        if time_since_last < min_interval:
            time.sleep(min_interval - time_since_last)
        
        self.last_request_time = time.time()
    
    def _normalize_gene_name(self, name: str) -> str:
        """Normalize gene name for searching.
        
        Args:
            name: Raw gene name input
            
        Returns:
            Normalized gene name
        """
        # Remove extra whitespace
        normalized = ' '.join(name.strip().split())
        
        # Common formatting issues
        normalized = normalized.replace('_', '')
        normalized = normalized.replace('-', '')
        
        # Handle common variations (but preserve original for search)
        # We'll search with both original and normalized
        return normalized
    
    def _get_cache_path(self, query: str) -> Path:
        """Get cache file path for a query."""
        safe_query = re.sub(r'[^\w\-_]', '_', query.lower())
        return self.CACHE_DIR / f"{safe_query}.json"
    
    def _load_from_cache(self, query: str) -> Optional[Dict]:
        """Load results from cache if available."""
        if not self.cache_enabled:
            return None
            
        cache_path = self._get_cache_path(query)
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    data = json.load(f)
                # Check if cache is less than 30 days old
                if time.time() - data['timestamp'] < 30 * 24 * 3600:
                    logger.debug(f"Cache hit for query: {query}")
                    return data['result']
            except Exception as e:
                logger.warning(f"Failed to load cache for {query}: {e}")
        
        return None
    
    def _save_to_cache(self, query: str, result: Dict) -> None:
        """Save results to cache."""
        if not self.cache_enabled:
            return
            
        cache_path = self._get_cache_path(query)
        try:
            with open(cache_path, 'w') as f:
                json.dump({
                    'timestamp': time.time(),
                    'query': query,
                    'result': result
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache for {query}: {e}")
    
    def _search_gene(self, query: str) -> List[Dict]:
        """Search for genes matching the query.
        
        Args:
            query: Gene name or alias to search
            
        Returns:
            List of matching gene records
        """
        # Check cache first
        cached = self._load_from_cache(query)
        if cached is not None:
            return cached
        
        # Build search URL
        params = {
            'db': 'gene',
            'term': f'"{query}"[Gene Name] OR "{query}"[All Fields] AND human[organism]',
            'retmode': 'json',
            'retmax': 20
        }
        
        if self.api_key:
            params['api_key'] = self.api_key
        
        # Make request with rate limiting
        self._rate_limit()
        
        try:
            response = self.session.get(
                f"{self.NCBI_BASE_URL}/esearch.fcgi",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            search_results = response.json()
            
            if 'esearchresult' not in search_results:
                logger.error(f"Invalid search response for {query}")
                return []
            
            gene_ids = search_results['esearchresult'].get('idlist', [])
            
            if not gene_ids:
                logger.info(f"No genes found for query: {query}")
                return []
            
            # Fetch gene details
            genes = self._fetch_gene_details(gene_ids)
            
            # Cache the results
            self._save_to_cache(query, genes)
            
            return genes
            
        except requests.RequestException as e:
            logger.error(f"Failed to search for gene {query}: {e}")
            return []
    
    def _fetch_gene_details(self, gene_ids: List[str]) -> List[Dict]:
        """Fetch detailed information for gene IDs.
        
        Args:
            gene_ids: List of NCBI gene IDs
            
        Returns:
            List of gene detail dictionaries
        """
        if not gene_ids:
            return []
        
        params = {
            'db': 'gene',
            'id': ','.join(gene_ids),
            'retmode': 'json'
        }
        
        if self.api_key:
            params['api_key'] = self.api_key
        
        self._rate_limit()
        
        try:
            response = self.session.get(
                f"{self.NCBI_BASE_URL}/esummary.fcgi",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            summary_data = response.json()
            
            if 'result' not in summary_data:
                logger.error("Invalid summary response")
                return []
            
            genes = []
            for gene_id in gene_ids:
                if gene_id in summary_data['result']:
                    genes.append(summary_data['result'][gene_id])
            
            return genes
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch gene details: {e}")
            return []
    
    def _search_uniprot(self, query: str) -> List[Dict]:
        """Search for genes in UniProt database.
        
        Args:
            query: Gene name or symbol to search
            
        Returns:
            List of matching UniProt entries
        """
        # Check cache first
        cache_key = f"uniprot_{query}"
        cached = self._load_from_cache(cache_key)
        if cached is not None:
            return cached
        
        # Build UniProt search query
        params = {
            'query': f'(gene:{query} OR gene_exact:{query}) AND organism_id:9606 AND reviewed:true',
            'format': 'json',
            'size': 10,
            'fields': 'accession,gene_names,organism_name,protein_name,xref_geneid'
        }
        
        # Rate limit for UniProt
        current_time = time.time()
        time_since_last = current_time - self.last_uniprot_request_time
        min_interval = 1.0 / self.UNIPROT_RATE_LIMIT
        
        if time_since_last < min_interval:
            time.sleep(min_interval - time_since_last)
        
        self.last_uniprot_request_time = time.time()
        
        try:
            response = self.session.get(
                self.UNIPROT_BASE_URL,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            logger.info(f"Found {len(results)} UniProt entries for query: {query}")
            
            # Cache the results
            self._save_to_cache(cache_key, results)
            
            return results
            
        except requests.RequestException as e:
            logger.error(f"Failed to search UniProt for {query}: {e}")
            return []
    
    def _extract_gene_id_from_uniprot(self, uniprot_entry: Dict) -> Optional[str]:
        """Extract NCBI Gene ID from UniProt cross-references.
        
        Args:
            uniprot_entry: UniProt entry dictionary
            
        Returns:
            NCBI Gene ID or None
        """
        cross_refs = uniprot_entry.get('uniProtKBCrossReferences', [])
        
        for ref in cross_refs:
            if ref.get('database') == 'GeneID':
                return ref.get('id')
        
        return None
    
    def _parse_uniprot_gene_names(self, uniprot_entry: Dict) -> Tuple[str, List[str]]:
        """Parse gene names from UniProt entry.
        
        Args:
            uniprot_entry: UniProt entry dictionary
            
        Returns:
            Tuple of (primary gene name, list of aliases)
        """
        genes = uniprot_entry.get('genes', [])
        
        if not genes:
            return "", []
        
        gene_info = genes[0]  # Primary gene
        primary_name = gene_info.get('geneName', {}).get('value', '')
        
        aliases = []
        # Add synonyms
        for synonym in gene_info.get('synonyms', []):
            aliases.append(synonym.get('value', ''))
        
        return primary_name, aliases
    
    def _calculate_uniprot_confidence(self, query: str, uniprot_entry: Dict) -> float:
        """Calculate confidence score for UniProt match.
        
        Args:
            query: Original search query
            uniprot_entry: UniProt entry
            
        Returns:
            Confidence score between 0 and 1
        """
        query_lower = query.lower()
        primary_name, aliases = self._parse_uniprot_gene_names(uniprot_entry)
        
        # Exact match on primary name
        if primary_name.lower() == query_lower:
            return 0.95  # Slightly lower than NCBI exact match
        
        # Exact match on alias
        if query_lower in [a.lower() for a in aliases]:
            return 0.85
        
        # Partial match
        if query_lower in primary_name.lower():
            return 0.7
        
        return 0.5
    
    def _calculate_confidence(self, query: str, gene: Dict) -> float:
        """Calculate confidence score for a gene match.
        
        Args:
            query: Original search query
            gene: Gene information dictionary
            
        Returns:
            Confidence score between 0 and 1
        """
        query_lower = query.lower()
        
        # Exact match on official symbol
        if gene.get('name', '').lower() == query_lower:
            return 1.0
        
        # Check aliases
        other_aliases = gene.get('otheraliases', '').lower().split(', ')
        if query_lower in other_aliases:
            return 0.9
        
        # Check description
        if query_lower in gene.get('description', '').lower():
            return 0.7
        
        # Partial match
        if query_lower in gene.get('name', '').lower():
            return 0.6
        
        return 0.5
    
    def resolve(self, gene_name: str) -> Optional[ResolvedGene]:
        """Resolve a single gene name to its official symbol.
        
        Uses NCBI Gene as primary source, falls back to UniProt if needed.
        
        Args:
            gene_name: Gene name to resolve
            
        Returns:
            ResolvedGene object or None if not found
        """
        logger.info(f"Resolving gene: {gene_name}")
        
        # First try NCBI
        ncbi_result = self._resolve_via_ncbi(gene_name)
        
        # If NCBI gives high confidence result, use it (threshold: 0.8)
        if ncbi_result and ncbi_result.confidence >= self.CONFIDENCE_THRESHOLD:
            logger.info(f"NCBI resolved {gene_name} -> {ncbi_result.official_symbol} with high confidence ({ncbi_result.confidence})")
            return ncbi_result
        
        # Otherwise, try UniProt
        logger.info(f"NCBI confidence too low ({ncbi_result.confidence if ncbi_result else 0}), trying UniProt")
        uniprot_result = self._resolve_via_uniprot(gene_name)
        
        # If we have both results, merge them
        if ncbi_result and uniprot_result:
            # Prefer UniProt if it has higher confidence
            if uniprot_result.confidence > ncbi_result.confidence:
                logger.info(f"Using UniProt result: {uniprot_result.official_symbol}")
                return uniprot_result
            else:
                # Keep NCBI but note the UniProt alternative
                ncbi_result.disambiguation_reason = f"UniProt suggests {uniprot_result.official_symbol}"
                return ncbi_result
        
        # Return whichever result we have
        return uniprot_result or ncbi_result
    
    def _resolve_via_ncbi(self, gene_name: str) -> Optional[ResolvedGene]:
        """Resolve gene name using NCBI Gene database.
        
        Args:
            gene_name: Gene name to resolve
            
        Returns:
            ResolvedGene object or None if not found
        """
        # Normalize the input
        normalized = self._normalize_gene_name(gene_name)
        
        # Search with both original and normalized
        candidates = []
        
        for query in [gene_name, normalized]:
            if query:  # Skip empty queries
                try:
                    results = self._search_gene(query)
                    candidates.extend(results)
                except Exception as e:
                    logger.error(f"NCBI search failed for {query}: {e}")
                    continue
        
        if not candidates:
            logger.warning(f"No NCBI candidates found for: {gene_name}")
            return None
        
        # Remove duplicates by gene ID
        seen_ids = set()
        unique_candidates = []
        for gene in candidates:
            if gene.get('uid') not in seen_ids:
                seen_ids.add(gene.get('uid'))
                unique_candidates.append(gene)
        
        # Score and sort candidates
        scored_candidates = []
        for gene in unique_candidates:
            confidence = self._calculate_confidence(gene_name, gene)
            scored_candidates.append((confidence, gene))
        
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        # Take the best match
        best_confidence, best_gene = scored_candidates[0]
        
        # Build resolved gene object
        aliases = best_gene.get('otheraliases', '').split(', ') if best_gene.get('otheraliases') else []
        
        disambiguation_reason = None
        if len(scored_candidates) > 1 and scored_candidates[1][0] > 0.7:
            # Close match - note the disambiguation
            disambiguation_reason = f"Selected over {scored_candidates[1][1].get('name')} based on confidence score"
        
        resolved = ResolvedGene(
            input_name=gene_name,
            official_symbol=best_gene.get('name', ''),
            gene_id=str(best_gene.get('uid', '')),
            description=best_gene.get('description', ''),
            aliases=aliases,
            confidence=best_confidence,
            disambiguation_reason=disambiguation_reason,
            source="NCBI"
        )
        
        return resolved
    
    def _resolve_via_uniprot(self, gene_name: str) -> Optional[ResolvedGene]:
        """Resolve gene name using UniProt database.
        
        Args:
            gene_name: Gene name to resolve
            
        Returns:
            ResolvedGene object or None if not found
        """
        try:
            # Search UniProt
            uniprot_results = self._search_uniprot(gene_name)
            
            if not uniprot_results:
                logger.warning(f"No UniProt results for: {gene_name}")
                return None
        except Exception as e:
            logger.error(f"UniProt search failed for {gene_name}: {e}")
            return None
        
        # Score and sort candidates
        scored_candidates = []
        for entry in uniprot_results:
            confidence = self._calculate_uniprot_confidence(gene_name, entry)
            gene_id = self._extract_gene_id_from_uniprot(entry)
            
            # Only consider entries with NCBI Gene ID
            if gene_id:
                scored_candidates.append((confidence, entry, gene_id))
        
        if not scored_candidates:
            logger.warning(f"No UniProt entries with NCBI Gene ID for: {gene_name}")
            return None
        
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        # Take the best match
        best_confidence, best_entry, gene_id = scored_candidates[0]
        primary_name, aliases = self._parse_uniprot_gene_names(best_entry)
        
        # Get protein description
        protein_desc = best_entry.get('proteinDescription', {})
        recommended_name = protein_desc.get('recommendedName', {})
        full_name = recommended_name.get('fullName', {}).get('value', '')
        
        disambiguation_reason = None
        if len(scored_candidates) > 1 and scored_candidates[1][0] > 0.7:
            other_name, _ = self._parse_uniprot_gene_names(scored_candidates[1][1])
            disambiguation_reason = f"Selected over {other_name} based on confidence score"
        
        resolved = ResolvedGene(
            input_name=gene_name,
            official_symbol=primary_name,
            gene_id=gene_id,
            description=full_name or f"UniProt: {best_entry.get('primaryAccession', '')}",
            aliases=aliases,
            confidence=best_confidence,
            disambiguation_reason=disambiguation_reason,
            source="UniProt"
        )
        
        logger.info(f"UniProt resolved {gene_name} -> {resolved.official_symbol} (Gene ID: {gene_id})")
        
        return resolved
    
    def resolve_batch(self, gene_names: List[str]) -> Dict[str, Optional[ResolvedGene]]:
        """Resolve multiple gene names.
        
        Args:
            gene_names: List of gene names to resolve
            
        Returns:
            Dictionary mapping input names to resolved genes
        """
        results = {}
        
        for i, gene_name in enumerate(gene_names):
            logger.info(f"Processing gene {i+1}/{len(gene_names)}: {gene_name}")
            
            try:
                resolved = self.resolve(gene_name)
                results[gene_name] = resolved
            except Exception as e:
                logger.error(f"Failed to resolve {gene_name}: {e}")
                results[gene_name] = None
        
        return results