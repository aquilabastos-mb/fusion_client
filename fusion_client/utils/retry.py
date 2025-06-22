"""Retry logic and rate limiting utilities."""

import asyncio
import time
from functools import wraps
from typing import Callable, Any, Tuple, Type, Optional, Union
from collections import deque
import random


class RateLimiter:
    """Rate limiter using token bucket algorithm."""
    
    def __init__(self, max_calls: int = 100, window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_calls: Maximum calls per window
            window: Time window in seconds
        """
        self.max_calls = max_calls
        self.window = window
        self.calls: deque = deque()
    
    async def acquire(self) -> None:
        """Wait for permission to make a call."""
        now = time.time()
        
        # Remove calls outside the window
        while self.calls and now - self.calls[0] > self.window:
            self.calls.popleft()
        
        # If at limit, wait until oldest call expires
        if len(self.calls) >= self.max_calls:
            sleep_time = self.window - (now - self.calls[0]) + 0.1  # Small buffer
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                return await self.acquire()  # Recursive call after waiting
        
        # Record this call
        self.calls.append(now)
    
    def can_proceed(self) -> bool:
        """Check if a call can proceed without waiting."""
        now = time.time()
        
        # Remove expired calls
        while self.calls and now - self.calls[0] > self.window:
            self.calls.popleft()
        
        return len(self.calls) < self.max_calls
    
    def time_until_available(self) -> float:
        """Get time in seconds until next call is available."""
        if self.can_proceed():
            return 0.0
        
        now = time.time()
        oldest_call = self.calls[0] if self.calls else now
        return max(0.0, self.window - (now - oldest_call))


def with_retry(
    max_attempts: int = 3,
    backoff_factor: float = 1.0,
    max_backoff: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    jitter: bool = True
):
    """
    Decorator for retry with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Base backoff time multiplier
        max_backoff: Maximum backoff time
        exceptions: Tuple of exception types to retry on
        jitter: Add random jitter to backoff time
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        # Last attempt, re-raise the exception
                        raise
                    
                    # Calculate backoff time
                    backoff_time = min(
                        backoff_factor * (2 ** attempt),
                        max_backoff
                    )
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        backoff_time *= (0.5 + random.random() * 0.5)
                    
                    await asyncio.sleep(backoff_time)
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
            
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        raise
                    
                    backoff_time = min(
                        backoff_factor * (2 ** attempt),
                        max_backoff
                    )
                    
                    if jitter:
                        backoff_time *= (0.5 + random.random() * 0.5)
                    
                    time.sleep(backoff_time)
            
            if last_exception:
                raise last_exception
        
        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(
        self,
        threshold: int = 5,
        timeout: float = 60.0,
        recovery_timeout: float = 30.0
    ):
        """
        Initialize circuit breaker.
        
        Args:
            threshold: Number of failures before opening circuit
            timeout: Time to keep circuit open
            recovery_timeout: Time to wait in half-open state
        """
        self.threshold = threshold
        self.timeout = timeout
        self.recovery_timeout = recovery_timeout
        
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half-open
    
    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        now = time.time()
        
        if self.state == "closed":
            return True
        elif self.state == "open":
            if self.last_failure_time and now - self.last_failure_time > self.timeout:
                self.state = "half-open"
                return True
            return False
        else:  # half-open
            return True
    
    def record_success(self) -> None:
        """Record a successful execution."""
        self.failure_count = 0
        self.state = "closed"
        self.last_failure_time = None
    
    def record_failure(self) -> None:
        """Record a failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.threshold:
            self.state = "open"
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if not self.can_execute():
            raise Exception("Circuit breaker is open")
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise 