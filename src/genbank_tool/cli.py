"""Command-line interface for the NCBI GenBank tool."""

import logging
import sys

import click

from .gene_resolver import GeneResolver
from .sequence_retriever import SequenceRetriever


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
def main(input_file, output_file, api_key, email, no_cache, test_genes, verbose):
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
        
        # Retrieve sequences
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
        
        results.append({
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
        })
    
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
                'Confidence', 'Source', 'Error'
            ]
            
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
            writer.writeheader()
            
            for result in results:
                writer.writerow({
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
                    'Error': result.get('error', '')
                })
        
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