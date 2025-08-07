# Constitutional.seq Performance Test Report
Generated: 2025-08-07 00:50:38

## Executive Summary
- Average throughput: 4.89 genes/second
- Maximum throughput: 4.89 genes/second
- Average memory usage: 51.7 MB

## Checkpoint Resume

### Checkpoint/Resume
- **Genes processed**: 10
- **Duration**: 2.05s
- **Success rate**: 100.0%
- **Throughput**: 4.89 genes/sec
- **Peak memory**: 51.7 MB
- **Cache hits/misses**: 0/0
- **Network requests**: 0

## Performance Recommendations

## Limitations and Notes
- Tests performed with NCBI rate limiting (3 req/sec)
- Network latency and NCBI server response time affect results
- Memory usage includes Python interpreter overhead
- GUI tests require PyQt5 installation
- Some tests use mock data to avoid excessive API calls