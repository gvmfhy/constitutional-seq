"""Tests for cache manager."""

import json
import tempfile
import time
from pathlib import Path

import pytest

from genbank_tool.cache_manager import CacheManager, CacheStats


class TestCacheManager:
    """Test cases for cache manager."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def cache_manager(self, temp_cache_dir):
        """Create a cache manager instance."""
        return CacheManager(
            cache_dir=str(temp_cache_dir),
            max_size_mb=10,
            default_ttl_seconds=60
        )
    
    def test_basic_get_set(self, cache_manager):
        """Test basic get and set operations."""
        # Set a value
        assert cache_manager.set('test', 'key1', {'data': 'value1'})
        
        # Get the value
        result = cache_manager.get('test', 'key1')
        assert result == {'data': 'value1'}
        
        # Stats should reflect the operation
        stats = cache_manager.get_stats()
        assert stats.hit_count == 1
        assert stats.miss_count == 0
        assert stats.total_entries == 1
    
    def test_cache_miss(self, cache_manager):
        """Test cache miss."""
        result = cache_manager.get('test', 'nonexistent')
        assert result is None
        
        stats = cache_manager.get_stats()
        assert stats.miss_count == 1
        assert stats.hit_count == 0
    
    def test_expiration(self, cache_manager):
        """Test cache expiration."""
        # Set with short TTL
        cache_manager.set('test', 'expire_me', {'data': 'temp'}, ttl_seconds=1)
        
        # Should be available immediately
        assert cache_manager.get('test', 'expire_me') == {'data': 'temp'}
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Should be expired
        assert cache_manager.get('test', 'expire_me') is None
        
        stats = cache_manager.get_stats()
        assert stats.expired_count == 1
    
    def test_size_limit(self, cache_manager):
        """Test size limit enforcement."""
        # Create large data that exceeds limit
        large_data = {'data': 'x' * (5 * 1024 * 1024)}  # 5MB string
        
        # Set multiple entries
        cache_manager.set('test', 'large1', large_data)
        cache_manager.set('test', 'large2', large_data)
        
        # Third should trigger eviction
        cache_manager.set('test', 'large3', large_data)
        
        # First should be evicted
        assert cache_manager.get('test', 'large1') is None
        assert cache_manager.get('test', 'large3') is not None
        
        stats = cache_manager.get_stats()
        assert stats.evicted_count > 0
    
    def test_delete(self, cache_manager):
        """Test deletion."""
        cache_manager.set('test', 'delete_me', {'data': 'temp'})
        
        # Verify it exists
        assert cache_manager.get('test', 'delete_me') is not None
        
        # Delete it
        assert cache_manager.delete('test', 'delete_me')
        
        # Verify it's gone
        assert cache_manager.get('test', 'delete_me') is None
    
    def test_clear_namespace(self, cache_manager):
        """Test clearing a namespace."""
        # Set entries in different namespaces
        cache_manager.set('ns1', 'key1', {'data': '1'})
        cache_manager.set('ns1', 'key2', {'data': '2'})
        cache_manager.set('ns2', 'key1', {'data': '3'})
        
        # Clear ns1
        cleared = cache_manager.clear('ns1')
        assert cleared == 2
        
        # ns1 should be empty, ns2 should remain
        assert cache_manager.get('ns1', 'key1') is None
        assert cache_manager.get('ns1', 'key2') is None
        assert cache_manager.get('ns2', 'key1') == {'data': '3'}
    
    def test_clear_all(self, cache_manager):
        """Test clearing all cache."""
        # Set multiple entries
        cache_manager.set('ns1', 'key1', {'data': '1'})
        cache_manager.set('ns2', 'key1', {'data': '2'})
        
        # Clear all
        cleared = cache_manager.clear()
        assert cleared == 2
        
        # Everything should be gone
        assert cache_manager.get('ns1', 'key1') is None
        assert cache_manager.get('ns2', 'key1') is None
        
        stats = cache_manager.get_stats()
        assert stats.total_entries == 0
    
    def test_cleanup_expired(self, cache_manager):
        """Test cleanup of expired entries."""
        # Set entries with different TTLs
        cache_manager.set('test', 'short', {'data': '1'}, ttl_seconds=1)
        cache_manager.set('test', 'long', {'data': '2'}, ttl_seconds=60)
        
        # Wait for short to expire
        time.sleep(1.5)
        
        # Cleanup
        removed = cache_manager.cleanup_expired()
        assert removed == 1
        
        # Only long should remain
        assert cache_manager.get('test', 'short') is None
        assert cache_manager.get('test', 'long') == {'data': '2'}
    
    def test_size_info(self, cache_manager):
        """Test size information."""
        # Set entries in different namespaces
        cache_manager.set('genes', 'BRCA1', {'id': '672'})
        cache_manager.set('genes', 'TP53', {'id': '7157'})
        cache_manager.set('sequences', 'NM_001234', {'seq': 'ATCG' * 100})
        
        size_info = cache_manager.get_size_info()
        
        assert size_info['total_entries'] == 3
        assert 'genes' in size_info['namespaces']
        assert 'sequences' in size_info['namespaces']
        assert size_info['namespaces']['genes']['count'] == 2
        assert size_info['namespaces']['sequences']['count'] == 1
    
    def test_persistence(self, temp_cache_dir):
        """Test cache persistence across restarts."""
        # Create and populate cache
        cache1 = CacheManager(str(temp_cache_dir))
        cache1.set('test', 'persist', {'data': 'saved'})
        stats1 = cache1.get_stats()
        
        # Create new instance with same directory
        cache2 = CacheManager(str(temp_cache_dir))
        
        # Should load persisted data
        assert cache2.get('test', 'persist') == {'data': 'saved'}
        
        # Stats should be restored
        stats2 = cache2.get_stats()
        assert stats2.total_entries == stats1.total_entries
    
    def test_special_characters_in_key(self, cache_manager):
        """Test handling of special characters in keys."""
        special_key = "gene/with:special\\chars"
        cache_manager.set('test', special_key, {'data': 'special'})
        
        result = cache_manager.get('test', special_key)
        assert result == {'data': 'special'}
    
    def test_concurrent_access(self, cache_manager):
        """Test thread safety with concurrent access."""
        import threading
        
        results = []
        errors = []
        
        def worker(i):
            try:
                # Each thread sets and gets its own key
                key = f'key_{i}'
                value = {'thread': i}
                
                cache_manager.set('concurrent', key, value)
                result = cache_manager.get('concurrent', key)
                
                if result == value:
                    results.append(True)
                else:
                    results.append(False)
                    
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # All operations should succeed
        assert len(errors) == 0
        assert all(results)
        assert len(results) == 10