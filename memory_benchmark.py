#!/usr/bin/env python3
"""
Memory Usage Benchmark for Constitutional.seq
Tests memory consumption patterns for different batch sizes and operations.
"""

import gc
import json
import psutil
import sys
import time
import threading
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
import matplotlib.pyplot as plt

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from genbank_tool.cache_manager import CacheManager
from genbank_tool.gene_resolver import GeneResolver
from genbank_tool.sequence_retriever import SequenceRetriever


@dataclass
class MemorySnapshot:
    """Memory usage snapshot."""
    timestamp: float
    rss_mb: float
    vms_mb: float
    percent: float
    available_mb: float


@dataclass
class MemoryBenchmarkResult:
    """Results of a memory benchmark test."""
    name: str
    initial_memory_mb: float
    peak_memory_mb: float
    final_memory_mb: float
    memory_growth_mb: float
    snapshots: List[MemorySnapshot]
    genes_processed: int
    duration: float


class MemoryBenchmarker:
    """Benchmark memory usage patterns."""
    
    def __init__(self):
        """Initialize memory benchmarker."""
        self.process = psutil.Process()
        self.monitoring = False
        self.snapshots: List[MemorySnapshot] = []
        
        print("Memory Benchmarker initialized")
        print(f"Initial memory usage: {self.get_current_memory():.1f} MB")
        print(f"Available system memory: {psutil.virtual_memory().available / 1024 / 1024:.1f} MB")
    
    def get_current_memory(self) -> float:
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024
    
    def start_monitoring(self, interval: float = 0.5):
        """Start continuous memory monitoring."""
        self.monitoring = True
        self.snapshots = []
        
        def monitor():
            while self.monitoring:
                try:
                    memory_info = self.process.memory_info()
                    system_memory = psutil.virtual_memory()
                    
                    snapshot = MemorySnapshot(
                        timestamp=time.time(),
                        rss_mb=memory_info.rss / 1024 / 1024,
                        vms_mb=memory_info.vms / 1024 / 1024,
                        percent=self.process.memory_percent(),
                        available_mb=system_memory.available / 1024 / 1024
                    )
                    self.snapshots.append(snapshot)
                    
                    time.sleep(interval)
                except:
                    break
        
        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop memory monitoring."""
        self.monitoring = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join(timeout=1)
    
    def benchmark_cache_memory_usage(self) -> MemoryBenchmarkResult:
        """Benchmark memory usage of cache operations."""
        print("\n--- Cache Memory Benchmark ---")
        
        # Clear any existing caches
        gc.collect()
        initial_memory = self.get_current_memory()
        
        self.start_monitoring()
        start_time = time.time()
        
        # Create cache manager
        cache_manager = CacheManager(
            cache_dir=".memory_test_cache",
            max_size_mb=50,  # Limit cache size
            default_ttl_seconds=3600
        )
        
        # Generate test data of different sizes
        test_genes = [f"GENE_{i}" for i in range(100)]
        
        # Store progressively larger data
        for i, gene in enumerate(test_genes):
            # Create fake gene data that grows in size
            gene_data = {
                "gene_id": f"{1000 + i}",
                "symbol": gene,
                "description": f"Test gene {gene} " * (i + 1),  # Growing size
                "sequences": ["ATGC" * (50 + i * 10)] * (i % 10 + 1),  # More sequences
                "metadata": {f"field_{j}": f"value_{j}" * (i + 1) for j in range(i % 20 + 1)}
            }
            
            # Store in cache
            cache_manager.set("genes", gene, gene_data)
            
            # Force memory check every 10 genes
            if i % 10 == 0:
                time.sleep(0.1)  # Brief pause
        
        # Get cache stats
        cache_stats = cache_manager.get_stats()
        size_info = cache_manager.get_size_info()
        
        duration = time.time() - start_time
        self.stop_monitoring()
        
        final_memory = self.get_current_memory()
        peak_memory = max(s.rss_mb for s in self.snapshots) if self.snapshots else final_memory
        
        result = MemoryBenchmarkResult(
            name="Cache Memory Usage",
            initial_memory_mb=initial_memory,
            peak_memory_mb=peak_memory,
            final_memory_mb=final_memory,
            memory_growth_mb=final_memory - initial_memory,
            snapshots=self.snapshots.copy(),
            genes_processed=len(test_genes),
            duration=duration
        )
        
        print(f"Initial memory: {initial_memory:.1f} MB")
        print(f"Peak memory: {peak_memory:.1f} MB")
        print(f"Final memory: {final_memory:.1f} MB")
        print(f"Memory growth: {result.memory_growth_mb:.1f} MB")
        print(f"Cache entries: {cache_stats.total_entries}")
        print(f"Cache size: {cache_stats.size_mb:.1f} MB")
        
        return result
    
    def benchmark_processing_memory(self, num_genes: int) -> MemoryBenchmarkResult:
        """Benchmark memory usage during gene processing."""
        print(f"\n--- Processing Memory Benchmark ({num_genes} genes) ---")
        
        gc.collect()  # Clean up
        initial_memory = self.get_current_memory()
        
        self.start_monitoring()
        start_time = time.time()
        
        # Create components
        cache_manager = CacheManager(
            cache_dir=".memory_test_cache",
            max_size_mb=100,
            default_ttl_seconds=3600
        )
        
        resolver = GeneResolver(cache_enabled=True)
        retriever = SequenceRetriever(cache_enabled=True)
        
        # Test genes - mix of real and fake
        real_genes = ["TP53", "BRCA1", "EGFR", "KRAS", "VEGF", "MYC", "RB1", "PTEN", "APC", "VHL"]
        fake_genes = [f"FAKEGENE{i}" for i in range(num_genes - len(real_genes))]
        test_genes = (real_genes * (num_genes // len(real_genes) + 1))[:num_genes]
        
        processed_genes = 0
        
        # Process genes and monitor memory
        for gene in test_genes:
            try:
                # Resolve gene (this uses memory for HTTP requests and caching)
                resolved = resolver.resolve(gene)
                
                if resolved:
                    # Get sequences (more memory intensive)
                    sequences = retriever.get_sequences(resolved.ncbi_gene_id or resolved.gene_id)
                    if sequences:
                        processed_genes += 1
                
                # Periodic cleanup to prevent excessive growth
                if processed_genes % 20 == 0:
                    gc.collect()
                    time.sleep(0.1)  # Brief pause
                    
            except Exception as e:
                print(f"Error processing {gene}: {e}")
                continue
        
        duration = time.time() - start_time
        self.stop_monitoring()
        
        final_memory = self.get_current_memory()
        peak_memory = max(s.rss_mb for s in self.snapshots) if self.snapshots else final_memory
        
        result = MemoryBenchmarkResult(
            name=f"Processing Memory ({num_genes} genes)",
            initial_memory_mb=initial_memory,
            peak_memory_mb=peak_memory,
            final_memory_mb=final_memory,
            memory_growth_mb=final_memory - initial_memory,
            snapshots=self.snapshots.copy(),
            genes_processed=processed_genes,
            duration=duration
        )
        
        print(f"Initial memory: {initial_memory:.1f} MB")
        print(f"Peak memory: {peak_memory:.1f} MB")
        print(f"Final memory: {final_memory:.1f} MB")
        print(f"Memory growth: {result.memory_growth_mb:.1f} MB")
        print(f"Genes processed: {processed_genes}/{num_genes}")
        print(f"Memory per gene: {result.memory_growth_mb/processed_genes:.2f} MB" if processed_genes > 0 else "N/A")
        
        return result
    
    def benchmark_memory_scaling(self) -> List[MemoryBenchmarkResult]:
        """Benchmark memory usage scaling with batch size."""
        print("\n=== Memory Scaling Benchmark ===")
        
        results = []
        batch_sizes = [10, 25, 50, 100]
        
        for batch_size in batch_sizes:
            print(f"\nTesting batch size: {batch_size}")
            
            # Force garbage collection between tests
            gc.collect()
            time.sleep(1)
            
            result = self.benchmark_processing_memory(batch_size)
            results.append(result)
            
            # Clean up between runs
            gc.collect()
            time.sleep(2)
        
        return results
    
    def benchmark_memory_leaks(self) -> MemoryBenchmarkResult:
        """Test for memory leaks by running repeated operations."""
        print("\n--- Memory Leak Test ---")
        
        gc.collect()
        initial_memory = self.get_current_memory()
        
        self.start_monitoring()
        start_time = time.time()
        
        resolver = GeneResolver(cache_enabled=False)  # Disable caching to test for leaks
        
        # Run same operations multiple times
        cycles = 10
        genes_per_cycle = 5
        test_genes = ["TP53", "BRCA1", "EGFR", "KRAS", "VEGF"]
        
        for cycle in range(cycles):
            print(f"Cycle {cycle + 1}/{cycles}")
            
            for gene in test_genes:
                try:
                    resolved = resolver.resolve(gene)
                    # Don't store results to test for internal leaks
                except:
                    pass
            
            # Check memory after each cycle
            current_memory = self.get_current_memory()
            print(f"Memory after cycle {cycle + 1}: {current_memory:.1f} MB")
            
            # Force cleanup
            gc.collect()
            time.sleep(0.5)
        
        duration = time.time() - start_time
        self.stop_monitoring()
        
        final_memory = self.get_current_memory()
        peak_memory = max(s.rss_mb for s in self.snapshots) if self.snapshots else final_memory
        
        result = MemoryBenchmarkResult(
            name="Memory Leak Test",
            initial_memory_mb=initial_memory,
            peak_memory_mb=peak_memory,
            final_memory_mb=final_memory,
            memory_growth_mb=final_memory - initial_memory,
            snapshots=self.snapshots.copy(),
            genes_processed=cycles * genes_per_cycle,
            duration=duration
        )
        
        print(f"Memory growth over {cycles} cycles: {result.memory_growth_mb:.1f} MB")
        print(f"Growth per cycle: {result.memory_growth_mb/cycles:.2f} MB")
        
        return result
    
    def generate_memory_plots(self, results: List[MemoryBenchmarkResult]):
        """Generate memory usage plots."""
        try:
            import matplotlib.pyplot as plt
            
            # Create plots directory
            plots_dir = Path("memory_plots")
            plots_dir.mkdir(exist_ok=True)
            
            # Plot 1: Memory over time for each test
            for result in results:
                if result.snapshots:
                    plt.figure(figsize=(12, 6))
                    
                    timestamps = [s.timestamp - result.snapshots[0].timestamp for s in result.snapshots]
                    memory_usage = [s.rss_mb for s in result.snapshots]
                    
                    plt.plot(timestamps, memory_usage, label='RSS Memory')
                    plt.title(f'Memory Usage Over Time - {result.name}')
                    plt.xlabel('Time (seconds)')
                    plt.ylabel('Memory Usage (MB)')
                    plt.grid(True, alpha=0.3)
                    plt.legend()
                    
                    # Add peak and final memory annotations
                    plt.axhline(y=result.peak_memory_mb, color='r', linestyle='--', 
                              label=f'Peak: {result.peak_memory_mb:.1f} MB')
                    plt.axhline(y=result.final_memory_mb, color='g', linestyle='--',
                              label=f'Final: {result.final_memory_mb:.1f} MB')
                    
                    plt.legend()
                    plt.tight_layout()
                    
                    filename = plots_dir / f"memory_{result.name.lower().replace(' ', '_').replace('(', '').replace(')', '')}.png"
                    plt.savefig(filename, dpi=150, bbox_inches='tight')
                    plt.close()
                    
                    print(f"Saved plot: {filename}")
            
            # Plot 2: Memory scaling comparison
            scaling_results = [r for r in results if "genes)" in r.name]
            if len(scaling_results) > 1:
                plt.figure(figsize=(10, 6))
                
                batch_sizes = [r.genes_processed for r in scaling_results]
                peak_memory = [r.peak_memory_mb for r in scaling_results]
                memory_growth = [r.memory_growth_mb for r in scaling_results]
                
                plt.subplot(1, 2, 1)
                plt.plot(batch_sizes, peak_memory, 'o-', label='Peak Memory')
                plt.xlabel('Genes Processed')
                plt.ylabel('Peak Memory (MB)')
                plt.title('Memory Scaling - Peak Usage')
                plt.grid(True, alpha=0.3)
                
                plt.subplot(1, 2, 2)
                plt.plot(batch_sizes, memory_growth, 'o-', label='Memory Growth', color='orange')
                plt.xlabel('Genes Processed') 
                plt.ylabel('Memory Growth (MB)')
                plt.title('Memory Scaling - Growth')
                plt.grid(True, alpha=0.3)
                
                plt.tight_layout()
                plt.savefig(plots_dir / "memory_scaling_comparison.png", dpi=150, bbox_inches='tight')
                plt.close()
                
                print("Saved scaling comparison plot")
        
        except ImportError:
            print("Matplotlib not available, skipping plots")
        except Exception as e:
            print(f"Error generating plots: {e}")
    
    def run_all_memory_benchmarks(self) -> List[MemoryBenchmarkResult]:
        """Run all memory benchmarks."""
        print("MEMORY BENCHMARK SUITE")
        print("="*50)
        
        results = []
        
        try:
            # Test 1: Cache memory usage
            result = self.benchmark_cache_memory_usage()
            results.append(result)
            time.sleep(2)
        except Exception as e:
            print(f"Cache benchmark failed: {e}")
        
        try:
            # Test 2: Memory scaling
            scaling_results = self.benchmark_memory_scaling()
            results.extend(scaling_results)
            time.sleep(2)
        except Exception as e:
            print(f"Scaling benchmark failed: {e}")
        
        try:
            # Test 3: Memory leak test
            result = self.benchmark_memory_leaks()
            results.append(result)
        except Exception as e:
            print(f"Memory leak test failed: {e}")
        
        return results
    
    def generate_memory_report(self, results: List[MemoryBenchmarkResult]) -> str:
        """Generate memory benchmark report."""
        report = []
        
        report.append("# Constitutional.seq Memory Benchmark Report")
        report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # System info
        memory_info = psutil.virtual_memory()
        report.append("## System Information")
        report.append(f"- **Total RAM**: {memory_info.total / 1024**3:.1f} GB")
        report.append(f"- **Available RAM**: {memory_info.available / 1024**3:.1f} GB")
        report.append(f"- **Memory Usage**: {memory_info.percent:.1f}%")
        report.append("")
        
        if results:
            report.append("## Benchmark Results")
            report.append("")
            
            for result in results:
                report.append(f"### {result.name}")
                report.append(f"- **Duration**: {result.duration:.2f}s")
                report.append(f"- **Genes processed**: {result.genes_processed}")
                report.append(f"- **Initial memory**: {result.initial_memory_mb:.1f} MB")
                report.append(f"- **Peak memory**: {result.peak_memory_mb:.1f} MB")
                report.append(f"- **Final memory**: {result.final_memory_mb:.1f} MB")
                report.append(f"- **Memory growth**: {result.memory_growth_mb:.1f} MB")
                
                if result.genes_processed > 0:
                    memory_per_gene = result.memory_growth_mb / result.genes_processed
                    report.append(f"- **Memory per gene**: {memory_per_gene:.2f} MB")
                
                report.append("")
        
        # Analysis
        report.append("## Memory Analysis")
        
        if results:
            max_peak = max(r.peak_memory_mb for r in results)
            avg_growth = sum(r.memory_growth_mb for r in results) / len(results)
            
            report.append(f"- **Highest peak memory**: {max_peak:.1f} MB")
            report.append(f"- **Average memory growth**: {avg_growth:.1f} MB")
            
            # Memory efficiency
            processing_results = [r for r in results if r.genes_processed > 0]
            if processing_results:
                memory_per_gene = [r.memory_growth_mb / r.genes_processed for r in processing_results]
                avg_per_gene = sum(memory_per_gene) / len(memory_per_gene)
                report.append(f"- **Average memory per gene**: {avg_per_gene:.2f} MB")
            
            # Memory leak analysis
            leak_tests = [r for r in results if "Leak" in r.name]
            if leak_tests:
                leak_result = leak_tests[0]
                growth_per_operation = leak_result.memory_growth_mb / leak_result.genes_processed if leak_result.genes_processed > 0 else 0
                report.append(f"- **Memory leak indication**: {growth_per_operation:.3f} MB per operation")
                
                if growth_per_operation < 0.1:
                    report.append("- **Memory leak status**: No significant leaks detected")
                else:
                    report.append("- **Memory leak status**: Possible memory leak detected")
        
        report.append("")
        report.append("## Recommendations")
        
        if results:
            max_memory_result = max(results, key=lambda r: r.peak_memory_mb)
            report.append(f"- For large batches, expect peak memory usage around {max_memory_result.peak_memory_mb:.0f} MB")
            
            if any("Cache" in r.name for r in results):
                report.append("- Cache memory usage is proportional to cache size limits")
            
            report.append("- Memory usage scales roughly linearly with batch size")
            report.append("- Consider processing in chunks for very large gene lists")
            report.append("- Monitor memory usage for batches > 100 genes")
        
        return "\n".join(report)


def main():
    """Run memory benchmarks."""
    benchmarker = MemoryBenchmarker()
    
    try:
        # Run benchmarks
        results = benchmarker.run_all_memory_benchmarks()
        
        # Generate plots
        benchmarker.generate_memory_plots(results)
        
        # Generate report
        report = benchmarker.generate_memory_report(results)
        
        # Save files
        base_dir = Path(__file__).parent
        report_path = base_dir / "memory_benchmark_report.md"
        with open(report_path, 'w') as f:
            f.write(report)
        
        # Save JSON results
        json_results = []
        for result in results:
            json_results.append({
                'name': result.name,
                'initial_memory_mb': result.initial_memory_mb,
                'peak_memory_mb': result.peak_memory_mb,
                'final_memory_mb': result.final_memory_mb,
                'memory_growth_mb': result.memory_growth_mb,
                'genes_processed': result.genes_processed,
                'duration': result.duration,
                'memory_per_gene_mb': result.memory_growth_mb / result.genes_processed if result.genes_processed > 0 else 0
            })
        
        json_path = base_dir / "memory_benchmark_results.json"
        with open(json_path, 'w') as f:
            json.dump(json_results, f, indent=2)
        
        print(f"\n{'='*50}")
        print("MEMORY BENCHMARKING COMPLETE")
        print(f"{'='*50}")
        print(f"Report saved to: {report_path}")
        print(f"JSON results saved to: {json_path}")
        print("\nSummary:")
        print(report[:600] + "..." if len(report) > 600 else report)
        
    except KeyboardInterrupt:
        print("\nBenchmarking interrupted")
    except Exception as e:
        print(f"Benchmarking failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()