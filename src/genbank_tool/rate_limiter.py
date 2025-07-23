"""Rate limiting for API calls with token bucket algorithm."""

import logging
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_second: float
    burst_size: Optional[int] = None  # Max tokens in bucket
    
    def __post_init__(self):
        if self.burst_size is None:
            # Default burst size is 2x the rate
            self.burst_size = max(1, int(self.requests_per_second * 2))


class TokenBucket:
    """Token bucket implementation for rate limiting."""
    
    def __init__(self, config: RateLimitConfig):
        """Initialize token bucket."""
        self.config = config
        self.tokens = float(config.burst_size)
        self.last_update = time.time()
        self.lock = Lock()
        
        # Stats
        self.total_requests = 0
        self.total_wait_time = 0.0
        self.blocked_count = 0
    
    def acquire(self, tokens: int = 1, blocking: bool = True) -> bool:
        """
        Acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
            blocking: Wait if tokens not available
            
        Returns:
            True if tokens acquired, False if non-blocking and not available
        """
        with self.lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                self.total_requests += 1
                return True
            
            if not blocking:
                self.blocked_count += 1
                return False
            
            # Calculate wait time
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.config.requests_per_second
            
            logger.debug(f"Rate limit: waiting {wait_time:.2f}s for {tokens} tokens")
            self.total_wait_time += wait_time
            
            time.sleep(wait_time)
            
            # Refill and acquire
            self._refill()
            self.tokens -= tokens
            self.total_requests += 1
            return True
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        
        # Add tokens based on rate
        new_tokens = elapsed * self.config.requests_per_second
        self.tokens = min(self.config.burst_size, self.tokens + new_tokens)
        self.last_update = now
    
    def get_stats(self) -> Dict[str, float]:
        """Get rate limiter statistics."""
        with self.lock:
            return {
                'total_requests': self.total_requests,
                'total_wait_time': self.total_wait_time,
                'blocked_count': self.blocked_count,
                'average_wait_time': self.total_wait_time / self.total_requests if self.total_requests > 0 else 0,
                'current_tokens': self.tokens,
                'max_tokens': self.config.burst_size
            }


class RateLimiter:
    """Manages rate limiting for multiple APIs."""
    
    def __init__(self):
        """Initialize rate limiter."""
        self.buckets: Dict[str, TokenBucket] = {}
        self.lock = Lock()
    
    def configure(self, api_name: str, config: RateLimitConfig) -> None:
        """Configure rate limit for an API."""
        with self.lock:
            self.buckets[api_name] = TokenBucket(config)
            logger.info(f"Configured rate limit for {api_name}: {config.requests_per_second} req/s")
    
    def acquire(self, api_name: str, tokens: int = 1, blocking: bool = True) -> bool:
        """Acquire permission to make API call."""
        with self.lock:
            if api_name not in self.buckets:
                # No rate limit configured
                return True
            
            bucket = self.buckets[api_name]
        
        # Acquire outside the lock to avoid blocking other APIs
        return bucket.acquire(tokens, blocking)
    
    def get_stats(self, api_name: Optional[str] = None) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        with self.lock:
            if api_name:
                if api_name in self.buckets:
                    return {api_name: self.buckets[api_name].get_stats()}
                else:
                    return {}
            
            return {name: bucket.get_stats() for name, bucket in self.buckets.items()}


# Global rate limiter instance
_rate_limiter = RateLimiter()


def configure_rate_limit(api_name: str, requests_per_second: float, burst_size: Optional[int] = None) -> None:
    """Configure rate limit for an API."""
    config = RateLimitConfig(requests_per_second, burst_size)
    _rate_limiter.configure(api_name, config)


def rate_limit(api_name: str, tokens: int = 1, blocking: bool = True) -> bool:
    """Acquire rate limit tokens for an API call."""
    return _rate_limiter.acquire(api_name, tokens, blocking)


def get_rate_limit_stats(api_name: Optional[str] = None) -> Dict[str, Any]:
    """Get rate limiter statistics."""
    return _rate_limiter.get_stats(api_name)