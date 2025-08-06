# 🧬 GenBank CDS Retrieval Tool

## What This Tool Does

This tool automates the retrieval of canonical coding sequences (CDS) from NCBI GenBank for mRNA therapeutic development. It resolves any gene name format to its official symbol, identifies the most therapeutically relevant transcript, and returns the complete CDS sequence ready for synthesis.

## Quick Start Guide

**Simply enter gene names in any format** (e.g., CD31, p53, HER2, IL-2) and click "🧬 Process Genes". The tool handles all nomenclature variations, case sensitivity, and hyphenation automatically.

**Review your results:** Green rows indicate high-confidence retrieval. Check the "Selection Method" column to understand how each transcript was chosen. Click any row for detailed sequence information.

**Export when ready:** Save results as TSV/Excel for downstream workflows.

## How It Works

**Gene Resolution → Transcript Selection → Sequence Retrieval**

The tool implements a four-stage pipeline:

1. **HGNC Resolution** - Converts any gene alias to its official symbol (e.g., CD31 → PECAM1)
2. **MANE Database Query** - Checks for expert-consensus transcripts (~19,000 genes covered)  
3. **GenBank Retrieval** - Fetches all transcript variants and their CDS regions
4. **Intelligent Selection** - Applies evidence-based hierarchy to select the most appropriate isoform

## Transcript Selection Hierarchy

When multiple transcript variants exist, the tool applies this evidence-based selection order:

| Priority | Method | Confidence | Description |
|----------|--------|------------|-------------|
| 1 | MANE Select | 1.00 | NCBI/EMBL-EBI consensus standard |
| 2 | MANE Plus Clinical | 0.98 | Clinically validated alternatives |
| 3 | RefSeq Select | 0.95 | NCBI manually curated |
| 4 | Longest ATG transcript | 0.75 | Proxy for canonical when databases unavailable |
| 5 | Longest CDS | 0.70 | Size-based heuristic |
| 6 | First available | 0.40 | Emergency fallback (requires review) |

**Confidence scores ≥0.90 are therapeutic-grade.** Lower scores indicate manual validation is recommended.

## Scientific Background

**The Challenge:** Genes have multiple names and produce multiple transcript variants (isoforms). Selecting the wrong variant for mRNA therapeutics can result in non-functional or immunogenic products.

**The Solution:** This tool systematically resolves gene nomenclature through HGNC (the international authority for gene names) and selects transcripts using MANE (Matched Annotation from NCBI and EMBL-EBI), which represents unprecedented consensus between the world's two largest genomic databases.

**Key Databases:**
- **HGNC** - Resolves all gene aliases to official symbols
- **MANE** - Provides expert-consensus transcript selection for ~19,000 genes
- **RefSeq** - NCBI's curated reference sequences
- **GenBank** - Comprehensive repository of all DNA sequences

## Important Considerations

**Start Codon Preferences:** The tool prioritizes ATG start codons for predictable translation, though alternative starts (CTG, GTG) exist in nature.

**UniProt Canonical Proxy:** Direct UniProt canonical detection is not implemented. The tool uses "longest ATG-starting transcript" as a simplified proxy.

**Manual Review Recommended When:**
- Confidence score < 0.8
- Non-ATG start codon warnings appear
- Multiple equal-length transcripts exist
- Working with tissue-specific or disease-relevant isoforms

## Test Genes for Validation

**Therapeutic Targets:** CFTR, F8, F9, GAA, IDUA  
**Oncology:** TP53, BRCA1, BRCA2, KRAS, EGFR  
**Immunotherapy:** CD19, CD20, PD1, PDL1  
**Complex Cases:** VEGFA (non-ATG starts), SERPINA1, PAH

---

## About This Tool

**Developed by:** Austin P. Morrissey  
**Date:** August 6, 2025  
**License:** MIT - Please use however you'd like

**This is a demonstration of "vibe coding" - showing the untapped utility of computational tools for the life sciences.**

I'm particularly interested in learning science from others and happy to collaborate on tasks. If you have something to teach and think it can be automated but don't know how, I'll help in exchange for you teaching me something from your domain.

**Contact:** austin.morrissey@proton.me

---

*Interested in AI safety? Check out [The AI Safety Book](https://www.aisafetybook.com/) - essential reading for understanding how to build beneficial AI systems.*
