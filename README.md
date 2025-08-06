# Constitutional.seq

Principle-based canonical sequence retrieval for mRNA therapeutics. An AI-safety inspired approach to biological sequence selection.

Automated tool for retrieving Coding DNA Sequences (CDS) from NCBI GenBank for mRNA therapeutic development workflows.

## Features

- Intelligent gene name resolution handling aliases and synonyms
- Automated retrieval of CDS sequences from NCBI RefSeq
- Hierarchical transcript selection: MANE Select > MANE Plus Clinical > RefSeq Select > Longest CDS
- Note: UniProt canonical detection simplified to longest ATG-starting transcript (proxy method)
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

### Prerequisites
- Python 3.8 or higher
- pip package manager
- Git (for cloning the repository)

### Quick Install

```bash
# Clone the repository
git clone https://github.com/yourusername/constitutional-seq.git
cd constitutional-seq

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Verify Installation

```bash
# Set Python path to find the modules
export PYTHONPATH=$PWD/src:$PYTHONPATH

# Test CLI
python -m genbank_tool.cli --help

# Launch GUI
python -m genbank_tool.gui.main_window
```

Or install in development mode:
```bash
pip install -e .
```

### Troubleshooting

If you encounter PyQt5 installation issues:
```bash
# macOS
brew install pyqt5

# Ubuntu/Debian
sudo apt-get install python3-pyqt5

# Windows - use pip
pip install PyQt5
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

### CLI Versions

The tool provides multiple CLI entry points for different use cases:

- **`genbank-tool`** - Main CLI with comprehensive error handling and recovery features (recommended)
- **`genbank-tool-enhanced`** - Enhanced CLI with additional features for advanced users  
- **`genbank-tool-legacy`** - Legacy CLI for backward compatibility
- **`genbank-tool-gui`** - Launch the graphical user interface

For most users, the standard `genbank-tool` command is recommended as it includes the most robust error handling and recovery mechanisms.

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

MIT License - Please use however you'd like

## Author

**Austin P. Morrissey**  
August 6, 2025

This is a demonstration of "vibe coding" - showing the untapped utility of computational tools for the life sciences. This tool was developed through AI-human collaboration using Claude Opus 4.

I'm particularly interested in learning science from others and happy to collaborate on tasks. If you have something to teach and think it can be automated but don't know how, I'll help in exchange for you teaching me something from your domain.

**Contact:** austin.morrissey@proton.me