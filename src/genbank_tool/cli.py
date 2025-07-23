"""Command-line interface for the NCBI GenBank tool."""

import logging
import sys
from pathlib import Path

import click

from .gene_resolver import GeneResolver
from .sequence_retriever import SequenceRetriever
from .data_validator import DataValidator
from .input_parser import InputParser
from .output_formatter import OutputFormatter
from .config import Config, get_default_config_path, create_example_config
from .cli_utils import echo, progressbar, set_quiet_mode


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@click.command()
@click.argument('input_file', type=click.Path(exists=True), required=False)
@click.argument('output_file', type=click.Path(), required=False)
@click.option('--api-key', envvar='NCBI_API_KEY', help='NCBI API key for increased rate limits')
@click.option('--email', envvar='EMAIL', default='user@example.com', help='Email for NCBI')
@click.option('--no-cache', is_flag=True, help='Disable caching')
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
def main(input_file, output_file, api_key, email, no_cache, test_genes, verbose, quiet, canonical, prefer_transcript, validate, strict_validation, output_format, no_audit, encoding, delimiter, config, generate_config):
    """NCBI GenBank CDS Retrieval Tool.
    
    Retrieve CDS sequences from NCBI GenBank for gene names.
    
    Examples:
        genbank-tool genes.txt output.tsv
        genbank-tool --test-genes
    """
    # Handle quiet and verbose modes
    if quiet and verbose:
        click.echo("Error: Cannot use both --quiet and --verbose", err=True)
        sys.exit(1)
    
    if quiet:
        logging.getLogger().setLevel(logging.ERROR)
        set_quiet_mode(True)
    elif verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Handle config generation
    if generate_config:
        config_path = create_example_config()
        echo(f"Generated example configuration file: {config_path}")
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
    
    # Handle test mode
    if test_genes:
        test_gene_list = ['VEGF', 'TP53', 'BRCA1']
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
            echo(f"ERROR: Failed to parse input file: {e}", err=True)
            sys.exit(1)
    else:
        # Show help if no input
        ctx = click.get_current_context()
        echo(ctx.get_help())
        return
    
    # Initialize components with configuration
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
    results = []
    
    # Progress bar
    with progressbar(genes, label='Processing genes') as gene_list:
        for gene_name in gene_list:
            if verbose:
                echo(f"\nProcessing: {gene_name}")
            
            # Resolve gene name
            resolved = resolver.resolve(gene_name)
            
            if not resolved:
                if verbose:
                    echo(f"  ERROR: Could not resolve gene name")
                result = formatter.format_sequence_result(
                    input_name=gene_name,
                    error='Gene name not resolved'
                )
                results.append(result)
                continue
            
            if verbose:
                echo(f"  Resolved to: {resolved.official_symbol} (Gene ID: {resolved.gene_id}) via {resolved.source}")
            
            if cfg.selection.canonical_only:
                # Get canonical transcript
                selection = retriever.get_canonical_transcript(
                    resolved.official_symbol,
                    resolved.gene_id,
                    user_preference=prefer_transcript
                )
                
                if not selection:
                    if verbose:
                        echo(f"  ERROR: No sequences found")
                    result = formatter.format_sequence_result(
                        input_name=gene_name,
                        error='No sequences found'
                    )
                    results.append(result)
                    continue
                
                best_seq = selection.transcript
                if verbose:
                    echo(f"  Selected: {best_seq.full_accession} ({best_seq.cds_length} bp)")
                    echo(f"  Method: {selection.method.value} (confidence: {selection.confidence:.2f})")
                    
                    if selection.warnings:
                        for warning in selection.warnings:
                            echo(f"  ⚠️  {warning}")
                    
                    if selection.alternatives_count > 0:
                        echo(f"  Alternatives: {selection.alternatives_count} other transcript(s) available")
            else:
                # Get all sequences
                sequences = retriever.retrieve_by_gene_id(resolved.official_symbol, resolved.gene_id)
                
                if not sequences:
                    if verbose:
                        echo(f"  ERROR: No sequences found")
                    result = formatter.format_sequence_result(
                        input_name=gene_name,
                        error='No sequences found'
                    )
                    results.append(result)
                    continue
                
                # For now, take the first (best) sequence
                best_seq = sequences[0]
                selection = None  # No selection in all-transcripts mode
                
                if verbose:
                    echo(f"  Found sequence: {best_seq.full_accession} ({best_seq.cds_length} bp)")
                    if best_seq.refseq_select:
                        echo("  ✓ RefSeq Select")
            
            # Validate sequence if requested
            validation_result = None
            if validator:
                validation_result = validator.validate_sequence(best_seq, resolved.official_symbol)
                
                if verbose and validation_result.issues:
                    echo("  Validation issues:")
                    for issue in validation_result.issues:
                        echo(f"    [{issue.level.value}] {issue.message}")
                elif verbose:
                    echo("  ✓ Validation passed")
            
            # Format result using OutputFormatter
            result = formatter.format_sequence_result(
                input_name=gene_name,
                sequence=best_seq,
                selection=selection if cfg.selection.canonical_only else None,
                validation=validation_result
            )
            results.append(result)
    
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


if __name__ == '__main__':
    main()