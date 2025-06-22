"""Agent model."""

from typing import Optional
from uuid import UUID
from pydantic import Field
from .base import BaseModel


class Agent(BaseModel):
    """Represents an agent in the Fusion system."""
    
    id: UUID = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    image: Optional[str] = Field(None, description="Agent image URL")
    status: bool = Field(True, description="Whether agent is active")
    system_agent: bool = Field(False, description="Whether this is a system agent")
    transcription: Optional[str] = Field(None, description="Agent transcription settings")
    
    def __str__(self) -> str:
        status_emoji = "🟢" if self.status else "🔴"
        return f"{status_emoji} {self.name}"
    
    @property
    def is_active(self) -> bool:
        """Check if agent is active."""
        return self.status
    
    @property
    def display_name(self) -> str:
        """Get display name with status indicator."""
        return str(self) 