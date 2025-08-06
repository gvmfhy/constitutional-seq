"""Comprehensive error handling and recovery system."""

import json
import logging
import sys
import time
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable



class ErrorType(Enum):
    """Types of errors that can occur."""
    NETWORK_TIMEOUT = "network_timeout"
    API_RATE_LIMIT = "api_rate_limit"
    INVALID_GENE_NAME = "invalid_gene_name"
    PARTIAL_FAILURE = "partial_failure"
    DATABASE_ERROR = "database_error"
    VALIDATION_ERROR = "validation_error"
    FILE_IO_ERROR = "file_io_error"
    PARSE_ERROR = "parse_error"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Severity levels for errors."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    """Context information for an error."""
    error_type: ErrorType
    severity: ErrorSeverity
    message: str
    timestamp: float
    operation: str
    item_id: Optional[str] = None
    api_name: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    details: Optional[Dict[str, Any]] = None
    exception: Optional[Exception] = None
    traceback: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class RecoveryStrategy:
    """Strategy for recovering from an error."""
    can_retry: bool
    retry_delay: float
    fallback_action: Optional[str] = None
    user_action_required: bool = False
    recovery_function: Optional[Callable] = None
    suggestion: Optional[str] = None


@dataclass
class CheckpointData:
    """Data for checkpoint/resume functionality."""
    checkpoint_id: str
    timestamp: float
    operation: str
    total_items: int
    processed_items: int
    failed_items: List[str]
    successful_items: List[str]
    state_data: Dict[str, Any]
    errors: List[ErrorContext]


class ErrorHandler:
    """Handles errors with recovery mechanisms and logging."""
    
    # Default recovery strategies
    DEFAULT_STRATEGIES = {
        ErrorType.NETWORK_TIMEOUT: RecoveryStrategy(
            can_retry=True,
            retry_delay=5.0,
            fallback_action="wait_and_retry",
            suggestion="Network timeout detected. Will retry after 5 seconds."
        ),
        ErrorType.API_RATE_LIMIT: RecoveryStrategy(
            can_retry=True,
            retry_delay=60.0,
            fallback_action="exponential_backoff",
            suggestion="API rate limit reached. Waiting 60 seconds before retry."
        ),
        ErrorType.INVALID_GENE_NAME: RecoveryStrategy(
            can_retry=False,
            retry_delay=0,
            user_action_required=True,
            suggestion="Invalid gene name. Please check the gene symbol and try again."
        ),
        ErrorType.PARTIAL_FAILURE: RecoveryStrategy(
            can_retry=True,
            retry_delay=2.0,
            fallback_action="process_successful_items",
            suggestion="Partial failure detected. Will retry failed items."
        ),
        ErrorType.DATABASE_ERROR: RecoveryStrategy(
            can_retry=True,
            retry_delay=10.0,
            fallback_action="use_cache",
            suggestion="Database error. Checking cache for available data."
        ),
        ErrorType.VALIDATION_ERROR: RecoveryStrategy(
            can_retry=False,
            retry_delay=0,
            user_action_required=True,
            suggestion="Validation error. Please check the input data format."
        ),
        ErrorType.FILE_IO_ERROR: RecoveryStrategy(
            can_retry=True,
            retry_delay=1.0,
            fallback_action="alternative_path",
            suggestion="File I/O error. Checking permissions and retrying."
        ),
        ErrorType.PARSE_ERROR: RecoveryStrategy(
            can_retry=False,
            retry_delay=0,
            fallback_action="skip_item",
            suggestion="Parse error. Item will be skipped and logged."
        ),
        ErrorType.UNKNOWN: RecoveryStrategy(
            can_retry=True,
            retry_delay=5.0,
            fallback_action="log_and_continue",
            suggestion="Unknown error occurred. Will retry with caution."
        )
    }
    
    def __init__(self,
                 log_dir: str = ".genbank_logs",
                 checkpoint_dir: str = ".genbank_checkpoints",
                 max_retries: int = 3,
                 enable_checkpoints: bool = True):
        """
        Initialize error handler.
        
        Args:
            log_dir: Directory for log files
            checkpoint_dir: Directory for checkpoint files
            max_retries: Default maximum retry attempts
            enable_checkpoints: Enable checkpoint/resume functionality
        """
        self.log_dir = Path(log_dir)
        self.checkpoint_dir = Path(checkpoint_dir)
        self.max_retries = max_retries
        self.enable_checkpoints = enable_checkpoints
        
        # Create directories
        self.log_dir.mkdir(parents=True, exist_ok=True)
        if self.enable_checkpoints:
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self._setup_logging()
        
        # Error history for analysis
        self.error_history: List[ErrorContext] = []
        
        # Custom recovery strategies
        self.recovery_strategies = self.DEFAULT_STRATEGIES.copy()
        
        # Recovery functions
        self.recovery_functions: Dict[str, Callable] = {}
    
    def _setup_logging(self):
        """Setup comprehensive logging system."""
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_formatter = logging.Formatter(
            '%(levelname)s - %(message)s'
        )
        
        # File handler for all logs
        log_file = self.log_dir / f"genbank_tool_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        
        # File handler for errors only
        error_file = self.log_dir / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = logging.FileHandler(error_file)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Add handlers
        root_logger.addHandler(file_handler)
        root_logger.addHandler(error_handler)
        root_logger.addHandler(console_handler)
        
        # Create specific loggers
        self.logger = logging.getLogger(__name__)
        self.error_logger = logging.getLogger(f"{__name__}.errors")
    
    def handle_error(self,
                     error: Exception,
                     operation: str,
                     item_id: Optional[str] = None,
                     api_name: Optional[str] = None,
                     retry_count: int = 0,
                     **kwargs) -> ErrorContext:
        """
        Handle an error with appropriate logging and recovery.
        
        Args:
            error: The exception that occurred
            operation: The operation being performed
            item_id: Optional item identifier
            api_name: Optional API name
            retry_count: Current retry attempt
            **kwargs: Additional context data
            
        Returns:
            ErrorContext with error details and suggestions
        """
        # Determine error type
        error_type = self._classify_error(error)
        
        # Determine severity
        severity = self._determine_severity(error_type, retry_count)
        
        # Create error context
        context = ErrorContext(
            error_type=error_type,
            severity=severity,
            message=str(error),
            timestamp=time.time(),
            operation=operation,
            item_id=item_id,
            api_name=api_name,
            retry_count=retry_count,
            max_retries=self.max_retries,
            details=kwargs,
            exception=error,
            traceback=traceback.format_exc() if severity in [ErrorSeverity.ERROR, ErrorSeverity.CRITICAL] else None
        )
        
        # Get recovery strategy
        strategy = self.recovery_strategies.get(error_type, self.DEFAULT_STRATEGIES[ErrorType.UNKNOWN])
        if not context.suggestion and strategy.suggestion:
            context.suggestion = strategy.suggestion
        
        # Log the error
        self._log_error(context)
        
        # Add to history
        self.error_history.append(context)
        
        return context
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify the error type based on exception."""
        error_str = str(error).lower()
        error_type_name = type(error).__name__
        
        # Network timeouts
        if any(term in error_str for term in ['timeout', 'timed out', 'connection']):
            return ErrorType.NETWORK_TIMEOUT
        
        # Rate limits
        if any(term in error_str for term in ['rate limit', 'too many requests', '429']):
            return ErrorType.API_RATE_LIMIT
        
        # Invalid gene names
        if any(term in error_str for term in ['invalid gene', 'gene not found', 'unknown gene']):
            return ErrorType.INVALID_GENE_NAME
        
        # Database errors
        if any(term in error_str for term in ['database', 'db error', 'sql']):
            return ErrorType.DATABASE_ERROR
        
        # Validation errors
        if any(term in error_str for term in ['validation', 'invalid format', 'missing required']):
            return ErrorType.VALIDATION_ERROR
        
        # File I/O errors
        if error_type_name in ['FileNotFoundError', 'PermissionError', 'IOError']:
            return ErrorType.FILE_IO_ERROR
        
        # Parse errors
        if any(term in error_str for term in ['parse', 'parsing', 'json', 'xml']):
            return ErrorType.PARSE_ERROR
        
        return ErrorType.UNKNOWN
    
    def _determine_severity(self, error_type: ErrorType, retry_count: int) -> ErrorSeverity:
        """Determine error severity based on type and retry count."""
        if retry_count >= self.max_retries:
            return ErrorSeverity.CRITICAL
        
        if error_type in [ErrorType.INVALID_GENE_NAME, ErrorType.VALIDATION_ERROR]:
            return ErrorSeverity.WARNING
        
        if error_type in [ErrorType.NETWORK_TIMEOUT, ErrorType.API_RATE_LIMIT]:
            return ErrorSeverity.WARNING if retry_count < 2 else ErrorSeverity.ERROR
        
        return ErrorSeverity.ERROR
    
    def _log_error(self, context: ErrorContext):
        """Log error with appropriate level and details."""
        log_message = f"{context.operation} - {context.error_type.value}: {context.message}"
        
        if context.item_id:
            log_message += f" (item: {context.item_id})"
        
        if context.api_name:
            log_message += f" [API: {context.api_name}]"
        
        if context.retry_count > 0:
            log_message += f" (retry {context.retry_count}/{context.max_retries})"
        
        # Log with appropriate level
        if context.severity == ErrorSeverity.INFO:
            self.logger.info(log_message)
        elif context.severity == ErrorSeverity.WARNING:
            self.logger.warning(log_message)
        elif context.severity == ErrorSeverity.ERROR:
            self.error_logger.error(log_message)
            if context.traceback:
                self.error_logger.error(f"Traceback:\n{context.traceback}")
        elif context.severity == ErrorSeverity.CRITICAL:
            self.error_logger.critical(log_message)
            if context.traceback:
                self.error_logger.critical(f"Traceback:\n{context.traceback}")
        
        # Log suggestion if available
        if context.suggestion:
            self.logger.info(f"Suggestion: {context.suggestion}")
    
    def get_recovery_strategy(self, error_type: ErrorType) -> RecoveryStrategy:
        """Get recovery strategy for error type."""
        return self.recovery_strategies.get(error_type, self.DEFAULT_STRATEGIES[ErrorType.UNKNOWN])
    
    def add_recovery_strategy(self, error_type: ErrorType, strategy: RecoveryStrategy):
        """Add custom recovery strategy."""
        self.recovery_strategies[error_type] = strategy
    
    def register_recovery_function(self, name: str, func: Callable):
        """Register a custom recovery function."""
        self.recovery_functions[name] = func
    
    def attempt_recovery(self, context: ErrorContext) -> bool:
        """
        Attempt to recover from an error.
        
        Args:
            context: Error context
            
        Returns:
            True if recovery successful, False otherwise
        """
        strategy = self.get_recovery_strategy(context.error_type)
        
        if not strategy.can_retry or context.retry_count >= context.max_retries:
            return False
        
        # Wait before retry
        if strategy.retry_delay > 0:
            self.logger.info(f"Waiting {strategy.retry_delay}s before retry...")
            time.sleep(strategy.retry_delay)
        
        # Execute recovery function if available
        if strategy.recovery_function:
            try:
                return strategy.recovery_function(context)
            except Exception as e:
                self.logger.error(f"Recovery function failed: {e}")
                return False
        
        # Check for custom recovery function
        if strategy.fallback_action and strategy.fallback_action in self.recovery_functions:
            try:
                return self.recovery_functions[strategy.fallback_action](context)
            except Exception as e:
                self.logger.error(f"Custom recovery function failed: {e}")
                return False
        
        return True  # Allow retry
    
    def create_checkpoint(self,
                          operation: str,
                          total_items: int,
                          processed_items: int,
                          failed_items: List[str],
                          successful_items: List[str],
                          state_data: Dict[str, Any]) -> Optional[str]:
        """
        Create a checkpoint for recovery.
        
        Returns:
            Checkpoint ID if successful, None otherwise
        """
        if not self.enable_checkpoints:
            return None
        
        checkpoint_id = f"{operation}_{int(time.time())}"
        
        checkpoint = CheckpointData(
            checkpoint_id=checkpoint_id,
            timestamp=time.time(),
            operation=operation,
            total_items=total_items,
            processed_items=processed_items,
            failed_items=failed_items,
            successful_items=successful_items,
            state_data=state_data,
            errors=[asdict(e) for e in self.error_history[-10:]]  # Last 10 errors
        )
        
        try:
            checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.json"
            with open(checkpoint_file, 'w') as f:
                json.dump(asdict(checkpoint), f, indent=2)
            
            self.logger.info(f"Checkpoint created: {checkpoint_id}")
            return checkpoint_id
            
        except Exception as e:
            self.logger.error(f"Failed to create checkpoint: {e}")
            return None
    
    def load_checkpoint(self, checkpoint_id: str) -> Optional[CheckpointData]:
        """Load a checkpoint for resuming."""
        if not self.enable_checkpoints:
            return None
        
        try:
            checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.json"
            
            if not checkpoint_file.exists():
                self.logger.error(f"Checkpoint not found: {checkpoint_id}")
                return None
            
            with open(checkpoint_file, 'r') as f:
                data = json.load(f)
            
            # Convert back to CheckpointData
            checkpoint = CheckpointData(
                checkpoint_id=data['checkpoint_id'],
                timestamp=data['timestamp'],
                operation=data['operation'],
                total_items=data['total_items'],
                processed_items=data['processed_items'],
                failed_items=data['failed_items'],
                successful_items=data['successful_items'],
                state_data=data['state_data'],
                errors=data['errors']
            )
            
            self.logger.info(f"Checkpoint loaded: {checkpoint_id}")
            return checkpoint
            
        except Exception as e:
            self.logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """List available checkpoints."""
        if not self.enable_checkpoints:
            return []
        
        checkpoints = []
        
        try:
            for checkpoint_file in self.checkpoint_dir.glob("*.json"):
                try:
                    with open(checkpoint_file, 'r') as f:
                        data = json.load(f)
                    
                    checkpoints.append({
                        'id': data['checkpoint_id'],
                        'operation': data['operation'],
                        'timestamp': datetime.fromtimestamp(data['timestamp']).isoformat(),
                        'progress': f"{data['processed_items']}/{data['total_items']}",
                        'failed': len(data['failed_items'])
                    })
                except Exception:
                    continue
            
            # Sort by timestamp
            checkpoints.sort(key=lambda x: x['timestamp'], reverse=True)
            
        except Exception as e:
            self.logger.error(f"Failed to list checkpoints: {e}")
        
        return checkpoints
    
    def cleanup_old_checkpoints(self, days: int = 7):
        """Remove checkpoints older than specified days."""
        if not self.enable_checkpoints:
            return
        
        cutoff_time = time.time() - (days * 86400)
        removed = 0
        
        try:
            for checkpoint_file in self.checkpoint_dir.glob("*.json"):
                if checkpoint_file.stat().st_mtime < cutoff_time:
                    checkpoint_file.unlink()
                    removed += 1
            
            if removed > 0:
                self.logger.info(f"Removed {removed} old checkpoints")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup checkpoints: {e}")
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of errors for reporting."""
        if not self.error_history:
            return {
                'total_errors': 0,
                'by_type': {},
                'by_severity': {},
                'recent_errors': []
            }
        
        # Count by type
        by_type = {}
        for error in self.error_history:
            error_type = error.error_type.value
            by_type[error_type] = by_type.get(error_type, 0) + 1
        
        # Count by severity
        by_severity = {}
        for error in self.error_history:
            severity = error.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        # Recent errors
        recent_errors = []
        for error in self.error_history[-5:]:
            recent_errors.append({
                'type': error.error_type.value,
                'severity': error.severity.value,
                'message': error.message,
                'operation': error.operation,
                'timestamp': datetime.fromtimestamp(error.timestamp).isoformat(),
                'suggestion': error.suggestion
            })
        
        return {
            'total_errors': len(self.error_history),
            'by_type': by_type,
            'by_severity': by_severity,
            'recent_errors': recent_errors
        }
    
    def export_error_report(self, output_file: str):
        """Export detailed error report."""
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': self.get_error_summary(),
            'detailed_errors': []
        }
        
        for error in self.error_history:
            error_dict = asdict(error)
            # Remove exception object (not serializable)
            error_dict.pop('exception', None)
            # Convert enums to strings
            error_dict['error_type'] = error.error_type.value
            error_dict['severity'] = error.severity.value
            error_dict['timestamp'] = datetime.fromtimestamp(error.timestamp).isoformat()
            
            report['detailed_errors'].append(error_dict)
        
        try:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            self.logger.info(f"Error report exported to {output_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to export error report: {e}")


# Global error handler instance
_error_handler = None


def get_error_handler() -> ErrorHandler:
    """Get global error handler instance."""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


def setup_error_handler(**kwargs) -> ErrorHandler:
    """Setup error handler with custom configuration."""
    global _error_handler
    _error_handler = ErrorHandler(**kwargs)
    return _error_handler