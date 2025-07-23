"""Tests for CLI quiet mode functionality."""

import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from genbank_tool.cli import main


class TestCLIQuietMode:
    """Test cases for CLI quiet mode."""
    
    @pytest.fixture
    def runner(self):
        """Create a Click test runner."""
        return CliRunner()
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_quiet_mode_suppresses_output(self, runner, temp_dir):
        """Test that quiet mode suppresses normal output."""
        # Create test input
        input_file = temp_dir / "genes.txt"
        input_file.write_text("TP53")
        output_file = temp_dir / "output.tsv"
        
        # Run with quiet mode
        result = runner.invoke(main, [
            str(input_file),
            str(output_file),
            '--quiet'
        ])
        
        # Should succeed with minimal output
        assert result.exit_code == 0
        assert "Processing genes" not in result.output
        assert "Results written to" not in result.output
        assert output_file.exists()
    
    def test_quiet_mode_shows_errors(self, runner, temp_dir):
        """Test that quiet mode still shows errors."""
        # Try to read non-existent file
        result = runner.invoke(main, [
            'nonexistent.txt',
            'output.tsv',
            '--quiet'
        ])
        
        # Should fail and show error
        assert result.exit_code != 0
        assert "ERROR" in result.output or "Error" in result.output
    
    def test_quiet_and_verbose_conflict(self, runner):
        """Test that quiet and verbose flags conflict."""
        result = runner.invoke(main, [
            '--test-genes',
            '--quiet',
            '--verbose'
        ])
        
        assert result.exit_code == 1
        assert "Cannot use both --quiet and --verbose" in result.output
    
    def test_generate_config_quiet(self, runner, temp_dir):
        """Test config generation in quiet mode."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(main, ['--generate-config', '--quiet'])
            
            assert result.exit_code == 0
            # Should generate file but no output
            assert Path('genbank.config.example.json').exists()
            assert result.output.strip() == ""
    
    def test_normal_mode_output(self, runner, temp_dir):
        """Test normal mode shows output."""
        # Create test input
        input_file = temp_dir / "genes.txt"
        input_file.write_text("TP53")
        output_file = temp_dir / "output.tsv"
        
        # Run without quiet mode
        result = runner.invoke(main, [
            str(input_file),
            str(output_file)
        ])
        
        # Should show progress
        assert result.exit_code == 0
        assert "Read 1 genes from" in result.output
        assert "Processing genes" in result.output
        assert "Writing results" in result.output
        assert "Results written to" in result.output