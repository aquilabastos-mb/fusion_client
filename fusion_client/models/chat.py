"""Chat-related models."""

from datetime import datetime
from typing import List, Optional, Literal
from uuid import UUID
from pydantic import Field
from .base import BaseModel
from .agent import Agent
from .user import User


class Message(BaseModel):
    """Represents a message in a chat."""
    
    id: UUID = Field(..., description="Unique message identifier")
    chat_id: UUID = Field(..., description="Chat identifier")
    message: str = Field(..., description="Message content")
    message_type: Literal["user", "agent"] = Field(..., description="Type of message")
    created_at: datetime = Field(..., description="Message creation timestamp")
    files: List[str] = Field(default_factory=list, description="List of file attachments")
    
    def __str__(self) -> str:
        sender = "User" if self.message_type == "user" else "Agent"
        preview = self.message[:50] + "..." if len(self.message) > 50 else self.message
        return f"[{sender}] {preview}"
    
    @property
    def is_from_user(self) -> bool:
        """Check if message is from user."""
        return self.message_type == "user"
    
    @property
    def is_from_agent(self) -> bool:
        """Check if message is from agent."""
        return self.message_type == "agent"
    
    @property
    def has_files(self) -> bool:
        """Check if message has file attachments."""
        return len(self.files) > 0
    
    @property
    def word_count(self) -> int:
        """Count words in message."""
        return len(self.message.split()) if self.message else 0


class Chat(BaseModel):
    """Represents a chat conversation."""
    
    id: UUID = Field(..., description="Unique chat identifier")
    agent: Agent = Field(..., description="Agent participating in chat")
    user: User = Field(..., description="User participating in chat")
    folder: Optional[str] = Field(None, description="Folder/category for organization")
    message: str = Field(..., description="Initial or latest message")
    knowledge: List[str] = Field(default_factory=list, description="Knowledge sources")
    created_at: datetime = Field(..., description="Chat creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    system_chat: bool = Field(False, description="Whether this is a system chat")
    
    def __str__(self) -> str:
        return f"Chat with {self.agent.name} ({self.id})"
    
    @property
    def is_recent(self) -> bool:
        """Check if chat was updated recently (within 24 hours)."""
        from datetime import timedelta
        if not self.updated_at:
            return False
        return (datetime.utcnow() - self.updated_at) < timedelta(hours=24)
    
    @property
    def has_knowledge(self) -> bool:
        """Check if chat has knowledge sources."""
        return len(self.knowledge) > 0
    
    @property
    def display_title(self) -> str:
        """Generate a display title for the chat."""
        if self.folder:
            return f"[{self.folder}] Chat with {self.agent.name}"
        return f"Chat with {self.agent.name}"


class ChatResponse(BaseModel):
    """Complete chat response with messages."""
    
    chat: Chat = Field(..., description="Chat information")
    messages: List[Message] = Field(..., description="Chat messages")
    
    def __str__(self) -> str:
        return f"{self.chat} ({len(self.messages)} messages)"
    
    @property
    def last_message(self) -> Optional[Message]:
        """Get the last message in the chat."""
        return self.messages[-1] if self.messages else None
    
    @property
    def first_message(self) -> Optional[Message]:
        """Get the first message in the chat."""
        return self.messages[0] if self.messages else None
    
    @property
    def user_messages(self) -> List[Message]:
        """Get all messages from the user."""
        return [msg for msg in self.messages if msg.is_from_user]
    
    @property
    def agent_messages(self) -> List[Message]:
        """Get all messages from the agent."""
        return [msg for msg in self.messages if msg.is_from_agent]
    
    @property
    def message_count(self) -> int:
        """Total number of messages."""
        return len(self.messages)
    
    @property
    def total_words(self) -> int:
        """Total word count across all messages."""
        return sum(msg.word_count for msg in self.messages)
    
    @property
    def has_files(self) -> bool:
        """Check if any message has file attachments."""
        return any(msg.has_files for msg in self.messages)
    
    def get_messages_by_type(self, message_type: Literal["user", "agent"]) -> List[Message]:
        """Get messages filtered by type."""
        return [msg for msg in self.messages if msg.message_type == message_type]
    
    def get_messages_with_files(self) -> List[Message]:
        """Get messages that have file attachments."""
        return [msg for msg in self.messages if msg.has_files]
    
    def get_conversation_summary(self, max_messages: int = 5) -> str:
        """Get a summary of the conversation."""
        if not self.messages:
            return "No messages in chat"
        
        recent_messages = self.messages[-max_messages:]
        summary_parts = []
        
        for msg in recent_messages:
            sender = "You" if msg.is_from_user else self.chat.agent.name
            preview = msg.message[:100] + "..." if len(msg.message) > 100 else msg.message
            summary_parts.append(f"{sender}: {preview}")
        
        return "\n".join(summary_parts) 