"""Enhanced CLI with comprehensive error handling and logging."""

import sys
from pathlib import Path

import click

from .batch_processor import BatchProcessor
from .cache_manager import CacheManager
from .cli_utils import echo
from .config import Config, get_default_config_path, create_example_config
from .data_validator import DataValidator
from .error_handler import setup_error_handler, get_error_handler, ErrorType
from .gene_resolver import GeneResolver
from .input_parser import InputParser
from .logging_config import setup_logging, ProgressLogger, get_logger
from .network_recovery import get_recovery_manager
from .output_formatter import OutputFormatter
from .parallel_processor import ParallelProcessor
from .rate_limiter import configure_rate_limit
from .sequence_retriever import SequenceRetriever

logger = get_logger('cli')


def process_gene(gene_name: str, resolver, retriever, validator, cfg, prefer_transcript=None):
    """Process a single gene with error handling."""
    error_handler = get_error_handler()
    
    try:
        # Resolve gene name
        resolved = resolver.resolve(gene_name)
        
        if not resolved:
            error_handler.handle_error(
                ValueError(f"Gene name not resolved: {gene_name}"),
                operation="gene_resolution",
                item_id=gene_name,
                error_type=ErrorType.INVALID_GENE_NAME
            )
            return {
                'input_name': gene_name,
                'error': 'Gene name not resolved'
            }
        
        # Get sequences
        if cfg.selection.canonical_only:
            selection = retriever.get_canonical_transcript(
                resolved.official_symbol,
                resolved.gene_id,
                user_preference=prefer_transcript
            )
            
            if not selection:
                return {
                    'input_name': gene_name,
                    'error': 'No sequences found'
                }
            
            best_seq = selection.transcript
        else:
            sequences = retriever.retrieve_by_gene_id(resolved.official_symbol, resolved.gene_id)
            
            if not sequences:
                return {
                    'input_name': gene_name,
                    'error': 'No sequences found'
                }
            
            best_seq = sequences[0]
            selection = None
        
        # Validate if requested
        validation_result = None
        if validator:
            validation_result = validator.validate_sequence(best_seq, resolved.official_symbol)
        
        return {
            'input_name': gene_name,
            'sequence': best_seq,
            'selection': selection,
            'validation': validation_result
        }
        
    except Exception as e:
        context = error_handler.handle_error(
            e,
            operation="process_gene",
            item_id=gene_name
        )
        
        return {
            'input_name': gene_name,
            'error': context.suggestion or str(e)
        }


@click.command()
@click.argument('input_file', type=click.Path(exists=True), required=False)
@click.argument('output_file', type=click.Path(), required=False)
@click.option('--api-key', envvar='NCBI_API_KEY', help='NCBI API key for increased rate limits')
@click.option('--email', envvar='EMAIL', default='user@example.com', help='Email for NCBI')
@click.option('--no-cache', is_flag=True, help='Disable caching')
@click.option('--clear-cache', is_flag=True, help='Clear cache before processing')
@click.option('--cache-stats', is_flag=True, help='Show cache statistics')
@click.option('--test-genes', is_flag=True, help='Test with sample genes')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--quiet', '-q', is_flag=True, help='Suppress all output except errors')
@click.option('--canonical/--all-transcripts', default=True, help='Select canonical transcript only')
@click.option('--prefer-transcript', help='Preferred transcript accession (e.g., NM_001234)')
@click.option('--validate/--no-validate', default=False, help='Validate sequences against databases')
@click.option('--strict-validation', is_flag=True, help='Treat validation warnings as errors')
@click.option('--output-format', type=click.Choice(['tsv', 'csv', 'json', 'excel']), default='tsv', help='Output file format')
@click.option('--no-audit', is_flag=True, help='Disable audit trail generation')
@click.option('--encoding', help='Input file encoding (auto-detected if not specified)')
@click.option('--delimiter', help='CSV delimiter (auto-detected if not specified)')
@click.option('--config', type=click.Path(exists=True), help='Configuration file path')
@click.option('--generate-config', is_flag=True, help='Generate example configuration file')
@click.option('--parallel/--sequential', default=True, help='Use parallel processing')
@click.option('--workers', type=int, default=5, help='Number of parallel workers')
@click.option('--chunk-size', type=int, help='Process genes in chunks (for large batches)')
@click.option('--checkpoint/--no-checkpoint', default=True, help='Enable checkpoint/resume capability')
@click.option('--resume', help='Resume from checkpoint ID')
@click.option('--retry-failed', help='Retry failed items from checkpoint ID')
@click.option('--list-checkpoints', is_flag=True, help='List available checkpoints')
@click.option('--log-dir', default='.genbank_logs', help='Directory for log files')
@click.option('--log-level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']), default='INFO', help='Logging level')
@click.option('--error-report', help='Export error report to file')
def main(input_file, output_file, api_key, email, no_cache, clear_cache, cache_stats, test_genes, verbose, quiet, 
         canonical, prefer_transcript, validate, strict_validation, output_format, no_audit, encoding, delimiter, 
         config, generate_config, parallel, workers, chunk_size, checkpoint, resume, retry_failed, list_checkpoints,
         log_dir, log_level, error_report):
    """Enhanced NCBI GenBank CDS Retrieval Tool with error handling and recovery.
    
    Retrieve CDS sequences from NCBI GenBank for gene names with comprehensive error handling.
    
    Examples:
        genbank-tool genes.txt output.tsv
        genbank-tool genes.txt output.tsv --parallel --workers 10
        genbank-tool --resume batch_1234567890 output.tsv
        genbank-tool --retry-failed batch_1234567890 output.tsv
    """
    # Setup logging
    if quiet and verbose:
        click.echo("Error: Cannot use both --quiet and --verbose", err=True)
        sys.exit(1)
    
    loggers = setup_logging(
        log_level=log_level if not verbose else 'DEBUG',
        log_dir=log_dir,
        quiet=quiet,
        colors=True
    )
    
    # Setup error handler
    error_handler = setup_error_handler(
        log_dir=log_dir,
        enable_checkpoints=checkpoint,
        max_retries=3
    )
    
    # Handle config generation
    if generate_config:
        config_path = create_example_config()
        echo(f"Generated example configuration file: {config_path}")
        sys.exit(0)
    
    # Handle checkpoint listing
    if list_checkpoints:
        batch_processor = BatchProcessor(
            checkpoint_dir=".genbank_checkpoints",
            enable_checkpoints=True
        )
        checkpoints = batch_processor.list_checkpoints()
        
        if checkpoints:
            echo("\nAvailable checkpoints:")
            for cp in checkpoints:
                echo(f"  {cp['batch_id']}")
                echo(f"    Created: {cp['timestamp']}")
                echo(f"    Progress: {cp['processed']}/{cp['total_items']} processed, {cp['failed']} failed")
                echo(f"    File: {cp['file']}")
        else:
            echo("No checkpoints found")
        
        sys.exit(0)
    
    # Handle error report export
    if error_report:
        error_handler.export_error_report(error_report)
        echo(f"Error report exported to: {error_report}")
        if not input_file and not test_genes and not resume and not retry_failed:
            sys.exit(0)
    
    # Load configuration
    if config:
        config_path = Path(config)
    else:
        config_path = get_default_config_path()
    
    cfg = Config.from_file(config_path)
    cfg.merge_env_vars()
    cfg.merge_cli_args(
        api_key=api_key,
        email=email,
        no_cache=no_cache,
        canonical=canonical,
        validate=validate,
        strict_validation=strict_validation,
        output_format=output_format,
        no_audit=no_audit
    )
    
    # Initialize cache manager
    cache_manager = CacheManager(
        cache_dir=cfg.cache.directory,
        max_size_mb=cfg.cache.max_size_mb
    )
    
    # Handle cache operations
    if clear_cache:
        cleared = cache_manager.clear()
        echo(f"Cleared {cleared} cache entries")
    
    if cache_stats:
        stats = cache_manager.get_stats()
        size_info = cache_manager.get_size_info()
        
        echo("\nCache Statistics:")
        echo(f"  Total entries: {stats.total_entries}")
        echo(f"  Total size: {size_info['total_size_mb']:.2f} MB")
        echo(f"  Hit rate: {stats.hit_rate:.1%}")
        echo(f"  Hits: {stats.hit_count}, Misses: {stats.miss_count}")
        echo(f"  Expired: {stats.expired_count}, Evicted: {stats.evicted_count}")
        
        if size_info['namespaces']:
            echo("\n  By namespace:")
            for ns, info in size_info['namespaces'].items():
                echo(f"    {ns}: {info['count']} entries, {info['size_mb']:.2f} MB")
        
        if not input_file and not test_genes and not resume and not retry_failed:
            sys.exit(0)
    
    # Configure rate limiting
    ncbi_rate = cfg.api.rate_limit_per_second
    if cfg.api.ncbi_api_key:
        ncbi_rate = 10  # With API key
    
    configure_rate_limit('ncbi', ncbi_rate)
    configure_rate_limit('uniprot', 10)  # UniProt allows 10 req/s
    configure_rate_limit('ensembl', 15)  # Ensembl allows 15 req/s
    
    # Handle test mode
    if test_genes:
        test_gene_list = ['VEGF', 'TP53', 'BRCA1', 'EGFR', 'KRAS']
        echo(f"Testing with genes: {', '.join(test_gene_list)}")
        genes = test_gene_list
    elif input_file:
        # Use InputParser to read genes from file
        parser = InputParser()
        try:
            genes = parser.parse_file(input_file, encoding=encoding, delimiter=delimiter)
            format_info = parser.get_format_info()
            echo(f"Read {len(genes)} genes from {input_file} (format: {format_info['format']})")
        except Exception as e:
            error_handler.handle_error(
                e,
                operation="parse_input_file",
                error_type=ErrorType.FILE_IO_ERROR
            )
            echo(f"ERROR: Failed to parse input file: {e}", err=True)
            sys.exit(1)
    elif resume or retry_failed:
        # Will load genes from checkpoint
        genes = []
    else:
        # Show help if no input
        ctx = click.get_current_context()
        echo(ctx.get_help())
        return
    
    # Initialize components
    resolver = GeneResolver(
        api_key=cfg.api.ncbi_api_key,
        cache_enabled=cfg.cache.enabled
    )
    retriever = SequenceRetriever(
        api_key=cfg.api.ncbi_api_key,
        email=cfg.api.email,
        cache_enabled=cfg.cache.enabled
    )
    validator = DataValidator(
        validate_cross_refs=cfg.validation.cross_reference,
        strict_mode=cfg.validation.strict_mode
    ) if cfg.validation.enabled else None
    formatter = OutputFormatter(include_audit_trail=cfg.output.include_audit_trail)
    
    # Process genes
    echo("\nProcessing genes...")
    
    if checkpoint and (resume or retry_failed or len(genes) > 50):
        # Use batch processor with checkpoints
        batch_processor = BatchProcessor(
            checkpoint_dir=".genbank_checkpoints",
            enable_checkpoints=True,
            checkpoint_interval=10,
            max_workers=workers if parallel else 1
        )
        
        def process_func(gene_name):
            return process_gene(gene_name, resolver, retriever, validator, cfg, prefer_transcript)
        
        def on_error(gene_name, error):
            logger.error(f"Failed to process {gene_name}: {error}")
        
        if retry_failed:
            # Retry failed items
            echo(f"Retrying failed items from checkpoint: {retry_failed}")
            results_dict, checkpoint_data = batch_processor.retry_failed_items(
                retry_failed,
                process_func,
                genes,
                item_id_func=lambda x: x
            )
        else:
            # Normal processing or resume
            results_dict, checkpoint_data = batch_processor.process_batch(
                genes,
                process_func,
                batch_id=None,
                resume_from_checkpoint=resume,
                item_id_func=lambda x: x,
                on_error=on_error,
                metadata={
                    'config': cfg.to_dict(),
                    'command': ' '.join(sys.argv)
                }
            )
        
        # Format results
        results = []
        for gene_name, gene_result in results_dict.items():
            if isinstance(gene_result, dict):
                result = formatter.format_sequence_result(
                    input_name=gene_result.get('input_name', gene_name),
                    sequence=gene_result.get('sequence'),
                    selection=gene_result.get('selection'),
                    validation=gene_result.get('validation'),
                    error=gene_result.get('error')
                )
            else:
                result = formatter.format_sequence_result(
                    input_name=gene_name,
                    error='Processing failed'
                )
            results.append(result)
        
        echo(f"\nProcessing complete: {len(checkpoint_data.processed_items)}/{checkpoint_data.total_items} successful")
        if checkpoint_data.failed_items:
            echo(f"Failed items: {len(checkpoint_data.failed_items)}")
            echo(f"Checkpoint ID for retry: {checkpoint_data.batch_id}")
        
    elif parallel and len(genes) > 1:
        # Parallel processing without checkpoints
        echo(f"Using parallel processing with {workers} workers")
        
        def process_func(gene_name):
            return process_gene(gene_name, resolver, retriever, validator, cfg, prefer_transcript)
        
        processor = ParallelProcessor(
            max_workers=workers,
            rate_limit_api='ncbi'
        )
        
        processing_results, stats = processor.process_batch(
            genes,
            process_func,
            chunk_size=chunk_size
        )
        
        # Format results
        results = []
        for proc_result in processing_results:
            if proc_result.success and proc_result.result:
                gene_result = proc_result.result
                result = formatter.format_sequence_result(
                    input_name=gene_result['input_name'],
                    sequence=gene_result.get('sequence'),
                    selection=gene_result.get('selection'),
                    validation=gene_result.get('validation'),
                    error=gene_result.get('error')
                )
            else:
                result = formatter.format_sequence_result(
                    input_name=proc_result.item,
                    error=str(proc_result.error) if proc_result.error else 'Unknown error'
                )
            results.append(result)
        
        echo(f"\nProcessing complete: {stats.successful}/{stats.total_items} successful")
        
    else:
        # Sequential processing
        results = []
        progress = ProgressLogger(logger, len(genes), "Processing genes")
        
        for gene_name in genes:
            if verbose:
                echo(f"\nProcessing: {gene_name}")
            
            gene_result = process_gene(gene_name, resolver, retriever, validator, cfg, prefer_transcript)
            
            result = formatter.format_sequence_result(
                input_name=gene_result['input_name'],
                sequence=gene_result.get('sequence'),
                selection=gene_result.get('selection'),
                validation=gene_result.get('validation'),
                error=gene_result.get('error')
            )
            results.append(result)
            
            progress.update(success='error' not in gene_result, item=gene_name)
        
        progress.complete()
    
    # Clean up
    cache_manager.cleanup_expired()
    error_handler.cleanup_old_checkpoints()
    get_recovery_manager().close_all()
    
    # Output results
    echo(f"\n\nWriting results...")
    
    if output_file:
        # Use OutputFormatter to write results
        try:
            formatter.format_results(
                results,
                output_file,
                format=cfg.output.format,
                excel_compatible=cfg.output.excel_compatible
            )
            echo(f"Results written to: {output_file}")
            
            if cfg.output.include_audit_trail:
                audit_path = Path(output_file).with_suffix('.audit.json')
                echo(f"Audit trail written to: {audit_path}")
        except Exception as e:
            error_handler.handle_error(
                e,
                operation="write_output",
                error_type=ErrorType.FILE_IO_ERROR
            )
            echo(f"ERROR: Failed to write output file: {e}", err=True)
            sys.exit(1)
    else:
        # Display summary
        stats = formatter.get_statistics()
        echo("\n" + "=" * 80)
        echo(f"Processed {stats['total_processed']} genes")
        echo(f"Successful: {stats['successful']}")
        echo(f"Failed: {stats['failed']}")
        echo(f"Duration: {stats['duration']}")
        
        # Show error summary
        error_summary = error_handler.get_error_summary()
        if error_summary['total_errors'] > 0:
            echo(f"\nErrors encountered: {error_summary['total_errors']}")
            echo("Error types:")
            for error_type, count in error_summary['by_type'].items():
                echo(f"  {error_type}: {count}")
            
            if verbose and error_summary['recent_errors']:
                echo("\nRecent errors:")
                for err in error_summary['recent_errors']:
                    echo(f"  [{err['timestamp']}] {err['type']}: {err['message']}")
                    if err['suggestion']:
                        echo(f"    Suggestion: {err['suggestion']}")
        
        # Show final cache stats if verbose
        if verbose:
            final_stats = cache_manager.get_stats()
            echo(f"\nCache performance: {final_stats.hit_rate:.1%} hit rate "
                 f"({final_stats.hit_count} hits, {final_stats.miss_count} misses)")


if __name__ == '__main__':
    main()