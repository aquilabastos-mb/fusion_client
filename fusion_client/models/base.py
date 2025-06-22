"""Base model for all Pydantic models."""

from datetime import datetime
from typing import Any, Dict
from pydantic import BaseModel as PydanticBaseModel, Field, ConfigDict


class BaseModel(PydanticBaseModel):
    """Base model with common configuration."""
    
    model_config = ConfigDict(
        # Allow extra fields for future compatibility
        extra="ignore",
        # Use enum values instead of names
        use_enum_values=True,
        # Validate assignment
        validate_assignment=True,
        # Populate by name (support aliases)
        populate_by_name=True,
        # Support datetime parsing
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
    
    def model_dump_json_safe(self, **kwargs: Any) -> Dict[str, Any]:
        """Dump model to dict with safe JSON serialization."""
        return self.model_dump(
            mode="json",
            exclude_none=True,
            **kwargs
        )
    
    def model_copy_with_changes(self, **changes: Any) -> "BaseModel":
        """Create a copy of the model with specific changes."""
        return self.model_copy(update=changes) 