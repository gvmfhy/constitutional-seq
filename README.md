# NCBI GenBank CDS Retrieval Tool

Automated tool for retrieving Coding DNA Sequences (CDS) from NCBI GenBank for mRNA therapeutic development workflows.

## Features

- Intelligent gene name resolution handling aliases and synonyms
- Automated retrieval of CDS sequences from NCBI RefSeq
- Smart canonical transcript selection based on RefSeq Select and UniProt
- Cross-validation with multiple databases (UniProt, Ensembl)
- Excel-compatible output format with multiple file format support
- Comprehensive audit trails for reproducibility
- **NEW: Advanced error handling and recovery**
  - Automatic retry with exponential backoff for network issues
  - Checkpoint/resume capability for large batch operations
  - Detailed error reporting and analysis
  - API rate limiting and health monitoring
- **NEW: Performance optimizations**
  - Parallel processing with configurable workers
  - Smart caching with expiration and size limits
  - Batch processing with progress tracking

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

## Usage

### Basic Usage

```bash
# Process a list of genes
genbank-tool genes.txt output.tsv

# Test with sample genes
genbank-tool --test-genes

# Use parallel processing for large lists
genbank-tool large_gene_list.txt output.tsv --parallel --workers 10
```

### Advanced Features

```bash
# Resume interrupted processing
genbank-tool --resume batch_1234567890 output.tsv

# Retry only failed items
genbank-tool --retry-failed batch_1234567890 output.tsv

# Generate detailed error report
genbank-tool genes.txt output.tsv --error-report analysis.json

# Enable debug logging
genbank-tool genes.txt output.tsv --verbose --log-level DEBUG
```

See [Error Handling Documentation](docs/error_handling.md) for comprehensive recovery features.

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src tests

# Type checking
mypy src
```

## License

MIT License