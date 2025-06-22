"""File-related models."""

from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID
from pydantic import Field, validator
from .base import BaseModel


class FileUploadResponse(BaseModel):
    """Response from file upload."""
    
    file_id: UUID = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME content type")
    size_bytes: int = Field(..., description="File size in bytes")
    upload_url: Optional[str] = Field(None, description="Upload URL if needed")
    download_url: Optional[str] = Field(None, description="Download URL")
    created_at: datetime = Field(..., description="Upload timestamp")
    
    @property
    def size_mb(self) -> float:
        """File size in megabytes."""
        return self.size_bytes / (1024 * 1024)
    
    @property
    def file_extension(self) -> str:
        """Extract file extension."""
        return Path(self.filename).suffix.lower().lstrip('.')
    
    def __str__(self) -> str:
        return f"{self.filename} ({self.size_mb:.2f}MB)"


class FileMetadata(BaseModel):
    """Metadata for a file."""
    
    filename: str = Field(..., description="File name")
    content_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(..., description="File size")
    
    @validator('size_bytes')
    def validate_size(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("File size must be positive")
        return v
    
    @validator('filename')
    def validate_filename(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("Filename cannot be empty")
        return v.strip()
    
    @property
    def size_mb(self) -> float:
        """File size in megabytes."""
        return self.size_bytes / (1024 * 1024)
    
    @property
    def file_extension(self) -> str:
        """Extract file extension."""
        return Path(self.filename).suffix.lower().lstrip('.') 