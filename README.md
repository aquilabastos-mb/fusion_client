# Fusion Client

[![PyPI version](https://badge.fury.io/py/fusion-client.svg)](https://badge.fury.io/py/fusion-client)
[![Python versions](https://img.shields.io/pypi/pyversions/fusion-client.svg)](https://pypi.org/project/fusion-client/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Coverage Status](https://coveralls.io/repos/github/company/fusion-client/badge.svg?branch=main)](https://coveralls.io/github/company/fusion-client?branch=main)

A modern, async-first Python client for the Fusion API with support for chats, agents, files, and integrations with LangChain and CrewAI.

## ✨ Features

- **🚀 Async/Await Support**: Built from the ground up with asyncio
- **🔐 Multiple Auth Methods**: API keys, environment variables, file-based tokens
- **📁 File Management**: Upload and manage files with automatic validation
- **💬 Chat Operations**: Create chats, send messages, stream responses
- **🤖 Agent Integration**: Work with specialized AI agents
- **🔄 Automatic Retry**: Exponential backoff with jitter
- **⚡ Smart Caching**: Reduce API calls with intelligent caching
- **📊 Rate Limiting**: Built-in rate limiting to respect API limits
- **🔍 Rich Validation**: Input validation and sanitization
- **🧩 Framework Integration**: Ready-to-use LangChain and CrewAI integrations
- **📈 Observability**: Structured logging and OpenTelemetry support

## 🚀 Quick Start

### Installation

```bash
# Basic installation
pip install fusion-client

# With LangChain integration
pip install fusion-client[langchain]

# With CrewAI integration  
pip install fusion-client[crewai]

# With all integrations
pip install fusion-client[all]
```

### Basic Usage

```python
import asyncio
from fusion_client import FusionClient

async def main():
    # Initialize client
    client = FusionClient(api_key="your-api-key")
    
    # List available agents
    agents = await client.list_agents()
    print(f"Available agents: {len(agents)}")
    
    # Create a chat with an agent
    chat = await client.create_chat(
        agent_id=str(agents[0].id),
        initial_message="Hello! How can you help me today?"
    )
    
    print(f"Agent response: {chat.last_message.message}")
    
    # Continue the conversation
    response = await client.send_message(
        agent_id=str(agents[0].id),
        chat_id=str(chat.chat.id),
        message="Tell me more about your capabilities"
    )
    
    print(f"Follow-up response: {response.last_message.message}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Streaming Responses

```python
async def streaming_example():
    client = FusionClient(api_key="your-api-key")
    
    # Stream response tokens in real-time
    stream = await client.send_message(
        agent_id="agent-id",
        message="Write a story about AI",
        stream=True
    )
    
    print("Story: ", end="")
    async for token in stream:
        print(token, end="", flush=True)
    print()  # New line at the end
```

### File Upload

```python
async def file_example():
    client = FusionClient(api_key="your-api-key")
    
    # Upload a file
    file_response = await client.upload_file("document.pdf")
    print(f"Uploaded: {file_response.filename}")
    
    # Use file in conversation
    response = await client.send_message(
        agent_id="analysis-agent",
        message="Please analyze this document",
        files=[str(file_response.file_id)]
    )
    
    print(f"Analysis: {response.last_message.message}")
```

## 🔧 Configuration

### Environment Variables

```bash
# API Configuration
export FUSION_API_KEY="your-api-key"
export FUSION_BASE_URL="https://api.fusion.com/v1"  # Optional
export FUSION_TIMEOUT=30.0                          # Optional

# Performance Settings
export FUSION_CACHE_ENABLED=true                    # Optional
export FUSION_CACHE_TTL=300                         # Optional (seconds)
export FUSION_RATE_LIMIT_CALLS=100                  # Optional
export FUSION_RATE_LIMIT_WINDOW=60                  # Optional (seconds)

# Security Settings
export FUSION_MAX_MESSAGE_LENGTH=10000              # Optional
export FUSION_MAX_FILE_SIZE_MB=10                   # Optional
```

### Programmatic Configuration

```python
from fusion_client import FusionClient, FusionSettings

# Using settings object
settings = FusionSettings(
    fusion_api_key="your-api-key",
    fusion_timeout=60.0,
    cache_enabled=True,
    rate_limit_calls=50
)

client = FusionClient.from_settings(settings)
```

## 🧩 Framework Integrations

### LangChain Integration

```python
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from fusion_client.integrations.langchain import FusionChatModel

# Create Fusion LLM
llm = FusionChatModel(
    api_key="your-api-key",
    agent_id="general-agent",
    temperature=0.7
)

# Use in LangChain
memory = ConversationBufferMemory()
conversation = ConversationChain(llm=llm, memory=memory)

response = conversation.predict(input="Explain quantum computing")
print(response)
```

### CrewAI Integration

```python
from crewai import Crew, Task
from fusion_client.integrations.crewai import FusionAgent

# Create Fusion agents
researcher = FusionAgent(
    api_key="your-api-key",
    agent_id="research-agent",
    role="Researcher",
    goal="Gather comprehensive information"
)

writer = FusionAgent(
    api_key="your-api-key",
    agent_id="writer-agent", 
    role="Content Writer",
    goal="Create engaging content"
)

# Define tasks
research_task = Task(
    description="Research the latest trends in renewable energy",
    agent=researcher
)

writing_task = Task(
    description="Write an article based on the research",
    agent=writer,
    depends_on=[research_task]
)

# Execute crew
crew = Crew(agents=[researcher, writer], tasks=[research_task, writing_task])
result = crew.kickoff()
```

## 📚 Advanced Usage

### Custom Retry Configuration

```python
from fusion_client.utils import with_retry

@with_retry(max_attempts=5, backoff_factor=2.0)
async def robust_api_call():
    return await client.send_message(
        agent_id="agent-id",
        message="Important message"
    )
```

### Custom Caching

```python
from fusion_client.utils import FusionCache

# Initialize with custom cache
cache = FusionCache(ttl=600, max_size=2000)  # 10 minutes, 2000 items
client = FusionClient(api_key="your-api-key", cache=cache)

# Cache statistics
stats = cache.stats()
print(f"Cache hit ratio: {stats['hit_ratio']:.2%}")
```

### Error Handling

```python
from fusion_client import (
    FusionClient, 
    AuthenticationError, 
    RateLimitError,
    AgentNotFoundError
)

async def handle_errors():
    client = FusionClient(api_key="your-api-key")
    
    try:
        response = await client.send_message(
            agent_id="nonexistent-agent",
            message="Hello"
        )
    except AuthenticationError:
        print("Invalid API key")
    except AgentNotFoundError as e:
        print(f"Agent not found: {e.details['agent_id']}")
    except RateLimitError as e:
        print(f"Rate limited. Retry after {e.retry_after} seconds")
    except Exception as e:
        print(f"Unexpected error: {e}")
```

## 🔍 Observability

### Structured Logging

```python
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)

# Client will automatically log structured events
client = FusionClient(api_key="your-api-key", enable_tracing=True)
```

### OpenTelemetry Integration

```python
from fusion_client.integrations.opentelemetry import setup_tracing

# Setup distributed tracing
tracer = setup_tracing("my-fusion-app")

# All API calls will be automatically traced
client = FusionClient(api_key="your-api-key", enable_tracing=True)
```

## 📖 API Reference

### FusionClient

Main client class for interacting with the Fusion API.

#### Methods

- `list_agents() -> List[Agent]` - List available agents
- `create_chat(agent_id, initial_message=None, folder=None) -> ChatResponse` - Create new chat
- `get_chat(chat_id) -> ChatResponse` - Get existing chat
- `send_message(agent_id, message, chat_id=None, files=None, stream=False)` - Send message
- `upload_file(file_path, chat_id=None) -> FileUploadResponse` - Upload file

### Models

- `Agent` - Represents an AI agent
- `Chat` - Represents a chat conversation  
- `Message` - Represents a message in a chat
- `ChatResponse` - Complete chat response with messages
- `User` - Represents a user
- `FileUploadResponse` - File upload response

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

```bash
# Clone repository
git clone https://github.com/company/fusion-client.git
cd fusion-client

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check .
black --check .
mypy fusion_client/

# Run all quality checks
make check
```

### Running Tests

```bash
# Unit tests only
pytest tests/unit/

# Integration tests (requires API key)
export FUSION_API_KEY="your-test-api-key"
pytest tests/integration/

# All tests with coverage
pytest --cov=fusion_client --cov-report=html
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- [Documentation](https://fusion-client.readthedocs.io/)
- [PyPI Package](https://pypi.org/project/fusion-client/)
- [Source Code](https://github.com/company/fusion-client)
- [Issue Tracker](https://github.com/company/fusion-client/issues)
- [Changelog](https://github.com/company/fusion-client/blob/main/CHANGELOG.md)

## 🆘 Support

- 📧 Email: support@fusion.com
- 💬 Discord: [Fusion Community](https://discord.gg/fusion)
- 📖 Documentation: [docs.fusion.com](https://docs.fusion.com)
- 🐛 Issues: [GitHub Issues](https://github.com/company/fusion-client/issues) 