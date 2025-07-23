"""Tests for rate limiter."""

import time
from threading import Thread

import pytest

from genbank_tool.rate_limiter import (
    RateLimitConfig, TokenBucket, RateLimiter,
    configure_rate_limit, rate_limit, get_rate_limit_stats
)


class TestTokenBucket:
    """Test cases for token bucket."""
    
    def test_basic_acquire(self):
        """Test basic token acquisition."""
        config = RateLimitConfig(requests_per_second=2, burst_size=4)
        bucket = TokenBucket(config)
        
        # Should be able to acquire burst size immediately
        assert bucket.acquire(1)
        assert bucket.acquire(1)
        assert bucket.acquire(1)
        assert bucket.acquire(1)
        
        # Next should require waiting
        start = time.time()
        assert bucket.acquire(1)
        elapsed = time.time() - start
        
        # Should have waited approximately 0.5s (1 token at 2/s rate)
        assert 0.4 < elapsed < 0.6
    
    def test_non_blocking_acquire(self):
        """Test non-blocking acquisition."""
        config = RateLimitConfig(requests_per_second=1, burst_size=1)
        bucket = TokenBucket(config)
        
        # First should succeed
        assert bucket.acquire(1, blocking=False)
        
        # Second should fail (no tokens left)
        assert not bucket.acquire(1, blocking=False)
        
        # Stats should show blocked request
        stats = bucket.get_stats()
        assert stats['blocked_count'] == 1
    
    def test_refill(self):
        """Test token refill over time."""
        config = RateLimitConfig(requests_per_second=10, burst_size=10)
        bucket = TokenBucket(config)
        
        # Use all tokens
        for _ in range(10):
            bucket.acquire(1)
        
        # Wait for refill
        time.sleep(0.5)
        
        # Should have ~5 tokens available
        count = 0
        while bucket.acquire(1, blocking=False):
            count += 1
        
        assert 4 <= count <= 6  # Allow some timing variance
    
    def test_stats(self):
        """Test statistics tracking."""
        config = RateLimitConfig(requests_per_second=10, burst_size=5)
        bucket = TokenBucket(config)
        
        # Make some requests
        bucket.acquire(2)
        bucket.acquire(1)
        bucket.acquire(1, blocking=False)
        
        stats = bucket.get_stats()
        assert stats['total_requests'] == 3
        assert stats['current_tokens'] < 5
        assert stats['max_tokens'] == 5


class TestRateLimiter:
    """Test cases for rate limiter."""
    
    def test_configure_and_acquire(self):
        """Test configuration and acquisition."""
        limiter = RateLimiter()
        
        # Configure API
        config = RateLimitConfig(requests_per_second=5)
        limiter.configure('test_api', config)
        
        # Should be able to acquire
        assert limiter.acquire('test_api')
        
        # Unknown API should always succeed
        assert limiter.acquire('unknown_api')
    
    def test_multiple_apis(self):
        """Test multiple API configurations."""
        limiter = RateLimiter()
        
        # Configure different APIs
        limiter.configure('api1', RateLimitConfig(requests_per_second=10))
        limiter.configure('api2', RateLimitConfig(requests_per_second=5))
        
        # Each should have independent limits
        start = time.time()
        
        # Use all tokens from api2 (burst=10)
        for _ in range(10):
            limiter.acquire('api2')
        
        # api1 should still be available immediately
        assert limiter.acquire('api1', blocking=False)
        
        # api2 should require waiting
        assert not limiter.acquire('api2', blocking=False)
    
    def test_global_functions(self):
        """Test global rate limiting functions."""
        # Configure
        configure_rate_limit('global_test', 10, burst_size=5)
        
        # Acquire
        assert rate_limit('global_test')
        
        # Get stats
        stats = get_rate_limit_stats('global_test')
        assert 'global_test' in stats
        assert stats['global_test']['total_requests'] >= 1


class TestConcurrentRateLimiting:
    """Test concurrent rate limiting scenarios."""
    
    def test_concurrent_requests(self):
        """Test rate limiting with concurrent threads."""
        configure_rate_limit('concurrent', 10, burst_size=5)
        
        results = []
        
        def worker():
            # Each worker tries to make 3 requests
            for _ in range(3):
                acquired = rate_limit('concurrent', blocking=False)
                results.append(acquired)
        
        # Start 5 threads
        threads = []
        for _ in range(5):
            t = Thread(target=worker)
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Should have 15 attempts, but only ~5 immediate successes
        assert len(results) == 15
        immediate_successes = sum(1 for r in results if r)
        assert 4 <= immediate_successes <= 6  # Burst size + timing variance
    
    def test_rate_enforcement(self):
        """Test that rate is enforced over time."""
        configure_rate_limit('rate_test', 5, burst_size=2)  # 5 req/s, burst of 2
        
        start_time = time.time()
        request_times = []
        
        # Make 10 requests
        for _ in range(10):
            rate_limit('rate_test')
            request_times.append(time.time() - start_time)
        
        # Total time should be approximately 1.6-1.8s
        # (2 immediate, then 8 more at 5/s = 1.6s)
        total_time = request_times[-1]
        assert 1.4 < total_time < 2.0
        
        # Verify spacing between requests after burst
        for i in range(3, len(request_times)):
            gap = request_times[i] - request_times[i-1]
            assert 0.15 < gap < 0.25  # ~0.2s between requests (5/s)