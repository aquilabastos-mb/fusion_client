"""Custom exceptions for Fusion client."""

from typing import Optional, Dict, Any


class FusionError(Exception):
    """Base exception for Fusion API errors."""
    
    def __init__(
        self, 
        message: str, 
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class AuthenticationError(FusionError):
    """Authentication failed."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class AuthorizationError(FusionError):
    """Authorization failed - insufficient permissions."""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status_code=403)


class RateLimitError(FusionError):
    """Rate limit exceeded."""
    
    def __init__(
        self, 
        message: str = "Rate limit exceeded", 
        retry_after: Optional[int] = None
    ):
        self.retry_after = retry_after
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(message, status_code=429, details=details)


class AgentNotFoundError(FusionError):
    """Agent not found."""
    
    def __init__(self, agent_id: str):
        message = f"Agent '{agent_id}' not found"
        super().__init__(message, status_code=404, details={"agent_id": agent_id})


class ChatNotFoundError(FusionError):
    """Chat not found."""
    
    def __init__(self, chat_id: str):
        message = f"Chat '{chat_id}' not found"
        super().__init__(message, status_code=404, details={"chat_id": chat_id})


class ValidationError(FusionError):
    """Data validation error."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        details = {"field": field} if field else {}
        super().__init__(message, status_code=400, details=details)


class NetworkError(FusionError):
    """Network/connectivity error."""
    
    def __init__(self, message: str = "Network error occurred"):
        super().__init__(message)


class ServerError(FusionError):
    """Server-side error."""
    
    def __init__(self, message: str = "Internal server error", status_code: int = 500):
        super().__init__(message, status_code=status_code)


class TimeoutError(FusionError):
    """Request timeout error."""
    
    def __init__(self, message: str = "Request timed out"):
        super().__init__(message, status_code=408)


class FileTooLargeError(ValidationError):
    """File size exceeds maximum allowed."""
    
    def __init__(self, size_mb: float, max_size_mb: int):
        message = f"File size {size_mb:.2f}MB exceeds maximum {max_size_mb}MB"
        super().__init__(message)


class UnsupportedFileTypeError(ValidationError):
    """Unsupported file type."""
    
    def __init__(self, file_type: str, allowed_types: list[str]):
        message = f"File type '{file_type}' not supported. Allowed: {', '.join(allowed_types)}"
        super().__init__(message) 