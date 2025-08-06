"""Command-line interface for the NCBI GenBank tool."""

import logging

import click

from .gene_resolver import GeneResolver
from .sequence_retriever import SequenceRetriever
from .data_validator import DataValidator


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
@click.option('--canonical/--all-transcripts', default=True, help='Select canonical transcript only')
@click.option('--prefer-transcript', help='Preferred transcript accession (e.g., NM_001234)')
@click.option('--validate/--no-validate', default=False, help='Validate sequences against databases')
@click.option('--strict-validation', is_flag=True, help='Treat validation warnings as errors')
@click.option('--output-format', type=click.Choice(['tsv', 'csv', 'json', 'excel']), default='tsv', help='Output file format')
@click.option('--no-audit', is_flag=True, help='Disable audit trail generation')
@click.option('--encoding', help='Input file encoding (auto-detected if not specified)')
@click.option('--delimiter', help='CSV delimiter (auto-detected if not specified)')
def main(input_file, output_file, api_key, email, no_cache, test_genes, verbose, canonical, prefer_transcript, validate, strict_validation, output_format, no_audit, encoding, delimiter):
    """NCBI GenBank CDS Retrieval Tool.
    
    Retrieve CDS sequences from NCBI GenBank for gene names.
    
    Examples:
        genbank-tool genes.txt output.tsv
        genbank-tool --test-genes
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Handle test mode
    if test_genes:
        test_gene_list = ['VEGF', 'TP53', 'BRCA1']
        click.echo(f"Testing with genes: {', '.join(test_gene_list)}")
        genes = test_gene_list
    elif input_file:
        # Read genes from file
        with open(input_file, 'r') as f:
            genes = [line.strip() for line in f if line.strip()]
        click.echo(f"Read {len(genes)} genes from {input_file}")
    else:
        # Show help if no input
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        return
    
    # Initialize components
    resolver = GeneResolver(api_key=api_key, cache_enabled=not no_cache)
    retriever = SequenceRetriever(api_key=api_key, email=email, cache_enabled=not no_cache)
    validator = DataValidator(validate_cross_refs=validate, strict_mode=strict_validation) if validate else None
    
    # Process genes
    click.echo("\nProcessing genes...")
    results = []
    
    for i, gene_name in enumerate(genes, 1):
        click.echo(f"\n[{i}/{len(genes)}] Processing: {gene_name}")
        
        # Resolve gene name
        resolved = resolver.resolve(gene_name)
        
        if not resolved:
            click.echo(f"  ERROR: Could not resolve gene name")
            results.append({
                'input_name': gene_name,
                'error': 'Gene name not resolved'
            })
            continue
        
        click.echo(f"  Resolved to: {resolved.official_symbol} (Gene ID: {resolved.gene_id}) via {resolved.source}")
        
        if canonical:
            # Get canonical transcript
            selection = retriever.get_canonical_transcript(
                resolved.official_symbol,
                resolved.gene_id,
                user_preference=prefer_transcript
            )
            
            if not selection:
                click.echo(f"  ERROR: No sequences found")
                results.append({
                    'input_name': gene_name,
                    'official_symbol': resolved.official_symbol,
                    'gene_id': resolved.gene_id,
                    'error': 'No sequences found'
                })
                continue
            
            best_seq = selection.transcript
            click.echo(f"  Selected: {best_seq.full_accession} ({best_seq.cds_length} bp)")
            click.echo(f"  Method: {selection.method.value} (confidence: {selection.confidence:.2f})")
            
            if selection.warnings:
                for warning in selection.warnings:
                    click.echo(f"  ⚠️  {warning}")
            
            if selection.alternatives_count > 0:
                click.echo(f"  Alternatives: {selection.alternatives_count} other transcript(s) available")
        else:
            # Get all sequences
            sequences = retriever.retrieve_by_gene_id(resolved.official_symbol, resolved.gene_id)
            
            if not sequences:
                click.echo(f"  ERROR: No sequences found")
                results.append({
                    'input_name': gene_name,
                    'official_symbol': resolved.official_symbol,
                    'gene_id': resolved.gene_id,
                    'error': 'No sequences found'
                })
                continue
            
            # For now, take the first (best) sequence
            best_seq = sequences[0]
            
            click.echo(f"  Found sequence: {best_seq.full_accession} ({best_seq.cds_length} bp)")
            if best_seq.refseq_select:
                click.echo("  ✓ RefSeq Select")
        
        # Validate sequence if requested
        validation_result = None
        if validator:
            validation_result = validator.validate_sequence(best_seq, resolved.official_symbol)
            
            if validation_result.issues:
                click.echo("  Validation issues:")
                for issue in validation_result.issues:
                    click.echo(f"    [{issue.level.value}] {issue.message}")
            else:
                click.echo("  ✓ Validation passed")
        
        # Build result entry
        result_entry = {
            'input_name': gene_name,
            'official_symbol': resolved.official_symbol,
            'gene_id': resolved.gene_id,
            'accession': best_seq.full_accession,
            'genbank_url': best_seq.genbank_url,
            'cds_length': best_seq.cds_length,
            'cds_sequence': best_seq.cds_sequence,
            'refseq_select': best_seq.refseq_select,
            'confidence': resolved.confidence,
            'resolution_source': resolved.source
        }
        
        # Add selection info if using canonical mode
        if canonical and 'selection' in locals():
            result_entry['selection_method'] = selection.method.value
            result_entry['selection_confidence'] = selection.confidence
            result_entry['selection_warnings'] = '; '.join(selection.warnings) if selection.warnings else ''
        
        # Add validation info if available
        if validation_result:
            result_entry['validation_status'] = 'Valid' if validation_result.is_valid else 'Invalid'
            result_entry['validation_confidence'] = validation_result.confidence_score
            result_entry['validation_issues'] = '; '.join(
                f"[{issue.level.value}] {issue.flag.value}" 
                for issue in validation_result.issues
            ) if validation_result.issues else ''
        
        results.append(result_entry)
    
    # Output results
    if output_file:
        # Write TSV file
        import csv
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            # Add BOM for Excel compatibility
            f.write('\ufeff')
            
            fieldnames = [
                'Input Name', 'Official Symbol', 'Gene ID', 'RefSeq Accession',
                'GenBank URL', 'CDS Length', 'CDS Sequence', 'RefSeq Select',
                'Confidence', 'Source', 'Selection Method', 'Selection Confidence',
                'Selection Warnings'
            ]
            
            # Add validation fields if validation is enabled
            if validate:
                fieldnames.extend(['Validation Status', 'Validation Confidence', 'Validation Issues'])
            
            fieldnames.append('Error')
            
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
            writer.writeheader()
            
            for result in results:
                row_data = {
                    'Input Name': result.get('input_name', ''),
                    'Official Symbol': result.get('official_symbol', ''),
                    'Gene ID': result.get('gene_id', ''),
                    'RefSeq Accession': result.get('accession', ''),
                    'GenBank URL': result.get('genbank_url', ''),
                    'CDS Length': result.get('cds_length', ''),
                    'CDS Sequence': result.get('cds_sequence', ''),
                    'RefSeq Select': 'Yes' if result.get('refseq_select') else 'No',
                    'Confidence': f"{result.get('confidence', 0):.2f}" if 'confidence' in result else '',
                    'Source': result.get('resolution_source', ''),
                    'Selection Method': result.get('selection_method', ''),
                    'Selection Confidence': f"{result.get('selection_confidence', 0):.2f}" if 'selection_confidence' in result else '',
                    'Selection Warnings': result.get('selection_warnings', ''),
                    'Error': result.get('error', '')
                }
                
                # Add validation fields if present
                if validate:
                    row_data['Validation Status'] = result.get('validation_status', '')
                    row_data['Validation Confidence'] = f"{result.get('validation_confidence', 0):.2f}" if 'validation_confidence' in result else ''
                    row_data['Validation Issues'] = result.get('validation_issues', '')
                
                writer.writerow(row_data)
        
        click.echo(f"\nResults written to: {output_file}")
    else:
        # Display summary
        click.echo("\n" + "=" * 80)
        click.echo(f"Processed {len(genes)} genes")
        successful = len([r for r in results if 'error' not in r])
        click.echo(f"Successful: {successful}")
        click.echo(f"Failed: {len(genes) - successful}")


if __name__ == '__main__':
    main()