# Error Handling and Recovery

The NCBI GenBank Tool includes comprehensive error handling and recovery mechanisms to ensure reliable operation even in the face of network issues, API rate limits, and other failures.

## Features

### 1. Automatic Error Classification

The tool automatically classifies errors into categories:
- **Network Timeout**: Connection timeouts and network interruptions
- **API Rate Limit**: 429 errors and rate limiting
- **Invalid Gene Name**: Gene not found or invalid symbol
- **Database Error**: Database connection issues
- **Validation Error**: Input format or data validation failures
- **File I/O Error**: Permission or file access issues
- **Parse Error**: JSON/XML parsing failures

Each error type has specific recovery strategies and user-friendly suggestions.

### 2. Network Recovery

Resilient network handling with:
- Automatic retry with exponential backoff
- Connection health checking
- API-specific rate limiting
- Configurable timeout and retry settings

```bash
# The tool automatically handles network issues
genbank-tool genes.txt output.tsv

# Customize network behavior
genbank-tool genes.txt output.tsv --config network_config.json
```

### 3. Checkpoint/Resume Capability

For large batch operations, the tool saves progress automatically:

```bash
# Start a large batch (checkpoints saved automatically)
genbank-tool large_gene_list.txt output.tsv

# If interrupted, resume from checkpoint
genbank-tool --resume batch_1234567890 output.tsv

# Retry only failed items
genbank-tool --retry-failed batch_1234567890 output.tsv

# List available checkpoints
genbank-tool --list-checkpoints
```

### 4. Comprehensive Logging

Multiple log levels with detailed information:

```bash
# Enable verbose logging
genbank-tool genes.txt output.tsv --verbose

# Set specific log level
genbank-tool genes.txt output.tsv --log-level DEBUG

# Specify log directory
genbank-tool genes.txt output.tsv --log-dir ./my_logs
```

Log files include:
- `genbank_tool_YYYYMMDD.log`: General application logs
- `errors_YYYYMMDD.log`: Error-specific logs with stack traces

### 5. Error Reporting

Generate detailed error reports for analysis:

```bash
# Export error report after processing
genbank-tool genes.txt output.tsv --error-report error_analysis.json
```

The report includes:
- Error summary by type and severity
- Detailed error contexts with timestamps
- Recovery suggestions
- Processing statistics

## Configuration

### Error Handler Settings

Create a configuration file to customize error handling:

```json
{
  "error_handling": {
    "max_retries": 5,
    "enable_checkpoints": true,
    "checkpoint_interval": 10,
    "log_dir": ".genbank_logs",
    "checkpoint_dir": ".genbank_checkpoints"
  },
  "network": {
    "timeout": 60,
    "backoff_factor": 2.0,
    "retry_on_status": [408, 429, 500, 502, 503, 504]
  }
}
```

### API-Specific Settings

Configure different settings per API:

```json
{
  "api_configs": {
    "ncbi": {
      "timeout": 60,
      "max_retries": 5,
      "rate_limit_per_second": 3
    },
    "uniprot": {
      "timeout": 30,
      "max_retries": 3,
      "rate_limit_per_second": 10
    },
    "ensembl": {
      "timeout": 45,
      "max_retries": 4,
      "rate_limit_per_second": 15
    }
  }
}
```

## Usage Examples

### Basic Usage with Error Handling

```bash
# Process genes with automatic error handling
genbank-tool genes.txt output.tsv

# Enable checkpoint for large batches
genbank-tool large_list.txt output.tsv --checkpoint

# Quiet mode (only show errors)
genbank-tool genes.txt output.tsv --quiet
```

### Advanced Recovery Scenarios

```bash
# Resume interrupted processing
genbank-tool --resume batch_1234567890 output.tsv

# Retry failed items with increased timeout
genbank-tool --retry-failed batch_1234567890 output.tsv --config high_timeout.json

# Process with parallel workers and checkpoints
genbank-tool genes.txt output.tsv --parallel --workers 10 --checkpoint
```

### Monitoring and Debugging

```bash
# Real-time monitoring with verbose output
genbank-tool genes.txt output.tsv --verbose

# Debug mode with detailed logging
genbank-tool genes.txt output.tsv --log-level DEBUG

# Generate error report for analysis
genbank-tool genes.txt output.tsv --error-report analysis.json
```

## Error Recovery Strategies

### Network Timeouts
- Automatic retry with exponential backoff
- Wait for network connectivity restoration
- Fallback to cached data when available

### API Rate Limits
- Respect Retry-After headers
- Token bucket rate limiting
- Automatic throttling for sustained operation

### Invalid Gene Names
- Detailed error messages with suggestions
- Alternative gene symbol lookup
- Batch continuation despite individual failures

### Partial Failures
- Continue processing valid items
- Save failed items for retry
- Generate detailed failure reports

## Best Practices

1. **Use Checkpoints for Large Batches**
   - Enable checkpoints for lists > 50 genes
   - Checkpoints allow resuming without reprocessing

2. **Monitor Rate Limits**
   - Use API keys for higher rate limits
   - Configure appropriate rate limits per API
   - Monitor rate limit statistics in logs

3. **Handle Errors Gracefully**
   - Review error reports regularly
   - Adjust retry strategies based on error types
   - Use validation to catch issues early

4. **Optimize for Your Use Case**
   - Increase workers for I/O bound operations
   - Adjust timeouts for slow networks
   - Configure appropriate checkpoint intervals

## Troubleshooting

### Common Issues

1. **Persistent Network Failures**
   ```bash
   # Increase timeout and retries
   genbank-tool genes.txt output.tsv --config high_tolerance.json
   ```

2. **Rate Limit Errors**
   ```bash
   # Reduce parallel workers
   genbank-tool genes.txt output.tsv --workers 1
   
   # Add API key for higher limits
   export NCBI_API_KEY=your_key_here
   genbank-tool genes.txt output.tsv
   ```

3. **Checkpoint Corruption**
   ```bash
   # List and clean old checkpoints
   genbank-tool --list-checkpoints
   rm .genbank_checkpoints/corrupted_checkpoint.json
   ```

### Debug Information

When reporting issues, include:
1. Error report: `--error-report issue_report.json`
2. Debug logs: `--log-level DEBUG --log-dir debug_logs`
3. Checkpoint files if relevant
4. Configuration file used

## Performance Considerations

- Checkpoint saves have minimal overhead (~1ms)
- Error handling adds < 5% processing time
- Network recovery may extend total time based on failures
- Parallel processing with checkpoints scales linearly

## API Reference

See the [API documentation](api_reference.md) for detailed information about:
- ErrorHandler class
- NetworkRecoveryManager
- BatchProcessor
- Logging configuration