# Constitutional.seq GUI Guide

Constitutional.seq includes a modern graphical user interface built with PyQt5, providing an intuitive way to retrieve canonical CDS sequences for mRNA therapeutics without using the command line.

## Launching the GUI

After installation, launch the GUI using:

```bash
genbank-tool-gui
```

Or run directly:
```bash
python -m genbank_tool.gui_app
```

## Main Features

### 1. Gene Input Panel
- **Text Area**: Enter gene names directly (one per line)
- **File Loading**: Click "Load from File" to import gene lists
- **Drag & Drop**: Drag text files directly onto the input area
- **Gene Counter**: Shows the total number of genes to process

### 2. Results Table
- **Comprehensive View**: Shows all retrieved sequences with metadata
- **Color Coding**: Green for successful retrievals, red for errors
- **Sortable Columns**: Click headers to sort by any field
- **Selection**: Click any row to view the full sequence

### 3. Sequence Viewer
- **Formatted Display**: Shows sequences in FASTA-like format
- **Metadata**: Includes accession, version, length, and selection method
- **Copy Support**: Select and copy sequences for use elsewhere

### 4. Error Log
- **Detailed Errors**: Shows timestamped error messages
- **Troubleshooting**: Helps identify problematic gene names

## Toolbar Options

### Quick Settings
- **Canonical Only**: Toggle canonical transcript selection
- **Validate**: Enable/disable sequence validation
- **Workers**: Adjust parallel processing (1-10 workers)

### Actions
- **Process Genes**: Start retrieving sequences
- **Stop**: Cancel ongoing processing

## Menu Options

### File Menu
- **Open Gene List**: Load genes from file
- **Save Results**: Export results in various formats
- **Exit**: Close the application

### Edit Menu
- **Clear Input**: Remove all input genes
- **Clear Results**: Clear the results table

### Tools Menu
- **Settings**: Configure API keys, processing options, and network settings
- **Manage Cache**: View cache statistics and clear cached data

## Settings Dialog

### API Settings Tab
- **NCBI API Key**: Optional key for increased rate limits
- **Email**: Required for NCBI E-utilities
- **UniProt Fallback**: Enable UniProt as backup source
- **Confidence Threshold**: Minimum confidence for gene resolution

### Processing Tab
- **Canonical Selection**: Choose canonical transcripts only
- **Validation**: Enable sequence validation
- **Workers**: Maximum parallel processing threads
- **Output Format**: Default export format

### Cache Tab
- **Enable Cache**: Toggle caching on/off
- **Cache Directory**: Location of cache files
- **Max Size**: Maximum cache size in MB
- **Expiration**: How long to keep cached data

### Network Tab
- **Timeout**: Request timeout in seconds
- **Max Retries**: Retry attempts for failed requests
- **Rate Limits**: Configure API rate limiting

## Export Options

Results can be exported in multiple formats:
- **TSV**: Tab-separated values (Excel-compatible)
- **CSV**: Comma-separated values
- **Excel**: Native Excel format (.xlsx)
- **JSON**: Structured JSON format

## Tips for Best Performance

1. **Use API Keys**: Add your NCBI API key in settings for 10x higher rate limits
2. **Batch Processing**: Process multiple genes at once for efficiency
3. **Enable Caching**: Keep cache enabled to avoid redundant API calls
4. **Monitor Progress**: Watch the progress bar and status messages
5. **Check Errors**: Review the error log for failed genes

## Keyboard Shortcuts

- `Ctrl+O`: Open gene list file
- `Ctrl+S`: Save results
- `Ctrl+Q`: Quit application

## Troubleshooting

### Common Issues

1. **"No API Key" Warning**
   - Add your NCBI API key in Settings → API Settings
   - Without a key, you're limited to 3 requests/second

2. **Network Timeouts**
   - Increase timeout in Settings → Network
   - Check your internet connection
   - Try reducing the number of workers

3. **Gene Not Found**
   - Check gene name spelling
   - Try official gene symbols instead of aliases
   - Enable UniProt fallback in settings

4. **Rate Limit Errors**
   - Reduce the number of parallel workers
   - Add an NCBI API key
   - Wait a few minutes before retrying

### Cache Management

The cache dialog shows:
- Total cached entries and size
- Cache hit rate (higher is better)
- Breakdown by data type
- Options to clean expired entries or clear all

## Advanced Features

### Checkpoint Recovery
While the GUI doesn't directly expose checkpoint functionality, processing is resilient:
- Results are updated in real-time
- You can export partial results at any time
- Failed genes are clearly marked for retry

### Validation Warnings
When validation is enabled, the GUI will show:
- Missing start codons (ATG)
- Missing stop codons
- Internal stop codons
- Sequences not divisible by 3

## System Requirements

- Python 3.8 or higher
- PyQt5 5.15 or higher
- At least 100MB free disk space for cache
- Internet connection for API access
- 1024x768 minimum screen resolution

## Data Privacy

- API keys are stored locally in your system's settings
- No data is sent to external servers except NCBI/UniProt APIs
- Cache files are stored locally and never uploaded
- All processing happens on your local machine