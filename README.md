# NCBI GenBank CDS Retrieval Tool

Automated tool for retrieving Coding DNA Sequences (CDS) from NCBI GenBank for mRNA therapeutic development workflows.

## Features

- Intelligent gene name resolution handling aliases and synonyms
- Automated retrieval of CDS sequences from NCBI RefSeq
- Smart canonical transcript selection based on RefSeq Select and UniProt
- Cross-validation with multiple databases
- Excel-compatible output format
- Comprehensive audit trails

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

## Usage

```bash
genbank-tool genes.txt output.tsv
```

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