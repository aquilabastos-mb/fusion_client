"""Testes unitários para o cliente principal FusionClient."""

import pytest
import asyncio
import httpx
import respx
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import json
import time

from fusion_client import FusionClient
from fusion_client.core.exceptions import (
    FusionError, AuthenticationError, RateLimitError,
    AgentNotFoundError, ChatNotFoundError, ValidationError
)
from fusion_client.models import ChatResponse, Agent
from tests.fixtures.test_data import TestData


class TestFusionClientInitialization:
    """Testes para inicialização do FusionClient."""
    
    def test_client_initialization_with_api_key(self):
        """Teste inicialização com API key."""
        client = FusionClient(api_key="test-key")
        
        assert client._api_key == "test-key"
        assert client._base_url == "https://api.fusion.com/v1"  # URL padrão
        assert client._timeout == 30.0
        assert client._max_retries == 3
    
    def test_client_initialization_custom_settings(self):
        """Teste inicialização com configurações customizadas."""
        client = FusionClient(
            api_key="test-key",
            base_url="https://custom.api.com",
            timeout=60.0,
            max_retries=5,
            enable_cache=True,
            enable_tracing=True
        )
        
        assert client._api_key == "test-key"
        assert client._base_url == "https://custom.api.com"
        assert client._timeout == 60.0
        assert client._max_retries == 5
        assert client._enable_cache is True
        assert client._enable_tracing is True
    
    def test_client_initialization_from_env(self):
        """Teste inicialização a partir de variáveis de ambiente."""
        with patch.dict('os.environ', {'FUSION_API_KEY': 'env-key'}):
            client = FusionClient()
            assert client._api_key == 'env-key'
    
    def test_client_initialization_missing_api_key(self):
        """Teste falha na inicialização sem API key."""
        with pytest.raises(ValueError, match="API key is required"):
            FusionClient()


class TestFusionClientSendMessage:
    """Testes para o método send_message."""
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_send_message_success(self, fusion_client, mock_api_responses):
        """Teste envio de mensagem com sucesso."""
        # Mock da resposta da API
        respx.post(f"{fusion_client._base_url}/chat").mock(
            return_value=httpx.Response(200, json=mock_api_responses["create_chat"])
        )
        
        response = await fusion_client.send_message(
            agent_id="550e8400-e29b-41d4-a716-446655440001",
            message="Hello, how are you?"
        )
        
        assert isinstance(response, ChatResponse)
        assert len(response.messages) == 2
        assert response.last_message.message_type == "agent"
        assert "assist" in response.last_message.message.lower()
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_send_message_with_chat_id(self, fusion_client, mock_api_responses):
        """Teste envio de mensagem para chat existente."""
        chat_id = "550e8400-e29b-41d4-a716-446655440000"
        
        respx.post(f"{fusion_client._base_url}/chat/{chat_id}/message").mock(
            return_value=httpx.Response(200, json=mock_api_responses["create_chat"])
        )
        
        response = await fusion_client.send_message(
            agent_id="550e8400-e29b-41d4-a716-446655440001",
            message="Follow up message",
            chat_id=chat_id
        )
        
        assert isinstance(response, ChatResponse)
        assert str(response.chat.id) == chat_id
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_send_message_with_files(self, fusion_client, mock_api_responses):
        """Teste envio de mensagem com arquivos."""
        respx.post(f"{fusion_client._base_url}/chat").mock(
            return_value=httpx.Response(200, json=mock_api_responses["create_chat"])
        )
        
        response = await fusion_client.send_message(
            agent_id="550e8400-e29b-41d4-a716-446655440001",
            message="Analyze this file",
            files=["file-12345"]
        )
        
        assert isinstance(response, ChatResponse)
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_send_message_streaming(self, fusion_client, streaming_response_data):
        """Teste envio de mensagem com streaming."""
        # Mock streaming response
        async def stream_response():
            for chunk in streaming_response_data:
                yield chunk.encode('utf-8')
        
        respx.post(f"{fusion_client._base_url}/chat").mock(
            return_value=httpx.Response(200, stream=stream_response())
        )
        
        stream = await fusion_client.send_message(
            agent_id="550e8400-e29b-41d4-a716-446655440001",
            message="Tell me a story",
            stream=True
        )
        
        tokens = []
        async for token in stream:
            tokens.append(token)
        
        assert len(tokens) > 0
        assert "Hello" in tokens[0]
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_send_message_authentication_error(self, fusion_client):
        """Teste erro de autenticação."""
        respx.post(f"{fusion_client._base_url}/chat").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )
        
        with pytest.raises(AuthenticationError):
            await fusion_client.send_message(
                agent_id="550e8400-e29b-41d4-a716-446655440001",
                message="Hello"
            )
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_send_message_agent_not_found(self, fusion_client):
        """Teste erro de agente não encontrado."""
        respx.post(f"{fusion_client._base_url}/chat").mock(
            return_value=httpx.Response(
                404, 
                json={"error": "Agent not found", "message": "The specified agent does not exist"}
            )
        )
        
        with pytest.raises(AgentNotFoundError):
            await fusion_client.send_message(
                agent_id="nonexistent-agent",
                message="Hello"
            )
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_send_message_rate_limit_error(self, fusion_client):
        """Teste erro de rate limit."""
        respx.post(f"{fusion_client._base_url}/chat").mock(
            return_value=httpx.Response(
                429,
                json={"error": "Rate limit exceeded", "retry_after": 60},
                headers={"Retry-After": "60"}
            )
        )
        
        with pytest.raises(RateLimitError) as exc_info:
            await fusion_client.send_message(
                agent_id="550e8400-e29b-41d4-a716-446655440001",
                message="Hello"
            )
        
        assert exc_info.value.retry_after == 60
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_send_message_validation_error(self, fusion_client):
        """Teste erro de validação."""
        respx.post(f"{fusion_client._base_url}/chat").mock(
            return_value=httpx.Response(
                422,
                json={"error": "Validation error", "message": "Message cannot be empty"}
            )
        )
        
        with pytest.raises(ValidationError):
            await fusion_client.send_message(
                agent_id="550e8400-e29b-41d4-a716-446655440001",
                message=""  # Mensagem vazia
            )
    
    @pytest.mark.asyncio
    async def test_send_message_with_retry(self, fusion_client):
        """Teste retry automático em caso de erro temporário."""
        with patch.object(fusion_client, '_make_request') as mock_request:
            # Primeira chamada falha, segunda sucede
            mock_request.side_effect = [
                httpx.TimeoutException("Timeout"),
                TestData.get_test_chat_response()
            ]
            
            response = await fusion_client.send_message(
                agent_id="550e8400-e29b-41d4-a716-446655440001",
                message="Test retry"
            )
            
            assert isinstance(response, ChatResponse)
            assert mock_request.call_count == 2


class TestFusionClientCreateChat:
    """Testes para o método create_chat."""
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_chat_success(self, fusion_client, mock_api_responses):
        """Teste criação de chat com sucesso."""
        respx.post(f"{fusion_client._base_url}/chat").mock(
            return_value=httpx.Response(200, json=mock_api_responses["create_chat"])
        )
        
        response = await fusion_client.create_chat(
            agent_id="550e8400-e29b-41d4-a716-446655440001",
            initial_message="Hello, I need help"
        )
        
        assert isinstance(response, ChatResponse)
        assert len(response.messages) >= 1
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_chat_with_folder(self, fusion_client, mock_api_responses):
        """Teste criação de chat com pasta."""
        respx.post(f"{fusion_client._base_url}/chat").mock(
            return_value=httpx.Response(200, json=mock_api_responses["create_chat"])
        )
        
        response = await fusion_client.create_chat(
            agent_id="550e8400-e29b-41d4-a716-446655440001",
            initial_message="Work related question",
            folder="work"
        )
        
        assert isinstance(response, ChatResponse)
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_chat_no_initial_message(self, fusion_client, mock_api_responses):
        """Teste criação de chat sem mensagem inicial."""
        respx.post(f"{fusion_client._base_url}/chat").mock(
            return_value=httpx.Response(200, json=mock_api_responses["create_chat"])
        )
        
        response = await fusion_client.create_chat(
            agent_id="550e8400-e29b-41d4-a716-446655440001"
        )
        
        assert isinstance(response, ChatResponse)


class TestFusionClientGetChat:
    """Testes para o método get_chat."""
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_chat_success(self, fusion_client, mock_api_responses):
        """Teste recuperação de chat com sucesso."""
        chat_id = "550e8400-e29b-41d4-a716-446655440000"
        
        respx.get(f"{fusion_client._base_url}/chat/{chat_id}").mock(
            return_value=httpx.Response(200, json=mock_api_responses["create_chat"])
        )
        
        response = await fusion_client.get_chat(chat_id)
        
        assert isinstance(response, ChatResponse)
        assert str(response.chat.id) == chat_id
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_chat_not_found(self, fusion_client):
        """Teste chat não encontrado."""
        chat_id = "nonexistent-chat"
        
        respx.get(f"{fusion_client._base_url}/chat/{chat_id}").mock(
            return_value=httpx.Response(404, json={"error": "Chat not found"})
        )
        
        with pytest.raises(ChatNotFoundError):
            await fusion_client.get_chat(chat_id)


class TestFusionClientListAgents:
    """Testes para o método list_agents."""
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_agents_success(self, fusion_client, mock_api_responses):
        """Teste listagem de agentes com sucesso."""
        respx.get(f"{fusion_client._base_url}/agents").mock(
            return_value=httpx.Response(200, json=mock_api_responses["agents_list"])
        )
        
        agents = await fusion_client.list_agents()
        
        assert isinstance(agents, list)
        assert len(agents) == 2
        assert all(isinstance(agent, Agent) for agent in agents)
        assert agents[0].name == "General Assistant"
        assert agents[1].name == "Code Helper"
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_agents_empty(self, fusion_client):
        """Teste listagem de agentes vazia."""
        respx.get(f"{fusion_client._base_url}/agents").mock(
            return_value=httpx.Response(200, json=[])
        )
        
        agents = await fusion_client.list_agents()
        
        assert isinstance(agents, list)
        assert len(agents) == 0


class TestFusionClientUploadFile:
    """Testes para o método upload_file."""
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_upload_file_success(self, fusion_client, mock_api_responses, sample_pdf_file):
        """Teste upload de arquivo com sucesso."""
        respx.post(f"{fusion_client._base_url}/files").mock(
            return_value=httpx.Response(200, json=mock_api_responses["file_upload"])
        )
        
        response = await fusion_client.upload_file(str(sample_pdf_file))
        
        assert response["file_id"] == "file-12345"
        assert response["filename"] == "test-document.pdf"
    
    @respx.mock
    @pytest.mark.asyncio
    async def test_upload_file_with_chat_id(self, fusion_client, mock_api_responses, sample_pdf_file):
        """Teste upload de arquivo para chat específico."""
        chat_id = "550e8400-e29b-41d4-a716-446655440000"
        
        respx.post(f"{fusion_client._base_url}/chat/{chat_id}/files").mock(
            return_value=httpx.Response(200, json=mock_api_responses["file_upload"])
        )
        
        response = await fusion_client.upload_file(
            str(sample_pdf_file),
            chat_id=chat_id
        )
        
        assert response["file_id"] == "file-12345"
    
    @pytest.mark.asyncio
    async def test_upload_file_not_found(self, fusion_client):
        """Teste upload de arquivo não encontrado."""
        with pytest.raises(FileNotFoundError):
            await fusion_client.upload_file("nonexistent-file.pdf")


class TestFusionClientRateLimiting:
    """Testes para rate limiting."""
    
    @pytest.mark.asyncio
    async def test_rate_limiting_applied(self, fusion_client):
        """Teste aplicação de rate limiting."""
        with patch.object(fusion_client, '_rate_limiter') as mock_limiter:
            mock_limiter.acquire = AsyncMock()
            
            with patch.object(fusion_client, '_make_request') as mock_request:
                mock_request.return_value = TestData.get_test_chat_response()
                
                await fusion_client.send_message(
                    agent_id="test-agent",
                    message="Test message"
                )
                
                mock_limiter.acquire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rate_limiting_delay(self, fusion_client):
        """Teste delay por rate limiting."""
        with patch.object(fusion_client, '_rate_limiter') as mock_limiter:
            # Simular delay de 1 segundo
            async def delayed_acquire():
                await asyncio.sleep(0.1)  # Delay menor para teste
            
            mock_limiter.acquire = delayed_acquire
            
            with patch.object(fusion_client, '_make_request') as mock_request:
                mock_request.return_value = TestData.get_test_chat_response()
                
                start_time = time.time()
                await fusion_client.send_message(
                    agent_id="test-agent",
                    message="Test message"
                )
                elapsed = time.time() - start_time
                
                assert elapsed >= 0.1  # Pelo menos o delay esperado


class TestFusionClientCaching:
    """Testes para sistema de cache."""
    
    @pytest.mark.asyncio
    async def test_cache_hit(self, fusion_client):
        """Teste cache hit."""
        # Habilitar cache
        fusion_client._enable_cache = True
        
        with patch.object(fusion_client, '_cache') as mock_cache:
            mock_cache.get.return_value = TestData.get_test_chat_response()
            
            response = await fusion_client.get_chat("test-chat-id")
            
            assert isinstance(response, ChatResponse)
            mock_cache.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cache_miss_and_set(self, fusion_client):
        """Teste cache miss e subsequente set."""
        fusion_client._enable_cache = True
        
        with patch.object(fusion_client, '_cache') as mock_cache:
            mock_cache.get.return_value = None  # Cache miss
            
            with patch.object(fusion_client, '_make_request') as mock_request:
                mock_request.return_value = TestData.get_test_chat_response()
                
                response = await fusion_client.get_chat("test-chat-id")
                
                assert isinstance(response, ChatResponse)
                mock_cache.get.assert_called_once()
                mock_cache.set.assert_called_once()


class TestFusionClientErrorHandling:
    """Testes para tratamento de erros."""
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, fusion_client):
        """Teste tratamento de erro de rede."""
        with patch.object(fusion_client, '_http_client') as mock_client:
            mock_client.post.side_effect = httpx.ConnectError("Connection failed")
            
            with pytest.raises(FusionError, match="Connection failed"):
                await fusion_client.send_message(
                    agent_id="test-agent",
                    message="Test message"
                )
    
    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, fusion_client):
        """Teste tratamento de timeout."""
        with patch.object(fusion_client, '_http_client') as mock_client:
            mock_client.post.side_effect = httpx.TimeoutException("Request timeout")
            
            with pytest.raises(FusionError, match="Request timeout"):
                await fusion_client.send_message(
                    agent_id="test-agent",
                    message="Test message"
                )
    
    @pytest.mark.asyncio
    async def test_invalid_json_response(self, fusion_client):
        """Teste resposta JSON inválida."""
        with patch.object(fusion_client, '_http_client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "Invalid JSON"
            mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
            mock_client.post.return_value = mock_response
            
            with pytest.raises(FusionError, match="Invalid response format"):
                await fusion_client.send_message(
                    agent_id="test-agent",
                    message="Test message"
                ) 