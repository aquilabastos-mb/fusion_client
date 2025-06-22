"""Validation utilities for inputs and files."""

import re
import mimetypes
from pathlib import Path
from typing import List, Optional, Dict, Any
from ..core.exceptions import ValidationError, FileTooLargeError, UnsupportedFileTypeError


class MessageValidator:
    """Validator for chat messages."""
    
    def __init__(self, max_length: int = 10000):
        self.max_length = max_length
        self.suspicious_patterns = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'javascript:',                # JavaScript URLs
            r'eval\s*\(',                 # eval() calls
            r'document\.',                # DOM access
            r'window\.',                  # Window object access
            r'onclick\s*=',               # Event handlers
            r'onerror\s*=',
            r'onload\s*=',
            r'<iframe[^>]*>',             # iframes
            r'<object[^>]*>',             # Objects
            r'<embed[^>]*>',              # Embeds
        ]
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.suspicious_patterns]
    
    def validate_message(self, message: str) -> None:
        """
        Validate a chat message.
        
        Args:
            message: Message content to validate
            
        Raises:
            ValidationError: If message is invalid
        """
        if not message or not message.strip():
            raise ValidationError("Message cannot be empty", field="message")
        
        if len(message) > self.max_length:
            raise ValidationError(
                f"Message too long. Maximum {self.max_length} characters allowed",
                field="message"
            )
        
        # Check for suspicious patterns
        for pattern in self.compiled_patterns:
            if pattern.search(message):
                raise ValidationError(
                    "Message contains potentially unsafe content",
                    field="message"
                )
    
    def sanitize_message(self, message: str) -> str:
        """
        Sanitize message by removing/escaping dangerous content.
        
        Args:
            message: Message to sanitize
            
        Returns:
            Sanitized message
        """
        if not message:
            return ""
        
        # Remove common unsafe patterns
        sanitized = message
        for pattern in self.compiled_patterns:
            sanitized = pattern.sub('', sanitized)
        
        # Basic HTML escape
        sanitized = (
            sanitized
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#x27;')
        )
        
        return sanitized.strip()
    
    def is_safe_message(self, message: str) -> bool:
        """
        Check if message is safe without raising exceptions.
        
        Args:
            message: Message to check
            
        Returns:
            True if message is safe
        """
        try:
            self.validate_message(message)
            return True
        except ValidationError:
            return False


class FileValidator:
    """Validator for file uploads."""
    
    def __init__(
        self, 
        max_size_mb: int = 10,
        allowed_types: Optional[List[str]] = None
    ):
        self.max_size_mb = max_size_mb
        self.max_size_bytes = max_size_mb * 1024 * 1024
        
        # Default allowed file types
        self.allowed_types = allowed_types or [
            'txt', 'pdf', 'doc', 'docx', 'md', 'csv', 'json', 'xml',
            'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg',
            'mp3', 'wav', 'mp4', 'avi', 'mov',
            'zip', 'tar', 'gz'
        ]
    
    def validate_file_path(self, file_path: str) -> None:
        """
        Validate file path and basic properties.
        
        Args:
            file_path: Path to file to validate
            
        Raises:
            ValidationError: If file is invalid
            FileTooLargeError: If file is too large
            UnsupportedFileTypeError: If file type not allowed
        """
        path = Path(file_path)
        
        # Check if file exists
        if not path.exists():
            raise ValidationError(f"File not found: {file_path}", field="file_path")
        
        # Check if it's actually a file
        if not path.is_file():
            raise ValidationError(f"Path is not a file: {file_path}", field="file_path")
        
        # Check file size
        size_bytes = path.stat().st_size
        if size_bytes > self.max_size_bytes:
            size_mb = size_bytes / (1024 * 1024)
            raise FileTooLargeError(size_mb, self.max_size_mb)
        
        # Check file type
        file_extension = path.suffix.lower().lstrip('.')
        if file_extension not in self.allowed_types:
            raise UnsupportedFileTypeError(file_extension, self.allowed_types)
    
    def validate_file_content(self, content: bytes, filename: str) -> None:
        """
        Validate file content.
        
        Args:
            content: File content as bytes
            filename: Original filename
            
        Raises:
            ValidationError: If content is invalid
            FileTooLargeError: If content is too large
            UnsupportedFileTypeError: If file type not allowed
        """
        # Check size
        if len(content) > self.max_size_bytes:
            size_mb = len(content) / (1024 * 1024)
            raise FileTooLargeError(size_mb, self.max_size_mb)
        
        # Check file extension
        file_extension = Path(filename).suffix.lower().lstrip('.')
        if file_extension not in self.allowed_types:
            raise UnsupportedFileTypeError(file_extension, self.allowed_types)
        
        # Basic magic number checks for common file types
        self._validate_file_magic(content, file_extension)
    
    def _validate_file_magic(self, content: bytes, expected_extension: str) -> None:
        """Validate file content matches expected type using magic numbers."""
        if not content:
            return
        
        # Common file magic numbers
        magic_numbers = {
            'pdf': [b'%PDF'],
            'jpg': [b'\xff\xd8\xff'],
            'jpeg': [b'\xff\xd8\xff'],
            'png': [b'\x89PNG\r\n\x1a\n'],
            'gif': [b'GIF87a', b'GIF89a'],
            'zip': [b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'],
            'mp3': [b'ID3', b'\xff\xfb'],
            'mp4': [b'ftyp'],
        }
        
        expected_magics = magic_numbers.get(expected_extension)
        if expected_magics:
            if not any(content.startswith(magic) for magic in expected_magics):
                raise ValidationError(
                    f"File content doesn't match expected type: {expected_extension}",
                    field="file_content"
                )
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get comprehensive file information.
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary with file information
        """
        path = Path(file_path)
        if not path.exists():
            raise ValidationError(f"File not found: {file_path}")
        
        stat = path.stat()
        mime_type, _ = mimetypes.guess_type(file_path)
        
        return {
            'filename': path.name,
            'size_bytes': stat.st_size,
            'size_mb': stat.st_size / (1024 * 1024),
            'extension': path.suffix.lower().lstrip('.'),
            'mime_type': mime_type,
            'is_text': mime_type and mime_type.startswith('text/'),
            'is_image': mime_type and mime_type.startswith('image/'),
            'is_audio': mime_type and mime_type.startswith('audio/'),
            'is_video': mime_type and mime_type.startswith('video/'),
            'created_at': stat.st_ctime,
            'modified_at': stat.st_mtime,
        }
    
    def is_supported_type(self, filename: str) -> bool:
        """
        Check if file type is supported.
        
        Args:
            filename: Name of file to check
            
        Returns:
            True if file type is supported
        """
        extension = Path(filename).suffix.lower().lstrip('.')
        return extension in self.allowed_types
    
    def get_max_size_for_type(self, file_extension: str) -> int:
        """
        Get maximum allowed size for specific file type.
        
        Args:
            file_extension: File extension
            
        Returns:
            Maximum size in bytes
        """
        # You could implement different size limits per file type
        size_limits = {
            'pdf': 50 * 1024 * 1024,  # 50MB for PDFs
            'mp4': 100 * 1024 * 1024,  # 100MB for videos
            'jpg': 10 * 1024 * 1024,  # 10MB for images
            'jpeg': 10 * 1024 * 1024,
            'png': 10 * 1024 * 1024,
        }
        
        return size_limits.get(file_extension.lower(), self.max_size_bytes)


class AgentIdValidator:
    """Validator for agent IDs."""
    
    def __init__(self):
        # UUID pattern (with or without hyphens)
        self.uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$',
            re.IGNORECASE
        )
        # Simple alphanumeric pattern for non-UUID IDs
        self.simple_pattern = re.compile(r'^[a-zA-Z0-9\-_]+$')
    
    def validate_agent_id(self, agent_id: str) -> None:
        """
        Validate agent ID format.
        
        Args:
            agent_id: Agent ID to validate
            
        Raises:
            ValidationError: If agent ID is invalid
        """
        if not agent_id or not agent_id.strip():
            raise ValidationError("Agent ID cannot be empty", field="agent_id")
        
        agent_id = agent_id.strip()
        
        # Check length
        if len(agent_id) < 3 or len(agent_id) > 100:
            raise ValidationError(
                "Agent ID must be between 3 and 100 characters",
                field="agent_id"
            )
        
        # Check format - either UUID or simple alphanumeric
        if not (self.uuid_pattern.match(agent_id) or self.simple_pattern.match(agent_id)):
            raise ValidationError(
                "Agent ID must be UUID or alphanumeric with hyphens/underscores",
                field="agent_id"
            )
    
    def is_valid_agent_id(self, agent_id: str) -> bool:
        """
        Check if agent ID is valid without raising exceptions.
        
        Args:
            agent_id: Agent ID to check
            
        Returns:
            True if agent ID is valid
        """
        try:
            self.validate_agent_id(agent_id)
            return True
        except ValidationError:
            return False 