"""
Fusion API Client - Main client implementation.

This module contains the main FusionClient class that provides a Pythonic
interface to the Fusion API with support for async/await, retry logic,
caching, and rate limiting.
"""

import asyncio
import time
from typing import Optional, List, Dict, Any, AsyncIterator, Union
from uuid import UUID

import httpx
import structlog
from tenacity import retry, wait_exponential, stop_after_attempt

from .http import HTTPClient
from .auth import FusionAuth
from .exceptions import (
    FusionError,
    AuthenticationError,
    RateLimitError,
    AgentNotFoundError,
    ChatNotFoundError,
    ValidationError,
    NetworkError,
    ServerError,
    TimeoutError,
)

from ..models.chat import Chat, ChatResponse, Message
from ..models.agent import Agent
from ..models.user import User
from ..models.file import FileUploadResponse
from ..config.settings import FusionSettings
from ..utils.cache import FusionCache
from ..utils.retry import RateLimiter
from ..utils.streaming import StreamingParser
from ..utils.validators import MessageValidator, FileValidator

logger = structlog.get_logger(__name__)


class FusionClient:
    """
    Main client for interacting with the Fusion API.
    
    Provides async/await support, automatic retry with exponential backoff,
    intelligent caching, rate limiting, and streaming responses.
    
    Example:
        ```python
        client = FusionClient(api_key="your-key")
        
        # Send a message
        response = await client.send_message(
            agent_id="agent-id",
            message="Hello!"
        )
        
        # Stream responses
        async for token in client.send_message(
            agent_id="agent-id", 
            message="Write an essay",
            stream=True
        ):
            print(token, end="")
        ```
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        enable_cache: bool = True,
        enable_tracing: bool = False,
        rate_limit_calls: int = 100,
        rate_limit_window: int = 60,
        cache_ttl: int = 300,
        cache_max_size: int = 1000
    ):
        """
        Initialize the Fusion client.
        
        Args:
            api_key: API key for authentication. If not provided, will look for
                    FUSION_API_KEY environment variable.
            base_url: Base URL for the Fusion API. Defaults to production URL.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts.
            enable_cache: Whether to enable response caching.
            enable_tracing: Whether to enable OpenTelemetry tracing.
            rate_limit_calls: Maximum calls per window for rate limiting.
            rate_limit_window: Time window in seconds for rate limiting.
            cache_ttl: Cache time-to-live in seconds.
            cache_max_size: Maximum number of cached items.
        """
        # Initialize settings
        self.settings = FusionSettings(
            fusion_api_key=api_key or "",
            fusion_base_url=base_url or "https://api.fusion.com/v1",
            fusion_timeout=timeout,
            fusion_max_retries=max_retries,
            cache_enabled=enable_cache,
            cache_ttl=cache_ttl,
            cache_max_size=cache_max_size,
            rate_limit_calls=rate_limit_calls,
            rate_limit_window=rate_limit_window,
            enable_tracing=enable_tracing
        )
        
        # Initialize components
        self.auth = FusionAuth(api_key=self.settings.fusion_api_key)
        self.http = HTTPClient(
            base_url=self.settings.fusion_base_url,
            api_key=self.settings.fusion_api_key,
            timeout=self.settings.fusion_timeout,
            max_retries=self.settings.fusion_max_retries
        )
        
        # Rate limiting
        self.rate_limiter = RateLimiter(
            max_calls=self.settings.rate_limit_calls,
            window=self.settings.rate_limit_window
        )
        
        # Caching
        self.cache = FusionCache(
            ttl=self.settings.cache_ttl,
            max_size=self.settings.cache_max_size
        ) if self.settings.cache_enabled else None
        
        # Validators
        self.message_validator = MessageValidator()
        self.file_validator = FileValidator()
        
        # Streaming
        self.streaming_parser = StreamingParser()
        
        logger.info(
            "FusionClient initialized",
            base_url=self.settings.fusion_base_url,
            cache_enabled=self.settings.cache_enabled,
            rate_limiting=f"{rate_limit_calls}/{rate_limit_window}s"
        )

    async def send_message(
        self,
        agent_id: str,
        message: str,
        chat_id: Optional[str] = None,
        files: Optional[List[str]] = None,
        stream: bool = False,
        folder: Optional[str] = None
    ) -> Union[ChatResponse, AsyncIterator[str]]:
        """
        Send a message to an agent.
        
        Args:
            agent_id: ID of the target agent
            message: Message content to send
            chat_id: Existing chat ID. If None, creates new chat.
            files: List of file IDs to attach
            stream: Whether to stream the response
            folder: Folder to organize the chat in
            
        Returns:
            ChatResponse object or AsyncIterator for streaming
            
        Raises:
            ValidationError: If message validation fails
            AgentNotFoundError: If agent doesn't exist
            ChatNotFoundError: If chat doesn't exist
            RateLimitError: If rate limit exceeded
        """
        # Validate input
        self.message_validator.validate(message)
        
        # Rate limiting
        await self.rate_limiter.acquire()
        
        logger.info(
            "Sending message",
            agent_id=agent_id,
            chat_id=chat_id,
            message_length=len(message),
            has_files=bool(files),
            stream=stream
        )
        
        try:
            if chat_id:
                # Send message to existing chat
                return await self._send_to_existing_chat(
                    chat_id=chat_id,
                    message=message,
                    files=files,
                    stream=stream
                )
            else:
                # Create new chat
                return await self._create_new_chat(
                    agent_id=agent_id,
                    message=message,
                    files=files,
                    folder=folder,
                    stream=stream
                )
                
        except Exception as e:
            logger.error(
                "Failed to send message",
                agent_id=agent_id,
                chat_id=chat_id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    async def create_chat(
        self,
        agent_id: str,
        initial_message: Optional[str] = None,
        folder: Optional[str] = None
    ) -> ChatResponse:
        """
        Create a new chat with an agent.
        
        Args:
            agent_id: ID of the target agent
            initial_message: Optional initial message
            folder: Folder to organize the chat in
            
        Returns:
            ChatResponse object
        """
        await self.rate_limiter.acquire()
        
        payload = {
            "agent_id": agent_id,
            "folder": folder
        }
        
        if initial_message:
            self.message_validator.validate(initial_message)
            payload["message"] = initial_message
        
        response = await self.http.post("/chat", json=payload)
        return ChatResponse.model_validate(response)

    async def get_chat(self, chat_id: str) -> ChatResponse:
        """
        Retrieve an existing chat.
        
        Args:
            chat_id: ID of the chat to retrieve
            
        Returns:
            ChatResponse object
        """
        # Check cache first
        if self.cache:
            cache_key = f"chat:{chat_id}"
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug("Chat retrieved from cache", chat_id=chat_id)
                return cached
        
        await self.rate_limiter.acquire()
        
        try:
            response = await self.http.get(f"/chat/{chat_id}")
            chat_response = ChatResponse.model_validate(response)
            
            # Cache the response
            if self.cache:
                self.cache.set(cache_key, chat_response)
            
            return chat_response
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ChatNotFoundError(chat_id)
            raise

    async def list_agents(self) -> List[Agent]:
        """
        List available agents.
        
        Returns:
            List of Agent objects
        """
        # Check cache first
        if self.cache:
            cache_key = "agents:list"
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug("Agents list retrieved from cache")
                return cached
        
        await self.rate_limiter.acquire()
        
        response = await self.http.get("/agents")
        agents = [Agent.model_validate(agent) for agent in response.get("agents", [])]
        
        # Cache the response
        if self.cache:
            self.cache.set(cache_key, agents)
        
        return agents

    async def upload_file(
        self,
        file_path: str,
        chat_id: Optional[str] = None
    ) -> FileUploadResponse:
        """
        Upload a file.
        
        Args:
            file_path: Path to the file to upload
            chat_id: Optional chat ID to associate with
            
        Returns:
            FileUploadResponse object
        """
        # Validate file
        self.file_validator.validate(file_path)
        
        await self.rate_limiter.acquire()
        
        # Prepare multipart form data
        files = {"file": open(file_path, "rb")}
        data = {}
        
        if chat_id:
            data["chat_id"] = chat_id
        
        try:
            response = await self.http.post(
                "/files/upload",
                files=files,
                data=data
            )
            return FileUploadResponse.model_validate(response)
            
        finally:
            files["file"].close()

    async def _send_to_existing_chat(
        self,
        chat_id: str,
        message: str,
        files: Optional[List[str]] = None,
        stream: bool = False
    ) -> Union[ChatResponse, AsyncIterator[str]]:
        """Send message to existing chat."""
        payload = {
            "message": message,
            "files": files or []
        }
        
        if stream:
            return await self._stream_response(f"/chat/{chat_id}/message", payload)
        
        response = await self.http.post(f"/chat/{chat_id}/message", json=payload)
        return ChatResponse.model_validate(response)

    async def _create_new_chat(
        self,
        agent_id: str,
        message: str,
        files: Optional[List[str]] = None,
        folder: Optional[str] = None,
        stream: bool = False
    ) -> Union[ChatResponse, AsyncIterator[str]]:
        """Create new chat and send message."""
        payload = {
            "agent_id": agent_id,
            "message": message,
            "files": files or [],
            "folder": folder
        }
        
        if stream:
            return await self._stream_response("/chat", payload)
        
        response = await self.http.post("/chat", json=payload)
        return ChatResponse.model_validate(response)

    async def _stream_response(
        self,
        endpoint: str,
        payload: Dict[str, Any]
    ) -> AsyncIterator[str]:
        """Stream response from API."""
        payload["stream"] = True
        
        async with self.http.stream("POST", endpoint, json=payload) as response:
            async for token in self.streaming_parser.parse_stream(response.aiter_bytes()):
                yield token

    async def close(self):
        """Close the HTTP client and cleanup resources."""
        await self.http.close()
        logger.info("FusionClient closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close() 