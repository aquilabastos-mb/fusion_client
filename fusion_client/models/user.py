"""User model."""

from pydantic import Field, EmailStr, field_validator
from .base import BaseModel


class User(BaseModel):
    """Represents a user in the Fusion system."""
    
    email: EmailStr = Field(..., description="User's email address")
    full_name: str = Field(..., description="User's full name")
    
    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v):
        """Validate that full_name is not empty."""
        if not v or not v.strip():
            raise ValueError("Full name cannot be empty")
        return v
    
    def __str__(self) -> str:
        return f"{self.full_name} <{self.email}>"
    
    @property
    def first_name(self) -> str:
        """Extract first name from full name."""
        return self.full_name.split()[0] if self.full_name else ""
    
    @property 
    def last_name(self) -> str:
        """Extract last name from full name."""
        parts = self.full_name.split()
        return " ".join(parts[1:]) if len(parts) > 1 else "" 