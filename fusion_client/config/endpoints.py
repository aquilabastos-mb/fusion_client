"""API endpoint definitions."""

from typing import Dict, Any


class Endpoints:
    """API endpoint definitions for Fusion API."""
    
    # Chat endpoints
    CHAT_CREATE = "/chat"
    CHAT_GET = "/chat/{chat_id}"
    CHAT_MESSAGES = "/chat/{chat_id}/messages"
    CHAT_MESSAGE_SEND = "/chat/{chat_id}/message"
    
    # Agent endpoints
    AGENTS_LIST = "/agents"
    AGENT_GET = "/agents/{agent_id}"
    
    # File endpoints
    FILE_UPLOAD = "/chat/{chat_id}/files"
    FILE_DOWNLOAD = "/files/{file_id}"
    
    # Knowledge endpoints
    KNOWLEDGE_UPLOAD = "/knowledge"
    KNOWLEDGE_LIST = "/knowledge"
    KNOWLEDGE_DELETE = "/knowledge/{knowledge_id}"
    
    # Health and status
    HEALTH = "/health"
    STATUS = "/status"
    
    @classmethod
    def format_endpoint(cls, endpoint: str, **kwargs: Any) -> str:
        """Format endpoint with parameters."""
        return endpoint.format(**kwargs)


# Singleton instance
ENDPOINTS = Endpoints() 