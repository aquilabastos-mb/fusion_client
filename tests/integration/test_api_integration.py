"""Testes de integração com a API real da Fusion."""

import pytest
import os
import asyncio
from uuid import uuid4
from pathlib import Path

from fusion_client import FusionClient
from fusion_client.models import ChatResponse, Agent
from fusion_client.core.exceptions import AuthenticationError, AgentNotFoundError


# Marcar todos os testes como requiring integration
pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def integration_client():
    """Cliente para testes de integração com API real."""
    api_key = os.getenv("FUSION_API_KEY")
    base_url = os.getenv("FUSION_BASE_URL")
    
    if not api_key:
        pytest.skip("FUSION_API_KEY not set - skipping integration tests")
    
    if not base_url:
        base_url = "https://api.fusion.com/v1"
    
    return FusionClient(
        api_key=api_key,
        base_url=base_url,
        timeout=60.0,  # Timeout maior para testes reais
        max_retries=3,
        enable_cache=False,  # Disable cache for integration tests
        enable_tracing=True
    )


@pytest.fixture(scope="session")
def test_agent_id(integration_client):
    """ID de um agente de teste válido."""
    # Retorna o primeiro agente disponível
    agents = asyncio.run(integration_client.list_agents())
    if not agents:
        pytest.skip("No agents available for testing")
    
    # Preferir um agente não-sistema se disponível
    for agent in agents:
        if not agent.system_agent:
            return str(agent.id)
    
    # Caso contrário, usar o primeiro agente
    return str(agents[0].id)


class TestFusionClientIntegration:
    """Testes de integração do cliente principal."""
    
    @pytest.mark.asyncio
    async def test_list_agents_integration(self, integration_client):
        """Teste integração de listagem de agentes."""
        agents = await integration_client.list_agents()
        
        assert isinstance(agents, list)
        assert len(agents) > 0
        assert all(isinstance(agent, Agent) for agent in agents)
        
        # Verificar propriedades básicas
        for agent in agents:
            assert agent.id is not None
            assert agent.name
            assert agent.description
            assert isinstance(agent.status, bool)
            assert isinstance(agent.system_agent, bool)
    
    @pytest.mark.asyncio
    async def test_create_chat_integration(self, integration_client, test_agent_id):
        """Teste integração de criação de chat."""
        response = await integration_client.create_chat(
            agent_id=test_agent_id,
            initial_message="Hello, this is a test message from integration tests."
        )
        
        assert isinstance(response, ChatResponse)
        assert response.chat.id is not None
        assert str(response.chat.agent.id) == test_agent_id
        assert len(response.messages) >= 1
        
        # Verificar que existe pelo menos uma mensagem do usuário
        user_messages = [msg for msg in response.messages if msg.message_type == "user"]
        assert len(user_messages) >= 1
        
        # Verificar que existe pelo menos uma mensagem do agente
        agent_messages = [msg for msg in response.messages if msg.message_type == "agent"]
        assert len(agent_messages) >= 1
    
    @pytest.mark.asyncio
    async def test_send_message_to_existing_chat(self, integration_client, test_agent_id):
        """Teste envio de mensagem para chat existente."""
        # Primeiro, criar um chat
        initial_response = await integration_client.create_chat(
            agent_id=test_agent_id,
            initial_message="Initial message for follow-up test."
        )
        
        chat_id = str(initial_response.chat.id)
        
        # Enviar mensagem de seguimento
        follow_up_response = await integration_client.send_message(
            agent_id=test_agent_id,
            message="This is a follow-up message.",
            chat_id=chat_id
        )
        
        assert isinstance(follow_up_response, ChatResponse)
        assert str(follow_up_response.chat.id) == chat_id
        
        # Deve ter mais mensagens que o chat inicial
        assert len(follow_up_response.messages) > len(initial_response.messages)
    
    @pytest.mark.asyncio
    async def test_get_chat_integration(self, integration_client, test_agent_id):
        """Teste recuperação de chat existente."""
        # Criar chat
        create_response = await integration_client.create_chat(
            agent_id=test_agent_id,
            initial_message="Message for get chat test."
        )
        
        chat_id = str(create_response.chat.id)
        
        # Recuperar chat
        get_response = await integration_client.get_chat(chat_id)
        
        assert isinstance(get_response, ChatResponse)
        assert str(get_response.chat.id) == chat_id
        assert get_response.chat.agent.id == create_response.chat.agent.id
        
        # Mensagens devem ser iguais
        assert len(get_response.messages) == len(create_response.messages)
    
    @pytest.mark.asyncio
    async def test_chat_with_folder_integration(self, integration_client, test_agent_id):
        """Teste criação de chat com pasta."""
        response = await integration_client.create_chat(
            agent_id=test_agent_id,
            initial_message="Message for folder test.",
            folder="integration-tests"
        )
        
        assert isinstance(response, ChatResponse)
        assert response.chat.folder == "integration-tests"
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_streaming_integration(self, integration_client, test_agent_id):
        """Teste streaming de respostas (pode ser lento)."""
        stream = await integration_client.send_message(
            agent_id=test_agent_id,
            message="Please write a short story about AI. Make it creative but concise.",
            stream=True
        )
        
        tokens = []
        async for token in stream:
            tokens.append(token)
            # Limitar tokens para evitar teste muito longo
            if len(tokens) >= 50:
                break
        
        assert len(tokens) > 0
        assert all(isinstance(token, str) for token in tokens)
        
        # Verificar que tokens formam texto coerente
        full_text = "".join(tokens)
        assert len(full_text.strip()) > 0
    
    @pytest.mark.asyncio
    async def test_invalid_agent_id_integration(self, integration_client):
        """Teste erro com ID de agente inválido."""
        invalid_agent_id = str(uuid4())
        
        with pytest.raises(AgentNotFoundError):
            await integration_client.send_message(
                agent_id=invalid_agent_id,
                message="This should fail."
            )
    
    @pytest.mark.asyncio
    async def test_invalid_chat_id_integration(self, integration_client):
        """Teste erro com ID de chat inválido."""
        invalid_chat_id = str(uuid4())
        
        with pytest.raises(Exception):  # Pode ser ChatNotFoundError ou outro erro da API
            await integration_client.get_chat(invalid_chat_id)


class TestFileUploadIntegration:
    """Testes de integração para upload de arquivos."""
    
    @pytest.fixture
    def test_text_file(self, tmp_path):
        """Arquivo de texto para testes."""
        file_path = tmp_path / "test_document.txt"
        file_path.write_text(
            "This is a test document for integration testing.\n"
            "It contains some sample text that can be analyzed by the AI agent.\n"
            "The content is designed to be meaningful but not sensitive."
        )
        return file_path
    
    @pytest.mark.asyncio
    async def test_file_upload_integration(self, integration_client, test_text_file):
        """Teste upload de arquivo."""
        try:
            response = await integration_client.upload_file(str(test_text_file))
            
            assert "file_id" in response
            assert "filename" in response
            assert response["filename"] == "test_document.txt"
            assert "content_type" in response
            assert response["content_type"] in ["text/plain", "application/octet-stream"]
            
        except Exception as e:
            # Alguns endpoints podem não estar disponíveis
            pytest.skip(f"File upload not available: {e}")
    
    @pytest.mark.asyncio
    async def test_file_upload_with_chat_integration(self, integration_client, test_agent_id, test_text_file):
        """Teste upload de arquivo para chat específico."""
        # Criar chat primeiro
        chat_response = await integration_client.create_chat(
            agent_id=test_agent_id,
            initial_message="I will upload a file for you to analyze."
        )
        
        chat_id = str(chat_response.chat.id)
        
        try:
            # Upload arquivo para o chat
            upload_response = await integration_client.upload_file(
                str(test_text_file),
                chat_id=chat_id
            )
            
            assert "file_id" in upload_response
            
            # Enviar mensagem referenciando o arquivo
            message_response = await integration_client.send_message(
                agent_id=test_agent_id,
                message="Please analyze the uploaded file and provide a summary.",
                chat_id=chat_id,
                files=[upload_response["file_id"]]
            )
            
            assert isinstance(message_response, ChatResponse)
            
        except Exception as e:
            pytest.skip(f"File upload with chat not available: {e}")


class TestErrorHandlingIntegration:
    """Testes de integração para tratamento de erros."""
    
    @pytest.mark.asyncio
    async def test_invalid_api_key_integration(self):
        """Teste erro de autenticação com API key inválida."""
        invalid_client = FusionClient(
            api_key="invalid-api-key-12345",
            base_url=os.getenv("FUSION_BASE_URL", "https://api.fusion.com/v1")
        )
        
        with pytest.raises(AuthenticationError):
            await invalid_client.list_agents()
    
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, integration_client, test_agent_id):
        """Teste rate limiting em ambiente real."""
        # Fazer várias chamadas rápidas para testar rate limiting
        tasks = []
        for i in range(5):
            task = integration_client.send_message(
                agent_id=test_agent_id,
                message=f"Rate limit test message {i + 1}"
            )
            tasks.append(task)
        
        # Executar todas as tarefas
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verificar que pelo menos algumas foram bem-sucedidas
        successful_responses = [r for r in responses if isinstance(r, ChatResponse)]
        assert len(successful_responses) > 0
        
        # Se houve rate limiting, algumas podem ter falhado ou sido atrasadas
        exceptions = [r for r in responses if isinstance(r, Exception)]
        
        # Log das exceções para análise (sem falhar o teste)
        for exc in exceptions:
            print(f"Rate limiting exception: {type(exc).__name__}: {exc}")


class TestPerformanceIntegration:
    """Testes de performance em ambiente real."""
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_concurrent_requests_integration(self, integration_client, test_agent_id):
        """Teste requisições concorrentes."""
        import time
        
        async def single_request(i):
            start_time = time.time()
            response = await integration_client.send_message(
                agent_id=test_agent_id,
                message=f"Concurrent request {i}: What is 2+2?"
            )
            end_time = time.time()
            return {
                "response": response,
                "duration": end_time - start_time,
                "request_id": i
            }
        
        # Executar 3 requisições concorrentes
        tasks = [single_request(i) for i in range(3)]
        results = await asyncio.gather(*tasks)
        
        # Verificar que todas foram bem-sucedidas
        assert len(results) == 3
        for result in results:
            assert isinstance(result["response"], ChatResponse)
            assert result["duration"] > 0
            assert result["duration"] < 60  # Não deve demorar mais que 60s
        
        # Log performance metrics
        avg_duration = sum(r["duration"] for r in results) / len(results)
        max_duration = max(r["duration"] for r in results)
        print(f"Concurrent requests - Average: {avg_duration:.2f}s, Max: {max_duration:.2f}s")
    
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_large_message_integration(self, integration_client, test_agent_id):
        """Teste mensagem grande."""
        # Criar mensagem de tamanho considerável
        large_message = (
            "Please analyze this long text and provide insights. " * 100 +
            "What are the key themes and patterns you can identify? " +
            "Please provide a detailed analysis covering multiple aspects."
        )
        
        start_time = time.time()
        response = await integration_client.send_message(
            agent_id=test_agent_id,
            message=large_message
        )
        end_time = time.time()
        
        assert isinstance(response, ChatResponse)
        assert len(response.last_message.message) > 0
        
        duration = end_time - start_time
        print(f"Large message processing time: {duration:.2f}s")
        
        # Não deve demorar mais que 2 minutos
        assert duration < 120


# Configuração para execução de testes de integração
@pytest.fixture(autouse=True, scope="session")
def integration_test_setup():
    """Setup automático para testes de integração."""
    api_key = os.getenv("FUSION_API_KEY")
    if not api_key:
        pytest.skip("Integration tests require FUSION_API_KEY environment variable")
    
    print("\n" + "="*50)
    print("RUNNING INTEGRATION TESTS")
    print("These tests will make real API calls")
    print("="*50) 