"""Test data fixtures and utilities."""

from datetime import datetime
from uuid import UUID, uuid4
from typing import Dict, List, Any

from fusion_client.models import Agent, User, Chat, Message, ChatResponse


class TestData:
    """Centralized test data for consistent testing."""
    
    # Test IDs
    AGENT_ID = UUID("550e8400-e29b-41d4-a716-446655440001")
    CHAT_ID = UUID("550e8400-e29b-41d4-a716-446655440000")
    USER_EMAIL = "test@example.com"
    
    @classmethod
    def get_test_agent(cls, **overrides) -> Agent:
        """Create a test agent with optional overrides."""
        defaults = {
            "id": cls.AGENT_ID,
            "name": "Test Agent",
            "description": "A test agent for testing purposes",
            "image": None,
            "status": True,
            "system_agent": False,
            "transcription": None
        }
        defaults.update(overrides)
        return Agent(**defaults)
    
    @classmethod
    def get_test_user(cls, **overrides) -> User:
        """Create a test user with optional overrides."""
        defaults = {
            "email": cls.USER_EMAIL,
            "full_name": "Test User"
        }
        defaults.update(overrides)
        return User(**defaults)
    
    @classmethod
    def get_test_chat(cls, **overrides) -> Chat:
        """Create a test chat with optional overrides."""
        defaults = {
            "id": cls.CHAT_ID,
            "agent": cls.get_test_agent(),
            "user": cls.get_test_user(),
            "folder": None,
            "message": "Initial test message",
            "knowledge": [],
            "created_at": datetime.fromisoformat("2024-01-01T00:00:00+00:00"),
            "updated_at": datetime.fromisoformat("2024-01-01T00:00:00+00:00"),
            "system_chat": False
        }
        defaults.update(overrides)
        return Chat(**defaults)
    
    @classmethod
    def get_test_messages(cls, chat_id: UUID = None, count: int = 2) -> List[Message]:
        """Create test messages for a chat."""
        if chat_id is None:
            chat_id = cls.CHAT_ID
        
        messages = []
        for i in range(count):
            message_type = "user" if i % 2 == 0 else "agent"
            content = f"Test message {i + 1} from {message_type}"
            
            messages.append(Message(
                id=uuid4(),
                chat_id=chat_id,
                message=content,
                message_type=message_type,
                created_at=datetime.fromisoformat(f"2024-01-01T00:00:0{i}+00:00"),
                files=[]
            ))
        
        return messages
    
    @classmethod
    def get_test_chat_response(cls, **overrides) -> ChatResponse:
        """Create a complete test chat response."""
        chat = cls.get_test_chat()
        messages = cls.get_test_messages(chat.id)
        
        defaults = {
            "chat": chat,
            "messages": messages
        }
        defaults.update(overrides)
        return ChatResponse(**defaults)
    
    @classmethod
    def get_multiple_agents(cls, count: int = 3) -> List[Agent]:
        """Create multiple test agents."""
        agents = []
        for i in range(count):
            agent = cls.get_test_agent(
                id=uuid4(),
                name=f"Test Agent {i + 1}",
                description=f"Test agent number {i + 1}",
                system_agent=i == 0  # First agent is system agent
            )
            agents.append(agent)
        return agents


# Common test scenarios
TEST_SCENARIOS = {
    "simple_chat": {
        "user_message": "Hello, how are you?",
        "agent_response": "Hello! I'm doing well, thank you for asking. How can I help you today?",
        "expected_tokens": ["Hello!", " I'm", " doing", " well,", " thank", " you"]
    },
    "long_message": {
        "user_message": "Tell me a long story about artificial intelligence and its impact on society, including both positive and negative aspects, historical context, and future predictions.",
        "agent_response": "Artificial intelligence has a rich history dating back to the 1950s...",
        "expected_length": 500
    },
    "code_assistance": {
        "user_message": "Write a Python function to sort a list",
        "agent_response": "Here's a Python function to sort a list:\n\n```python\ndef sort_list(items):\n    return sorted(items)\n```",
        "contains_code": True
    },
    "file_upload": {
        "filename": "test-document.pdf",
        "content_type": "application/pdf",
        "size": 2048,
        "expected_file_id": "file-12345"
    },
    "error_cases": {
        "empty_message": "",
        "too_long_message": "x" * 50000,
        "invalid_agent_id": "invalid-uuid",
        "nonexistent_chat_id": "550e8400-e29b-41d4-a716-446655440999"
    }
}

# API endpoint patterns for testing
API_ENDPOINTS = {
    "create_chat": "/chat",
    "send_message": "/chat/{chat_id}/message",
    "get_chat": "/chat/{chat_id}",
    "list_messages": "/chat/{chat_id}/messages",
    "upload_file": "/chat/{chat_id}/files",
    "list_agents": "/agents",
    "get_agent": "/agents/{agent_id}",
    "create_agent": "/agents",
    "update_agent": "/agents/{agent_id}",
    "delete_agent": "/agents/{agent_id}"
}

# Rate limiting test scenarios
RATE_LIMIT_SCENARIOS = {
    "normal_usage": {
        "requests_per_minute": 50,
        "expected_delay": 0
    },
    "burst_usage": {
        "requests_per_minute": 150,
        "expected_delay": 5.0
    },
    "excessive_usage": {
        "requests_per_minute": 500,
        "expected_delay": 60.0
    }
}

# Cache test scenarios
CACHE_SCENARIOS = {
    "cacheable_request": {
        "method": "GET",
        "endpoint": "/agents",
        "params": {"status": "active"},
        "cache_key": "GET:/agents:{'status': 'active'}",
        "ttl": 300
    },
    "non_cacheable_request": {
        "method": "POST",
        "endpoint": "/chat",
        "params": {"message": "Hello"},
        "should_cache": False
    }
} 