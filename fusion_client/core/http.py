"""HTTP client layer for Fusion API."""

import asyncio
from typing import Optional, Dict, Any, Union, AsyncIterator
import httpx
import structlog
from .exceptions import (
    FusionError,
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
    NetworkError,
    ServerError,
    TimeoutError as FusionTimeoutError,
)
from ..utils.retry import with_retry, RateLimiter
from ..utils.cache import FusionCache


logger = structlog.get_logger(__name__)


class HTTPClient:
    """HTTP client for Fusion API with retry, caching, and error handling."""
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        rate_limiter: Optional[RateLimiter] = None,
        cache: Optional[FusionCache] = None,
        enable_tracing: bool = False
    ):
        """
        Initialize HTTP client.
        
        Args:
            base_url: Base URL for API
            api_key: API key for authentication
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            rate_limiter: Optional rate limiter
            cache: Optional cache instance
            enable_tracing: Enable request tracing
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.enable_tracing = enable_tracing
        
        # Initialize httpx client
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            headers=self._get_default_headers(),
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=30.0
            )
        )
    
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default headers for requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "fusion-client/0.1.0",
        }
    
    def _get_cache_key(self, method: str, url: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Generate cache key for request."""
        if self.cache:
            return self.cache._generate_key(method, url, params)
        return ""
    
    def _should_cache(self, method: str, status_code: int) -> bool:
        """Determine if response should be cached."""
        return (
            self.cache is not None and
            method.upper() == "GET" and
            200 <= status_code < 300
        )
    
    def _handle_http_error(self, response: httpx.Response) -> None:
        """Handle HTTP error responses."""
        status_code = response.status_code
        
        try:
            error_data = response.json()
            message = error_data.get("message", f"HTTP {status_code}")
            details = error_data.get("details", {})
        except Exception:
            message = f"HTTP {status_code}"
            details = {}
        
        if status_code == 401:
            raise AuthenticationError(message)
        elif status_code == 403:
            raise AuthorizationError(message)
        elif status_code == 404:
            from .exceptions import AgentNotFoundError, ChatNotFoundError
            # Try to determine specific 404 error type from URL
            url = str(response.url)
            if "/agents/" in url:
                agent_id = url.split("/agents/")[-1].split("/")[0]
                raise AgentNotFoundError(agent_id)
            elif "/chat/" in url:
                chat_id = url.split("/chat/")[-1].split("/")[0]
                raise ChatNotFoundError(chat_id)
            else:
                raise FusionError(message, status_code=status_code, details=details)
        elif status_code == 429:
            retry_after = None
            if "retry-after" in response.headers:
                try:
                    retry_after = int(response.headers["retry-after"])
                except ValueError:
                    pass
            raise RateLimitError(message, retry_after=retry_after)
        elif 400 <= status_code < 500:
            raise FusionError(message, status_code=status_code, details=details)
        elif 500 <= status_code < 600:
            raise ServerError(message, status_code=status_code)
        else:
            raise FusionError(message, status_code=status_code, details=details)
    
    @with_retry(max_attempts=3, exceptions=(NetworkError, ServerError, FusionTimeoutError))
    async def _make_request(
        self,
        method: str,
        url: str,
        **kwargs: Any
    ) -> httpx.Response:
        """Make HTTP request with error handling."""
        # Apply rate limiting
        if self.rate_limiter:
            await self.rate_limiter.acquire()
        
        # Log request
        if self.enable_tracing:
            logger.info(
                "Making HTTP request",
                method=method,
                url=url,
                headers_count=len(kwargs.get("headers", {}))
            )
        
        try:
            response = await self._client.request(method, url, **kwargs)
            
            # Log response
            if self.enable_tracing:
                logger.info(
                    "HTTP response received",
                    method=method,
                    url=url,
                    status_code=response.status_code,
                    response_size=len(response.content) if hasattr(response, 'content') else 0
                )
            
            # Handle error status codes
            if not response.is_success:
                self._handle_http_error(response)
            
            return response
            
        except httpx.TimeoutException as e:
            logger.error("Request timeout", method=method, url=url, timeout=self.timeout)
            raise FusionTimeoutError(f"Request timed out after {self.timeout}s") from e
        except httpx.ConnectError as e:
            logger.error("Connection error", method=method, url=url, error=str(e))
            raise NetworkError(f"Failed to connect to {self.base_url}") from e
        except httpx.HTTPError as e:
            logger.error("HTTP error", method=method, url=url, error=str(e))
            raise NetworkError(f"HTTP error: {str(e)}") from e
    
    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Make GET request."""
        # Check cache first
        cache_key = ""
        if use_cache and self.cache:
            cache_key = self._get_cache_key("GET", url, params)
            cached_response = self.cache.get(cache_key)
            if cached_response is not None:
                return cached_response
        
        response = await self._make_request("GET", url, params=params, **kwargs)
        result = response.json()
        
        # Cache successful responses
        if use_cache and self._should_cache("GET", response.status_code):
            self.cache.set(cache_key, result)
        
        return result
    
    async def post(
        self,
        url: str,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        files: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Make POST request."""
        response = await self._make_request(
            "POST",
            url,
            json=json_data,
            data=data,
            files=files,
            **kwargs
        )
        return response.json()
    
    async def put(
        self,
        url: str,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Make PUT request."""
        response = await self._make_request("PUT", url, json=json_data, **kwargs)
        return response.json()
    
    async def delete(
        self,
        url: str,
        **kwargs: Any
    ) -> Optional[Dict[str, Any]]:
        """Make DELETE request."""
        response = await self._make_request("DELETE", url, **kwargs)
        if response.status_code == 204:  # No content
            return None
        return response.json()
    
    async def stream_post(
        self,
        url: str,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> AsyncIterator[bytes]:
        """Make streaming POST request."""
        # Apply rate limiting
        if self.rate_limiter:
            await self.rate_limiter.acquire()
        
        headers = kwargs.get("headers", {})
        headers.update(self._get_default_headers())
        headers["Accept"] = "text/event-stream"
        
        async with self._client.stream(
            "POST",
            url,
            json=json_data,
            headers=headers,
            **{k: v for k, v in kwargs.items() if k != "headers"}
        ) as response:
            if not response.is_success:
                # Read response content for error handling
                await response.aread()
                self._handle_http_error(response)
            
            async for chunk in response.aiter_bytes():
                yield chunk
    
    async def upload_file(
        self,
        url: str,
        file_path: str,
        field_name: str = "file",
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Upload file to API."""
        files = {field_name: open(file_path, "rb")}
        data = additional_data or {}
        
        try:
            response = await self._make_request(
                "POST",
                url,
                files=files,
                data=data
            )
            return response.json()
        finally:
            # Always close file
            if field_name in files:
                files[field_name].close()
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close() 