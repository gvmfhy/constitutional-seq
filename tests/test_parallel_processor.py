"""Tests for parallel processor."""

import time
from typing import List

import pytest

from genbank_tool.parallel_processor import (
    ParallelProcessor, QueueProcessor, ProcessingResult,
    BatchProcessingStats, process_batch_parallel
)
from genbank_tool.rate_limiter import configure_rate_limit


class TestParallelProcessor:
    """Test cases for parallel processor."""
    
    def test_basic_processing(self):
        """Test basic parallel processing."""
        items = list(range(10))
        
        def process_func(x):
            return x * 2
        
        processor = ParallelProcessor(max_workers=3)
        results, stats = processor.process_batch(items, process_func)
        
        # Check results
        assert len(results) == 10
        assert all(r.success for r in results)
        assert sorted(r.result for r in results) == [x * 2 for x in range(10)]
        
        # Check stats
        assert stats.total_items == 10
        assert stats.successful == 10
        assert stats.failed == 0
        assert stats.success_rate == 1.0
    
    def test_error_handling(self):
        """Test error handling in parallel processing."""
        items = list(range(5))
        
        def process_func(x):
            if x == 2:
                raise ValueError(f"Error processing {x}")
            return x * 2
        
        errors_caught = []
        
        def error_handler(item, error):
            errors_caught.append((item, str(error)))
        
        processor = ParallelProcessor(max_workers=2)
        results, stats = processor.process_batch(items, process_func, error_handler)
        
        # Check results
        assert len(results) == 5
        assert sum(1 for r in results if r.success) == 4
        assert sum(1 for r in results if not r.success) == 1
        
        # Check error was caught
        assert len(errors_caught) == 1
        assert errors_caught[0][0] == 2
        assert "Error processing 2" in errors_caught[0][1]
        
        # Check stats
        assert stats.successful == 4
        assert stats.failed == 1
        assert stats.success_rate == 0.8
    
    def test_rate_limiting(self):
        """Test rate limiting in parallel processing."""
        # Configure rate limit
        configure_rate_limit('test_api', 5)  # 5 requests per second
        
        items = list(range(10))
        
        def process_func(x):
            return x
        
        processor = ParallelProcessor(
            max_workers=3,
            rate_limit_api='test_api'
        )
        
        start_time = time.time()
        results, stats = processor.process_batch(items, process_func)
        elapsed = time.time() - start_time
        
        # Should take at least 1.8 seconds (10 items at 5/s)
        assert elapsed >= 1.5  # Allow some variance
        assert all(r.success for r in results)
    
    def test_chunking(self):
        """Test processing in chunks."""
        items = list(range(20))
        
        def process_func(x):
            return x * 2
        
        chunks_processed = []
        
        def progress_callback(processed, total):
            chunks_processed.append(processed)
        
        processor = ParallelProcessor(
            max_workers=2,
            progress_callback=progress_callback
        )
        
        results, stats = processor.process_batch(
            items, 
            process_func,
            chunk_size=5
        )
        
        # Should process 4 chunks of 5
        assert len(results) == 20
        assert all(r.success for r in results)
        assert stats.total_items == 20
        assert stats.successful == 20
    
    def test_shutdown(self):
        """Test shutdown functionality."""
        processor = ParallelProcessor(max_workers=2)
        
        # Start processing
        items = list(range(100))
        
        def slow_process(x):
            time.sleep(0.1)
            return x
        
        # Start in a thread
        import threading
        results_container = []
        
        def run_processing():
            results, _ = processor.process_batch(items, slow_process)
            results_container.extend(results)
        
        thread = threading.Thread(target=run_processing)
        thread.start()
        
        # Shutdown after brief delay
        time.sleep(0.2)
        processor.shutdown()
        
        thread.join(timeout=1)
        
        # Should have processed some but not all
        assert len(results_container) < 100


class TestQueueProcessor:
    """Test cases for queue processor."""
    
    def test_queue_processing(self):
        """Test basic queue processing."""
        def process_func(x):
            return x * 3
        
        processor = QueueProcessor(
            worker_count=2,
            process_func=process_func
        )
        
        processor.start()
        
        # Submit items
        for i in range(5):
            processor.submit(i)
        
        # Get results
        results = []
        for _ in range(5):
            result = processor.get_result(timeout=2)
            assert result is not None
            results.append(result)
        
        processor.shutdown()
        
        # Check results
        assert all(r.success for r in results)
        result_values = sorted(r.result for r in results)
        assert result_values == [0, 3, 6, 9, 12]
    
    def test_queue_error_handling(self):
        """Test error handling in queue processing."""
        def process_func(x):
            if x == 'error':
                raise RuntimeError("Test error")
            return f"processed_{x}"
        
        processor = QueueProcessor(
            worker_count=1,
            process_func=process_func
        )
        
        # Submit mixed items
        processor.submit('good1')
        processor.submit('error')
        processor.submit('good2')
        
        # Get results
        results = []
        for _ in range(3):
            result = processor.get_result(timeout=2)
            results.append(result)
        
        processor.shutdown()
        
        # Check results
        success_results = [r for r in results if r.success]
        error_results = [r for r in results if not r.success]
        
        assert len(success_results) == 2
        assert len(error_results) == 1
        assert any('Test error' in str(r.error) for r in error_results)


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_process_batch_parallel(self):
        """Test convenience function for parallel processing."""
        items = ['a', 'b', 'c', 'd', 'e']
        
        def process_func(x):
            return x.upper()
        
        progress_updates = []
        
        def progress_callback(processed, total):
            progress_updates.append((processed, total))
        
        results = process_batch_parallel(
            items,
            process_func,
            max_workers=2,
            progress_callback=progress_callback
        )
        
        # Check results
        assert len(results) == 5
        assert all(r.success for r in results)
        
        result_values = sorted(r.result for r in results)
        assert result_values == ['A', 'B', 'C', 'D', 'E']
        
        # Should have progress updates
        assert len(progress_updates) > 0
        assert progress_updates[-1][0] == 5  # Final count