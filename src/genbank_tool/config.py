"""Configuration management for the GenBank tool."""

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class CacheConfig:
    """Cache configuration settings."""
    enabled: bool = True
    directory: str = ".genbank_cache"
    gene_expiry_days: int = 30
    sequence_expiry_days: int = 7
    max_size_mb: int = 500


@dataclass
class APIConfig:
    """API configuration settings."""
    ncbi_api_key: Optional[str] = None
    email: str = "user@example.com"
    retry_attempts: int = 3
    timeout_seconds: int = 30
    rate_limit_per_second: float = 3.0  # NCBI default without API key


@dataclass
class SelectionConfig:
    """Transcript selection configuration."""
    canonical_only: bool = True
    prefer_refseq_select: bool = True
    prefer_longest_cds: bool = True
    enable_uniprot: bool = True


@dataclass
class ValidationConfig:
    """Validation configuration settings."""
    enabled: bool = False
    strict_mode: bool = False
    cross_reference: bool = True


@dataclass
class OutputConfig:
    """Output configuration settings."""
    format: str = "tsv"
    include_audit_trail: bool = True
    excel_compatible: bool = True


@dataclass
class Config:
    """Main configuration container."""
    cache: CacheConfig
    api: APIConfig
    selection: SelectionConfig
    validation: ValidationConfig
    output: OutputConfig
    
    @classmethod
    def default(cls) -> 'Config':
        """Create default configuration."""
        return cls(
            cache=CacheConfig(),
            api=APIConfig(),
            selection=SelectionConfig(),
            validation=ValidationConfig(),
            output=OutputConfig()
        )
    
    @classmethod
    def from_file(cls, path: Path) -> 'Config':
        """Load configuration from JSON file."""
        if not path.exists():
            return cls.default()
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        return cls(
            cache=CacheConfig(**data.get('cache', {})),
            api=APIConfig(**data.get('api', {})),
            selection=SelectionConfig(**data.get('selection', {})),
            validation=ValidationConfig(**data.get('validation', {})),
            output=OutputConfig(**data.get('output', {}))
        )
    
    def to_file(self, path: Path) -> None:
        """Save configuration to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'cache': asdict(self.cache),
            'api': asdict(self.api),
            'selection': asdict(self.selection),
            'validation': asdict(self.validation),
            'output': asdict(self.output)
        }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def merge_env_vars(self) -> None:
        """Merge environment variables into configuration."""
        # API settings from environment
        if os.getenv('NCBI_API_KEY'):
            self.api.ncbi_api_key = os.getenv('NCBI_API_KEY')
        if os.getenv('EMAIL'):
            self.api.email = os.getenv('EMAIL')
        
        # Cache settings
        if os.getenv('GENBANK_CACHE_DIR'):
            self.cache.directory = os.getenv('GENBANK_CACHE_DIR')
        if os.getenv('GENBANK_NO_CACHE'):
            self.cache.enabled = False
        
        # Rate limiting
        if os.getenv('NCBI_RATE_LIMIT'):
            self.api.rate_limit_per_second = float(os.getenv('NCBI_RATE_LIMIT'))
    
    def merge_cli_args(self, **kwargs) -> None:
        """Merge CLI arguments into configuration."""
        # API settings
        if kwargs.get('api_key'):
            self.api.ncbi_api_key = kwargs['api_key']
        if kwargs.get('email'):
            self.api.email = kwargs['email']
        
        # Cache settings
        if kwargs.get('no_cache'):
            self.cache.enabled = False
        
        # Selection settings
        if 'canonical' in kwargs:
            self.selection.canonical_only = kwargs['canonical']
        
        # Validation settings
        if kwargs.get('validate'):
            self.validation.enabled = True
        if kwargs.get('strict_validation'):
            self.validation.strict_mode = True
        
        # Output settings
        if kwargs.get('output_format'):
            self.output.format = kwargs['output_format']
        if kwargs.get('no_audit'):
            self.output.include_audit_trail = False


def get_default_config_path() -> Path:
    """Get the default configuration file path."""
    # Check common locations
    locations = [
        Path.home() / '.genbank' / 'config.json',
        Path.home() / '.config' / 'genbank' / 'config.json',
        Path('.genbank.json'),
        Path('genbank.config.json')
    ]
    
    # Return first existing file
    for path in locations:
        if path.exists():
            return path
    
    # Default to user home directory
    return Path.home() / '.genbank' / 'config.json'


def create_example_config(path: Optional[Path] = None) -> Path:
    """Create an example configuration file."""
    if path is None:
        path = Path('genbank.config.example.json')
    
    config = Config.default()
    
    # Add some example values
    config.api.ncbi_api_key = "your_api_key_here"
    config.api.email = "your_email@example.com"
    config.cache.directory = ".genbank_cache"
    config.selection.canonical_only = True
    config.validation.enabled = False
    
    config.to_file(path)
    return path