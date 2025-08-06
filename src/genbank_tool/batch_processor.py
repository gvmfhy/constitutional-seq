"""Batch processing with checkpoint/resume capability."""

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Generic
from concurrent.futures import ThreadPoolExecutor, as_completed

from .error_handler import get_error_handler
from .logging_config import ProgressLogger, get_logger
from .parallel_processor import ProcessingResult

logger = get_logger('batch_processor')

T = TypeVar('T')  # Input type
R = TypeVar('R')  # Result type


@dataclass
class BatchCheckpoint:
    """Checkpoint data for batch processing."""
    batch_id: str
    timestamp: float
    total_items: int
    processed_items: List[str]
    failed_items: List[str]
    pending_items: List[str]
    results: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_file(self, filepath: Path):
        """Save checkpoint to file."""
        data = asdict(self)
        data['timestamp_readable'] = datetime.fromtimestamp(self.timestamp).isoformat()
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def from_file(cls, filepath: Path) -> 'BatchCheckpoint':
        """Load checkpoint from file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Remove readable timestamp if present
        data.pop('timestamp_readable', None)
        
        return cls(**data)


class BatchProcessor(Generic[T, R]):
    """Process batches with checkpoint/resume capability."""
    
    def __init__(self,
                 checkpoint_dir: str = ".genbank_checkpoints",
                 enable_checkpoints: bool = True,
                 checkpoint_interval: int = 10,
                 max_workers: int = 1):
        """
        Initialize batch processor.
        
        Args:
            checkpoint_dir: Directory for checkpoint files
            enable_checkpoints: Enable checkpoint functionality
            checkpoint_interval: Save checkpoint every N items
            max_workers: Maximum parallel workers
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.enable_checkpoints = enable_checkpoints
        self.checkpoint_interval = checkpoint_interval
        self.max_workers = max_workers
        self.error_handler = get_error_handler()
        
        if self.enable_checkpoints:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def process_batch(self,
                      items: List[T],
                      process_func: Callable[[T], R],
                      batch_id: Optional[str] = None,
                      resume_from_checkpoint: Optional[str] = None,
                      item_id_func: Optional[Callable[[T], str]] = None,
                      on_success: Optional[Callable[[T, R], None]] = None,
                      on_error: Optional[Callable[[T, Exception], None]] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, R], BatchCheckpoint]:
        """
        Process batch of items with checkpoint support.
        
        Args:
            items: List of items to process
            process_func: Function to process each item
            batch_id: Unique batch identifier
            resume_from_checkpoint: Checkpoint ID to resume from
            item_id_func: Function to get unique ID for each item
            on_success: Callback for successful items
            on_error: Callback for failed items
            metadata: Additional metadata to store in checkpoint
            
        Returns:
            Tuple of (results dict, final checkpoint)
        """
        # Generate batch ID if not provided
        if batch_id is None:
            batch_id = f"batch_{int(time.time())}"
        
        # Default item ID function
        if item_id_func is None:
            item_id_func = lambda x: str(x)
        
        # Initialize or load checkpoint
        if resume_from_checkpoint:
            checkpoint = self._load_checkpoint(resume_from_checkpoint)
            if checkpoint is None:
                raise ValueError(f"Checkpoint not found: {resume_from_checkpoint}")
            
            logger.info(
                f"Resuming batch {batch_id} from checkpoint: "
                f"{len(checkpoint.processed_items)} processed, "
                f"{len(checkpoint.failed_items)} failed, "
                f"{len(checkpoint.pending_items)} pending"
            )
        else:
            # Create new checkpoint
            item_ids = [item_id_func(item) for item in items]
            checkpoint = BatchCheckpoint(
                batch_id=batch_id,
                timestamp=time.time(),
                total_items=len(items),
                processed_items=[],
                failed_items=[],
                pending_items=item_ids,
                results={},
                metadata=metadata or {}
            )
        
        # Create item lookup
        item_lookup = {item_id_func(item): item for item in items}
        
        # Setup progress logging
        progress = ProgressLogger(
            logger,
            len(checkpoint.pending_items),
            f"Processing batch {batch_id}"
        )
        
        # Process pending items
        processed_count = 0
        
        if self.max_workers > 1:
            # Parallel processing
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit tasks
                future_to_item = {}
                for item_id in checkpoint.pending_items:
                    if item_id in item_lookup:
                        item = item_lookup[item_id]
                        future = executor.submit(self._process_single_item, 
                                                 item, item_id, process_func)
                        future_to_item[future] = (item, item_id)
                
                # Process results
                for future in as_completed(future_to_item):
                    item, item_id = future_to_item[future]
                    result = future.result()
                    
                    self._handle_result(
                        item, item_id, result, checkpoint,
                        on_success, on_error, progress
                    )
                    
                    processed_count += 1
                    
                    # Save checkpoint periodically
                    if self.enable_checkpoints and processed_count % self.checkpoint_interval == 0:
                        self._save_checkpoint(checkpoint)
        else:
            # Sequential processing
            for item_id in checkpoint.pending_items[:]:  # Copy list to allow modification
                if item_id not in item_lookup:
                    logger.warning(f"Item {item_id} not found in batch, skipping")
                    checkpoint.pending_items.remove(item_id)
                    continue
                
                item = item_lookup[item_id]
                result = self._process_single_item(item, item_id, process_func)
                
                self._handle_result(
                    item, item_id, result, checkpoint,
                    on_success, on_error, progress
                )
                
                processed_count += 1
                
                # Save checkpoint periodically
                if self.enable_checkpoints and processed_count % self.checkpoint_interval == 0:
                    self._save_checkpoint(checkpoint)
        
        # Final checkpoint save
        if self.enable_checkpoints:
            self._save_checkpoint(checkpoint)
        
        # Log completion
        progress.complete()
        
        # Log summary
        logger.info(
            f"Batch {batch_id} complete: "
            f"{len(checkpoint.processed_items)} successful, "
            f"{len(checkpoint.failed_items)} failed"
        )
        
        return checkpoint.results, checkpoint
    
    def _process_single_item(self,
                             item: T,
                             item_id: str,
                             process_func: Callable[[T], R]) -> ProcessingResult:
        """Process a single item with error handling."""
        try:
            result = process_func(item)
            return ProcessingResult(
                item=item,
                result=result,
                error=None
            )
        except Exception as e:
            error_context = self.error_handler.handle_error(
                e,
                operation="process_item",
                item_id=item_id
            )
            
            return ProcessingResult(
                item=item,
                result=None,
                error=e
            )
    
    def _handle_result(self,
                       item: T,
                       item_id: str,
                       result: ProcessingResult,
                       checkpoint: BatchCheckpoint,
                       on_success: Optional[Callable],
                       on_error: Optional[Callable],
                       progress: ProgressLogger):
        """Handle processing result and update checkpoint."""
        if result.success:
            # Success
            checkpoint.processed_items.append(item_id)
            checkpoint.pending_items.remove(item_id)
            checkpoint.results[item_id] = result.result
            
            progress.update(success=True, item=item_id)
            
            if on_success:
                try:
                    on_success(item, result.result)
                except Exception as e:
                    logger.error(f"Success callback failed for {item_id}: {e}")
        else:
            # Failure
            checkpoint.failed_items.append(item_id)
            checkpoint.pending_items.remove(item_id)
            
            progress.update(success=False, item=item_id)
            
            if on_error:
                try:
                    on_error(item, result.error)
                except Exception as e:
                    logger.error(f"Error callback failed for {item_id}: {e}")
    
    def _save_checkpoint(self, checkpoint: BatchCheckpoint):
        """Save checkpoint to file."""
        try:
            filepath = self.checkpoint_dir / f"{checkpoint.batch_id}_checkpoint.json"
            checkpoint.to_file(filepath)
            logger.debug(f"Checkpoint saved: {checkpoint.batch_id}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    def _load_checkpoint(self, checkpoint_id: str) -> Optional[BatchCheckpoint]:
        """Load checkpoint from file."""
        try:
            # Try with and without _checkpoint suffix
            filepath = self.checkpoint_dir / f"{checkpoint_id}.json"
            if not filepath.exists():
                filepath = self.checkpoint_dir / f"{checkpoint_id}_checkpoint.json"
            
            if not filepath.exists():
                return None
            
            return BatchCheckpoint.from_file(filepath)
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List available checkpoints."""
        checkpoints = []
        
        if not self.enable_checkpoints:
            return checkpoints
        
        try:
            for filepath in self.checkpoint_dir.glob("*_checkpoint.json"):
                try:
                    checkpoint = BatchCheckpoint.from_file(filepath)
                    checkpoints.append({
                        'batch_id': checkpoint.batch_id,
                        'timestamp': datetime.fromtimestamp(checkpoint.timestamp).isoformat(),
                        'total_items': checkpoint.total_items,
                        'processed': len(checkpoint.processed_items),
                        'failed': len(checkpoint.failed_items),
                        'pending': len(checkpoint.pending_items),
                        'file': filepath.name
                    })
                except Exception:
                    continue
            
            # Sort by timestamp
            checkpoints.sort(key=lambda x: x['timestamp'], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list checkpoints: {e}")
        
        return checkpoints
    
    def retry_failed_items(self,
                           checkpoint_id: str,
                           process_func: Callable[[T], R],
                           items: List[T],
                           item_id_func: Optional[Callable[[T], str]] = None) -> Tuple[Dict[str, R], BatchCheckpoint]:
        """
        Retry failed items from a checkpoint.
        
        Args:
            checkpoint_id: Checkpoint to retry from
            process_func: Function to process each item
            items: Original items list
            item_id_func: Function to get unique ID for each item
            
        Returns:
            Tuple of (results dict, new checkpoint)
        """
        # Load checkpoint
        checkpoint = self._load_checkpoint(checkpoint_id)
        if checkpoint is None:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")
        
        # Default item ID function
        if item_id_func is None:
            item_id_func = lambda x: str(x)
        
        # Create item lookup
        item_lookup = {item_id_func(item): item for item in items}
        
        # Filter items to only failed ones
        failed_items = []
        for item_id in checkpoint.failed_items:
            if item_id in item_lookup:
                failed_items.append(item_lookup[item_id])
        
        if not failed_items:
            logger.info("No failed items to retry")
            return checkpoint.results, checkpoint
        
        logger.info(f"Retrying {len(failed_items)} failed items from batch {checkpoint.batch_id}")
        
        # Create new batch ID for retry
        retry_batch_id = f"{checkpoint.batch_id}_retry_{int(time.time())}"
        
        # Process failed items
        retry_results, retry_checkpoint = self.process_batch(
            failed_items,
            process_func,
            batch_id=retry_batch_id,
            item_id_func=item_id_func,
            metadata={
                'retry_of': checkpoint.batch_id,
                'original_failed_count': len(checkpoint.failed_items)
            }
        )
        
        # Merge results
        checkpoint.results.update(retry_results)
        
        # Update checkpoint with retry results
        for item_id in retry_checkpoint.processed_items:
            if item_id in checkpoint.failed_items:
                checkpoint.failed_items.remove(item_id)
                checkpoint.processed_items.append(item_id)
        
        return checkpoint.results, checkpoint
    
    def cleanup_old_checkpoints(self, days: int = 7):
        """Remove checkpoints older than specified days."""
        if not self.enable_checkpoints:
            return
        
        self.error_handler.cleanup_old_checkpoints(days)


# Convenience function for simple batch processing
def process_batch_with_checkpoint(
    items: List[T],
    process_func: Callable[[T], R],
    batch_id: Optional[str] = None,
    checkpoint_dir: str = ".genbank_checkpoints",
    max_workers: int = 1,
    **kwargs
) -> Tuple[Dict[str, R], BatchCheckpoint]:
    """
    Process batch with checkpoint support.
    
    Args:
        items: Items to process
        process_func: Processing function
        batch_id: Batch identifier
        checkpoint_dir: Checkpoint directory
        max_workers: Maximum parallel workers
        **kwargs: Additional arguments for process_batch
        
    Returns:
        Tuple of (results, checkpoint)
    """
    processor = BatchProcessor(
        checkpoint_dir=checkpoint_dir,
        max_workers=max_workers
    )
    
    return processor.process_batch(
        items,
        process_func,
        batch_id=batch_id,
        **kwargs
    )