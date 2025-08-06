# 🧬 mRNA Therapeutics CDS Retrieval Guide

## Purpose

This tool retrieves validated canonical coding sequences (CDS) for mRNA therapeutic development. Selecting the correct isoform is critical for therapeutic efficacy, safety, and regulatory approval.

## 🔄 Complete Processing Pipeline

```
╔═══════════════════════════════════════════════════════════════════╗
║                    mRNA THERAPEUTIC CDS RETRIEVAL                    ║
║                         Scientific Workflow                          ║
╚═══════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────┐
│ USER INPUT: Any gene name format                                    │
│ Examples: "cd31", "P53", "Her2", "vegf", "IL-2"                    │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: HGNC GENE NAME RESOLUTION                                   │
│ • Queries HUGO Gene Nomenclature Committee database                 │
│ • Resolves ALL aliases to official symbol                           │
│ • Returns: PECAM1, TP53, ERBB2, VEGFA, IL2                        │
│ • Provides stable NCBI Gene ID for database queries                 │
│ Scientific Basis: Eliminates nomenclature ambiguity                 │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: MANE DATABASE CHECK                                         │
│ • Queries Matched Annotation (NCBI + EMBL-EBI consensus)           │
│ • Checks ~19,000 genes for expert-selected transcript              │
│ • Returns: e.g., NM_000546.6 for TP53                              │
│ • Confidence: 1.0 (gold standard)                                   │
│ Scientific Basis: International consensus on canonical transcript    │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: GENBANK RETRIEVAL & SELECTION                              │
│ • Fetches ALL transcript variants (10-50 per gene)                 │
│ • Identifies MANE/RefSeq Select/best match                         │
│ • Extracts CDS region (ATG → Stop codon)                           │
│ • Validates reading frame and completeness                          │
│ Scientific Basis: Ensures complete, functional coding sequence      │
└─────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────┐
│ OUTPUT: THERAPEUTIC-GRADE CDS                                       │
│ • DNA sequence: ATGCCCAGCGGC...TGA                                 │
│ • Confidence score: 0.40-1.00                                       │
│ • Selection method documented                                       │
│ • Ready for codon optimization → mRNA synthesis                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

1. **Enter Gene Names:** Use ANY format - official symbols, common aliases, clinical names
   - Works with: CD31, HER2, p53, IL-2, vegf, BRCA-1, etc.
   - Case doesn't matter: TP53, tp53, Tp53 all work
   - Hyphens optional: IL2 and IL-2 both resolve correctly
   
2. **Process:** Click the green "🧬 Process Genes" button
   - Tool automatically resolves aliases to official symbols
   - Selects the most therapeutically relevant transcript
   - Retrieves actual DNA sequences from GenBank
   
3. **Review Results:**
   - Green = successful retrieval with high confidence
   - Check "Selection Method" column for how transcript was chosen
   - Review any warnings in the warnings column
   
4. **Validate:** Click any row to see:
   - Full CDS sequence
   - Selection rationale
   - Alternative transcripts available
   
5. **Export:** Save results as TSV/Excel for downstream workflows

## 🔬 The Complete Data Processing Pipeline

```
╔══════════════════════════════════════════════════════════════╗
║              COMPLETE DATA FLOW (FINAL DESIGN)               ║
╚══════════════════════════════════════════════════════════════╝

USER INPUT: "cd31", "P53", "Her2", etc.
            ↓
┌──────────────────────────────────────────┐
│ 1. HGNC RESOLVER (NEW)                   │
│   - Handles any case                     │
│   - Resolves aliases                     │
│   - Returns: PECAM1, TP53, ERBB2        │
│   - Provides NCBI Gene ID                │
└──────────────────────────────────────────┘
            ↓
┌──────────────────────────────────────────┐
│ 2. MANE DATABASE CHECK                   │
│   - Is there MANE Select?                │
│   - Returns: NM_000546.6                 │
│   - Highest confidence                   │
└──────────────────────────────────────────┘
            ↓
┌──────────────────────────────────────────┐
│ 3. GENBANK RETRIEVAL                     │
│   - Fetch all transcripts                │
│   - Find MANE/best transcript            │
│   - Extract CDS sequence                 │
└──────────────────────────────────────────┘
            ↓
OUTPUT: Actual DNA sequence
```

### Understanding the Challenge

When developing mRNA therapeutics, you need the exact DNA sequence that will be synthesized as therapeutic mRNA. However, genes have multiple names (CD31 vs PECAM1), and each gene can produce multiple transcript variants (isoforms). Selecting the wrong variant could result in a non-functional or immunogenic therapeutic. This tool solves both problems systematically.

### Step 1: HGNC Gene Name Resolution

**What is HGNC?**
The HUGO Gene Nomenclature Committee (HGNC) is the international authority responsible for approving unique symbols and names for human genes. Think of it as the "official registry" for human gene names, maintained by experts who ensure each gene has ONE official symbol.

**Scientific Reasoning:**
Gene nomenclature chaos is a major source of experimental errors. A single gene can have 10+ names in literature (e.g., CD31, PECAM-1, PECAM1, endoCAM, PECA1, GPIIA', CD31/EndoCAM). Without standardization, researchers risk:
- Ordering wrong reagents
- Missing critical literature
- Developing therapeutics for wrong targets
- Regulatory rejection due to nomenclature errors

**Why HGNC Matters for Therapeutics:**
- **Eliminates ambiguity:** The gene you know as "HER2" is officially "ERBB2". Without proper resolution, you might retrieve the wrong gene entirely.
- **Handles historical names:** Many genes have been renamed as science evolved. P53 became TP53, but both names persist in literature.
- **Resolves aliases:** CD31 is a widely-used name for PECAM1. HGNC knows all these relationships.
- **Provides Gene ID:** Links to NCBI's stable numerical identifier (e.g., 5175 for PECAM1)

**How It Works:**
1. You enter: "CD31" (common alias)
2. HGNC API searches across:
   - Current official symbols
   - Previous symbols (historical)
   - Alias symbols (alternative names)
   - Name synonyms
3. Returns: "PECAM1" (official symbol) + Gene ID 5175
4. Now we know EXACTLY which gene you want

**Real Examples:**
- CD31 → PECAM1 (platelet endothelial cell adhesion molecule)
- HER2 → ERBB2 (erb-b2 receptor tyrosine kinase 2)
- p53 → TP53 (tumor protein p53)
- IL-2 → IL2 (interleukin 2)
- VEGF → VEGFA (vascular endothelial growth factor A)

### Step 2: MANE Transcript Selection

**What is MANE?**
MANE (Matched Annotation from NCBI and EMBL-EBI) represents an unprecedented collaboration between the two largest genomic databases in the world - NCBI's RefSeq (USA) and EMBL-EBI's Ensembl (Europe). For years, these databases independently annotated human genes, often selecting different transcripts as "canonical." MANE resolves this by having experts from both organizations jointly agree on ONE transcript per gene.

**Scientific Reasoning:**
Transcript selection is NOT arbitrary. The wrong isoform can be:
- **Non-functional:** Missing critical domains (e.g., kinase domain in receptors)
- **Immunogenic:** Containing retained introns or nonsense-mediated decay signals
- **Unstable:** Lacking proper UTR elements for mRNA stability
- **Tissue-inappropriate:** Brain-specific isoform used for liver therapy

MANE transcripts are selected based on:
- Expression evidence (most abundant in most tissues)
- Conservation across species
- Protein functionality
- Clinical relevance
- Literature support

**Why MANE is Critical for Therapeutics:**
- **Consensus standard:** When NCBI and Ensembl agree, you can be confident this is THE transcript to use
- **Clinical relevance:** MANE transcripts are used by clinical laboratories for variant reporting
- **Regulatory alignment:** FDA submissions benefit from using consensus standards
- **Reduced risk:** Using MANE transcripts minimizes the chance of selecting a rare or artifactual variant

**The MANE Selection Process:**
1. For gene "PECAM1", check MANE database (~19,338 genes)
2. Database query returns:
   - MANE Select: NM_000442.5 (RefSeq) = ENST00000563921.5 (Ensembl)
   - Confidence: 1.0 (highest possible)
3. This means BOTH RefSeq and Ensembl experts agree
4. If MANE Select exists, STOP - use this transcript

**MANE Plus Clinical:**
Some genes have additional "MANE Plus Clinical" transcripts:
- Used for specific disease contexts
- Historically important in clinical testing
- Confidence: 0.98 (slightly lower than Select)

**MANE Coverage:**
- Currently covers ~19,000 human protein-coding genes
- ~95% of clinically relevant genes included
- For genes without MANE, tool falls back to other selection methods

### Step 3: GenBank Sequence Retrieval

**What is GenBank?**
GenBank is NCBI's comprehensive database of all publicly available DNA sequences. It contains the actual ATGC nucleotide sequences for every transcript.

**Scientific Reasoning:**
GenBank records contain more than just sequences - they include:
- **Feature annotations:** Exact CDS boundaries (start/stop positions)
- **Quality indicators:** RefSeq status, validation level
- **Cross-references:** Links to protein products, publications
- **Version history:** Sequence updates and corrections

**The Retrieval Process:**
1. Using PECAM1's Gene ID (5175), construct query:
   ```
   5175[Gene ID] AND refseq[filter] AND mRNA[filter]
   ```
2. Retrieve ALL available transcripts:
   - Typically 10-50 variants per gene
   - Each with different lengths, exon usage, UTRs
3. Parse each GenBank record to:
   - Check for MANE/RefSeq Select keywords
   - Extract CDS features
   - Verify start/stop codons
4. Match against MANE Select (NM_000442.5)
5. Extract CDS region:
   - Start: ATG (methionine)
   - End: TAA/TAG/TGA (stop codon)
   - Complete ORF validated

**Quality Checks Performed:**
- ✓ CDS length divisible by 3 (complete codons)
- ✓ Starts with ATG (or noted alternative)
- ✓ Ends with stop codon
- ✓ No internal stops (verified via translation)
- ✓ Matches expected protein length

**What You Get:**
- Actual DNA sequence: `ATGCCCAGCGGCAGCAGT...TGA`
- Length: 2217 base pairs for PECAM1 (738 amino acids + stop)
- Ready for codon optimization and mRNA synthesis
- Confidence score based on selection method

### Step 4: Fallback Selection Hierarchy

**When MANE Isn't Available:**
Not all genes have MANE annotation (~5% lack it). The tool implements a scientifically-grounded fallback hierarchy:

```
┌─────────────────────────────────────────────────┐
│         SELECTION HIERARCHY FLOWCHART           │
├─────────────────────────────────────────────────┤
│ 1. MANE Select? → Yes → Use (Confidence: 1.0)  │
│    ↓ No                                         │
│ 2. MANE Plus Clinical? → Yes → Use (0.98)      │
│    ↓ No                                         │
│ 3. RefSeq Select? → Yes → Use (0.95)           │
│    ↓ No                                         │
│ 4. UniProt Canonical? → Yes* → Use (0.75)      │
│    ↓ No (*simplified to longest ATG)           │
│ 5. Longest CDS with ATG? → Yes → Use (0.70)    │
│    ↓ No                                         │
│ 6. Most Recent Version → Use (0.50)            │
│    ↓ If multiple same length                    │
│ 7. First Available → Use (0.40) ⚠️              │
└─────────────────────────────────────────────────┘
```

**Scientific Justification for Each Level:**

1. **RefSeq Select (0.95):**
   - Manually curated by NCBI scientists
   - Reviewed for completeness and accuracy
   - Often matches CCDS (Consensus CDS) project

2. **UniProt Canonical Proxy (0.75):**
   - Since protein→mRNA mapping is complex
   - We use "longest ATG-starting transcript" as proxy
   - Rationale: Longest often = most complete protein

3. **Longest CDS (0.70):**
   - Biological principle: Evolution preserves functional length
   - Longer transcripts less likely to be truncated
   - Must start with ATG for reliable translation

4. **Non-ATG Handling (0.65):**
   - If longest starts with CTG/GTG (alternative starts)
   - Select longest ATG alternative instead
   - Non-ATG starts complicate therapeutic production

5. **Most Recent Version (0.50-0.60):**
   - Last resort: newest annotation may have corrections
   - Low confidence as this is arbitrary
   - Requires manual validation

6. **First Available (0.40):**
   - Emergency fallback only
   - Indicates algorithm failure
   - REQUIRES immediate manual review

## 🧪 Scientific Background for Canonical Isoform Selection

### Coding Sequences and Their Therapeutic Significance

A coding sequence (CDS) represents the portion of an mRNA transcript that is translated into protein, beginning with a start codon (typically ATG) and ending with a stop codon (TAA, TAG, or TGA). In the context of mRNA therapeutics, the selection of the appropriate CDS is paramount to therapeutic success. The CDS directly determines the amino acid sequence of the resulting protein, and even minor variations can significantly impact protein function, stability, and immunogenicity. For therapeutic applications, researchers must identify the most appropriate transcript variant—often called the canonical isoform—to ensure optimal therapeutic outcomes.

### Understanding Canonical Isoforms and Database Disagreements

The concept of a canonical isoform refers to the primary or reference transcript for a given gene, ideally representing the most functionally relevant variant for the intended therapeutic application. However, canonicity is not universally defined, and different authoritative databases often disagree. RefSeq Select, MANE Select (Matched Annotation from NCBI and EMBL-EBI), and UniProt canonical annotations may point to entirely different transcripts for the same gene. This disagreement reflects genuine scientific uncertainty rather than database error. In clinical dossiers, successful therapeutic developers typically justify their isoform choice through primary literature evidence, functional studies, and clinical precedent rather than deferring to a single database authority.

### The Complexity of Start Codon Selection

While ATG represents the canonical start codon recognized by standard translation machinery, alternative start codons (CTG, TTG, GTG) can produce functionally important protein variants. The extended VEGFA isoform initiated by CTG (leucine-VEGF or L-VEGF) exemplifies this complexity—it represents a legitimate biological entity with distinct functional properties. Therapeutic designers often prefer ATG-initiated forms for predictable expression and manufacturing consistency, but specific strategies may intentionally utilize non-ATG variants. For example, immuno-oncology applications targeting neoantigens or approaches emphasizing endogenous mimicry might deliberately select alternative start sites to recapitulate natural protein diversity.

### Evidence-Based Selection Hierarchy: A Beginner's Approach

This tool implements a simplified selection hierarchy that represents one reasonable approach to automated isoform selection, but it should not be mistaken for established best practice or community consensus. The algorithm prioritizes RefSeq Select transcripts when available, recognizing NCBI's expert curation process. In their absence, UniProt canonical annotations provide protein-focused guidance. For genes lacking these annotations, the algorithm applies biological filters: preferring ATG start codons over alternatives, and among functionally equivalent ATG-initiated transcripts, using length as a final tiebreaker.

This hierarchy reflects scientific reasoning but represents the author's interpretation rather than validated clinical standards. The preference for ATG start codons aims to ensure predictable translation, while the length criterion attempts to capture full-length coding potential. However, these heuristics can fail in complex cases where shorter isoforms are more physiologically relevant or where tissue-specific expression patterns override global abundance measures.

## 📊 Transparent Confidence Scoring System

| Score | Selection Method | Scientific Basis | Recommended Action |
|-------|------------------|------------------|-------------------|
| **1.00** | MANE Select | NCBI/EMBL-EBI expert consensus | ✅ Use directly for therapeutics |
| **0.98** | MANE Plus Clinical | Clinically validated alternative | ✅ Use with minimal validation |
| **0.95** | RefSeq Select | NCBI manual curation | ✅ Check selection rationale |
| **0.75** | UniProt Canonical (proxy) | Longest ATG transcript heuristic | ⚠️ Validate biological relevance |
| **0.70** | Longest CDS (ATG) | Size-based selection algorithm | ⚠️ Review alternative transcripts |
| **0.65** | Longest CDS (non-ATG avoided) | ATG preference over length | ⚠️ Check domain completeness |
| **0.60** | Most Recent / Equal length | Arbitrary tiebreaker | 🔍 Literature validation required |
| **0.50** | Most Recent (fallback) | No biological criteria met | 🔍 Manual curation essential |
| **0.40** | First Available | Algorithm failure | ❌ Do not use without review |

**Color Coding in Results:**
- 🟢 Green (≥0.90): High confidence - therapeutic grade
- 🟡 Yellow (0.70-0.89): Medium confidence - validate selection
- 🔴 Red (<0.70): Low confidence - manual review required

### Confidence Assessment: Automated Triage, Not Clinical Validation

The confidence scores generated by this tool represent an attempt to quantify selection certainty based on gene name matching quality and isoform selection method. These numeric values (0.5-1.0) provide internal triage capability but lack community validation or regulatory acceptance. The score bands (low/medium/high) are reasonable for initial screening but should not substitute for rigorous scientific evaluation.

As IBM's early computing pioneers observed, "A computer can never be held accountable, therefore a computer must never make a management decision." This principle applies directly to therapeutic isoform selection. While computational tools can accelerate initial screening and flag potential issues, the ultimate responsibility for isoform selection rests with experienced researchers who can integrate database annotations, literature evidence, and therapeutic context. The tool's warnings about non-ATG start codons, multiple equal-length transcripts, or low confidence scores should prompt immediate manual review rather than automated acceptance.

## 🔬 When to Override Automatic Selection

### Consider Manual Review If:

- Confidence score < 0.8
- Warning about non-ATG start codon
- Multiple equal-length transcripts
- Gene has known disease-relevant isoforms
- Target patient population has specific splice variants

### Validation Resources:

- **RefSeq:** Check for Select designation and CCDS support
- **MANE Select:** Cross-reference with matched annotation
- **UniProt:** Review canonical isoform rationale
- **GTEx:** Tissue-specific expression data
- **Literature:** PubMed for isoform-specific studies
- **Clinical Databases:** ClinVar for variant significance

### Tissue-Specific and Therapeutic Context Considerations

The concept of canonical isoforms becomes further complicated when considering tissue-specific expression patterns and therapeutic indications. For diseases with restricted tissue involvement, such as ornithine transcarbamylase deficiency affecting primarily hepatic function, the therapeutically relevant isoform should match the dominant transcript in the target tissue (liver) even if a different isoform ranks higher in pan-tissue databases. Similarly, certain patient populations may express disease-specific splice variants that become therapeutically relevant despite being globally minor.

## ⚙️ Advanced Options

Currently, all advanced options are integrated into the automatic workflow. HGNC handles all gene name resolution, making the previous UniProt First option obsolete.

## 🎯 Case Study Examples

**VEGFA:** Longest CDS (1239bp) starts with CTG → Tool selects shorter ATG-starting version (699bp) with warning. CTG start represents alternative translation initiation with different N-terminus that may have distinct functional properties.

**BRCA1:** Multiple transcripts with equal CDS length → Tool uses most recent version as tiebreaker, ensuring latest annotation updates.

## Implementation Limitations and Validation Requirements

This automated approach represents a starting point for isoform selection rather than a definitive solution. The algorithm cannot access tissue-specific expression data, incorporate recent literature findings, or evaluate disease-specific contexts. Experienced researchers should treat the tool's output as preliminary guidance requiring validation through multiple independent sources.

Critical validation steps include cross-referencing selections against multiple databases (RefSeq, MANE, UniProt, Ensembl), reviewing tissue-specific expression in GTEx or similar resources, examining functional studies in PubMed, and considering clinical precedents from ClinVar or therapeutic databases. For regulatory submissions, narrative justification supported by peer-reviewed evidence carries far more weight than algorithmic confidence scores.

## 🔍 Result Interpretation

- **✅ Green Rows:** Successful retrieval, ready for initial evaluation
- **❌ Red Rows:** Failed - check gene symbol or try synonyms
- **⚠️ Warnings:** Review needed - multiple transcripts or non-standard features
- **🔗 Gene URL:** Links to authoritative database records
- **📋 Full Name:** Verify correct gene identity

## 💊 mRNA Therapeutic Considerations

The selected CDS serves as the foundation for downstream therapeutic development. Codon optimization algorithms use the canonical sequence as their starting point, and improper isoform selection can cascade through the entire development process. Additionally, regulatory agencies expect therapeutic sequences to have clear scientific justification, with preference given to well-characterized, biologically relevant isoforms. The use of appropriate isoforms also facilitates comparison with existing literature and clinical data, supporting both safety assessments and mechanism-of-action studies.

## 📋 Recommended Test Genes

**Therapeutic Targets:** CFTR, F8, F9, GAA, IDUA  
**Oncology:** TP53, BRCA1, BRCA2, KRAS, EGFR  
**Immunotherapy:** CD19, CD20, PD1, PDL1  
**Complex Cases:** VEGFA, SERPINA1, PAH

## Honest Assessment of Tool Capabilities

This tool implements reasonable heuristics for initial isoform screening but should not be considered a replacement for expert scientific judgment. The selection algorithm reflects current understanding of transcript biology but cannot anticipate novel discoveries, unusual gene structures, or therapeutic-specific requirements. Users should approach the results with appropriate skepticism, particularly for complex genes, low confidence scores, or therapeutic applications where isoform choice has established clinical implications.

The ultimate goal is to accelerate the initial stages of therapeutic development while maintaining scientific rigor in final isoform selection. Researchers should view this tool as a starting point for investigation rather than an endpoint for decision-making.

---

**Remember:** This tool provides computational predictions. Always validate selections against current literature and regulatory guidance for your specific therapeutic application.