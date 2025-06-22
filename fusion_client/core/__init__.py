"""Core client functionality."""

from .client import FusionClient
from .exceptions import (
    FusionError,
    AuthenticationError,
    RateLimitError,
    AgentNotFoundError,
    ChatNotFoundError,
    ValidationError,
    NetworkError,
)

__all__ = [
    "FusionClient",
    "FusionError",
    "AuthenticationError",
    "RateLimitError", 
    "AgentNotFoundError",
    "ChatNotFoundError",
    "ValidationError",
    "NetworkError",
] 