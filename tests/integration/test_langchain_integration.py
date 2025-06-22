"""Testes de integração com LangChain."""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch

try:
    from langchain.chains import ConversationChain
    from langchain.memory import ConversationBufferMemory
    from langchain.schema import BaseMessage, HumanMessage, AIMessage
    from langchain.callbacks import CallbackManager
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

from fusion_client.integrations.langchain import FusionChatModel, FusionLLM
from fusion_client.models import ChatResponse, Agent, Message, Chat, User
from tests.fixtures.test_data import TestData


pytestmark = pytest.mark.skipif(
    not LANGCHAIN_AVAILABLE, 
    reason="LangChain not available"
)


@pytest.fixture
def mock_fusion_client():
    """Mock FusionClient para testes."""
    client = MagicMock()
    client.send_message = AsyncMock()
    client.list_agents = AsyncMock()
    return client


@pytest.fixture
def fusion_chat_model(mock_fusion_client):
    """Fixture para FusionChatModel."""
    return FusionChatModel(
        fusion_client=mock_fusion_client,
        agent_id="test-agent-id",
        temperature=0.7,
        max_tokens=1000
    )


@pytest.fixture
def sample_chat_response():
    """Resposta de chat de exemplo."""
    return TestData.get_test_chat_response()


class TestFusionChatModel:
    """Testes para FusionChatModel."""
    
    def test_fusion_chat_model_initialization(self, mock_fusion_client):
        """Teste inicialização do FusionChatModel."""
        model = FusionChatModel(
            fusion_client=mock_fusion_client,
            agent_id="test-agent",
            temperature=0.5,
            max_tokens=2000,
            streaming=True
        )
        
        assert model.fusion_client == mock_fusion_client
        assert model.agent_id == "test-agent"
        assert model.temperature == 0.5
        assert model.max_tokens == 2000
        assert model.streaming is True
    
    def test_fusion_chat_model_default_values(self, mock_fusion_client):
        """Teste valores padrão do FusionChatModel."""
        model = FusionChatModel(
            fusion_client=mock_fusion_client,
            agent_id="test-agent"
        )
        
        assert model.temperature == 0.7
        assert model.max_tokens == 1000
        assert model.streaming is False
    
    @pytest.mark.asyncio
    async def test_agenerate_single_message(self, fusion_chat_model, sample_chat_response):
        """Teste geração de resposta única."""
        # Configurar mock
        fusion_chat_model.fusion_client.send_message.return_value = sample_chat_response
        
        # Preparar mensagens
        messages = [HumanMessage(content="Hello, how are you?")]
        
        # Executar geração
        result = await fusion_chat_model._agenerate(messages)
        
        # Verificações
        assert len(result.generations) == 1
        assert len(result.generations[0]) == 1
        
        generation = result.generations[0][0]
        assert isinstance(generation.message, AIMessage)
        assert generation.message.content == sample_chat_response.last_message.message
        
        # Verificar chamada para fusion client
        fusion_chat_model.fusion_client.send_message.assert_called_once_with(
            agent_id="test-agent-id",
            message="Hello, how are you?",
            chat_id=None,
            files=None,
            stream=False
        )
    
    @pytest.mark.asyncio
    async def test_agenerate_with_chat_history(self, fusion_chat_model, sample_chat_response):
        """Teste geração com histórico de chat."""
        # Configurar mock
        fusion_chat_model.fusion_client.send_message.return_value = sample_chat_response
        
        # Preparar mensagens com histórico
        messages = [
            HumanMessage(content="What is Python?"),
            AIMessage(content="Python is a programming language."),
            HumanMessage(content="Tell me more about it.")
        ]
        
        # Executar geração
        result = await fusion_chat_model._agenerate(messages)
        
        # Verificações
        assert len(result.generations) == 1
        generation = result.generations[0][0]
        assert isinstance(generation.message, AIMessage)
        
        # Verificar que apenas a última mensagem foi enviada
        fusion_chat_model.fusion_client.send_message.assert_called_once_with(
            agent_id="test-agent-id",
            message="Tell me more about it.",
            chat_id=None,
            files=None,
            stream=False
        )
    
    @pytest.mark.asyncio
    async def test_agenerate_with_streaming(self, mock_fusion_client, sample_chat_response):
        """Teste geração com streaming."""
        # Criar modelo com streaming
        model = FusionChatModel(
            fusion_client=mock_fusion_client,
            agent_id="test-agent",
            streaming=True
        )
        
        # Mock stream
        async def mock_stream():
            tokens = ["Hello", " there", "!"]
            for token in tokens:
                yield token
        
        mock_fusion_client.send_message.return_value = mock_stream()
        
        # Preparar mensagens
        messages = [HumanMessage(content="Say hello")]
        
        # Executar geração
        result = await model._agenerate(messages)
        
        # Verificações
        assert len(result.generations) == 1
        generation = result.generations[0][0]
        assert isinstance(generation.message, AIMessage)
        assert generation.message.content == "Hello there!"
        
        # Verificar chamada com streaming
        mock_fusion_client.send_message.assert_called_once_with(
            agent_id="test-agent",
            message="Say hello",
            chat_id=None,
            files=None,
            stream=True
        )
    
    def test_llm_type_property(self, fusion_chat_model):
        """Teste propriedade _llm_type."""
        assert fusion_chat_model._llm_type == "fusion_chat"
    
    def test_identifying_params_property(self, fusion_chat_model):
        """Teste propriedade _identifying_params."""
        params = fusion_chat_model._identifying_params
        
        assert "agent_id" in params
        assert "temperature" in params
        assert "max_tokens" in params
        assert params["agent_id"] == "test-agent-id"
        assert params["temperature"] == 0.7
        assert params["max_tokens"] == 1000


class TestFusionLangChainIntegration:
    """Testes de integração com chains do LangChain."""
    
    @pytest.mark.asyncio
    async def test_conversation_chain_integration(self, mock_fusion_client):
        """Teste integração com ConversationChain."""
        # Preparar respostas mock
        responses = [
            TestData.get_test_chat_response(
                chat=TestData.get_test_chat(message="Hello! How can I help you?"),
                messages=[
                    Message(
                        id="msg-1",
                        chat_id=TestData.CHAT_ID,
                        message="Hi there",
                        message_type="user",
                        created_at="2024-01-01T00:00:00Z",
                        files=[]
                    ),
                    Message(
                        id="msg-2", 
                        chat_id=TestData.CHAT_ID,
                        message="Hello! How can I help you today?",
                        message_type="agent",
                        created_at="2024-01-01T00:00:01Z",
                        files=[]
                    )
                ]
            ),
            TestData.get_test_chat_response(
                chat=TestData.get_test_chat(message="I can help you with Python programming."),
                messages=[
                    Message(
                        id="msg-3",
                        chat_id=TestData.CHAT_ID,
                        message="Can you help me with Python?",
                        message_type="user",
                        created_at="2024-01-01T00:00:02Z",
                        files=[]
                    ),
                    Message(
                        id="msg-4",
                        chat_id=TestData.CHAT_ID,
                        message="I can help you with Python programming. What would you like to know?",
                        message_type="agent",
                        created_at="2024-01-01T00:00:03Z",
                        files=[]
                    )
                ]
            )
        ]
        
        mock_fusion_client.send_message.side_effect = responses
        
        # Criar modelo e chain
        llm = FusionChatModel(
            fusion_client=mock_fusion_client,
            agent_id="code-helper"
        )
        
        memory = ConversationBufferMemory()
        chain = ConversationChain(
            llm=llm,
            memory=memory,
            verbose=True
        )
        
        # Primeira conversa
        response1 = await chain.apredict(input="Hi there")
        assert "Hello! How can I help you today?" in response1
        
        # Segunda conversa (com memória)
        response2 = await chain.apredict(input="Can you help me with Python?")
        assert "Python programming" in response2
        
        # Verificar que memória foi mantida
        assert len(memory.chat_memory.messages) == 4  # 2 pares de human/ai
    
    @pytest.mark.asyncio
    async def test_chain_with_callbacks(self, mock_fusion_client):
        """Teste chain com callbacks."""
        # Callback para capturar eventos
        events = []
        
        class TestCallback:
            def on_llm_start(self, serialized, prompts, **kwargs):
                events.append(("llm_start", prompts))
            
            def on_llm_end(self, response, **kwargs):
                events.append(("llm_end", response))
        
        callback = TestCallback()
        callback_manager = CallbackManager([callback])
        
        # Configurar mock
        mock_response = TestData.get_test_chat_response()
        mock_fusion_client.send_message.return_value = mock_response
        
        # Criar modelo com callbacks
        llm = FusionChatModel(
            fusion_client=mock_fusion_client,
            agent_id="test-agent",
            callback_manager=callback_manager
        )
        
        # Executar geração
        messages = [HumanMessage(content="Test message")]
        await llm._agenerate(messages)
        
        # Verificar que callbacks foram chamados
        assert len(events) == 2
        assert events[0][0] == "llm_start"
        assert events[1][0] == "llm_end"
    
    @pytest.mark.asyncio
    async def test_error_handling_in_chain(self, mock_fusion_client):
        """Teste tratamento de erros em chains."""
        from fusion_client.core.exceptions import AgentNotFoundError
        
        # Configurar mock para lançar exceção
        mock_fusion_client.send_message.side_effect = AgentNotFoundError("Agent not found")
        
        # Criar modelo
        llm = FusionChatModel(
            fusion_client=mock_fusion_client,
            agent_id="nonexistent-agent"
        )
        
        # Preparar mensagens
        messages = [HumanMessage(content="This should fail")]
        
        # Verificar que exceção é propagada
        with pytest.raises(AgentNotFoundError):
            await llm._agenerate(messages)


class TestFusionLLMWrapper:
    """Testes para wrapper LLM legacy (não-chat)."""
    
    @pytest.fixture
    def fusion_llm(self, mock_fusion_client):
        """Fixture para FusionLLM."""
        return FusionLLM(
            fusion_client=mock_fusion_client,
            agent_id="test-agent"
        )
    
    @pytest.mark.asyncio
    async def test_fusion_llm_call(self, fusion_llm, sample_chat_response):
        """Teste chamada básica do FusionLLM."""
        # Configurar mock
        fusion_llm.fusion_client.send_message.return_value = sample_chat_response
        
        # Executar chamada
        result = await fusion_llm._acall("What is AI?")
        
        # Verificações
        assert result == sample_chat_response.last_message.message
        
        # Verificar chamada
        fusion_llm.fusion_client.send_message.assert_called_once_with(
            agent_id="test-agent",
            message="What is AI?",
            chat_id=None,
            files=None,
            stream=False
        )
    
    def test_fusion_llm_llm_type(self, fusion_llm):
        """Teste propriedade _llm_type do FusionLLM."""
        assert fusion_llm._llm_type == "fusion_llm"
    
    @pytest.mark.asyncio
    async def test_fusion_llm_with_stop_sequences(self, fusion_llm, sample_chat_response):
        """Teste FusionLLM com sequências de parada."""
        # Resposta com sequência de parada
        response_with_stop = TestData.get_test_chat_response()
        response_with_stop.messages[-1].message = "This is a response.\n\nSTOP"
        
        fusion_llm.fusion_client.send_message.return_value = response_with_stop
        
        # Executar com stop sequences
        result = await fusion_llm._acall("Generate text", stop=["STOP"])
        
        # Verificar que texto foi cortado na sequência de parada
        assert "This is a response." in result
        assert "STOP" not in result


class TestFusionToolIntegration:
    """Testes para integração com tools do LangChain."""
    
    @pytest.mark.asyncio
    async def test_fusion_as_tool(self, mock_fusion_client):
        """Teste usando Fusion como ferramenta LangChain."""
        from langchain.tools import Tool
        
        # Criar função wrapper
        async def fusion_chat(query: str) -> str:
            response = await mock_fusion_client.send_message(
                agent_id="helper-agent",
                message=query
            )
            return response.last_message.message
        
        # Configurar mock
        mock_response = TestData.get_test_chat_response()
        mock_fusion_client.send_message.return_value = mock_response
        
        # Criar tool
        fusion_tool = Tool(
            name="FusionChat",
            description="Chat with Fusion AI agent",
            func=lambda q: asyncio.run(fusion_chat(q))
        )
        
        # Usar tool
        result = fusion_tool.func("What is machine learning?")
        
        assert result == mock_response.last_message.message
        mock_fusion_client.send_message.assert_called_once()


# Configuração para testes LangChain
@pytest.fixture(autouse=True)
def setup_langchain_tests():
    """Setup para testes LangChain."""
    if not LANGCHAIN_AVAILABLE:
        pytest.skip("LangChain integration tests require langchain package")
    
    # Configurar ambiente se necessário
    os.environ.setdefault("LANGCHAIN_TRACING", "false") 