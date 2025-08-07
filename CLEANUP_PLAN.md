# Constitutional.seq Repository Cleanup Plan

## Project Structure Analysis

### Current State Overview
The repository contains a mix of:
- Active production code
- Multiple redundant CLI implementations
- Test output files scattered in root
- Demo/example files
- Documentation files
- Cache directories
- Configuration files

## Files to REMOVE (Not needed in repo)

### Test Output Files (Root Directory)
These are test outputs that shouldn't be tracked in git:
```
test_output.tsv
test_output.audit.json
test_output_complete.tsv
test_output_complete.audit.json
test_output_final.tsv
test_output_final.audit.json
test_output_final_fixed.tsv
test_output_final_fixed.audit.json
test_output_new.tsv
test_output_new.audit.json
test_output_uniprot.tsv
test_output_uniprot.audit.json
test_output_validated.tsv
test_output_validated.audit.json
test_problematic_output.tsv
test_problematic_output.audit.json
pax6_output.tsv
pax6_output2.tsv
pax6_enhanced.tsv
pax6_enhanced_output.tsv
multi_genes_output.tsv
multiple_output.tsv
canonical_output.tsv
threshold_output.tsv
threshold_multi_output.tsv
genbank_results1.tsv
genbank_results1.audit.json
BIMBAM.EXCEL.xlsx
BIMBAM.EXCEL.audit.json
```

### Test Input Files (Root Directory)
```
test_genes.txt
test_uniprot_gene.txt
test_problematic.txt
pax6_only.txt
```

### Demo Files (Can be moved to examples/)
```
demo_recorder.py
simple_demo.py
auto_demo.py
create_demo.py
```

### Generated/Cache Directories
These should be in .gitignore:
```
.genbank_cache/
.genbank_checkpoints/
.genbank_gui_logs/
.genbank_logs/
cache/
.coverage
.ruff_cache/
.pytest_cache/
__pycache__/
build/
venv/
node_modules/
```

## Files to CONSOLIDATE

### Duplicate CLI Files
Currently have 4 CLI implementations:
1. `cli.py` - Legacy basic CLI
2. `cli_with_error_handling.py` - Main production CLI (487 lines)
3. `cli_enhanced.py` - Enhanced version (344 lines)
4. `cli_old.py` - Old version (241 lines)

**Recommendation**: Keep only `cli_with_error_handling.py` as main, archive others

### Redundant Files
- `src/genbank_tool/gui_app.py` - Small wrapper, functionality in `gui/main_window.py`
- Multiple test outputs with similar names

## Files to KEEP/ORGANIZE

### Core Code Structure (src/genbank_tool/)
```
✅ __init__.py
✅ batch_processor.py - Batch processing functionality
✅ cache_manager.py - Cache management
✅ cli_with_error_handling.py - Main CLI (rename to cli.py)
✅ cli_utils.py - CLI utilities
✅ config.py - Configuration management
✅ data_validator.py - Data validation
✅ error_handler.py - Error handling
✅ gene_resolver.py - Gene resolution logic
✅ hgnc_resolver.py - HGNC integration
✅ input_parser.py - Input parsing
✅ logging_config.py - Logging configuration
✅ mane_database.py - MANE database integration
✅ mane_selector.py - MANE selection logic
✅ models.py - Data models
✅ network_recovery.py - Network error recovery
✅ output_formatter.py - Output formatting
✅ parallel_processor.py - Parallel processing
✅ rate_limiter.py - API rate limiting
✅ sequence_retriever.py - Sequence retrieval
✅ transcript_selector.py - Transcript selection logic
✅ uniprot_canonical.py - UniProt canonical mapping
✅ uniprot_downloader.py - UniProt data download
✅ uniprot_features.py - UniProt features
```

### GUI Module (src/genbank_tool/gui/)
```
✅ __init__.py
✅ main_window.py - Main GUI window
✅ cache_dialog.py - Cache management dialog
✅ settings_dialog.py - Settings dialog
```

### Documentation
```
✅ README.md - Main documentation
✅ LICENSE - MIT License
✅ docs/error_handling.md - Error handling guide
✅ docs/gui_features.md - GUI features documentation
✅ docs/gui_guide.md - GUI user guide
❌ CODE_REVIEW_REPORT.md - Move to docs/ or remove
❌ DATA_FLOW_ARCHITECTURE.md - Move to docs/
❌ DATA_FLOW_DIAGRAM.md - Move to docs/
```

### Configuration Files
```
✅ pyproject.toml - Package configuration
✅ requirements.txt - Python dependencies
✅ .gitignore - Git ignore rules
✅ .env.example - Environment variable template
✅ genbank.config.example.json - Config example
❌ .env - Should not be in repo (add to .gitignore)
```

### Task Master Files
```
✅ .taskmaster/ - Task management
✅ CLAUDE.md - Claude Code instructions
✅ .claude/ - Claude Code configuration
✅ .mcp.json - MCP configuration
```

### Package Files
```
❌ package.json - Not needed (Node.js file in Python project)
❌ package-lock.json - Not needed
```

## Recommended .gitignore Updates

Add these patterns:
```gitignore
# Test outputs
*.tsv
*.audit.json
test_*.txt

# Cache and temporary files
.genbank_cache/
.genbank_checkpoints/
.genbank_gui_logs/
.genbank_logs/
cache/
*.cache

# Environment
.env
venv/
.venv/

# IDE
.cursor/
.vscode/
.idea/

# Python
__pycache__/
*.py[cod]
*$py.class
.coverage
.pytest_cache/
.ruff_cache/
htmlcov/
dist/
build/
*.egg-info/

# Node (if needed for TaskMaster)
node_modules/

# OS
.DS_Store
Thumbs.db
```

## Proposed New Structure

```
constitutional-seq/
├── src/
│   └── genbank_tool/
│       ├── core/           # Core functionality
│       │   ├── gene_resolver.py
│       │   ├── sequence_retriever.py
│       │   ├── transcript_selector.py
│       │   └── data_validator.py
│       ├── integrations/   # External service integrations
│       │   ├── hgnc_resolver.py
│       │   ├── mane_database.py
│       │   ├── uniprot_canonical.py
│       │   └── ncbi_client.py
│       ├── utils/          # Utilities
│       │   ├── cache_manager.py
│       │   ├── error_handler.py
│       │   ├── logging_config.py
│       │   └── rate_limiter.py
│       ├── cli/            # CLI interface
│       │   ├── main.py (renamed from cli_with_error_handling.py)
│       │   └── utils.py
│       ├── gui/            # GUI interface
│       │   ├── main_window.py
│       │   ├── cache_dialog.py
│       │   └── settings_dialog.py
│       └── __init__.py
├── tests/                  # All test files
├── docs/                   # All documentation
│   ├── architecture/
│   │   ├── data_flow.md
│   │   └── system_design.md
│   ├── guides/
│   │   ├── error_handling.md
│   │   ├── gui_guide.md
│   │   └── cli_guide.md
│   └── api/
├── examples/              # Example scripts and data
│   ├── demo_scripts/
│   └── sample_data/
├── scripts/               # Utility scripts
├── README.md
├── LICENSE
├── pyproject.toml
├── requirements.txt
├── .gitignore
└── .env.example
```

## Action Items

### Immediate Actions
1. **Delete all test output files** from root directory
2. **Update .gitignore** with comprehensive patterns
3. **Remove .env** from repository
4. **Delete redundant CLI files** (keep only main one)
5. **Move documentation files** to docs/ directory

### Short-term Actions
1. **Reorganize src/ structure** into logical modules
2. **Move demo scripts** to examples/
3. **Clean up package.json** and node_modules (verify if needed)
4. **Create proper examples directory** with sample data

### Long-term Actions
1. **Refactor imports** after reorganization
2. **Update tests** to match new structure
3. **Update documentation** to reflect new organization
4. **Create API documentation** from docstrings

## Benefits of Cleanup

1. **Cleaner repository** - No test outputs or temporary files
2. **Better organization** - Logical grouping of related functionality
3. **Easier maintenance** - Clear separation of concerns
4. **Improved onboarding** - New developers can understand structure
5. **Reduced confusion** - No duplicate/redundant files
6. **Professional appearance** - Well-organized scientific tool

## Git Commands for Cleanup

```bash
# Remove test output files (careful with wildcards!)
git rm test_*.tsv test_*.audit.json
git rm pax6_*.tsv
git rm *_output.tsv *_output.audit.json
git rm BIMBAM.EXCEL.*

# Remove test input files
git rm test_*.txt pax6_only.txt

# Remove redundant CLI files
git rm src/genbank_tool/cli.py
git rm src/genbank_tool/cli_old.py
git rm src/genbank_tool/cli_enhanced.py

# Remove .env (should never be in repo)
git rm --cached .env

# Move documentation
mkdir -p docs/architecture
git mv DATA_FLOW_*.md docs/architecture/
git mv CODE_REVIEW_REPORT.md docs/

# Move demos to examples
mkdir -p examples/demo_scripts
git mv *_demo.py examples/demo_scripts/
git mv create_demo.py examples/demo_scripts/
```