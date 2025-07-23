#!/usr/bin/env python3
"""Demo script showing error handling and recovery features."""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from genbank_tool.error_handler import setup_error_handler, ErrorType
from genbank_tool.logging_config import setup_logging
from genbank_tool.network_recovery import NetworkRecoveryManager, NetworkConfig
from genbank_tool.batch_processor import BatchProcessor


def simulate_gene_processing(gene_name: str) -> str:
    """Simulate gene processing with random failures."""
    import random
    
    # Simulate different types of failures
    if gene_name == "TIMEOUT_GENE":
        raise TimeoutError("Network timeout while fetching gene data")
    elif gene_name == "INVALID_GENE":
        raise ValueError("Gene not found: INVALID_GENE")
    elif gene_name == "RATE_LIMIT":
        raise Exception("429 Too Many Requests")
    elif random.random() < 0.2:  # 20% random failure rate
        raise Exception("Random processing error")
    
    # Simulate processing time
    time.sleep(0.1)
    return f"Successfully processed {gene_name}"


def main():
    """Main demo function."""
    print("=== GenBank Tool Error Handling Demo ===\n")
    
    # Setup logging
    setup_logging(log_level="INFO", log_dir="demo_logs")
    
    # Setup error handler
    error_handler = setup_error_handler(
        log_dir="demo_logs",
        enable_checkpoints=True,
        max_retries=3
    )
    
    print("1. Testing basic error handling...")
    genes = ["BRCA1", "TP53", "INVALID_GENE", "EGFR", "TIMEOUT_GENE", "KRAS"]
    
    for gene in genes:
        try:
            result = simulate_gene_processing(gene)
            print(f"✓ {result}")
        except Exception as e:
            context = error_handler.handle_error(
                e,
                operation="process_gene",
                item_id=gene
            )
            print(f"✗ {gene}: {context.error_type.value} - {context.suggestion}")
    
    print("\n2. Testing batch processing with checkpoints...")
    batch_genes = [f"GENE_{i}" for i in range(20)]
    batch_genes[5] = "INVALID_GENE"
    batch_genes[10] = "TIMEOUT_GENE"
    batch_genes[15] = "RATE_LIMIT"
    
    processor = BatchProcessor(
        checkpoint_dir="demo_checkpoints",
        enable_checkpoints=True,
        checkpoint_interval=5
    )
    
    results, checkpoint = processor.process_batch(
        batch_genes,
        simulate_gene_processing,
        batch_id="demo_batch"
    )
    
    print(f"\nBatch processing complete:")
    print(f"  - Total items: {checkpoint.total_items}")
    print(f"  - Successful: {len(checkpoint.processed_items)}")
    print(f"  - Failed: {len(checkpoint.failed_items)}")
    
    if checkpoint.failed_items:
        print(f"\nFailed items: {', '.join(checkpoint.failed_items)}")
        
        print("\n3. Testing retry mechanism for failed items...")
        retry_results, retry_checkpoint = processor.retry_failed_items(
            checkpoint.batch_id,
            simulate_gene_processing,
            batch_genes
        )
        
        print(f"\nRetry results:")
        print(f"  - Retried: {len(checkpoint.failed_items)}")
        print(f"  - Now successful: {len(checkpoint.failed_items) - len(retry_checkpoint.failed_items)}")
        print(f"  - Still failing: {len(retry_checkpoint.failed_items)}")
    
    print("\n4. Testing network recovery...")
    recovery_manager = NetworkRecoveryManager()
    
    # Configure custom settings for demo API
    recovery_manager.api_configs['demo_api'] = NetworkConfig(
        timeout=5.0,
        max_retries=3,
        backoff_factor=0.5
    )
    
    session = recovery_manager.get_session('demo_api')
    print("Network recovery manager configured")
    
    print("\n5. Generating error report...")
    error_summary = error_handler.get_error_summary()
    print(f"\nError Summary:")
    print(f"  - Total errors: {error_summary['total_errors']}")
    print(f"  - Error types:")
    for error_type, count in error_summary['by_type'].items():
        print(f"    - {error_type}: {count}")
    
    # Export detailed report
    error_handler.export_error_report("demo_error_report.json")
    print("\nDetailed error report saved to: demo_error_report.json")
    
    # List checkpoints
    print("\n6. Available checkpoints:")
    checkpoints = processor.list_checkpoints()
    for cp in checkpoints:
        print(f"  - {cp['batch_id']} ({cp['timestamp']}): {cp['progress']}")
    
    # Cleanup
    print("\n7. Cleaning up old data...")
    error_handler.cleanup_old_checkpoints(days=0)  # Clean all for demo
    recovery_manager.close_all()
    
    print("\nDemo complete! Check the following files:")
    print("  - demo_logs/: Log files with detailed information")
    print("  - demo_checkpoints/: Checkpoint files for recovery")
    print("  - demo_error_report.json: Detailed error analysis")


if __name__ == "__main__":
    main()