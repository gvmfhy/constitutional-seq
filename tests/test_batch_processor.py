"""Tests for batch processor with checkpoint/resume."""

import json
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from genbank_tool.batch_processor import (
    BatchProcessor, BatchCheckpoint, process_batch_with_checkpoint
)


class TestBatchCheckpoint:
    """Test cases for batch checkpoint."""
    
    def test_checkpoint_creation(self):
        """Test checkpoint data creation."""
        checkpoint = BatchCheckpoint(
            batch_id="test_batch",
            timestamp=time.time(),
            total_items=100,
            processed_items=["item1", "item2"],
            failed_items=["item3"],
            pending_items=["item4", "item5"],
            results={"item1": "result1", "item2": "result2"},
            metadata={"key": "value"}
        )
        
        assert checkpoint.batch_id == "test_batch"
        assert checkpoint.total_items == 100
        assert len(checkpoint.processed_items) == 2
        assert len(checkpoint.failed_items) == 1
        assert len(checkpoint.pending_items) == 2
    
    def test_checkpoint_serialization(self, tmp_path):
        """Test checkpoint save/load."""
        checkpoint = BatchCheckpoint(
            batch_id="test_batch",
            timestamp=time.time(),
            total_items=10,
            processed_items=["item1"],
            failed_items=["item2"],
            pending_items=["item3"],
            results={"item1": {"data": "value"}},
            metadata={"test": True}
        )
        
        # Save to file
        filepath = tmp_path / "test_checkpoint.json"
        checkpoint.to_file(filepath)
        
        # Load from file
        loaded = BatchCheckpoint.from_file(filepath)
        
        assert loaded.batch_id == checkpoint.batch_id
        assert loaded.total_items == checkpoint.total_items
        assert loaded.processed_items == checkpoint.processed_items
        assert loaded.results == checkpoint.results


class TestBatchProcessor:
    """Test cases for batch processor."""
    
    @pytest.fixture
    def processor(self, tmp_path):
        """Create batch processor for testing."""
        return BatchProcessor(
            checkpoint_dir=str(tmp_path / "checkpoints"),
            enable_checkpoints=True,
            checkpoint_interval=2,
            max_workers=1
        )
    
    def test_basic_processing(self, processor):
        """Test basic batch processing."""
        items = ['item1', 'item2', 'item3']
        
        def process_func(item):
            return f"processed_{item}"
        
        results, checkpoint = processor.process_batch(
            items,
            process_func,
            batch_id="test_batch"
        )
        
        assert len(results) == 3
        assert results['item1'] == "processed_item1"
        assert results['item2'] == "processed_item2"
        assert results['item3'] == "processed_item3"
        
        assert checkpoint.batch_id == "test_batch"
        assert len(checkpoint.processed_items) == 3
        assert len(checkpoint.failed_items) == 0
        assert len(checkpoint.pending_items) == 0
    
    def test_processing_with_errors(self, processor):
        """Test processing with some failures."""
        items = ['good1', 'bad', 'good2']
        
        def process_func(item):
            if item == 'bad':
                raise ValueError(f"Cannot process {item}")
            return f"processed_{item}"
        
        error_items = []
        
        def on_error(item, error):
            error_items.append((item, str(error)))
        
        results, checkpoint = processor.process_batch(
            items,
            process_func,
            on_error=on_error
        )
        
        assert len(results) == 2
        assert 'good1' in results
        assert 'good2' in results
        assert 'bad' not in results
        
        assert len(checkpoint.processed_items) == 2
        assert len(checkpoint.failed_items) == 1
        assert 'bad' in checkpoint.failed_items
        assert len(error_items) == 1
    
    def test_checkpoint_saving(self, processor):
        """Test periodic checkpoint saving."""
        items = ['item1', 'item2', 'item3', 'item4']
        
        save_count = 0
        original_save = processor._save_checkpoint
        
        def mock_save(checkpoint):
            nonlocal save_count
            save_count += 1
            original_save(checkpoint)
        
        processor._save_checkpoint = mock_save
        processor.checkpoint_interval = 2  # Save every 2 items
        
        def process_func(item):
            time.sleep(0.01)  # Simulate work
            return f"processed_{item}"
        
        results, checkpoint = processor.process_batch(
            items,
            process_func
        )
        
        # Should save after items 2 and 4, plus final save
        assert save_count >= 2
    
    def test_resume_from_checkpoint(self, processor):
        """Test resuming from checkpoint."""
        # Create initial checkpoint
        initial_checkpoint = BatchCheckpoint(
            batch_id="resume_test",
            timestamp=time.time(),
            total_items=5,
            processed_items=["item1", "item2"],
            failed_items=["item3"],
            pending_items=["item4", "item5"],
            results={"item1": "result1", "item2": "result2"},
            metadata={}
        )
        
        # Save checkpoint
        processor._save_checkpoint(initial_checkpoint)
        
        # Resume processing
        items = ['item1', 'item2', 'item3', 'item4', 'item5']
        
        def process_func(item):
            return f"processed_{item}"
        
        results, checkpoint = processor.process_batch(
            items,
            process_func,
            resume_from_checkpoint="resume_test"
        )
        
        # Should only process pending items
        assert 'item4' in results
        assert 'item5' in results
        
        # Should preserve previous results
        assert results['item1'] == "result1"
        assert results['item2'] == "result2"
        
        # Check final state
        assert len(checkpoint.processed_items) == 4  # 2 original + 2 new
        assert len(checkpoint.failed_items) == 1  # item3 still failed
    
    def test_parallel_processing(self, processor):
        """Test parallel batch processing."""
        processor.max_workers = 3
        items = [f"item{i}" for i in range(10)]
        
        process_order = []
        
        def process_func(item):
            process_order.append(item)
            time.sleep(0.01)  # Simulate work
            return f"processed_{item}"
        
        results, checkpoint = processor.process_batch(
            items,
            process_func
        )
        
        assert len(results) == 10
        assert all(f"item{i}" in results for i in range(10))
        
        # Items may not be processed in order due to parallelism
        assert len(process_order) == 10
    
    def test_custom_item_id_function(self, processor):
        """Test custom item ID extraction."""
        items = [
            {'id': 'A', 'data': 'value1'},
            {'id': 'B', 'data': 'value2'}
        ]
        
        def process_func(item):
            return item['data'].upper()
        
        def item_id_func(item):
            return item['id']
        
        results, checkpoint = processor.process_batch(
            items,
            process_func,
            item_id_func=item_id_func
        )
        
        assert results['A'] == 'VALUE1'
        assert results['B'] == 'VALUE2'
    
    def test_success_callback(self, processor):
        """Test success callback."""
        items = ['item1', 'item2']
        successful_items = []
        
        def process_func(item):
            return f"processed_{item}"
        
        def on_success(item, result):
            successful_items.append((item, result))
        
        results, checkpoint = processor.process_batch(
            items,
            process_func,
            on_success=on_success
        )
        
        assert len(successful_items) == 2
        assert successful_items[0] == ('item1', 'processed_item1')
        assert successful_items[1] == ('item2', 'processed_item2')
    
    def test_list_checkpoints(self, processor):
        """Test listing available checkpoints."""
        # Create multiple checkpoints
        for i in range(3):
            checkpoint = BatchCheckpoint(
                batch_id=f"batch_{i}",
                timestamp=time.time() + i,
                total_items=10,
                processed_items=[f"item{j}" for j in range(i)],
                failed_items=[],
                pending_items=[],
                results={},
                metadata={}
            )
            processor._save_checkpoint(checkpoint)
            time.sleep(0.1)
        
        # List checkpoints
        checkpoints = processor.list_checkpoints()
        
        assert len(checkpoints) == 3
        # Should be sorted by timestamp (most recent first)
        assert checkpoints[0]['batch_id'] == 'batch_2'
        assert checkpoints[2]['batch_id'] == 'batch_0'
    
    def test_retry_failed_items(self, processor):
        """Test retrying failed items."""
        # Create checkpoint with failed items
        checkpoint = BatchCheckpoint(
            batch_id="retry_test",
            timestamp=time.time(),
            total_items=5,
            processed_items=["item1", "item2"],
            failed_items=["bad1", "bad2", "bad3"],
            pending_items=[],
            results={"item1": "result1", "item2": "result2"},
            metadata={}
        )
        processor._save_checkpoint(checkpoint)
        
        # All items including failed ones
        items = ['item1', 'item2', 'bad1', 'bad2', 'bad3']
        
        retry_count = 0
        
        def process_func(item):
            nonlocal retry_count
            if item.startswith('bad'):
                retry_count += 1
                # Succeed on retry for bad1 and bad2
                if item in ['bad1', 'bad2']:
                    return f"retry_success_{item}"
                else:
                    raise ValueError(f"Still failing: {item}")
            return f"processed_{item}"
        
        results, new_checkpoint = processor.retry_failed_items(
            "retry_test",
            process_func,
            items
        )
        
        # Should have retried 3 items
        assert retry_count == 3
        
        # Check results
        assert results['bad1'] == 'retry_success_bad1'
        assert results['bad2'] == 'retry_success_bad2'
        
        # bad3 should still be in failed
        assert 'bad3' in new_checkpoint.failed_items
        assert 'bad1' not in new_checkpoint.failed_items
        assert 'bad2' not in new_checkpoint.failed_items
    
    def test_checkpoint_not_found(self, processor):
        """Test handling of missing checkpoint."""
        # _load_checkpoint returns None for missing checkpoints
        assert processor._load_checkpoint("nonexistent_checkpoint") is None
        
        with pytest.raises(ValueError, match="Checkpoint not found"):
            processor.retry_failed_items(
                "nonexistent_checkpoint",
                lambda x: x,
                []
            )
    
    def test_disabled_checkpoints(self, tmp_path):
        """Test processor with checkpoints disabled."""
        processor = BatchProcessor(
            checkpoint_dir=str(tmp_path / "checkpoints"),
            enable_checkpoints=False
        )
        
        items = ['item1', 'item2']
        
        def process_func(item):
            return f"processed_{item}"
        
        results, checkpoint = processor.process_batch(
            items,
            process_func
        )
        
        assert len(results) == 2
        
        # Checkpoint operations should be no-ops
        assert processor.list_checkpoints() == []
        assert processor._load_checkpoint("any_id") is None


class TestConvenienceFunction:
    """Test convenience functions."""
    
    def test_process_batch_with_checkpoint(self, tmp_path):
        """Test convenience function."""
        items = ['a', 'b', 'c']
        
        def process_func(item):
            return item.upper()
        
        results, checkpoint = process_batch_with_checkpoint(
            items,
            process_func,
            batch_id="test",
            checkpoint_dir=str(tmp_path / "checkpoints")
        )
        
        assert results == {'a': 'A', 'b': 'B', 'c': 'C'}
        assert checkpoint.batch_id == "test"
        assert len(checkpoint.processed_items) == 3