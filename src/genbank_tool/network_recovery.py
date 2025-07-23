"""Network recovery mechanisms for handling interruptions and failures."""

import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional, Any, Dict, List
from urllib.parse import urlparse
import socket
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from .error_handler import ErrorContext, ErrorType, get_error_handler
from .logging_config import get_logger, LogTimer

logger = get_logger('network_recovery')


@dataclass
class NetworkConfig:
    """Configuration for network operations."""
    timeout: float = 30.0
    max_retries: int = 3
    backoff_factor: float = 1.0
    retry_on_status: List[int] = None
    verify_ssl: bool = True
    connection_pool_size: int = 10
    
    def __post_init__(self):
        if self.retry_on_status is None:
            self.retry_on_status = [408, 429, 500, 502, 503, 504]


class NetworkHealthChecker:
    """Check network connectivity and API availability."""
    
    def __init__(self):
        """Initialize health checker."""
        self.health_status: Dict[str, bool] = {}
        self.last_check: Dict[str, float] = {}
        self.check_interval = 60.0  # seconds
    
    def check_internet_connection(self) -> bool:
        """Check basic internet connectivity."""
        try:
            # Try to resolve a reliable domain
            socket.gethostbyname('www.google.com')
            return True
        except socket.error:
            logger.error("No internet connection detected")
            return False
    
    def check_api_health(self, api_name: str, health_url: str) -> bool:
        """Check if specific API is healthy."""
        current_time = time.time()
        
        # Use cached result if recent
        if api_name in self.last_check:
            if current_time - self.last_check[api_name] < self.check_interval:
                return self.health_status.get(api_name, False)
        
        try:
            response = requests.head(health_url, timeout=5)
            healthy = response.status_code < 500
            
            self.health_status[api_name] = healthy
            self.last_check[api_name] = current_time
            
            if not healthy:
                logger.warning(f"{api_name} API returned status {response.status_code}")
            
            return healthy
            
        except Exception as e:
            logger.error(f"Failed to check {api_name} health: {e}")
            self.health_status[api_name] = False
            self.last_check[api_name] = current_time
            return False
    
    def wait_for_connectivity(self, max_wait: int = 300) -> bool:
        """
        Wait for internet connectivity to be restored.
        
        Args:
            max_wait: Maximum seconds to wait
            
        Returns:
            True if connectivity restored, False if timeout
        """
        start_time = time.time()
        check_interval = 5.0
        
        logger.info("Waiting for network connectivity...")
        
        while time.time() - start_time < max_wait:
            if self.check_internet_connection():
                logger.info("Network connectivity restored")
                return True
            
            time.sleep(check_interval)
            # Exponential backoff for check interval
            check_interval = min(check_interval * 1.5, 30.0)
        
        logger.error(f"Network connectivity not restored after {max_wait}s")
        return False


class ResilientSession:
    """HTTP session with built-in retry and recovery mechanisms."""
    
    def __init__(self, config: Optional[NetworkConfig] = None):
        """
        Initialize resilient session.
        
        Args:
            config: Network configuration
        """
        self.config = config or NetworkConfig()
        self.session = self._create_session()
        self.health_checker = NetworkHealthChecker()
        self.error_handler = get_error_handler()
    
    def _create_session(self) -> requests.Session:
        """Create session with retry configuration."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.backoff_factor,
            status_forcelist=self.config.retry_on_status,
            allowed_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]
        )
        
        # Configure adapter
        adapter = HTTPAdapter(
            pool_connections=self.config.connection_pool_size,
            pool_maxsize=self.config.connection_pool_size,
            max_retries=retry_strategy
        )
        
        # Mount adapter for both HTTP and HTTPS
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default timeout
        session.timeout = self.config.timeout
        
        # SSL verification
        session.verify = self.config.verify_ssl
        
        return session
    
    def request_with_recovery(self,
                              method: str,
                              url: str,
                              api_name: Optional[str] = None,
                              health_check_url: Optional[str] = None,
                              **kwargs) -> requests.Response:
        """
        Make HTTP request with automatic recovery.
        
        Args:
            method: HTTP method
            url: Request URL
            api_name: API name for logging
            health_check_url: URL to check API health
            **kwargs: Additional request arguments
            
        Returns:
            Response object
            
        Raises:
            requests.RequestException: If all recovery attempts fail
        """
        if api_name is None:
            api_name = urlparse(url).netloc
        
        # Set default timeout if not provided
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.config.timeout
        
        attempt = 0
        last_error = None
        
        while attempt <= self.config.max_retries:
            try:
                # Check network connectivity first
                if attempt > 0 and not self.health_checker.check_internet_connection():
                    if not self.health_checker.wait_for_connectivity():
                        raise requests.ConnectionError("No network connectivity")
                
                # Check API health if URL provided
                if health_check_url and attempt > 0:
                    if not self.health_checker.check_api_health(api_name, health_check_url):
                        logger.warning(f"{api_name} API appears unhealthy, proceeding anyway")
                
                # Make request
                with LogTimer(f"{method} {url}"):
                    response = self.session.request(method, url, **kwargs)
                    response.raise_for_status()
                    return response
                
            except requests.exceptions.Timeout as e:
                last_error = e
                error_context = self.error_handler.handle_error(
                    e,
                    operation=f"{method} {url}",
                    api_name=api_name,
                    retry_count=attempt
                )
                
                if attempt < self.config.max_retries:
                    wait_time = self._calculate_backoff(attempt)
                    logger.info(f"Request timeout, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                
            except requests.exceptions.ConnectionError as e:
                last_error = e
                error_context = self.error_handler.handle_error(
                    e,
                    operation=f"{method} {url}",
                    api_name=api_name,
                    retry_count=attempt
                )
                
                if attempt < self.config.max_retries:
                    # Wait for connectivity
                    if self.health_checker.wait_for_connectivity(60):
                        logger.info("Retrying after network recovery...")
                    else:
                        break
                
            except requests.exceptions.HTTPError as e:
                last_error = e
                
                # Check if it's a rate limit error
                if e.response.status_code == 429:
                    error_context = self.error_handler.handle_error(
                        e,
                        operation=f"{method} {url}",
                        api_name=api_name,
                        retry_count=attempt,
                        error_type=ErrorType.API_RATE_LIMIT
                    )
                    
                    # Extract retry-after header if available
                    retry_after = e.response.headers.get('Retry-After', 60)
                    try:
                        wait_time = int(retry_after)
                    except ValueError:
                        wait_time = 60
                    
                    if attempt < self.config.max_retries:
                        logger.info(f"Rate limited, waiting {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        break
                else:
                    # Non-retryable HTTP error
                    raise
                
            except Exception as e:
                last_error = e
                error_context = self.error_handler.handle_error(
                    e,
                    operation=f"{method} {url}",
                    api_name=api_name,
                    retry_count=attempt
                )
                
                if attempt < self.config.max_retries:
                    wait_time = self._calculate_backoff(attempt)
                    logger.info(f"Unexpected error, retrying in {wait_time}s...")
                    time.sleep(wait_time)
            
            attempt += 1
        
        # All retries exhausted
        if last_error:
            raise last_error
        else:
            raise requests.RequestException(f"Failed to complete request after {self.config.max_retries} attempts")
    
    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff time."""
        return min(self.config.backoff_factor * (2 ** attempt), 300.0)  # Max 5 minutes
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """GET request with recovery."""
        return self.request_with_recovery('GET', url, **kwargs)
    
    def post(self, url: str, **kwargs) -> requests.Response:
        """POST request with recovery."""
        return self.request_with_recovery('POST', url, **kwargs)
    
    def close(self):
        """Close the session."""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class NetworkRecoveryManager:
    """Manages network recovery strategies for the application."""
    
    def __init__(self):
        """Initialize recovery manager."""
        self.sessions: Dict[str, ResilientSession] = {}
        self.api_configs: Dict[str, NetworkConfig] = {
            'ncbi': NetworkConfig(
                timeout=60.0,
                max_retries=5,
                backoff_factor=2.0
            ),
            'uniprot': NetworkConfig(
                timeout=30.0,
                max_retries=3,
                backoff_factor=1.5
            ),
            'ensembl': NetworkConfig(
                timeout=45.0,
                max_retries=4,
                backoff_factor=1.5
            )
        }
        self.health_urls = {
            'ncbi': 'https://www.ncbi.nlm.nih.gov/',
            'uniprot': 'https://www.uniprot.org/',
            'ensembl': 'https://rest.ensembl.org/info/ping'
        }
    
    def get_session(self, api_name: str) -> ResilientSession:
        """
        Get or create resilient session for API.
        
        Args:
            api_name: Name of the API
            
        Returns:
            ResilientSession instance
        """
        if api_name not in self.sessions:
            config = self.api_configs.get(api_name, NetworkConfig())
            self.sessions[api_name] = ResilientSession(config)
        
        return self.sessions[api_name]
    
    def make_request(self,
                      api_name: str,
                      method: str,
                      url: str,
                      **kwargs) -> requests.Response:
        """
        Make request with appropriate session.
        
        Args:
            api_name: Name of the API
            method: HTTP method
            url: Request URL
            **kwargs: Additional request arguments
            
        Returns:
            Response object
        """
        session = self.get_session(api_name)
        health_url = self.health_urls.get(api_name)
        
        return session.request_with_recovery(
            method,
            url,
            api_name=api_name,
            health_check_url=health_url,
            **kwargs
        )
    
    def close_all(self):
        """Close all sessions."""
        for session in self.sessions.values():
            session.close()
        self.sessions.clear()


# Global instance
_recovery_manager = NetworkRecoveryManager()


def get_recovery_manager() -> NetworkRecoveryManager:
    """Get global recovery manager instance."""
    return _recovery_manager


# Decorator for network recovery
def with_network_recovery(api_name: str, max_retries: Optional[int] = None):
    """
    Decorator to add network recovery to functions.
    
    Args:
        api_name: Name of the API being called
        max_retries: Override max retries
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            manager = get_recovery_manager()
            
            # Override max retries if specified
            if max_retries is not None:
                original_config = manager.api_configs.get(api_name)
                if original_config:
                    original_retries = original_config.max_retries
                    original_config.max_retries = max_retries
            
            try:
                # Inject session into function
                kwargs['_session'] = manager.get_session(api_name)
                return func(*args, **kwargs)
            finally:
                # Restore original config
                if max_retries is not None and original_config:
                    original_config.max_retries = original_retries
        
        return wrapper
    return decorator