"""Parallel processing for batch operations with rate limiting."""

import logging
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

from .rate_limiter import rate_limit

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


@dataclass
class ProcessingResult:
    """Result of processing an item."""
    item: Any
    result: Optional[Any] = None
    error: Optional[Exception] = None
    duration: float = 0.0
    
    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class BatchProcessingStats:
    """Statistics for batch processing."""
    total_items: int = 0
    processed: int = 0
    successful: int = 0
    failed: int = 0
    total_duration: float = 0.0
    
    @property
    def success_rate(self) -> float:
        return self.successful / self.processed if self.processed > 0 else 0.0
    
    @property
    def average_duration(self) -> float:
        return self.total_duration / self.processed if self.processed > 0 else 0.0


class ParallelProcessor:
    """Processes items in parallel with rate limiting and error handling."""
    
    def __init__(self, 
                 max_workers: int = 5,
                 rate_limit_api: Optional[str] = None,
                 progress_callback: Optional[Callable[[int, int], None]] = None):
        """
        Initialize parallel processor.
        
        Args:
            max_workers: Maximum number of worker threads
            rate_limit_api: API name for rate limiting
            progress_callback: Callback for progress updates (processed, total)
        """
        self.max_workers = max_workers
        self.rate_limit_api = rate_limit_api
        self.progress_callback = progress_callback
        self._shutdown = False
    
    def process_batch(self,
                     items: List[T],
                     process_func: Callable[[T], R],
                     error_handler: Optional[Callable[[T, Exception], Any]] = None,
                     chunk_size: Optional[int] = None) -> Tuple[List[ProcessingResult], BatchProcessingStats]:
        """
        Process a batch of items in parallel.
        
        Args:
            items: Items to process
            process_func: Function to process each item
            error_handler: Optional error handler
            chunk_size: Process items in chunks (useful for memory management)
            
        Returns:
            Tuple of (results, statistics)
        """
        if not items:
            return [], BatchProcessingStats()
        
        stats = BatchProcessingStats(total_items=len(items))
        results = []
        
        # Split into chunks if requested
        if chunk_size and chunk_size < len(items):
            chunks = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
            
            for i, chunk in enumerate(chunks):
                logger.info(f"Processing chunk {i+1}/{len(chunks)} ({len(chunk)} items)")
                chunk_results, chunk_stats = self._process_items(chunk, process_func, error_handler, stats)
                results.extend(chunk_results)
                
                # Update cumulative stats
                stats.processed += chunk_stats.processed
                stats.successful += chunk_stats.successful
                stats.failed += chunk_stats.failed
                stats.total_duration += chunk_stats.total_duration
        else:
            results, stats = self._process_items(items, process_func, error_handler, stats)
        
        return results, stats
    
    def _process_items(self,
                      items: List[T],
                      process_func: Callable[[T], R],
                      error_handler: Optional[Callable[[T, Exception], Any]],
                      parent_stats: Optional[BatchProcessingStats]) -> Tuple[List[ProcessingResult], BatchProcessingStats]:
        """Process a list of items."""
        stats = BatchProcessingStats(total_items=len(items))
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_item: Dict[Future, T] = {}
            
            for item in items:
                if self._shutdown:
                    break
                
                future = executor.submit(self._process_single, item, process_func)
                future_to_item[future] = item
            
            # Process completed tasks
            for future in as_completed(future_to_item):
                if self._shutdown:
                    break
                
                item = future_to_item[future]
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    stats.processed += 1
                    stats.total_duration += result.duration
                    
                    if result.success:
                        stats.successful += 1
                    else:
                        stats.failed += 1
                        if error_handler and result.error:
                            try:
                                error_handler(item, result.error)
                            except Exception as e:
                                logger.error(f"Error in error handler: {e}")
                    
                    # Progress callback
                    if self.progress_callback:
                        total_processed = parent_stats.processed + stats.processed if parent_stats else stats.processed
                        total_items = parent_stats.total_items if parent_stats else stats.total_items
                        self.progress_callback(total_processed, total_items)
                        
                except Exception as e:
                    logger.error(f"Unexpected error processing future: {e}")
                    results.append(ProcessingResult(item=item, error=e))
                    stats.processed += 1
                    stats.failed += 1
        
        return results, stats
    
    def _process_single(self, item: T, process_func: Callable[[T], R]) -> ProcessingResult:
        """Process a single item with rate limiting."""
        start_time = time.time()
        
        try:
            # Apply rate limiting if configured
            if self.rate_limit_api:
                rate_limit(self.rate_limit_api)
            
            # Process the item
            result = process_func(item)
            duration = time.time() - start_time
            
            return ProcessingResult(
                item=item,
                result=result,
                duration=duration
            )
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Error processing item {item}: {e}")
            
            return ProcessingResult(
                item=item,
                error=e,
                duration=duration
            )
    
    def shutdown(self):
        """Signal shutdown to stop processing."""
        self._shutdown = True


class QueueProcessor:
    """Processes items from a queue with multiple workers."""
    
    def __init__(self,
                 worker_count: int = 5,
                 process_func: Callable[[Any], Any] = None,
                 rate_limit_api: Optional[str] = None):
        """
        Initialize queue processor.
        
        Args:
            worker_count: Number of worker threads
            process_func: Function to process each item
            rate_limit_api: API name for rate limiting
        """
        self.worker_count = worker_count
        self.process_func = process_func
        self.rate_limit_api = rate_limit_api
        self.input_queue: queue.Queue = queue.Queue()
        self.output_queue: queue.Queue = queue.Queue()
        self.workers: List[threading.Thread] = []
        self._shutdown = False
        self._started = False
    
    def start(self):
        """Start worker threads."""
        if self._started:
            return
        
        self._started = True
        
        for i in range(self.worker_count):
            worker = threading.Thread(
                target=self._worker,
                name=f"QueueWorker-{i+1}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Started {self.worker_count} queue workers")
    
    def submit(self, item: Any) -> None:
        """Submit an item for processing."""
        if not self._started:
            self.start()
        
        self.input_queue.put(item)
    
    def get_result(self, timeout: Optional[float] = None) -> Optional[ProcessingResult]:
        """Get a processed result."""
        try:
            return self.output_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the processor."""
        self._shutdown = True
        
        # Add poison pills for workers
        for _ in range(self.worker_count):
            self.input_queue.put(None)
        
        if wait:
            for worker in self.workers:
                worker.join()
        
        logger.info("Queue processor shutdown complete")
    
    def _worker(self):
        """Worker thread function."""
        while not self._shutdown:
            try:
                item = self.input_queue.get(timeout=1)
                
                if item is None:  # Poison pill
                    break
                
                # Apply rate limiting
                if self.rate_limit_api:
                    rate_limit(self.rate_limit_api)
                
                # Process item
                start_time = time.time()
                
                try:
                    result = self.process_func(item)
                    duration = time.time() - start_time
                    
                    self.output_queue.put(ProcessingResult(
                        item=item,
                        result=result,
                        duration=duration
                    ))
                    
                except Exception as e:
                    duration = time.time() - start_time
                    logger.error(f"Worker error processing {item}: {e}")
                    
                    self.output_queue.put(ProcessingResult(
                        item=item,
                        error=e,
                        duration=duration
                    ))
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Unexpected worker error: {e}")


def process_batch_parallel(items: List[T],
                          process_func: Callable[[T], R],
                          max_workers: int = 5,
                          rate_limit_api: Optional[str] = None,
                          progress_callback: Optional[Callable[[int, int], None]] = None) -> List[ProcessingResult]:
    """
    Convenience function to process items in parallel.
    
    Args:
        items: Items to process
        process_func: Function to process each item
        max_workers: Maximum number of workers
        rate_limit_api: API name for rate limiting
        progress_callback: Progress callback function
        
    Returns:
        List of processing results
    """
    processor = ParallelProcessor(
        max_workers=max_workers,
        rate_limit_api=rate_limit_api,
        progress_callback=progress_callback
    )
    
    results, stats = processor.process_batch(items, process_func)
    
    logger.info(f"Batch processing complete: {stats.successful}/{stats.total_items} successful, "
               f"avg duration: {stats.average_duration:.2f}s")
    
    return results