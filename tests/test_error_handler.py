"""Tests for error handling."""

import json
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from genbank_tool.error_handler import (
    ErrorHandler, ErrorType, ErrorSeverity, ErrorContext,
    RecoveryStrategy, CheckpointData, get_error_handler, setup_error_handler
)


class TestErrorHandler:
    """Test cases for error handler."""
    
    @pytest.fixture
    def handler(self, tmp_path):
        """Create error handler for testing."""
        return ErrorHandler(
            log_dir=str(tmp_path / "logs"),
            checkpoint_dir=str(tmp_path / "checkpoints"),
            max_retries=3,
            enable_checkpoints=True
        )
    
    def test_error_classification(self, handler):
        """Test error type classification."""
        # Network timeout
        error = TimeoutError("Connection timed out")
        assert handler._classify_error(error) == ErrorType.NETWORK_TIMEOUT
        
        # Rate limit
        error = Exception("429 Too Many Requests")
        assert handler._classify_error(error) == ErrorType.API_RATE_LIMIT
        
        # Invalid gene
        error = ValueError("Gene not found: XYZ123")
        assert handler._classify_error(error) == ErrorType.INVALID_GENE_NAME
        
        # File I/O
        error = FileNotFoundError("File not found")
        assert handler._classify_error(error) == ErrorType.FILE_IO_ERROR
        
        # Unknown
        error = Exception("Something went wrong")
        assert handler._classify_error(error) == ErrorType.UNKNOWN
    
    def test_severity_determination(self, handler):
        """Test severity determination."""
        # Low retry count
        severity = handler._determine_severity(ErrorType.NETWORK_TIMEOUT, 0)
        assert severity == ErrorSeverity.WARNING
        
        # High retry count
        severity = handler._determine_severity(ErrorType.NETWORK_TIMEOUT, 3)
        assert severity == ErrorSeverity.CRITICAL
        
        # Validation error
        severity = handler._determine_severity(ErrorType.VALIDATION_ERROR, 0)
        assert severity == ErrorSeverity.WARNING
    
    def test_handle_error(self, handler):
        """Test error handling."""
        error = TimeoutError("Network timeout")
        
        context = handler.handle_error(
            error,
            operation="fetch_data",
            item_id="GENE123",
            api_name="ncbi",
            retry_count=1
        )
        
        assert context.error_type == ErrorType.NETWORK_TIMEOUT
        assert context.message == "Network timeout"
        assert context.operation == "fetch_data"
        assert context.item_id == "GENE123"
        assert context.api_name == "ncbi"
        assert context.retry_count == 1
        assert context.suggestion is not None
        
        # Check error was added to history
        assert len(handler.error_history) == 1
    
    def test_recovery_strategy(self, handler):
        """Test recovery strategy retrieval."""
        # Default strategy
        strategy = handler.get_recovery_strategy(ErrorType.NETWORK_TIMEOUT)
        assert strategy.can_retry is True
        assert strategy.retry_delay > 0
        
        # Custom strategy
        custom_strategy = RecoveryStrategy(
            can_retry=False,
            retry_delay=0,
            user_action_required=True
        )
        handler.add_recovery_strategy(ErrorType.PARSE_ERROR, custom_strategy)
        
        strategy = handler.get_recovery_strategy(ErrorType.PARSE_ERROR)
        assert strategy.can_retry is False
        assert strategy.user_action_required is True
    
    def test_checkpoint_creation(self, handler):
        """Test checkpoint creation and loading."""
        # Create checkpoint
        checkpoint_id = handler.create_checkpoint(
            operation="batch_process",
            total_items=100,
            processed_items=50,
            failed_items=["item1", "item2"],
            successful_items=["item3", "item4"],
            state_data={"key": "value"}
        )
        
        assert checkpoint_id is not None
        
        # Load checkpoint
        loaded = handler.load_checkpoint(checkpoint_id)
        assert loaded is not None
        assert loaded.operation == "batch_process"
        assert loaded.total_items == 100
        assert loaded.processed_items == 50
        assert len(loaded.failed_items) == 2
        assert loaded.state_data["key"] == "value"
    
    def test_checkpoint_listing(self, handler):
        """Test checkpoint listing."""
        # Create multiple checkpoints
        for i in range(3):
            handler.create_checkpoint(
                operation=f"batch_{i}",
                total_items=100,
                processed_items=i * 10,
                failed_items=[],
                successful_items=[],
                state_data={}
            )
            time.sleep(0.1)  # Ensure different timestamps
        
        # List checkpoints
        checkpoints = handler.list_checkpoints()
        assert len(checkpoints) == 3
        
        # Check ordering (most recent first)
        assert checkpoints[0]['operation'] == "batch_2"
        assert checkpoints[2]['operation'] == "batch_0"
    
    def test_checkpoint_cleanup(self, handler):
        """Test old checkpoint cleanup."""
        # Create old checkpoint
        old_checkpoint_id = handler.create_checkpoint(
            operation="old_batch",
            total_items=100,
            processed_items=100,
            failed_items=[],
            successful_items=[],
            state_data={}
        )
        
        # Modify checkpoint file timestamp to be old
        checkpoint_file = handler.checkpoint_dir / f"{old_checkpoint_id}.json"
        old_time = time.time() - (8 * 86400)  # 8 days ago
        import os
        os.utime(checkpoint_file, (old_time, old_time))
        
        # Create new checkpoint
        handler.create_checkpoint(
            operation="new_batch",
            total_items=100,
            processed_items=100,
            failed_items=[],
            successful_items=[],
            state_data={}
        )
        
        # Cleanup old checkpoints
        handler.cleanup_old_checkpoints(days=7)
        
        # Check that old checkpoint was removed
        checkpoints = handler.list_checkpoints()
        assert len(checkpoints) == 1
        assert checkpoints[0]['operation'] == "new_batch"
    
    def test_error_summary(self, handler):
        """Test error summary generation."""
        # Add various errors
        handler.handle_error(
            TimeoutError("Timeout 1"),
            operation="op1",
            retry_count=0
        )
        handler.handle_error(
            TimeoutError("Timeout 2"),
            operation="op2",
            retry_count=0
        )
        handler.handle_error(
            ValueError("Invalid gene"),
            operation="op3",
            retry_count=0
        )
        
        # Get summary
        summary = handler.get_error_summary()
        
        assert summary['total_errors'] == 3
        assert summary['by_type'][ErrorType.NETWORK_TIMEOUT.value] == 2
        assert summary['by_type'][ErrorType.INVALID_GENE_NAME.value] == 1
        assert len(summary['recent_errors']) == 3
    
    def test_error_report_export(self, handler, tmp_path):
        """Test error report export."""
        # Add some errors
        handler.handle_error(
            TimeoutError("Test timeout"),
            operation="test_op",
            item_id="TEST123"
        )
        
        # Export report
        report_file = tmp_path / "error_report.json"
        handler.export_error_report(str(report_file))
        
        # Check report file
        assert report_file.exists()
        
        with open(report_file, 'r') as f:
            report = json.load(f)
        
        assert 'generated_at' in report
        assert report['summary']['total_errors'] == 1
        assert len(report['detailed_errors']) == 1
        assert report['detailed_errors'][0]['operation'] == "test_op"
    
    def test_attempt_recovery(self, handler):
        """Test recovery attempt."""
        # Create error context
        context = ErrorContext(
            error_type=ErrorType.NETWORK_TIMEOUT,
            severity=ErrorSeverity.WARNING,
            message="Timeout",
            timestamp=time.time(),
            operation="test",
            retry_count=0,
            max_retries=3
        )
        
        # Should allow retry
        assert handler.attempt_recovery(context) is True
        
        # Max retries reached
        context.retry_count = 3
        assert handler.attempt_recovery(context) is False
        
        # Non-retryable error
        context.error_type = ErrorType.INVALID_GENE_NAME
        context.retry_count = 0
        assert handler.attempt_recovery(context) is False
    
    def test_custom_recovery_function(self, handler):
        """Test custom recovery function."""
        # Register custom recovery function
        recovery_called = False
        
        def custom_recovery(context):
            nonlocal recovery_called
            recovery_called = True
            return True
        
        handler.register_recovery_function("custom_recovery", custom_recovery)
        
        # Add strategy using custom function
        strategy = RecoveryStrategy(
            can_retry=True,
            retry_delay=0,
            fallback_action="custom_recovery"
        )
        handler.add_recovery_strategy(ErrorType.UNKNOWN, strategy)
        
        # Create error context
        context = ErrorContext(
            error_type=ErrorType.UNKNOWN,
            severity=ErrorSeverity.WARNING,
            message="Test",
            timestamp=time.time(),
            operation="test",
            retry_count=0,
            max_retries=3
        )
        
        # Attempt recovery
        result = handler.attempt_recovery(context)
        assert result is True
        assert recovery_called is True


class TestGlobalErrorHandler:
    """Test global error handler functions."""
    
    def test_get_error_handler(self):
        """Test getting global error handler."""
        handler1 = get_error_handler()
        handler2 = get_error_handler()
        
        # Should return same instance
        assert handler1 is handler2
    
    def test_setup_error_handler(self, tmp_path):
        """Test setting up custom error handler."""
        handler = setup_error_handler(
            log_dir=str(tmp_path / "custom_logs"),
            max_retries=5
        )
        
        assert handler.max_retries == 5
        assert handler.log_dir.name == "custom_logs"
        
        # Should be the global instance
        assert get_error_handler() is handler


