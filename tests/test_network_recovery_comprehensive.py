"""Comprehensive tests for network recovery module."""

import time
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests

from genbank_tool.network_recovery import (
    NetworkRecovery, CircuitBreaker, ExponentialBackoff,
    AdaptiveRetry, RecoveryStrategy, NetworkHealth,
    CircuitState
)


class TestExponentialBackoff:
    """Test cases for exponential backoff."""
    
    def test_initial_delay(self):
        """Test initial backoff delay."""
        backoff = ExponentialBackoff(base_delay=1.0, max_delay=30.0)
        delay = backoff.get_delay(attempt=1)
        assert 0.5 <= delay <= 1.5  # With jitter
    
    def test_exponential_growth(self):
        """Test exponential growth of delays."""
        backoff = ExponentialBackoff(base_delay=1.0, max_delay=30.0, jitter=False)
        
        assert backoff.get_delay(1) == 1.0
        assert backoff.get_delay(2) == 2.0
        assert backoff.get_delay(3) == 4.0
        assert backoff.get_delay(4) == 8.0
    
    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        backoff = ExponentialBackoff(base_delay=1.0, max_delay=10.0, jitter=False)
        
        assert backoff.get_delay(10) == 10.0  # Should be capped
        assert backoff.get_delay(100) == 10.0  # Still capped
    
    def test_jitter(self):
        """Test jitter adds randomness."""
        backoff = ExponentialBackoff(base_delay=2.0, jitter=True)
        
        delays = [backoff.get_delay(2) for _ in range(10)]
        # All should be different due to jitter
        assert len(set(delays)) > 1
        # All should be within expected range
        assert all(2.0 <= d <= 6.0 for d in delays)  # 4.0 ± 50%
    
    def test_reset(self):
        """Test resetting backoff."""
        backoff = ExponentialBackoff(base_delay=1.0)
        
        # Increase attempts
        assert backoff.get_delay(5) > 1.0
        
        # Reset
        backoff.reset()
        assert backoff.get_delay(1) <= 1.5  # Back to initial


class TestCircuitBreaker:
    """Test cases for circuit breaker."""
    
    def test_initial_state(self):
        """Test circuit breaker starts closed."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=5)
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed()
    
    def test_failure_counting(self):
        """Test failure counting."""
        breaker = CircuitBreaker(failure_threshold=3)
        
        breaker.record_failure()
        assert breaker.failure_count == 1
        assert breaker.is_closed()
        
        breaker.record_failure()
        assert breaker.failure_count == 2
        assert breaker.is_closed()
        
        breaker.record_failure()
        assert breaker.failure_count == 3
        assert breaker.is_open()  # Now open
    
    def test_success_resets_count(self):
        """Test success resets failure count."""
        breaker = CircuitBreaker(failure_threshold=3)
        
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2
        
        breaker.record_success()
        assert breaker.failure_count == 0
        assert breaker.is_closed()
    
    def test_half_open_state(self):
        """Test half-open state after timeout."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.is_open()
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        # Should be half-open now
        assert breaker.is_half_open()
        
        # Success should close it
        breaker.record_success()
        assert breaker.is_closed()
    
    def test_half_open_failure_reopens(self):
        """Test failure in half-open state reopens circuit."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        
        # Wait for half-open
        time.sleep(0.15)
        assert breaker.is_half_open()
        
        # Failure should reopen
        breaker.record_failure()
        assert breaker.is_open()
    
    def test_reset(self):
        """Test resetting circuit breaker."""
        breaker = CircuitBreaker(failure_threshold=2)
        
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.is_open()
        
        breaker.reset()
        assert breaker.is_closed()
        assert breaker.failure_count == 0


class TestAdaptiveRetry:
    """Test cases for adaptive retry strategy."""
    
    def test_initial_parameters(self):
        """Test initial retry parameters."""
        retry = AdaptiveRetry()
        assert retry.success_rate == 1.0
        assert retry.avg_response_time == 0.0
        assert retry.get_timeout() == 30.0  # Default
    
    def test_success_tracking(self):
        """Test tracking successful attempts."""
        retry = AdaptiveRetry()
        
        retry.record_attempt(success=True, response_time=1.0)
        retry.record_attempt(success=True, response_time=2.0)
        
        assert retry.total_attempts == 2
        assert retry.successful_attempts == 2
        assert retry.success_rate == 1.0
        assert retry.avg_response_time == 1.5
    
    def test_failure_tracking(self):
        """Test tracking failed attempts."""
        retry = AdaptiveRetry()
        
        retry.record_attempt(success=True, response_time=1.0)
        retry.record_attempt(success=False, response_time=0.0)
        retry.record_attempt(success=False, response_time=0.0)
        
        assert retry.total_attempts == 3
        assert retry.successful_attempts == 1
        assert retry.success_rate == pytest.approx(0.333, rel=0.01)
    
    def test_adaptive_timeout(self):
        """Test adaptive timeout adjustment."""
        retry = AdaptiveRetry()
        
        # Fast responses should decrease timeout
        for _ in range(10):
            retry.record_attempt(success=True, response_time=0.5)
        
        timeout = retry.get_timeout()
        assert timeout < 30.0  # Should be less than default
        
        # Slow responses should increase timeout
        for _ in range(10):
            retry.record_attempt(success=True, response_time=20.0)
        
        new_timeout = retry.get_timeout()
        assert new_timeout > timeout
    
    def test_should_retry(self):
        """Test retry decision logic."""
        retry = AdaptiveRetry(max_attempts=3)
        
        assert retry.should_retry(attempt=1)
        assert retry.should_retry(attempt=2)
        assert retry.should_retry(attempt=3)
        assert not retry.should_retry(attempt=4)  # Exceeded max
    
    def test_low_success_rate_affects_retry(self):
        """Test low success rate affects retry decision."""
        retry = AdaptiveRetry(min_success_rate=0.5)
        
        # Start with failures
        for _ in range(10):
            retry.record_attempt(success=False, response_time=1.0)
        
        # Success rate too low
        assert retry.success_rate < 0.5
        # May still retry initially but with adjusted strategy
        assert retry.should_retry(attempt=1)


class TestNetworkHealth:
    """Test cases for network health monitoring."""
    
    def test_initial_health(self):
        """Test initial health state."""
        health = NetworkHealth()
        status = health.get_status()
        
        assert status['health'] == 'unknown'
        assert status['total_requests'] == 0
    
    def test_healthy_status(self):
        """Test healthy network status."""
        health = NetworkHealth()
        
        # Record successful requests
        for _ in range(10):
            health.record_request(success=True, latency=0.1)
        
        status = health.get_status()
        assert status['health'] == 'healthy'
        assert status['success_rate'] == 1.0
        assert status['avg_latency'] == 0.1
    
    def test_degraded_status(self):
        """Test degraded network status."""
        health = NetworkHealth()
        
        # Mix of success and failures
        for _ in range(7):
            health.record_request(success=True, latency=0.5)
        for _ in range(3):
            health.record_request(success=False, latency=0.0)
        
        status = health.get_status()
        assert status['health'] == 'degraded'
        assert status['success_rate'] == 0.7
    
    def test_unhealthy_status(self):
        """Test unhealthy network status."""
        health = NetworkHealth()
        
        # Mostly failures
        for _ in range(2):
            health.record_request(success=True, latency=1.0)
        for _ in range(8):
            health.record_request(success=False, latency=0.0)
        
        status = health.get_status()
        assert status['health'] == 'unhealthy'
        assert status['success_rate'] == 0.2
    
    def test_error_tracking(self):
        """Test error type tracking."""
        health = NetworkHealth()
        
        health.record_error('timeout')
        health.record_error('timeout')
        health.record_error('connection_error')
        
        status = health.get_status()
        assert status['errors']['timeout'] == 2
        assert status['errors']['connection_error'] == 1


class TestNetworkRecovery:
    """Test cases for main network recovery class."""
    
    @pytest.fixture
    def recovery(self):
        """Create NetworkRecovery instance."""
        return NetworkRecovery(
            max_retries=3,
            initial_delay=1.0,
            max_delay=10.0
        )
    
    def test_successful_request(self, recovery):
        """Test successful request without retries."""
        mock_func = Mock(return_value="success")
        
        result = recovery.execute_with_recovery(mock_func)
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    def test_retry_on_timeout(self, recovery):
        """Test retry on timeout error."""
        mock_func = Mock(side_effect=[
            requests.Timeout("Timeout"),
            requests.Timeout("Timeout"),
            "success"
        ])
        
        result = recovery.execute_with_recovery(mock_func)
        
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_retry_on_connection_error(self, recovery):
        """Test retry on connection error."""
        mock_func = Mock(side_effect=[
            requests.ConnectionError("Connection failed"),
            "success"
        ])
        
        result = recovery.execute_with_recovery(mock_func)
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    def test_max_retries_exceeded(self, recovery):
        """Test max retries exceeded."""
        mock_func = Mock(side_effect=requests.Timeout("Timeout"))
        
        with pytest.raises(requests.Timeout):
            recovery.execute_with_recovery(mock_func)
        
        assert mock_func.call_count == 4  # Initial + 3 retries
    
    def test_circuit_breaker_integration(self, recovery):
        """Test circuit breaker prevents calls."""
        # Force circuit to open
        for _ in range(5):
            try:
                recovery.execute_with_recovery(
                    Mock(side_effect=requests.Timeout())
                )
            except:
                pass
        
        # Circuit should be open now
        assert recovery.circuit_breaker.is_open()
        
        # New request should fail immediately
        mock_func = Mock(return_value="success")
        
        with pytest.raises(Exception) as exc_info:
            recovery.execute_with_recovery(mock_func)
        
        assert "Circuit breaker is open" in str(exc_info.value)
        assert mock_func.call_count == 0  # Not called
    
    def test_strategy_selection(self, recovery):
        """Test different recovery strategies."""
        # Test EXPONENTIAL_BACKOFF
        recovery.strategy = RecoveryStrategy.EXPONENTIAL_BACKOFF
        mock_func = Mock(side_effect=[requests.Timeout(), "success"])
        
        with patch('time.sleep') as mock_sleep:
            result = recovery.execute_with_recovery(mock_func)
            assert result == "success"
            assert mock_sleep.called
        
        # Test CIRCUIT_BREAKER
        recovery.strategy = RecoveryStrategy.CIRCUIT_BREAKER
        recovery.circuit_breaker.reset()
        mock_func = Mock(return_value="success")
        
        result = recovery.execute_with_recovery(mock_func)
        assert result == "success"
        
        # Test ADAPTIVE
        recovery.strategy = RecoveryStrategy.ADAPTIVE
        mock_func = Mock(return_value="success")
        
        result = recovery.execute_with_recovery(mock_func)
        assert result == "success"
    
    def test_fallback_function(self, recovery):
        """Test fallback function execution."""
        primary_func = Mock(side_effect=Exception("Failed"))
        fallback_func = Mock(return_value="fallback_result")
        
        recovery.set_fallback(fallback_func)
        
        result = recovery.execute_with_recovery(primary_func)
        
        assert result == "fallback_result"
        assert fallback_func.called
    
    def test_health_monitoring(self, recovery):
        """Test health monitoring during requests."""
        mock_func = Mock(return_value="success")
        
        # Execute several successful requests
        for _ in range(5):
            recovery.execute_with_recovery(mock_func)
        
        health_status = recovery.health_monitor.get_status()
        assert health_status['total_requests'] == 5
        assert health_status['success_rate'] == 1.0
        
        # Execute with failures
        failing_func = Mock(side_effect=requests.Timeout())
        
        for _ in range(3):
            try:
                recovery.execute_with_recovery(failing_func)
            except:
                pass
        
        health_status = recovery.health_monitor.get_status()
        assert health_status['total_requests'] > 5
        assert health_status['success_rate'] < 1.0
    
    def test_timeout_configuration(self, recovery):
        """Test timeout configuration."""
        mock_func = Mock(return_value="success")
        
        # Set custom timeout
        recovery.set_timeout(5.0)
        
        with patch('requests.Session.request') as mock_request:
            mock_request.return_value = Mock(status_code=200)
            
            # Simulate an HTTP request
            def http_request():
                session = requests.Session()
                return session.get('http://example.com', timeout=recovery.timeout)
            
            recovery.execute_with_recovery(http_request)
            
            # Check timeout was passed
            call_args = mock_request.call_args
            assert call_args[1].get('timeout') == 5.0