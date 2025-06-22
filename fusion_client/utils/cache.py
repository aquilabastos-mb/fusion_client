"""Caching system for Fusion client."""

import time
import hashlib
import json
from typing import Any, Optional, Dict, Tuple
from threading import Lock


class FusionCache:
    """Thread-safe cache with TTL and LRU eviction."""
    
    def __init__(self, ttl: int = 300, max_size: int = 1000):
        """
        Initialize cache.
        
        Args:
            ttl: Time to live in seconds
            max_size: Maximum number of items to store
        """
        self.ttl = ttl
        self.max_size = max_size
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._access_times: Dict[str, float] = {}
        self._lock = Lock()
    
    def _generate_key(self, method: str, url: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Generate unique cache key."""
        params = params or {}
        data = f"{method}:{url}:{json.dumps(params, sort_keys=True, default=str)}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def _is_expired(self, timestamp: float) -> bool:
        """Check if cache entry is expired."""
        return time.time() - timestamp > self.ttl
    
    def _evict_expired(self) -> None:
        """Remove expired entries."""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self._cache.items()
            if current_time - timestamp > self.ttl
        ]
        
        for key in expired_keys:
            self._cache.pop(key, None)
            self._access_times.pop(key, None)
    
    def _evict_lru(self) -> None:
        """Evict least recently used item."""
        if not self._access_times:
            return
        
        lru_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        self._cache.pop(lru_key, None)
        self._access_times.pop(lru_key, None)
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get item from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                return None
            
            value, timestamp = self._cache[key]
            
            if self._is_expired(timestamp):
                self._cache.pop(key, None)
                self._access_times.pop(key, None)
                return None
            
            # Update access time for LRU
            self._access_times[key] = time.time()
            return value
    
    def set(self, key: str, value: Any) -> None:
        """
        Store item in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            current_time = time.time()
            
            # Clean expired entries first
            self._evict_expired()
            
            # Evict LRU if at capacity
            while len(self._cache) >= self.max_size:
                self._evict_lru()
            
            # Store new item
            self._cache[key] = (value, current_time)
            self._access_times[key] = current_time
    
    def invalidate(self, key: str) -> bool:
        """
        Remove specific key from cache.
        
        Args:
            key: Cache key to remove
            
        Returns:
            True if key was found and removed
        """
        with self._lock:
            if key in self._cache:
                self._cache.pop(key)
                self._access_times.pop(key, None)
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            current_time = time.time()
            expired_count = sum(
                1 for _, timestamp in self._cache.values()
                if current_time - timestamp > self.ttl
            )
            
            return {
                "total_items": len(self._cache),
                "expired_items": expired_count,
                "valid_items": len(self._cache) - expired_count,
                "max_size": self.max_size,
                "ttl_seconds": self.ttl,
                "hit_ratio": getattr(self, '_hits', 0) / max(getattr(self, '_requests', 1), 1)
            }
    
    def get_or_set(self, key: str, value_factory, *args, **kwargs) -> Any:
        """
        Get from cache or set using factory function.
        
        Args:
            key: Cache key
            value_factory: Function to generate value if not cached
            *args, **kwargs: Arguments for value_factory
            
        Returns:
            Cached or newly generated value
        """
        value = self.get(key)
        if value is not None:
            return value
        
        # Generate new value
        new_value = value_factory(*args, **kwargs)
        self.set(key, new_value)
        return new_value 