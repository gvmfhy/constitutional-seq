"""Comprehensive tests for CLI with error handling."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from click.testing import CliRunner

from genbank_tool.cli_with_error_handling import main
from genbank_tool.models import RetrievedSequence
from genbank_tool.error_handler import ErrorContext, ErrorType


class TestCLIWithErrorHandling:
    """Test cases for CLI with comprehensive error handling."""
    
    @pytest.fixture
    def runner(self):
        """Create a Click test runner."""
        return CliRunner()
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def mock_sequence(self):
        """Create a mock sequence for testing."""
        return RetrievedSequence(
            gene_symbol="TP53",
            gene_id="7157",
            accession="NM_000546",
            version="6",
            description="Tumor protein p53",
            cds_sequence="ATGGAGGAGCCGCAGTCA",
            cds_length=18,
            protein_id="NP_000537.3",
            genbank_url="https://www.ncbi.nlm.nih.gov/nuccore/NM_000546.6",
            refseq_select=True
        )
    
    def test_help_command(self, runner):
        """Test help command displays correctly."""
        result = runner.invoke(main, ['--help'])
        assert result.exit_code == 0
        assert "NCBI GenBank CDS Retrieval Tool" in result.output
        assert "--api-key" in result.output
        assert "--parallel" in result.output
    
    def test_test_genes_command(self, runner, temp_dir):
        """Test processing with test genes."""
        output_file = temp_dir / "test_output.tsv"
        
        with patch('genbank_tool.cli_with_error_handling.GeneResolver') as mock_resolver, \
             patch('genbank_tool.cli_with_error_handling.SequenceRetriever') as mock_retriever, \
             patch('genbank_tool.cli_with_error_handling.OutputFormatter') as mock_formatter:
            
            # Setup mocks
            mock_resolver_instance = Mock()
            mock_retriever_instance = Mock()
            mock_formatter_instance = Mock()
            
            mock_resolver.return_value = mock_resolver_instance
            mock_retriever.return_value = mock_retriever_instance
            mock_formatter.return_value = mock_formatter_instance
            
            # Mock gene resolution
            mock_resolver_instance.resolve_gene.return_value = Mock(
                gene_id="7157",
                official_symbol="TP53",
                confidence=1.0
            )
            
            # Mock sequence retrieval
            mock_retriever_instance.retrieve_sequences.return_value = [self.mock_sequence]
            
            result = runner.invoke(main, [
                '--test-genes',
                '--quiet'
            ])
            
            if result.exit_code != 0:
                print(f"CLI output: {result.output}")
                print(f"CLI exception: {result.exception}")
            assert result.exit_code == 0
            assert mock_resolver_instance.resolve_gene.called
            assert mock_retriever_instance.retrieve_sequences.called
    
    def test_input_file_processing(self, runner, temp_dir):
        """Test processing input file with genes."""
        input_file = temp_dir / "genes.txt"
        output_file = temp_dir / "output.tsv"
        input_file.write_text("TP53\nBRCA1\nEGFR")
        
        with patch('genbank_tool.cli_with_error_handling.InputParser') as mock_parser, \
             patch('genbank_tool.cli_with_error_handling.GeneResolver') as mock_resolver, \
             patch('genbank_tool.cli_with_error_handling.SequenceRetriever') as mock_retriever, \
             patch('genbank_tool.cli_with_error_handling.OutputFormatter') as mock_formatter:
            
            # Setup mocks
            mock_parser_instance = Mock()
            mock_parser.return_value = mock_parser_instance
            mock_parser_instance.parse_file.return_value = ["TP53", "BRCA1", "EGFR"]
            
            mock_resolver_instance = Mock()
            mock_resolver.return_value = mock_resolver_instance
            mock_resolver_instance.resolve_gene.return_value = Mock(
                gene_id="7157",
                official_symbol="TP53",
                confidence=1.0
            )
            
            mock_retriever_instance = Mock()
            mock_retriever.return_value = mock_retriever_instance
            mock_retriever_instance.retrieve_sequences.return_value = [self.mock_sequence]
            
            mock_formatter_instance = Mock()
            mock_formatter.return_value = mock_formatter_instance
            
            result = runner.invoke(main, [
                str(input_file),
                str(output_file),
                '--quiet'
            ])
            
            assert result.exit_code == 0
            assert mock_parser_instance.parse_file.called
            assert mock_parser_instance.parse_file.call_args[0][0] == input_file
    
    def test_parallel_processing(self, runner, temp_dir):
        """Test parallel processing mode."""
        input_file = temp_dir / "genes.txt"
        output_file = temp_dir / "output.tsv"
        input_file.write_text("TP53\nBRCA1\nEGFR\nVEGFA\nKRAS")
        
        with patch('genbank_tool.cli_with_error_handling.InputParser') as mock_parser, \
             patch('genbank_tool.cli_with_error_handling.ParallelProcessor') as mock_processor:
            
            mock_parser_instance = Mock()
            mock_parser.return_value = mock_parser_instance
            mock_parser_instance.parse_file.return_value = ["TP53", "BRCA1", "EGFR", "VEGFA", "KRAS"]
            
            mock_processor_instance = Mock()
            mock_processor.return_value = mock_processor_instance
            mock_processor_instance.process_batch.return_value = ([], Mock(successful=5, failed=0))
            
            result = runner.invoke(main, [
                str(input_file),
                str(output_file),
                '--parallel',
                '--workers', '4',
                '--quiet'
            ])
            
            assert result.exit_code == 0
            assert mock_processor.called
            assert mock_processor.call_args[1]['max_workers'] == 4
    
    def test_error_recovery_retry_failed(self, runner, temp_dir):
        """Test retry failed items functionality."""
        checkpoint_dir = temp_dir / ".genbank_checkpoints"
        checkpoint_dir.mkdir()
        
        # Create a checkpoint file with failed items
        checkpoint_data = {
            "batch_id": "test_batch_123",
            "total_items": 3,
            "processed": 2,
            "failed_items": ["INVALID_GENE"],
            "successful_items": ["TP53", "BRCA1"],
            "timestamp": "2025-08-06T10:00:00"
        }
        
        checkpoint_file = checkpoint_dir / "batch_test_batch_123.json"
        checkpoint_file.write_text(json.dumps(checkpoint_data))
        
        output_file = temp_dir / "output.tsv"
        
        with patch('genbank_tool.cli_with_error_handling.BatchProcessor') as mock_batch:
            mock_batch_instance = Mock()
            mock_batch.return_value = mock_batch_instance
            mock_batch_instance.retry_failed_items.return_value = Mock(
                successful=0,
                failed=1
            )
            
            result = runner.invoke(main, [
                '--retry-failed', 'test_batch_123',
                '--checkpoint-dir', str(checkpoint_dir),
                '--quiet'
            ])
            
            assert result.exit_code == 0
            assert mock_batch_instance.retry_failed_items.called
    
    def test_error_recovery_resume(self, runner, temp_dir):
        """Test resume from checkpoint functionality."""
        checkpoint_dir = temp_dir / ".genbank_checkpoints"
        checkpoint_dir.mkdir()
        
        # Create a checkpoint file
        checkpoint_data = {
            "batch_id": "test_batch_456",
            "total_items": 5,
            "processed": 3,
            "failed_items": [],
            "successful_items": ["TP53", "BRCA1", "EGFR"],
            "remaining_items": ["VEGFA", "KRAS"],
            "timestamp": "2025-08-06T10:00:00"
        }
        
        checkpoint_file = checkpoint_dir / "batch_test_batch_456.json"
        checkpoint_file.write_text(json.dumps(checkpoint_data))
        
        output_file = temp_dir / "output.tsv"
        
        with patch('genbank_tool.cli_with_error_handling.BatchProcessor') as mock_batch:
            mock_batch_instance = Mock()
            mock_batch.return_value = mock_batch_instance
            mock_batch_instance.resume_from_checkpoint.return_value = Mock(
                successful=2,
                failed=0
            )
            
            result = runner.invoke(main, [
                '--resume', 'test_batch_456',
                '--checkpoint-dir', str(checkpoint_dir),
                '--quiet'
            ])
            
            assert result.exit_code == 0
            assert mock_batch_instance.resume_from_checkpoint.called
    
    def test_cache_management(self, runner, temp_dir):
        """Test cache management options."""
        # Test clear cache
        with patch('genbank_tool.cli_with_error_handling.CacheManager') as mock_cache:
            mock_cache_instance = Mock()
            mock_cache.return_value = mock_cache_instance
            
            result = runner.invoke(main, ['--clear-cache', '--quiet'])
            
            assert result.exit_code == 0
            assert mock_cache_instance.clear_all.called
        
        # Test cache stats
        with patch('genbank_tool.cli_with_error_handling.CacheManager') as mock_cache:
            mock_cache_instance = Mock()
            mock_cache.return_value = mock_cache_instance
            mock_cache_instance.get_stats.return_value = {
                'total_entries': 100,
                'total_size': 1024000,
                'hit_rate': 0.85
            }
            
            result = runner.invoke(main, ['--cache-stats'])
            
            assert result.exit_code == 0
            assert mock_cache_instance.get_stats.called
    
    def test_config_file_loading(self, runner, temp_dir):
        """Test loading configuration from file."""
        config_file = temp_dir / "config.json"
        config_data = {
            "api": {
                "ncbi_api_key": "test_key_123",
                "email": "test@example.com"
            },
            "cache": {
                "enabled": True,
                "ttl_days": 7
            },
            "processing": {
                "batch_size": 50,
                "max_workers": 5
            }
        }
        config_file.write_text(json.dumps(config_data))
        
        output_file = temp_dir / "output.tsv"
        
        with patch('genbank_tool.cli_with_error_handling.Config') as mock_config:
            mock_config_instance = Mock()
            mock_config.from_file.return_value = mock_config_instance
            mock_config_instance.api.ncbi_api_key = "test_key_123"
            
            result = runner.invoke(main, [
                '--test-genes',
                '--config', str(config_file),
                '--quiet'
            ])
            
            assert result.exit_code == 0
            assert mock_config.from_file.called
            assert mock_config.from_file.call_args[0][0] == config_file
    
    def test_output_formats(self, runner, temp_dir):
        """Test different output formats."""
        input_file = temp_dir / "genes.txt"
        input_file.write_text("TP53")
        
        formats = ['tsv', 'csv', 'json', 'excel']
        
        for fmt in formats:
            output_file = temp_dir / f"output.{fmt}"
            
            with patch('genbank_tool.cli_with_error_handling.InputParser'), \
                 patch('genbank_tool.cli_with_error_handling.GeneResolver'), \
                 patch('genbank_tool.cli_with_error_handling.SequenceRetriever'), \
                 patch('genbank_tool.cli_with_error_handling.OutputFormatter') as mock_formatter:
                
                mock_formatter_instance = Mock()
                mock_formatter.return_value = mock_formatter_instance
                
                result = runner.invoke(main, [
                    str(input_file),
                    str(output_file),
                    '--output-format', fmt,
                    '--quiet'
                ])
                
                assert result.exit_code == 0
                assert mock_formatter_instance.format_results.called
                
                # Check format argument
                call_args = mock_formatter_instance.format_results.call_args
                assert call_args[1]['format'] == fmt
    
    def test_validation_options(self, runner, temp_dir):
        """Test validation options."""
        input_file = temp_dir / "genes.txt"
        output_file = temp_dir / "output.tsv"
        input_file.write_text("TP53")
        
        with patch('genbank_tool.cli_with_error_handling.DataValidator') as mock_validator:
            mock_validator_instance = Mock()
            mock_validator.return_value = mock_validator_instance
            mock_validator_instance.validate_sequence.return_value = Mock(
                is_valid=True,
                confidence=0.95
            )
            
            result = runner.invoke(main, [
                str(input_file),
                str(output_file),
                '--validate',
                '--strict-validation',
                '--quiet'
            ])
            
            assert result.exit_code == 0
            assert mock_validator.called
            assert mock_validator.call_args[1]['strict_mode'] == True
    
    def test_error_handling_network_failure(self, runner, temp_dir):
        """Test handling of network failures."""
        input_file = temp_dir / "genes.txt"
        output_file = temp_dir / "output.tsv"
        input_file.write_text("TP53")
        
        with patch('genbank_tool.cli_with_error_handling.GeneResolver') as mock_resolver:
            mock_resolver_instance = Mock()
            mock_resolver.return_value = mock_resolver_instance
            mock_resolver_instance.resolve_gene.side_effect = ConnectionError("Network error")
            
            with patch('genbank_tool.cli_with_error_handling.get_error_handler') as mock_error_handler:
                error_handler = Mock()
                mock_error_handler.return_value = error_handler
                error_handler.handle_error.return_value = (False, None, "Network error occurred")
                
                result = runner.invoke(main, [
                    str(input_file),
                    str(output_file),
                    '--quiet'
                ])
                
                # Should complete but with errors recorded
                assert error_handler.handle_error.called
    
    def test_verbose_and_quiet_modes(self, runner, temp_dir):
        """Test verbose and quiet output modes."""
        output_file = temp_dir / "output.tsv"
        
        # Test verbose mode
        result = runner.invoke(main, [
            '--test-genes',
            '--verbose'
        ])
        assert result.exit_code == 0
        
        # Test quiet mode
        result = runner.invoke(main, [
            '--test-genes',
            '--quiet'
        ])
        assert result.exit_code == 0
        
        # Test conflict
        result = runner.invoke(main, [
            '--test-genes',
            '--verbose',
            '--quiet'
        ])
        assert result.exit_code != 0
        assert "Cannot use both --quiet and --verbose" in result.output
    
    def test_checkpoint_directory_creation(self, runner, temp_dir):
        """Test automatic checkpoint directory creation."""
        checkpoint_dir = temp_dir / "custom_checkpoints"
        output_file = temp_dir / "output.tsv"
        
        assert not checkpoint_dir.exists()
        
        with patch('genbank_tool.cli_with_error_handling.BatchProcessor'):
            result = runner.invoke(main, [
                '--test-genes',
                '--checkpoint-dir', str(checkpoint_dir),
                '--checkpoint-interval', '5',
                '--quiet'
            ])
            
            assert result.exit_code == 0
            assert checkpoint_dir.exists()
    
    def test_generate_config(self, runner, temp_dir):
        """Test config file generation."""
        config_file = temp_dir / "new_config.json"
        
        result = runner.invoke(main, [
            '--generate-config'
        ])
        
        assert result.exit_code == 0
        assert config_file.exists()
        
        # Verify config structure
        with open(config_file) as f:
            config = json.load(f)
        
        assert 'api' in config
        assert 'cache' in config
        assert 'processing' in config