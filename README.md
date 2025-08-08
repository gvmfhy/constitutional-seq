# Constitutional.seq: Speed up your mRNA production via automated design.

This project was vibe coded by Opus 4, and hence is named after Constitutional AI principles. Ideally, just as Claude follows principled guidelines rather than arbitrary choices, Constitutional.seq follows a scientific hierarchy for transcript selection. However,this is partly tongue and cheek, as the opus 4 series was classified under ASL-3 due to its potential to assist with risky topics like synthetic biology. Yet Opus 4 was fully capable of writing, refining, and even explaining a multi-step automation pipeline involving transcript selection, gene filtering, and sequence formatting without any jailbreaking or goading. 

**Stop guessing which transcript variant to use for your mRNA therapeutics.**

When you search for a gene like TP53 or VEGF in NCBI, you get 20+ transcript variants. Which one should you use for your therapeutic? Pick wrong and you'll target the wrong tissue, produce a non-functional protein, or trigger an immune response.

Constitutional.seq solves this by automatically selecting the canonical transcript using the same scientific hierarchy that clinical geneticists use: MANE Select (expert consensus) → RefSeq Select → UniProt Canonical → Longest CDS.

**In short:** Give it a gene name, get back the one CDS sequence you should use, with a confidence score explaining why.

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
git clone https://github.com/gvmfhy/constitutional-seq.git
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

### Data Flow Overview

The tool implements a four-stage pipeline that mirrors how a molecular biologist would manually select sequences, but with computational rigor and reproducibility. Each stage feeds precisely into the next, creating a chain of custody from user input to final CDS sequence.

### 1. Gene Name Resolution (HGNC Module)

**Purpose**: Transform any gene identifier into a standardized, unambiguous reference.

When a user enters a gene name (like "p53", "VEGF", or even outdated symbols), the HGNC resolver acts as a universal translator. HGNC (HUGO Gene Nomenclature Committee) maintains the authoritative database of human gene names, serving as the Rosetta Stone of genomic nomenclature. This module queries HGNC's REST API to resolve aliases, deprecated symbols, and common misspellings into the official gene symbol and its corresponding NCBI Gene ID.

**Why this matters**: Gene naming in scientific literature is chaotic. The same gene might be called "p53" in one paper, "TP53" in another, and "TRP53" in older literature. Without proper resolution, you might retrieve the wrong sequence or miss the gene entirely. The HGNC module ensures that regardless of what name you provide, you get the correct gene's sequences.

**Data passed to next stage**: Official gene symbol (e.g., "TP53") and NCBI Gene ID (e.g., "7157")

### 2. Transcript Retrieval (NCBI Module)

**Purpose**: Extract the exact CDS (Coding DNA Sequence) needed for plasmid cloning and mRNA synthesis.

Armed with the NCBI Gene ID, this module queries the NCBI Entrez system to retrieve every RefSeq transcript associated with the gene. RefSeq is NCBI's curated collection of reference sequences, representing the gold standard for sequence data. The module fetches all mRNA transcripts (NM_ accessions) and extracts their coding sequences (CDS).

**What is a CDS?**: The CDS is the exact DNA sequence (ATGC nucleotides) that encodes the protein - starting from the start codon (usually ATG) through to the stop codon (TAA, TAG, or TGA). This is what you clone into your plasmid vector. For example:
```
ATGGAGGAGCCGCAGTCAGATCCTAGCGTCGAG...TGCTGTCTCCGGGTGA
```
This DNA gets transcribed to mRNA in vitro (T7/SP6 polymerase), then the mRNA gets translated to protein in cells.

**The Molecular Biology Pipeline**:
1. **CDS (DNA)** → cloned into plasmid vector
2. **Plasmid** → linearized and used as template
3. **In vitro transcription** → produces mRNA (with added 5' cap, 3' polyA tail)
4. **mRNA delivery** → transfection/injection into cells
5. **Translation** → ribosomes produce the therapeutic protein

**Why this matters**: Human genes typically produce multiple transcript variants through alternative splicing, alternative promoters, and other mechanisms. Some genes have over 20 variants. Each variant produces a different CDS, encoding a different protein isoform with potentially distinct functions. For mRNA therapeutics, choosing the wrong CDS variant could mean targeting the wrong biological pathway, expressing in the wrong tissue, or producing a non-functional protein.

**Data passed to next stage**: List of all transcript objects, each containing accession number, version, CDS sequence (the actual ATGC string), CDS length in base pairs, and metadata flags

### 3. Canonical Transcript Selection (Hierarchical Selection Engine)

**Purpose**: Apply scientific principles to select the most therapeutically relevant transcript.

This is the heart of Constitutional.seq's scientific logic. Rather than arbitrarily picking a transcript, the tool implements a hierarchy based on international scientific consensus:

#### **MANE Select (confidence: 1.0)** - The Gold Standard

MANE (Matched Annotation from NCBI and EMBL-EBI) represents an unprecedented collaboration between the world's two major genomic databases. For each gene, expert curators from both institutions independently evaluate all transcripts, then meet to reach consensus on a single "Select" transcript. They consider evolutionary conservation across species, expression levels in healthy tissues, clinical relevance in disease databases, and protein domain completeness. When Constitutional.seq finds a MANE Select transcript, it's using the same sequence that clinical geneticists use for variant interpretation and that drug developers use for therapeutic design.

**Coverage**: ~19,000 human protein-coding genes (about 95% of clinically relevant genes)

#### **MANE Plus Clinical (confidence: 0.98)** - Clinically Critical Alternatives

Some genes produce multiple isoforms that are each clinically important in different contexts. For example, the dystrophin gene produces a full-length protein in muscle but a shorter isoform in brain. MANE Plus Clinical captures these additional transcripts that, while not the primary "Select" choice, have documented clinical importance. Constitutional.seq checks these when the MANE Select transcript isn't available in the retrieved set.

#### **RefSeq Select (confidence: 0.95)** - Computational Consensus

For genes without MANE curation, NCBI provides RefSeq Select - their best computational prediction of the representative transcript. This algorithm integrates multiple data sources: RNA-seq expression data from the GTEx project, evolutionary conservation scores, UniProt annotations, and literature citations. While not manually curated, RefSeq Select benefits from NCBI's decades of experience in sequence analysis.

#### **UniProt Canonical (confidence: 0.85)** - Protein-Centric Selection

UniProt approaches the problem from the protein perspective. Their curators review experimental evidence from mass spectrometry, crystal structures, and functional studies to identify the canonical protein isoform. Constitutional.seq maps these protein selections back to their corresponding mRNA transcripts through a sophisticated pipeline:

**Understanding NM vs NP Accessions**: 
- **NM_** (RefSeq mRNA): These are the mRNA transcript sequences - the actual RNA molecules that get translated into proteins. Example: NM_000546 is the mRNA for human p53.
- **NP_** (RefSeq Protein): These are the protein sequences - the amino acid chains that result from translating mRNA. Example: NP_000537 is the p53 protein.
- **The Challenge**: UniProt provides protein accessions (NP_), but mRNA therapeutics need the corresponding mRNA sequences (NM_). A single protein can theoretically come from multiple mRNA variants due to codon degeneracy, though in practice RefSeq maintains 1:1 mappings.

**The Constitutional.seq Pipeline**:

1. **Gene → Protein Mapping**: Downloads UniProt's ID mapping database (119MB) containing 32,000+ human genes mapped to their canonical protein accessions
2. **Protein Accession Retrieval**: Identifies the UniProt canonical protein (e.g., TP53 → NP_000537.3)
3. **Protein → mRNA Reverse Mapping**: This is the critical step. The tool queries NCBI's protein database with the NP_ accession and parses the GenBank record to find the source mRNA in the DBSOURCE field. For example:
   ```
   DBSOURCE    REFSEQ: accession NM_000546.6
   ```
4. **Validation**: Confirms the retrieved NM_ accession exists in our transcript set and contains the expected CDS

**Why This Complexity?**: UniProt focuses on proteins because that's where biological function resides. They identify which protein isoform is "canonical" based on functional studies. But for mRNA therapeutics, we need the instructions (mRNA) not the final product (protein). This NP→NM mapping bridges that gap, ensuring we get the mRNA that produces UniProt's expertly selected canonical protein.

This protein-centric approach is particularly valuable for genes where protein function, rather than RNA expression, drives biological importance.

#### **Longest CDS (confidence: 0.50)** - The Reproducible Fallback

When all curated sources fail, the tool falls back to a simple heuristic: select the transcript with the longest coding sequence. **This is explicitly not a biological principle** - longer doesn't mean better in biology. Many important proteins are short, and many diseases result from inappropriately long isoforms. However, this fallback ensures reproducibility: given the same input, you'll always get the same output. The low confidence score (0.50) serves as a warning flag that manual review is essential.

**Special consideration**: The tool preferentially selects transcripts starting with ATG (the standard start codon) over those with alternative start codons, even if slightly shorter, because non-ATG starts often indicate incomplete annotation or specialized regulation.

### 4. Output Generation and Quality Control

**Purpose**: Deliver the exact CDS sequence for cloning, with comprehensive metadata for informed decision-making.

The final stage packages the selected transcript with rich metadata that enables informed decision-making. Every result includes:

- **The CDS sequence**: The complete DNA sequence (ATGC only) from start codon to stop codon, in 5' → 3' orientation. This is exactly what you need to:
  - Order as a gene synthesis product (gBlock, GenScript, etc.)
  - Clone into your expression vector between restriction sites
  - Use as template for PCR amplification
  - Design primers for Gibson assembly or other cloning methods
  
  Example output:
  ```
  ATGGAGGAGCCGCAGTCAGATCCTAGCGTCGAGCCCCCTCTGAGTCAGGAAACATTTTCAGACCTATGGAAACTACTTCCTGAAAACAACGTTCTGTCCCCCTTGCCGTCCCAAGCAATGGATGATTTGATGCTGTCCCCGGACGATATTGAACAATGGTTCACTGAAGACCCAGGTCCAGATGAAGCTCCCAGAATGCCAGAGGCTGCTCCCCGCGTGGCCCCTGCACCAGCAGCTCCTACACCGGCGGCCCCTGCACCAGCCCCCTCCTGGCCCCTGTCATCTTCTGTCCCTTCCCAGAAAACCTACCAGGGCAGCTACGGTTTCCGTCTGGGCTTCTTGCATTCTGGGACAGCCAAGTCTGTGACTTGCACGTACTCCCCTGCCCTCAACAAGATGTTTTGCCAACTGGCCAAGACCTGCCCTGTGCAGCTGTGGGTTGATTCCACACCCCCGCCCGGCACCCGCGTCCGCGCCATGGCCATCTACAAGCAGTCACAGCACATGACGGAGGTTGTGAGGCGCTGCCCCCACCATGAGCGCTGCTCAGATAGCGATGGTCTGGCCCCTCCTCAGCATCTTATCCGAGTGGAAGGAAATTTGCGTGTGGAGTATTTGGATGACAGAAACACTTTTCGACATAGTGTGGTGGTGCCCTATGAGCCGCCTGAGGTTGGCTCTGACTGTACCACCATCCACTACAACTACATGTGTAACAGTTCCTGCATGGGCGGCATGAACCGGAGGCCCATCCTCACCATCATCACACTGGAAGACTCCAGTGGTAATCTACTGGGACGGAACAGCTTTGAGGTGCGTGTTTGTGCCTGTCCTGGGAGAGACCGGCGCACAGAGGAAGAGAATCTCCGCAAGAAAGGGGAGCCTCACCACGAGCTGCCCCCAGGGAGCACTAAGCGAGCACTGCCCAACAACACCAGCTCCTCTCCCCAGCCAAAGAAGAAACCACTGGATGGAGAATATTTCACCCTTCAGATCCGTGGGCGTGAGCGCTTCGAGATGTTCCGAGAGCTGAATGAGGCCTTGGAACTCAAGGATGCCCAGGCTGGGAAGGAGCCAGGGGGGAGCAGGGCTCACTCCAGCCACCTGAAGTCCAAAAAGGGTCAGTCTACCTCCCGCCATAAAAAACTCATGTTCAAGACAGAAGGGCCTGACTCAGACTGA
  ```
  
- **Confidence score** (0.0-1.0) indicating the reliability of the selection
- **Selection method** explicitly stating which criterion was used (MANE, RefSeq, UniProt, etc.)
- **Warning flags** for potential issues (non-ATG starts, multiple equal-length variants, missing MANE despite gene importance)
- **Alternatives count** showing how many other transcripts exist, prompting review for critical applications
- **Full audit trail** documenting every API call and decision point for reproducibility

**What you do with the CDS**: This sequence is ready for immediate use in standard molecular biology workflows - no further processing needed. Simply copy-paste into your cloning software, gene synthesis order form, or primer design tool.

### Scientific Rationale for the Hierarchy

The selection hierarchy isn't arbitrary - it reflects how the scientific community establishes consensus:

1. **International consensus first** (MANE): When major institutions agree, that agreement represents thousands of hours of expert analysis
2. **Clinical evidence second** (MANE Plus Clinical): Real-world medical relevance trumps theoretical considerations
3. **Computational prediction third** (RefSeq Select): Sophisticated algorithms can identify patterns humans might miss
4. **Protein evidence fourth** (UniProt): Functional proteomics provides orthogonal validation of transcript importance
5. **Reproducible fallback last** (Longest CDS): When no evidence exists, at least be consistent and transparent

This hierarchy embodies the principle of "constitutional" selection - decisions based on established rules rather than arbitrary choices, with clear documentation when those rules must bend to practical necessity.

### Known Limitations
- **UniProt requires download**: Full UniProt canonical coverage requires downloading 119MB mapping file
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

**Contact:** [Create an issue](https://github.com/gvmfhy/constitutional-seq/issues) for questions or feedback
