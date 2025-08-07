# NCBI GenBank Tool - Comprehensive Data Flow Architecture

## Overview
The NCBI GenBank CDS Retrieval Tool is a sophisticated bioinformatics pipeline that retrieves Coding DNA Sequences (CDS) from NCBI GenBank for mRNA therapeutic development. This document provides a detailed analysis of how data flows through the system.

## 🔄 High-Level Data Flow

```
Input File → Parse → Resolve Genes → Retrieve Sequences → Select Transcripts → Validate → Format Output
     ↓         ↓           ↓                ↓                    ↓              ↓            ↓
  [genes.txt] [List]  [Gene IDs]      [CDS Sequences]      [Canonical]    [Verified]   [TSV/Excel]
```

## 📥 Phase 1: Input Processing

### Entry Point (`cli_with_error_handling.py:main()`)
```python
User Command: genbank-tool genes.txt output.tsv --parallel
                    ↓
Click CLI Parser → Arguments Dictionary
                    ↓
Configuration Merge (ENV → Config File → CLI Args)
                    ↓
Component Initialization
```

### Input Parser (`input_parser.py`)
**Purpose:** Convert various file formats into a clean list of gene names

**Data Transformations:**
1. **File Detection**
   - Auto-detect encoding (UTF-8, Latin-1, etc.)
   - Detect delimiter (comma, tab, etc.)
   - Identify file format (TXT, CSV, TSV, Excel, JSON)

2. **Content Extraction**
   ```
   Raw File → Binary Read → Encoding Detection → Text Decode → Parse
   ```
   - TXT: Line-by-line extraction
   - CSV/TSV: Column detection and extraction
   - Excel: Sheet parsing with openpyxl
   - JSON: Recursive key extraction

3. **Output:** `List[str]` of gene names/symbols

**Example Flow:**
```
genes.txt (UTF-8):          InputParser:              Output:
"VEGF\n"            →    detect_encoding()    →    ["VEGF",
"TP53\n"                 split_lines()              "TP53",
"BRCA1\n"                clean_whitespace()         "BRCA1"]
```

## 🔍 Phase 2: Gene Resolution

### Gene Resolver (`gene_resolver.py`)
**Purpose:** Convert gene symbols to official NCBI Gene IDs

**Data Flow:**
```python
Gene Symbol → Cache Check → NCBI Search → UniProt Fallback → Resolved Gene
    "VEGF"        ↓              ↓              ↓                  ↓
               [cached?]    [Gene ID: 7422]  [if failed]    {id: 7422,
                                                            symbol: "VEGFA",
                                                            confidence: 0.9}
```

**Processing Steps:**

1. **Cache Lookup** (30-day TTL)
   ```python
   cache_key = f"gene_{symbol.upper()}"
   if cached_data exists and not expired:
       return cached_data
   ```

2. **NCBI Gene Search**
   ```
   API Call: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
   Parameters: db=gene, term="VEGF[sym] AND human[orgn]"
   Response: XML with Gene IDs
   ```

3. **Gene Validation**
   ```
   API Call: esummary.fcgi?db=gene&id=7422
   Response: Gene metadata (official symbol, aliases, description)
   ```

4. **Confidence Scoring**
   - Exact match: 1.0
   - Alias match: 0.8-0.9
   - Partial match: 0.5-0.7
   - Fallback (UniProt): 0.6

5. **Output Structure:**
   ```python
   ResolvedGene(
       input_symbol="VEGF",
       gene_id=7422,
       official_symbol="VEGFA",
       confidence=0.9,
       source="ncbi",
       aliases=["VEGF", "VPF", "MVCD1"]
   )
   ```

## 🧬 Phase 3: Sequence Retrieval

### Sequence Retriever (`sequence_retriever.py`)
**Purpose:** Fetch all CDS sequences for a gene from NCBI RefSeq

**Data Flow:**
```
Gene ID → Search RefSeq → Fetch GenBank Records → Extract CDS → Sequences
  7422        ↓                   ↓                   ↓           ↓
         [20 transcripts]    [GenBank files]     [CDS features]  [List]
```

**Detailed Steps:**

1. **RefSeq Search**
   ```python
   # Search for all transcripts of gene
   handle = Entrez.esearch(
       db="nuccore",
       term=f"{gene_id}[Gene ID] AND refseq[filter]",
       retmax=100
   )
   # Returns: List of RefSeq accession IDs
   ```

2. **Batch Fetch GenBank Records**
   ```python
   # Fetch all records in one call
   handle = Entrez.efetch(
       db="nuccore",
       id=",".join(refseq_ids),
       rettype="gb",
       retmode="text"
   )
   # Parse with BioPython
   records = SeqIO.parse(handle, "genbank")
   ```

3. **CDS Extraction**
   ```python
   for record in records:
       for feature in record.features:
           if feature.type == "CDS":
               cds_sequence = feature.extract(record.seq)
               protein_id = feature.qualifiers.get("protein_id")
               product = feature.qualifiers.get("product")
   ```

4. **Data Structure Created:**
   ```python
   RetrievedSequence(
       accession="NM_001171623.2",
       gene_id=7422,
       gene_symbol="VEGFA",
       sequence="ATGAACTTTCTGCTGTCTT...",  # Full CDS
       length=639,
       protein_id="NP_001165094.1",
       description="vascular endothelial growth factor A isoform 2",
       url="https://www.ncbi.nlm.nih.gov/nuccore/NM_001171623.2"
   )
   ```

## 🎯 Phase 4: Transcript Selection

### Transcript Selector (`transcript_selector.py`)
**Purpose:** Select the canonical/best transcript from multiple options

**Selection Hierarchy:**
```
1. User Preference (if specified)
     ↓ (if not found)
2. RefSeq Select Designation
     ↓ (if not found)
3. UniProt Canonical Annotation
     ↓ (if not found)
4. Longest CDS with ATG Start
     ↓ (if tie)
5. Most Recent Version Number
```

**Processing Logic:**

1. **RefSeq Select Check**
   ```python
   # Check GenBank features for RefSeq-Select tag
   if "RefSeq-Select" in record.annotations:
       return transcript  # Confidence: 0.95
   ```

2. **UniProt Cross-Reference**
   ```python
   # Query UniProt for canonical transcript
   uniprot_response = query_uniprot(gene_symbol)
   if canonical_accession matches:
       return transcript  # Confidence: 0.90
   ```

3. **Longest CDS Selection**
   ```python
   # Sort by CDS length, prefer ATG start
   candidates = [t for t in transcripts if t.sequence.startswith("ATG")]
   if not candidates:
       candidates = transcripts  # Fall back to all
   longest = max(candidates, key=lambda t: t.length)
   # Confidence: 0.75
   ```

4. **Output:**
   ```python
   TranscriptSelection(
       selected=selected_sequence,
       rationale="RefSeq Select",
       confidence=0.95,
       warnings=["Multiple isoforms with same length"]
   )
   ```

## ✅ Phase 5: Validation (Optional)

### Data Validator (`data_validator.py`)
**Purpose:** Verify sequence integrity and cross-database consistency

**Validation Checks:**

1. **Sequence Completeness**
   ```python
   # Check start codon
   if not sequence.startswith(("ATG", "CTG", "TTG")):
       issues.append("Non-standard start codon")
   
   # Check stop codon
   if sequence[-3:] not in ["TAA", "TAG", "TGA"]:
       issues.append("Missing stop codon")
   
   # Check length divisible by 3
   if len(sequence) % 3 != 0:
       issues.append("CDS not in frame")
   ```

2. **Cross-Database Validation**
   ```python
   # Compare with UniProt
   uniprot_seq = fetch_uniprot_cds(gene_symbol)
   if sequences_differ:
       confidence *= 0.8
       issues.append("Sequence mismatch with UniProt")
   ```

3. **Output:**
   ```python
   ValidationResult(
       is_valid=True,
       confidence=0.85,
       issues=["Non-ATG start codon"],
       cross_references={
           "uniprot": "P15692",
           "ensembl": "ENST00000332736"
       }
   )
   ```

## 📊 Phase 6: Output Generation

### Output Formatter (`output_formatter.py`)
**Purpose:** Convert results to requested format with audit trail

**Format Transformations:**

1. **TSV Generation**
   ```python
   headers = ["Gene", "Official_Symbol", "Accession", "CDS_Sequence", ...]
   for result in results:
       row = [
           result.input_gene,
           result.gene_symbol,
           result.accession,
           result.sequence,
           ...
       ]
       writer.writerow(row)
   ```

2. **Excel Enhancement**
   ```python
   # Add formatting for Excel
   workbook = openpyxl.Workbook()
   sheet = workbook.active
   
   # Headers with bold formatting
   for col, header in enumerate(headers):
       cell = sheet.cell(row=1, column=col+1)
       cell.value = header
       cell.font = Font(bold=True)
   
   # Hyperlinks for GenBank URLs
   for row_num, result in enumerate(results, start=2):
       cell = sheet.cell(row=row_num, column=url_col)
       cell.hyperlink = result.genbank_url
   ```

3. **Audit Trail Generation**
   ```json
   {
       "timestamp": "2025-08-06T10:55:56",
       "version": "0.1.0",
       "parameters": {
           "canonical_only": true,
           "validation": true
       },
       "statistics": {
           "total_processed": 3,
           "successful": 3,
           "failed": 0
       },
       "genes": [
           {
               "input": "VEGF",
               "resolved": "VEGFA",
               "confidence": 0.9,
               "transcript": "NM_001171623.2",
               "selection_method": "Longest CDS"
           }
       ]
   }
   ```

## 🔄 Parallel Processing Flow

When `--parallel` flag is used:

```
Input List → Chunk Division → Thread Pool → Parallel Processing → Result Aggregation
    100         10x10          10 threads      Concurrent           Merged results
   genes        chunks          workers        API calls            Single output
```

**Implementation:**
```python
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = []
    for chunk in chunks:
        future = executor.submit(process_chunk, chunk)
        futures.append(future)
    
    for future in as_completed(futures):
        results.extend(future.result())
```

## 💾 Caching Architecture

### Multi-Level Cache System

1. **Gene Resolution Cache**
   - Location: `cache/genes/`
   - TTL: 30 days
   - Key: `gene_{symbol.upper()}`

2. **Sequence Cache**
   - Location: `cache/sequences/`
   - TTL: 7 days
   - Key: `gene_{gene_id}_sequences`

3. **Cache Hit Flow:**
   ```
   Request → Check Cache → Found & Valid? → Return Cached
      ↓                        ↓ No              ↑
      ↓                   Fetch from API → Store in Cache
      ↓
   Process Request
   ```

## 🚨 Error Recovery Flow

### Checkpoint System
```
Processing → Every 10 items → Save Checkpoint → Continue
     ↓              ↓                ↓              ↓
   Error      checkpoint.json   Resume Point    Retry Failed
```

### Recovery Strategies
1. **Network Timeout:** Exponential backoff (1s, 2s, 4s, 8s...)
2. **Rate Limit:** Wait and retry with rate adjustment
3. **Invalid Gene:** Skip and log for manual review
4. **API Error:** Fallback to cache or alternative database

## 📈 Performance Optimizations

1. **Batch API Calls:** Fetch multiple GenBank records in one request
2. **Connection Pooling:** Reuse HTTPS connections
3. **Smart Caching:** TTL-based with LRU eviction
4. **Parallel Processing:** Thread pool for concurrent operations
5. **Streaming Output:** Write results as processed (memory efficient)

## 🎯 Complete Example: Processing "VEGF"

```
1. Input: "VEGF" from genes.txt
2. Gene Resolution:
   - Cache miss
   - NCBI API: VEGF → Gene ID 7422, Official: VEGFA
   - Cache store
3. Sequence Retrieval:
   - Search RefSeq: 20 transcripts found
   - Fetch GenBank: 20 records retrieved
   - Extract CDS: 20 sequences parsed
4. Transcript Selection:
   - No RefSeq Select found
   - No UniProt canonical match
   - Select longest: NM_001171623.2 (639 bp)
5. Validation:
   - Start codon: CTG (non-standard, warning)
   - Stop codon: TGA (valid)
   - Frame: 639/3 = 213 (valid)
6. Output:
   - TSV row: "VEGF\tVEGFA\tNM_001171623.2\tATGAACTTT..."
   - Audit: {"gene": "VEGF", "success": true, ...}
```

## Summary

The NCBI GenBank tool implements a robust, fault-tolerant pipeline for CDS retrieval with:
- **6 major processing phases**
- **3 external API integrations**
- **Multi-level caching system**
- **Comprehensive error recovery**
- **Flexible output formats**
- **Full audit trail capabilities**

The architecture ensures reliable, efficient retrieval of canonical CDS sequences for mRNA therapeutic development workflows.