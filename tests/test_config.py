"""Tests for configuration management."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from genbank_tool.config import (
    Config, CacheConfig, APIConfig, SelectionConfig,
    ValidationConfig, OutputConfig, get_default_config_path,
    create_example_config
)


class TestConfig:
    """Test cases for configuration management."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_default_config(self):
        """Test default configuration creation."""
        config = Config.default()
        
        assert config.cache.enabled is True
        assert config.cache.directory == ".genbank_cache"
        assert config.cache.gene_expiry_days == 30
        assert config.cache.sequence_expiry_days == 7
        
        assert config.api.email == "user@example.com"
        assert config.api.retry_attempts == 3
        assert config.api.timeout_seconds == 30
        
        assert config.selection.canonical_only is True
        assert config.selection.prefer_refseq_select is True
        
        assert config.validation.enabled is False
        assert config.validation.strict_mode is False
        
        assert config.output.format == "tsv"
        assert config.output.include_audit_trail is True
    
    def test_config_to_file(self, temp_dir):
        """Test saving configuration to file."""
        config = Config.default()
        config_file = temp_dir / "config.json"
        
        config.to_file(config_file)
        
        assert config_file.exists()
        
        with open(config_file) as f:
            data = json.load(f)
        
        assert data['cache']['enabled'] is True
        assert data['api']['email'] == "user@example.com"
        assert data['selection']['canonical_only'] is True
    
    def test_config_from_file(self, temp_dir):
        """Test loading configuration from file."""
        config_data = {
            'cache': {'enabled': False, 'directory': 'custom_cache'},
            'api': {'email': 'test@example.com', 'retry_attempts': 5},
            'selection': {'canonical_only': False},
            'validation': {'enabled': True},
            'output': {'format': 'json'}
        }
        
        config_file = temp_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        config = Config.from_file(config_file)
        
        assert config.cache.enabled is False
        assert config.cache.directory == 'custom_cache'
        assert config.api.email == 'test@example.com'
        assert config.api.retry_attempts == 5
        assert config.selection.canonical_only is False
        assert config.validation.enabled is True
        assert config.output.format == 'json'
    
    def test_config_from_nonexistent_file(self):
        """Test loading from nonexistent file returns defaults."""
        config = Config.from_file(Path('nonexistent.json'))
        default = Config.default()
        
        assert config.cache.enabled == default.cache.enabled
        assert config.api.email == default.api.email
    
    def test_merge_env_vars(self):
        """Test merging environment variables."""
        config = Config.default()
        
        # Set environment variables
        os.environ['NCBI_API_KEY'] = 'test_key_123'
        os.environ['EMAIL'] = 'env@example.com'
        os.environ['GENBANK_CACHE_DIR'] = '/tmp/cache'
        os.environ['GENBANK_NO_CACHE'] = '1'
        os.environ['NCBI_RATE_LIMIT'] = '10.5'
        
        try:
            config.merge_env_vars()
            
            assert config.api.ncbi_api_key == 'test_key_123'
            assert config.api.email == 'env@example.com'
            assert config.cache.directory == '/tmp/cache'
            assert config.cache.enabled is False
            assert config.api.rate_limit_per_second == 10.5
        finally:
            # Clean up
            for key in ['NCBI_API_KEY', 'EMAIL', 'GENBANK_CACHE_DIR', 
                       'GENBANK_NO_CACHE', 'NCBI_RATE_LIMIT']:
                os.environ.pop(key, None)
    
    def test_merge_cli_args(self):
        """Test merging CLI arguments."""
        config = Config.default()
        
        config.merge_cli_args(
            api_key='cli_key',
            email='cli@example.com',
            no_cache=True,
            canonical=False,
            validate=True,
            strict_validation=True,
            output_format='json',
            no_audit=True
        )
        
        assert config.api.ncbi_api_key == 'cli_key'
        assert config.api.email == 'cli@example.com'
        assert config.cache.enabled is False
        assert config.selection.canonical_only is False
        assert config.validation.enabled is True
        assert config.validation.strict_mode is True
        assert config.output.format == 'json'
        assert config.output.include_audit_trail is False
    
    def test_create_example_config(self, temp_dir):
        """Test creating example configuration."""
        config_file = temp_dir / "example.json"
        result_path = create_example_config(config_file)
        
        assert result_path == config_file
        assert config_file.exists()
        
        with open(config_file) as f:
            data = json.load(f)
        
        assert data['api']['ncbi_api_key'] == "your_api_key_here"
        assert data['api']['email'] == "your_email@example.com"
    
    def test_get_default_config_path(self, monkeypatch):
        """Test getting default config path."""
        # Mock Path.exists to return False for all paths
        monkeypatch.setattr(Path, 'exists', lambda self: False)
        
        path = get_default_config_path()
        expected = Path.home() / '.genbank' / 'config.json'
        
        assert path == expected