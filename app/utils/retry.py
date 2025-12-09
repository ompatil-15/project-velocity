"""
Retry utilities with exponential backoff for handling rate limits.
Especially useful for Gemini free tier rate limiting.
"""
import asyncio
import random
from functools import wraps
from typing import Callable, Type, Tuple, Optional
import time


class RateLimitError(Exception):
    """Raised when rate limit is hit."""
    pass


def is_rate_limit_error(exception: Exception) -> bool:
    """
    Check if an exception is a rate limit error.
    Handles various LLM provider rate limit patterns.
    """
    error_str = str(exception).lower()
    rate_limit_patterns = [
        "rate limit",
        "rate_limit",
        "ratelimit",
        "quota exceeded",
        "resource exhausted",
        "429",
        "too many requests",
        "resourceexhausted",
        "quota",
    ]
    return any(pattern in error_str for pattern in rate_limit_patterns)


def retry_with_backoff(
    max_retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
):
    """
    Decorator for synchronous functions with exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff calculation
        jitter: Add random jitter to prevent thundering herd
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if not is_rate_limit_error(e):
                        # Not a rate limit error, re-raise immediately
                        raise
                    
                    if attempt == max_retries:
                        print(f"[Retry] Max retries ({max_retries}) exceeded. Giving up.")
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter (±25%)
                    if jitter:
                        delay = delay * (0.75 + random.random() * 0.5)
                    
                    print(f"[Retry] Rate limited. Attempt {attempt + 1}/{max_retries}. "
                          f"Waiting {delay:.2f}s before retry...")
                    time.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator


def async_retry_with_backoff(
    max_retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
):
    """
    Decorator for async functions with exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff calculation
        jitter: Add random jitter to prevent thundering herd
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if not is_rate_limit_error(e):
                        # Not a rate limit error, re-raise immediately
                        raise
                    
                    if attempt == max_retries:
                        print(f"[Retry] Max retries ({max_retries}) exceeded. Giving up.")
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter (±25%)
                    if jitter:
                        delay = delay * (0.75 + random.random() * 0.5)
                    
                    print(f"[Retry] Rate limited. Attempt {attempt + 1}/{max_retries}. "
                          f"Waiting {delay:.2f}s before retry...")
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator


class RetryingLLM:
    """
    Wrapper around LangChain LLM that adds retry logic with exponential backoff.
    """
    
    def __init__(
        self,
        llm,
        max_retries: int = 5,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
    ):
        self._llm = llm
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = min(self._base_delay * (2 ** attempt), self._max_delay)
        # Add jitter (±25%)
        return delay * (0.75 + random.random() * 0.5)
    
    def invoke(self, *args, **kwargs):
        """Synchronous invoke with retry logic."""
        last_exception = None
        
        for attempt in range(self._max_retries + 1):
            try:
                return self._llm.invoke(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if not is_rate_limit_error(e):
                    raise
                
                if attempt == self._max_retries:
                    print(f"[RetryingLLM] Max retries exceeded. Error: {e}")
                    raise
                
                delay = self._calculate_delay(attempt)
                print(f"[RetryingLLM] Rate limited. Attempt {attempt + 1}/{self._max_retries}. "
                      f"Waiting {delay:.2f}s...")
                time.sleep(delay)
        
        raise last_exception
    
    async def ainvoke(self, *args, **kwargs):
        """Async invoke with retry logic."""
        last_exception = None
        
        for attempt in range(self._max_retries + 1):
            try:
                return await self._llm.ainvoke(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if not is_rate_limit_error(e):
                    raise
                
                if attempt == self._max_retries:
                    print(f"[RetryingLLM] Max retries exceeded. Error: {e}")
                    raise
                
                delay = self._calculate_delay(attempt)
                print(f"[RetryingLLM] Rate limited. Attempt {attempt + 1}/{self._max_retries}. "
                      f"Waiting {delay:.2f}s...")
                await asyncio.sleep(delay)
        
        raise last_exception
    
    def __getattr__(self, name):
        """Proxy all other attributes to the underlying LLM."""
        return getattr(self._llm, name)

