# Constitutional.seq

Principle-based canonical sequence retrieval for mRNA therapeutics. An AI-safety inspired approach to biological sequence selection.

Automated tool for retrieving Coding DNA Sequences (CDS) from NCBI GenBank for mRNA therapeutic development workflows.

## Features

- Intelligent gene name resolution handling aliases and synonyms
- Automated retrieval of CDS sequences from NCBI RefSeq
- Science-based hierarchical transcript selection (see below)
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

## Scientific Approach: How Constitutional.seq Works

### 1. Gene Name Resolution (HGNC)
The tool first resolves your gene name using **HGNC (HUGO Gene Nomenclature Committee)**, the international authority for human gene naming:
- Handles common aliases (e.g., "VEGF" → "VEGFA", "p53" → "TP53")  
- Resolves outdated gene symbols to current approved names
- Returns the official NCBI Gene ID for database queries

### 2. Transcript Retrieval
Using the NCBI Gene ID, the tool queries RefSeq to retrieve all transcript variants:
- Fetches all NM_ (mRNA) and NR_ (non-coding RNA) sequences
- Extracts CDS (Coding DNA Sequence) regions
- Validates sequences have proper structure (start/stop codons)

### 3. Canonical Transcript Selection
The tool uses a hierarchical approach based on scientific consensus:

#### **MANE Select (confidence: 1.0)**
- **What it is**: Matched Annotation from NCBI and EMBL-EBI - a joint project between RefSeq and Ensembl
- **Why it matters**: Represents the scientific community's consensus on the most biologically relevant transcript
- **Coverage**: Available for ~19,000 human protein-coding genes
- **Selection criteria**: Based on conservation, expression, clinical relevance, and protein length

#### **MANE Plus Clinical (confidence: 0.98)**  
- **What it is**: Additional MANE transcripts with demonstrated clinical importance
- **Why it matters**: Some genes have multiple clinically relevant isoforms (e.g., different tissues)
- **Example**: Genes with tissue-specific isoforms important for disease

#### **RefSeq Select (confidence: 0.95)**
- **What it is**: NCBI's computationally selected representative transcript
- **Why it matters**: Provides coverage for genes without MANE curation
- **Selection criteria**: Algorithm considers expression data, conservation, and annotations

#### **UniProt Canonical (confidence: 0.85)**
- **What it is**: UniProt's expertly curated canonical isoform from 20,000+ human proteins
- **Why it matters**: Based on proteomics evidence, structural data, and literature
- **Current implementation**: Built-in mappings for ~60 major therapeutic targets
- **Full coverage available**: Download UniProt ID mapping file (119MB) for 20,000+ genes via `--download-uniprot` flag

#### **Longest CDS (confidence: 0.50)**
- **What it is**: Fallback selection of the transcript with the longest coding sequence
- **Why it matters**: When no curated data exists, provides a reproducible (though arbitrary) choice
- **Warning**: This is NOT biologically meaningful - just ensures you get *something*

### 4. Output Generation
The tool provides comprehensive information for each gene:
- Selected transcript accession and version
- Complete CDS sequence (5' → 3')
- Confidence score and selection method
- Warnings about non-standard features (e.g., non-ATG starts)
- Alternative transcripts count for awareness

### Why This Hierarchy?
1. **MANE transcripts** represent years of manual curation and international consensus
2. **RefSeq Select** uses NCBI's computational expertise when manual curation isn't available
3. **Length-based fallback** is clearly marked as arbitrary (0.50 confidence) to prevent misuse

### Known Limitations
- **No UniProt canonical**: We removed UniProt canonical detection because protein→mRNA mapping is unreliable and introduces errors
- **Non-ATG starts**: Some valid transcripts use alternative start codons (clearly flagged in output)
- **Incomplete MANE coverage**: ~30% of human genes lack MANE annotation (as of 2024)

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