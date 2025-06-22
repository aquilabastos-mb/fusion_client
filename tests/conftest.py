"""Configuração principal do pytest e fixtures compartilhadas."""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
import respx

from fusion_client import FusionClient
from fusion_client.models import Agent, User, Chat, Message, ChatResponse


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def api_key():
    """Test API key."""
    return "test-api-key-12345"


@pytest.fixture
def base_url():
    """Test base URL."""
    return "https://api.test.fusion.com/v1"


@pytest.fixture
def fusion_client(api_key, base_url):
    """Create a FusionClient instance for testing."""
    return FusionClient(
        api_key=api_key,
        base_url=base_url,
        timeout=30.0,
        max_retries=3,
        enable_cache=False,  # Disable cache for tests
        enable_tracing=False
    )


@pytest.fixture
def mock_agent():
    """Mock agent data."""
    return Agent(
        id=uuid4(),
        name="Test Agent",
        description="A test agent for testing purposes",
        image="https://example.com/agent.jpg",
        status=True,
        system_agent=False,
        transcription=None
    )


@pytest.fixture
def mock_user():
    """Mock user data."""
    return User(
        email="test@example.com",
        full_name="Test User"
    )


@pytest.fixture
def mock_chat(mock_agent, mock_user):
    """Mock chat data."""
    return Chat(
        id=uuid4(),
        agent=mock_agent,
        user=mock_user,
        folder=None,
        message="Initial message",
        knowledge=[],
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        system_chat=False
    )


@pytest.fixture
def mock_messages(mock_chat):
    """Mock messages list."""
    return [
        Message(
            id=uuid4(),
            chat_id=mock_chat.id,
            message="Hello, I need help",
            message_type="user",
            created_at="2024-01-01T00:00:00Z",
            files=[]
        ),
        Message(
            id=uuid4(),
            chat_id=mock_chat.id,
            message="Hello! How can I help you today?",
            message_type="agent",
            created_at="2024-01-01T00:00:01Z",
            files=[]
        )
    ]


@pytest.fixture
def mock_chat_response(mock_chat, mock_messages):
    """Mock complete chat response."""
    return ChatResponse(
        chat=mock_chat,
        messages=mock_messages
    )


@pytest.fixture
def mock_api_responses():
    """Mock API responses for various endpoints."""
    return {
        "create_chat": {
            "chat": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "agent": {
                    "id": "550e8400-e29b-41d4-a716-446655440001",
                    "name": "General Assistant",
                    "description": "A helpful general-purpose assistant",
                    "image": None,
                    "status": True,
                    "system_agent": False,
                    "transcription": None
                },
                "user": {
                    "email": "test@example.com",
                    "full_name": "Test User"
                },
                "folder": None,
                "message": "Hello, how can I help?",
                "knowledge": [],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "system_chat": False
            },
            "messages": [
                {
                    "id": "msg-1",
                    "chat_id": "550e8400-e29b-41d4-a716-446655440000",
                    "message": "Hello, how can I help?",
                    "message_type": "user",
                    "created_at": "2024-01-01T00:00:00Z",
                    "files": []
                },
                {
                    "id": "msg-2",
                    "chat_id": "550e8400-e29b-41d4-a716-446655440000",
                    "message": "Hello! I'm here to assist you.",
                    "message_type": "agent",
                    "created_at": "2024-01-01T00:00:01Z",
                    "files": []
                }
            ]
        },
        "agents_list": [
            {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "name": "General Assistant",
                "description": "A helpful general-purpose assistant",
                "image": None,
                "status": True,
                "system_agent": False,
                "transcription": None
            },
            {
                "id": "550e8400-e29b-41d4-a716-446655440002",
                "name": "Code Helper",
                "description": "Specialized in programming and code review",
                "image": "https://example.com/code-agent.jpg",
                "status": True,
                "system_agent": False,
                "transcription": None
            }
        ],
        "file_upload": {
            "file_id": "file-12345",
            "filename": "test-document.pdf",
            "size": 2048,
            "content_type": "application/pdf",
            "upload_url": "https://storage.example.com/files/file-12345"
        }
    }


@pytest.fixture
async def http_mock():
    """Create an httpx mock for API testing."""
    async with respx.mock:
        yield respx


@pytest.fixture
def test_files_dir():
    """Directory containing test files."""
    return Path(__file__).parent / "fixtures" / "files"


@pytest.fixture
def sample_pdf_file(test_files_dir, tmp_path):
    """Create a sample PDF file for testing."""
    test_files_dir.mkdir(parents=True, exist_ok=True)
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
    pdf_file = tmp_path / "test-document.pdf"
    pdf_file.write_bytes(pdf_content)
    return pdf_file


@pytest.fixture
def streaming_response_data():
    """Mock streaming response data."""
    return [
        "data: {\"token\": \"Hello\"}\n\n",
        "data: {\"token\": \" there!\"}\n\n",
        "data: {\"token\": \" How\"}\n\n",
        "data: {\"token\": \" can\"}\n\n",
        "data: {\"token\": \" I\"}\n\n",
        "data: {\"token\": \" help?\"}\n\n",
        "data: [DONE]\n\n"
    ]


@pytest.fixture
def rate_limiter_mock():
    """Mock rate limiter for testing."""
    mock = AsyncMock()
    mock.acquire = AsyncMock()
    return mock


class MockStreamingResponse:
    """Mock for streaming HTTP responses."""
    
    def __init__(self, data: list):
        self.data = data
        self.index = 0
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self.index >= len(self.data):
            raise StopAsyncIteration
        
        chunk = self.data[self.index].encode('utf-8')
        self.index += 1
        return chunk


@pytest.fixture
def mock_streaming_response(streaming_response_data):
    """Create a mock streaming response."""
    return MockStreamingResponse(streaming_response_data) 