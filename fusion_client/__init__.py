"""
Fusion API Python Library

A modern, async-first Python client for the Fusion API with support for
chats, agents, files, and integrations with LangChain and CrewAI.
"""

from .core.client import FusionClient
from .core.exceptions import (
    FusionError,
    AuthenticationError,
    RateLimitError,
    AgentNotFoundError,
    ChatNotFoundError,
    ValidationError,
    NetworkError,
)
from .models.chat import Chat, ChatResponse, Message
from .models.agent import Agent
from .models.user import User
from .models.file import FileUploadResponse
from .config.settings import FusionSettings

__version__ = "0.1.0"
__author__ = "Fusion Team"
__email__ = "dev@fusion.com"

__all__ = [
    # Core client
    "FusionClient",
    
    # Exceptions
    "FusionError",
    "AuthenticationError", 
    "RateLimitError",
    "AgentNotFoundError",
    "ChatNotFoundError",
    "ValidationError",
    "NetworkError",
    
    # Models
    "Chat",
    "ChatResponse",
    "Message",
    "Agent",
    "User",
    "FileUploadResponse",
    
    # Configuration
    "FusionSettings",
    
    # Version info
    "__version__",
    "__author__",
    "__email__",
] 