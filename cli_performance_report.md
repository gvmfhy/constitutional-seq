# Constitutional.seq CLI Performance Report
Generated: 2025-08-07 00:54:07

## Executive Summary
- **Average throughput**: 4.19 genes/second
- **Maximum throughput**: 9.74 genes/second
- **Average memory usage**: 18.4 MB
- **Average success rate**: 100.0%

## Batch Sizes

### Small Batch (5 genes)
- **Genes**: 5
- **Duration**: 0.74s
- **Success rate**: 100.0%
- **Throughput**: 6.80 genes/sec
- **Peak memory**: 23.3 MB
- **Output size**: 10.2 KB

### Medium Batch (20 genes)
- **Genes**: 20
- **Duration**: 9.83s
- **Success rate**: 100.0%
- **Throughput**: 2.03 genes/sec
- **Peak memory**: 17.0 MB
- **Output size**: 59.5 KB

### Large Batch (50 genes)
- **Genes**: 50
- **Duration**: 31.12s
- **Success rate**: 100.0%
- **Throughput**: 1.61 genes/sec
- **Peak memory**: 18.1 MB
- **Output size**: 170.5 KB

## Parallel Performance

### Parallel 1 workers
- **Genes**: 20
- **Duration**: 5.41s
- **Success rate**: 100.0%
- **Throughput**: 3.70 genes/sec
- **Peak memory**: 18.2 MB
- **Output size**: 59.5 KB

### Parallel 2 workers
- **Genes**: 20
- **Duration**: 5.38s
- **Success rate**: 100.0%
- **Throughput**: 3.72 genes/sec
- **Peak memory**: 18.2 MB
- **Output size**: 59.5 KB

### Parallel 5 workers
- **Genes**: 20
- **Duration**: 5.36s
- **Success rate**: 100.0%
- **Throughput**: 3.73 genes/sec
- **Peak memory**: 17.8 MB
- **Output size**: 59.5 KB

### Parallel 10 workers
- **Genes**: 20
- **Duration**: 5.28s
- **Success rate**: 100.0%
- **Throughput**: 3.79 genes/sec
- **Peak memory**: 17.9 MB
- **Output size**: 59.5 KB

## Cache Performance

### Cache Test - Cold
- **Genes**: 5
- **Duration**: 0.51s
- **Success rate**: 100.0%
- **Throughput**: 9.74 genes/sec
- **Peak memory**: 17.9 MB
- **Output size**: 10.2 KB

### Cache Test - Warm
- **Genes**: 5
- **Duration**: 0.58s
- **Success rate**: 100.0%
- **Throughput**: 8.66 genes/sec
- **Peak memory**: 18.0 MB
- **Output size**: 10.2 KB

### Cache Test - Disabled
- **Genes**: 5
- **Duration**: 5.60s
- **Success rate**: 100.0%
- **Throughput**: 0.89 genes/sec
- **Peak memory**: 18.0 MB
- **Output size**: 10.3 KB

## Error Handling

### Error Handling Test
- **Genes**: 5
- **Duration**: 3.64s
- **Success rate**: 100.0%
- **Throughput**: 1.37 genes/sec
- **Peak memory**: 18.1 MB
- **Output size**: 4.2 KB

## Performance Analysis

- **Parallel processing speedup**: 1.0x with Parallel 10 workers
- **Optimal worker count**: ~10 workers
- **Cache speedup**: 0.9x on repeated runs
- **Memory per gene**: ~1.16 MB

## Limitations and Notes
- Tests performed with NCBI rate limiting (3 req/sec without API key)
- Network latency affects actual performance
- Memory measurements are approximate
- Cache performance depends on gene selection
- Some tests may use cached data from previous runs