"""Centralized cache management with expiration tracking and statistics."""

import json
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a single cache entry with metadata."""
    key: str
    data: Any
    created_at: float
    expires_at: float
    hit_count: int = 0
    last_accessed: Optional[float] = None
    size_bytes: int = 0


@dataclass
class CacheStats:
    """Cache statistics."""
    total_entries: int = 0
    total_size_bytes: int = 0
    hit_count: int = 0
    miss_count: int = 0
    expired_count: int = 0
    evicted_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total_requests = self.hit_count + self.miss_count
        return self.hit_count / total_requests if total_requests > 0 else 0.0
    
    @property
    def size_mb(self) -> float:
        """Get total size in MB."""
        return self.total_size_bytes / (1024 * 1024)


class CacheManager:
    """Manages file-based caching with expiration and memory limits."""
    
    def __init__(self, 
                 cache_dir: str = ".genbank_cache",
                 max_size_mb: int = 500,
                 default_ttl_seconds: int = 86400):  # 24 hours default
        """
        Initialize cache manager.
        
        Args:
            cache_dir: Directory for cache files
            max_size_mb: Maximum cache size in MB
            default_ttl_seconds: Default time-to-live in seconds
        """
        self.cache_dir = Path(cache_dir)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.default_ttl = default_ttl_seconds
        self.stats = CacheStats()
        self._lock = Lock()
        self._metadata_file = self.cache_dir / "cache_metadata.json"
        self._index: Dict[str, CacheEntry] = {}
        
        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load metadata
        self._load_metadata()
    
    def get(self, namespace: str, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            namespace: Cache namespace (e.g., 'genes', 'sequences')
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            cache_key = f"{namespace}:{key}"
            
            # Check index first
            if cache_key in self._index:
                entry = self._index[cache_key]
                
                # Check expiration
                if time.time() > entry.expires_at:
                    self._remove_entry(cache_key)
                    self.stats.expired_count += 1
                    self.stats.miss_count += 1
                    return None
                
                # Update access info
                entry.hit_count += 1
                entry.last_accessed = time.time()
                self.stats.hit_count += 1
                
                # Load from file
                try:
                    file_path = self._get_file_path(namespace, key)
                    if file_path.exists():
                        with open(file_path, 'r') as f:
                            return json.load(f)
                except Exception as e:
                    logger.error(f"Error loading cache file: {e}")
                    self._remove_entry(cache_key)
            
            self.stats.miss_count += 1
            return None
    
    def set(self, namespace: str, key: str, value: Any, 
            ttl_seconds: Optional[int] = None) -> bool:
        """
        Set value in cache.
        
        Args:
            namespace: Cache namespace
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            cache_key = f"{namespace}:{key}"
            ttl = ttl_seconds or self.default_ttl
            
            # Serialize and calculate size
            try:
                serialized = json.dumps(value)
                size_bytes = len(serialized.encode('utf-8'))
            except (TypeError, ValueError) as e:
                logger.error(f"Cannot serialize value for {cache_key}: {e}")
                return False
            
            # Check size limit
            if self._would_exceed_limit(size_bytes, cache_key):
                self._evict_entries(size_bytes)
            
            # Create entry
            now = time.time()
            entry = CacheEntry(
                key=cache_key,
                data=value,
                created_at=now,
                expires_at=now + ttl,
                size_bytes=size_bytes
            )
            
            # Save to file
            try:
                file_path = self._get_file_path(namespace, key)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, 'w') as f:
                    json.dump(value, f)
                
                # Update index
                if cache_key in self._index:
                    self.stats.total_size_bytes -= self._index[cache_key].size_bytes
                self._index[cache_key] = entry
                self.stats.total_size_bytes += size_bytes
                self.stats.total_entries = len(self._index)
                
                # Save metadata after each set
                self._save_metadata()
                
                return True
                
            except Exception as e:
                logger.error(f"Error saving cache file: {e}")
                return False
    
    def delete(self, namespace: str, key: str) -> bool:
        """Delete entry from cache."""
        with self._lock:
            cache_key = f"{namespace}:{key}"
            return self._remove_entry(cache_key)
    
    def clear(self, namespace: Optional[str] = None) -> int:
        """
        Clear cache entries.
        
        Args:
            namespace: Clear only this namespace, or all if None
            
        Returns:
            Number of entries cleared
        """
        with self._lock:
            cleared = 0
            
            if namespace:
                # Clear specific namespace
                keys_to_remove = [k for k in self._index if k.startswith(f"{namespace}:")]
                for key in keys_to_remove:
                    if self._remove_entry(key):
                        cleared += 1
            else:
                # Clear all
                cleared = len(self._index)
                self._index.clear()
                self.stats = CacheStats()
                
                # Remove all cache files
                try:
                    for item in self.cache_dir.rglob("*.json"):
                        if item.name != "cache_metadata.json":
                            item.unlink()
                except Exception as e:
                    logger.error(f"Error clearing cache files: {e}")
            
            self._save_metadata()
            return cleared
    
    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        with self._lock:
            now = time.time()
            expired_keys = [k for k, v in self._index.items() if v.expires_at < now]
            
            removed = 0
            for key in expired_keys:
                if self._remove_entry(key):
                    removed += 1
                    self.stats.expired_count += 1
            
            if removed > 0:
                self._save_metadata()
            
            return removed
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self.stats
    
    def get_size_info(self) -> Dict[str, Any]:
        """Get detailed size information."""
        namespace_sizes = {}
        
        with self._lock:
            for key, entry in self._index.items():
                namespace = key.split(':', 1)[0]
                if namespace not in namespace_sizes:
                    namespace_sizes[namespace] = {
                        'count': 0,
                        'size_bytes': 0,
                        'size_mb': 0
                    }
                namespace_sizes[namespace]['count'] += 1
                namespace_sizes[namespace]['size_bytes'] += entry.size_bytes
            
            for ns_info in namespace_sizes.values():
                ns_info['size_mb'] = ns_info['size_bytes'] / (1024 * 1024)
        
        return {
            'total_size_mb': self.stats.size_mb,
            'total_entries': self.stats.total_entries,
            'max_size_mb': self.max_size_bytes / (1024 * 1024),
            'usage_percent': (self.stats.total_size_bytes / self.max_size_bytes * 100) if self.max_size_bytes > 0 else 0,
            'namespaces': namespace_sizes
        }
    
    def _get_file_path(self, namespace: str, key: str) -> Path:
        """Get file path for cache entry."""
        # Create safe filename
        safe_key = key.replace('/', '_').replace('\\', '_').replace(':', '_')
        return self.cache_dir / namespace / f"{safe_key}.json"
    
    def _would_exceed_limit(self, new_size: int, exclude_key: Optional[str] = None) -> bool:
        """Check if adding new entry would exceed size limit."""
        current_size = self.stats.total_size_bytes
        if exclude_key and exclude_key in self._index:
            current_size -= self._index[exclude_key].size_bytes
        return current_size + new_size > self.max_size_bytes
    
    def _evict_entries(self, required_space: int) -> None:
        """Evict entries to make space using LRU policy."""
        # Sort by last accessed time (oldest first)
        entries = [(k, v) for k, v in self._index.items()]
        entries.sort(key=lambda x: x[1].last_accessed or x[1].created_at)
        
        freed_space = 0
        for key, entry in entries:
            if self.stats.total_size_bytes - freed_space + required_space <= self.max_size_bytes:
                break
            
            if self._remove_entry(key):
                freed_space += entry.size_bytes
                self.stats.evicted_count += 1
    
    def _remove_entry(self, cache_key: str) -> bool:
        """Remove single cache entry."""
        if cache_key not in self._index:
            return False
        
        entry = self._index[cache_key]
        
        # Remove file
        namespace, key = cache_key.split(':', 1)
        file_path = self._get_file_path(namespace, key)
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            logger.error(f"Error removing cache file {file_path}: {e}")
        
        # Update index and stats
        del self._index[cache_key]
        self.stats.total_size_bytes -= entry.size_bytes
        self.stats.total_entries = len(self._index)
        
        return True
    
    def _load_metadata(self) -> None:
        """Load cache metadata from disk."""
        if not self._metadata_file.exists():
            return
        
        try:
            with open(self._metadata_file, 'r') as f:
                data = json.load(f)
            
            # Restore index
            self._index = {}
            for key, entry_data in data.get('index', {}).items():
                self._index[key] = CacheEntry(**entry_data)
            
            # Restore stats
            stats_data = data.get('stats', {})
            self.stats = CacheStats(**stats_data)
            
            # Clean up expired entries on load
            self.cleanup_expired()
            
        except Exception as e:
            logger.error(f"Error loading cache metadata: {e}")
            self._index = {}
            self.stats = CacheStats()
    
    def _save_metadata(self) -> None:
        """Save cache metadata to disk."""
        try:
            data = {
                'index': {k: asdict(v) for k, v in self._index.items()},
                'stats': asdict(self.stats),
                'saved_at': datetime.now().isoformat()
            }
            
            with open(self._metadata_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving cache metadata: {e}")