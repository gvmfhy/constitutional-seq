"""HGNC (HUGO Gene Nomenclature Committee) resolver for authoritative gene naming.

HGNC is the authoritative source for human gene symbols and names.
This resolver handles aliases, previous symbols, and case-insensitive queries.
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import json

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class HGNCGene:
    """Represents an HGNC gene record."""
    
    hgnc_id: str              # HGNC:1234
    symbol: str               # Official symbol (e.g., TP53)
    name: str                 # Full name
    entrez_id: Optional[str]  # NCBI Gene ID
    ensembl_id: Optional[str] # Ensembl Gene ID
    
    # Aliases and previous symbols
    aliases: List[str]        # Alternative symbols
    previous_symbols: List[str] # Historically used symbols
    
    # Additional metadata
    locus_group: Optional[str] = None  # protein-coding gene, non-coding RNA, etc.
    location: Optional[str] = None     # Chromosomal location
    
    @property
    def all_symbols(self) -> List[str]:
        """Get all possible symbols for this gene."""
        symbols = [self.symbol]
        symbols.extend(self.aliases)
        symbols.extend(self.previous_symbols)
        return list(set(symbols))


class HGNCResolver:
    """Resolves gene names using HGNC REST API."""
    
    BASE_URL = "https://rest.genenames.org"
    CACHE_DIR = Path("cache/hgnc_resolution")
    CACHE_EXPIRY = 30 * 24 * 3600  # 30 days
    
    def __init__(self, cache_enabled: bool = True):
        """Initialize HGNC resolver.
        
        Args:
            cache_enabled: Whether to cache HGNC results
        """
        self.cache_enabled = cache_enabled
        
        if cache_enabled:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Setup session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'NCBI-GenBank-Tool/1.0'
        })
    
    def resolve(self, query: str) -> Optional[HGNCGene]:
        """Resolve any gene query to official HGNC record.
        
        Tries in order:
        1. Exact symbol match
        2. Alias match
        3. Previous symbol match
        4. General search
        
        Args:
            query: Gene name, symbol, or alias (case-insensitive)
            
        Returns:
            HGNCGene object or None if not found
        """
        # Normalize query (HGNC is case-insensitive)
        query = query.strip()
        
        # Check cache first
        cached = self._load_from_cache(query)
        if cached:
            return cached
        
        # Try exact symbol match first (fastest)
        gene = self._fetch_by_symbol(query)
        if gene:
            logger.info(f"HGNC resolved '{query}' as symbol → {gene.symbol}")
            self._save_to_cache(query, gene)
            return gene
        
        # Try alias match
        gene = self._fetch_by_alias(query)
        if gene:
            logger.info(f"HGNC resolved '{query}' as alias → {gene.symbol}")
            self._save_to_cache(query, gene)
            return gene
        
        # Try previous symbol match
        gene = self._fetch_by_previous_symbol(query)
        if gene:
            logger.info(f"HGNC resolved '{query}' as previous symbol → {gene.symbol}")
            self._save_to_cache(query, gene)
            return gene
        
        # Last resort: general search
        gene = self._search_general(query)
        if gene:
            logger.info(f"HGNC resolved '{query}' via search → {gene.symbol}")
            self._save_to_cache(query, gene)
            return gene
        
        logger.warning(f"HGNC could not resolve '{query}'")
        return None
    
    def _fetch_by_symbol(self, symbol: str) -> Optional[HGNCGene]:
        """Fetch gene by exact symbol match."""
        try:
            url = f"{self.BASE_URL}/fetch/symbol/{symbol}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data['response']['numFound'] > 0:
                return self._parse_gene(data['response']['docs'][0])
            
        except Exception as e:
            logger.error(f"Failed to fetch by symbol '{symbol}': {e}")
        
        return None
    
    def _fetch_by_alias(self, alias: str) -> Optional[HGNCGene]:
        """Fetch gene by alias symbol."""
        try:
            url = f"{self.BASE_URL}/fetch/alias_symbol/{alias}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data['response']['numFound'] > 0:
                return self._parse_gene(data['response']['docs'][0])
            
        except Exception as e:
            logger.error(f"Failed to fetch by alias '{alias}': {e}")
        
        return None
    
    def _fetch_by_previous_symbol(self, prev_symbol: str) -> Optional[HGNCGene]:
        """Fetch gene by previous symbol."""
        try:
            url = f"{self.BASE_URL}/fetch/prev_symbol/{prev_symbol}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data['response']['numFound'] > 0:
                return self._parse_gene(data['response']['docs'][0])
            
        except Exception as e:
            logger.error(f"Failed to fetch by previous symbol '{prev_symbol}': {e}")
        
        return None
    
    def _search_general(self, query: str) -> Optional[HGNCGene]:
        """General search as last resort."""
        try:
            # Search with some intelligence about what might match
            url = f"{self.BASE_URL}/search/{query}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if data['response']['numFound'] > 0:
                # Try to find best match
                docs = data['response']['docs']
                
                # Prefer exact matches in symbol or aliases
                query_upper = query.upper()
                for doc in docs:
                    if doc.get('symbol', '').upper() == query_upper:
                        return self._parse_gene(doc)
                    
                    aliases = doc.get('alias_symbol', [])
                    if any(a.upper() == query_upper for a in aliases):
                        return self._parse_gene(doc)
                
                # Otherwise take first result with caution
                logger.warning(f"HGNC search returned {len(docs)} results for '{query}', using first")
                return self._parse_gene(docs[0])
            
        except Exception as e:
            logger.error(f"Failed general search for '{query}': {e}")
        
        return None
    
    def _parse_gene(self, doc: Dict) -> HGNCGene:
        """Parse HGNC API response into HGNCGene object."""
        return HGNCGene(
            hgnc_id=doc.get('hgnc_id', ''),
            symbol=doc.get('symbol', ''),
            name=doc.get('name', ''),
            entrez_id=doc.get('entrez_id'),
            ensembl_id=doc.get('ensembl_gene_id'),
            aliases=doc.get('alias_symbol', []),
            previous_symbols=doc.get('prev_symbol', []),
            locus_group=doc.get('locus_group'),
            location=doc.get('location')
        )
    
    def _load_from_cache(self, query: str) -> Optional[HGNCGene]:
        """Load from cache if available."""
        if not self.cache_enabled:
            return None
        
        cache_file = self.CACHE_DIR / f"{query.lower().replace(' ', '_')}.json"
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                
                # Check expiry
                if time.time() - data['timestamp'] < self.CACHE_EXPIRY:
                    gene_data = data['gene']
                    return HGNCGene(
                        hgnc_id=gene_data['hgnc_id'],
                        symbol=gene_data['symbol'],
                        name=gene_data['name'],
                        entrez_id=gene_data.get('entrez_id'),
                        ensembl_id=gene_data.get('ensembl_id'),
                        aliases=gene_data.get('aliases', []),
                        previous_symbols=gene_data.get('previous_symbols', []),
                        locus_group=gene_data.get('locus_group'),
                        location=gene_data.get('location')
                    )
            except Exception as e:
                logger.warning(f"Failed to load cache for '{query}': {e}")
        
        return None
    
    def _save_to_cache(self, query: str, gene: HGNCGene) -> None:
        """Save to cache."""
        if not self.cache_enabled or not gene:
            return
        
        cache_file = self.CACHE_DIR / f"{query.lower().replace(' ', '_')}.json"
        
        try:
            with open(cache_file, 'w') as f:
                json.dump({
                    'timestamp': time.time(),
                    'query': query,
                    'gene': {
                        'hgnc_id': gene.hgnc_id,
                        'symbol': gene.symbol,
                        'name': gene.name,
                        'entrez_id': gene.entrez_id,
                        'ensembl_id': gene.ensembl_id,
                        'aliases': gene.aliases,
                        'previous_symbols': gene.previous_symbols,
                        'locus_group': gene.locus_group,
                        'location': gene.location
                    }
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache for '{query}': {e}")