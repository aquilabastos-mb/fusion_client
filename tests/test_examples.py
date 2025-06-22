"""Testes para validar exemplos da documentação."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from fusion_client import FusionClient
from fusion_client.models import ChatResponse, Agent
from tests.fixtures.test_data import TestData


class TestBasicUsageExamples:
    """Testes para exemplos de uso básico."""
    
    @pytest.mark.asyncio
    async def test_basic_usage_example(self):
        """Teste exemplo de uso básico da documentação."""
        # Mock do cliente
        with patch('fusion_client.FusionClient') as MockClient:
            mock_client = MockClient.return_value
            mock_client.list_agents = AsyncMock()
            mock_client.create_chat = AsyncMock()
            mock_client.send_message = AsyncMock()
            
            # Mock das respostas
            mock_agents = TestData.get_multiple_agents(count=3)
            mock_agents[0].name = "News Agent"
            mock_client.list_agents.return_value = mock_agents
            
            chat_response = TestData.get_test_chat_response()
            chat_response.last_message.message = "Here are today's main news..."
            mock_client.create_chat.return_value = chat_response
            mock_client.send_message.return_value = chat_response
            
            # Código do exemplo
            client = FusionClient(
                api_key="your-api-key",
                enable_cache=True,
                max_retries=3
            )
            
            # Listar agentes disponíveis
            agents = await client.list_agents()
            news_agent = next(a for a in agents if "news" in a.name.lower())
            
            # Criar nova conversa
            chat = await client.create_chat(
                agent_id=str(news_agent.id),
                initial_message="Quais são as principais notícias hoje?"
            )
            
            print(f"Chat criado: {chat.chat.id}")
            print(f"Resposta: {chat.last_message.message}")
            
            # Continuar conversa
            response = await client.send_message(
                agent_id=str(news_agent.id),
                message="Pode resumir a primeira notícia?",
                chat_id=str(chat.chat.id)
            )
            
            print(f"Nova resposta: {response.last_message.message}")
            
            # Verificações
            assert isinstance(agents, list)
            assert len(agents) > 0
            assert isinstance(chat, ChatResponse)
            assert isinstance(response, ChatResponse)
            assert chat.chat.id == response.chat.id
    
    @pytest.mark.asyncio
    async def test_streaming_example(self):
        """Teste exemplo de streaming."""
        with patch('fusion_client.FusionClient') as MockClient:
            mock_client = MockClient.return_value
            
            # Mock stream generator
            async def mock_stream():
                tokens = ["Este", " é", " um", " exemplo", " de", " streaming", "."]
                for token in tokens:
                    yield token
            
            mock_client.send_message = AsyncMock(return_value=mock_stream())
            
            # Código do exemplo
            client = FusionClient(api_key="your-api-key")
            
            stream = await client.send_message(
                agent_id="agent-id",
                message="Escreva um artigo sobre IA",
                stream=True
            )
            
            print("Resposta em tempo real:")
            full_response = ""
            async for token in stream:
                print(token, end="", flush=True)
                full_response += token
            print()  # Nova linha no final
            
            # Verificações
            assert len(full_response) > 0
            assert "exemplo" in full_response
            assert "streaming" in full_response
    
    @pytest.mark.asyncio
    async def test_file_upload_example(self, tmp_path):
        """Teste exemplo de upload de arquivos."""
        with patch('fusion_client.FusionClient') as MockClient:
            mock_client = MockClient.return_value
            mock_client.upload_file = AsyncMock()
            mock_client.send_message = AsyncMock()
            
            # Criar arquivo de teste
            test_file = tmp_path / "document.pdf"
            test_file.write_bytes(b"PDF content")
            
            # Mock das respostas
            mock_client.upload_file.return_value = {"file_id": "file-123"}
            
            analysis_response = TestData.get_test_chat_response()
            analysis_response.last_message.message = "Análise do documento: O arquivo contém..."
            mock_client.send_message.return_value = analysis_response
            
            # Código do exemplo
            client = FusionClient(api_key="your-api-key")
            
            # Upload de arquivo
            file_response = await client.upload_file(str(test_file))
            
            # Usar arquivo em conversa
            response = await client.send_message(
                agent_id="analysis-agent",
                message="Analise este documento",
                files=[file_response["file_id"]]
            )
            
            print(f"Análise: {response.last_message.message}")
            
            # Verificações
            assert "file_id" in file_response
            assert file_response["file_id"] == "file-123"
            assert isinstance(response, ChatResponse)
            assert "análise" in response.last_message.message.lower()


class TestLangChainExamples:
    """Testes para exemplos de integração com LangChain."""
    
    @pytest.mark.skipif(
        not pytest.importorskip("langchain", reason="LangChain not available"),
        reason="LangChain integration examples require langchain"
    )
    @pytest.mark.asyncio
    async def test_langchain_integration_example(self):
        """Teste exemplo de integração com LangChain."""
        try:
            from langchain.chains import ConversationChain
            from langchain.memory import ConversationBufferMemory
        except ImportError:
            pytest.skip("LangChain not available")
        
        with patch('fusion_client.integrations.langchain.FusionChatModel') as MockModel:
            # Mock do modelo
            mock_model = MockModel.return_value
            mock_model.predict = AsyncMock(return_value="Machine learning é uma subárea da inteligência artificial...")
            
            # Mock da conversa
            mock_conversation = MagicMock()
            mock_conversation.predict = AsyncMock(return_value="Machine learning é uma subárea da inteligência artificial...")
            
            with patch('langchain.chains.ConversationChain', return_value=mock_conversation):
                # Código do exemplo (simulado)
                from fusion_client.integrations.langchain import FusionChatModel
                
                # Configurar modelo
                llm = FusionChatModel(
                    api_key="your-api-key",
                    agent_id="general-agent",
                    temperature=0.7,
                    max_tokens=1000
                )
                
                # Criar chain com memória
                memory = ConversationBufferMemory()
                conversation = ConversationChain(
                    llm=llm,
                    memory=memory,
                    verbose=True
                )
                
                # Usar chain
                response = await conversation.apredict(
                    input="Explique como funciona machine learning"
                )
                print(response)
                
                # Verificações
                assert isinstance(response, str)
                assert "machine learning" in response.lower()


class TestCrewAIExamples:
    """Testes para exemplos de integração com CrewAI."""
    
    @pytest.mark.skipif(
        not pytest.importorskip("crewai", reason="CrewAI not available"),
        reason="CrewAI integration examples require crewai"  
    )
    @pytest.mark.asyncio
    async def test_crewai_integration_example(self):
        """Teste exemplo de integração com CrewAI."""
        try:
            from crewai import Crew, Task
        except ImportError:
            pytest.skip("CrewAI not available")
        
        with patch('fusion_client.integrations.crewai.FusionAgent') as MockAgent:
            # Mock dos agentes
            mock_researcher = MockAgent.return_value
            mock_writer = MockAgent.return_value
            
            # Mock do crew
            mock_crew = MagicMock()
            mock_crew.kickoff = AsyncMock(return_value="Research completed and article written successfully")
            
            with patch('crewai.Crew', return_value=mock_crew):
                # Código do exemplo (simulado)
                from fusion_client.integrations.crewai import FusionAgent
                
                # Criar agentes Fusion como CrewAI agents
                researcher = FusionAgent(
                    api_key="your-api-key",
                    agent_id="research-agent",
                    role="Researcher",
                    goal="Gather comprehensive information on given topics",
                    backstory="Expert researcher with access to latest information"
                )
                
                writer = FusionAgent(
                    api_key="your-api-key", 
                    agent_id="writer-agent",
                    role="Content Writer",
                    goal="Create engaging and informative content",
                    backstory="Professional writer with expertise in technical topics"
                )
                
                # Definir tarefas
                research_task = Task(
                    description="Research the latest trends in AI for 2024",
                    agent=researcher
                )
                
                writing_task = Task(
                    description="Write a comprehensive article based on the research",
                    agent=writer,
                    depends_on=[research_task]
                )
                
                # Executar crew
                crew = Crew(
                    agents=[researcher, writer],
                    tasks=[research_task, writing_task],
                    verbose=True
                )
                
                result = await crew.akickoff()
                print(result)
                
                # Verificações
                assert isinstance(result, str)
                assert "successfully" in result.lower()


class TestErrorHandlingExamples:
    """Testes para exemplos de tratamento de erros."""
    
    @pytest.mark.asyncio
    async def test_error_handling_example(self):
        """Teste exemplo de tratamento de erros."""
        from fusion_client.core.exceptions import (
            AuthenticationError, RateLimitError, AgentNotFoundError
        )
        
        with patch('fusion_client.FusionClient') as MockClient:
            mock_client = MockClient.return_value
            
            # Teste erro de autenticação
            mock_client.send_message = AsyncMock(side_effect=AuthenticationError("Invalid API key"))
            
            client = FusionClient(api_key="invalid-key")
            
            try:
                await client.send_message(
                    agent_id="test-agent",
                    message="Hello"
                )
            except AuthenticationError as e:
                print(f"Authentication error: {e}")
                assert "Invalid API key" in str(e)
            
            # Teste erro de rate limit
            mock_client.send_message = AsyncMock(side_effect=RateLimitError(retry_after=60))
            
            try:
                await client.send_message(
                    agent_id="test-agent",
                    message="Hello"
                )
            except RateLimitError as e:
                print(f"Rate limit error: {e}")
                assert e.retry_after == 60
            
            # Teste agente não encontrado
            mock_client.send_message = AsyncMock(side_effect=AgentNotFoundError("Agent not found"))
            
            try:
                await client.send_message(
                    agent_id="nonexistent-agent",
                    message="Hello"
                )
            except AgentNotFoundError as e:
                print(f"Agent not found: {e}")
                assert "Agent not found" in str(e)


class TestPerformanceExamples:
    """Testes para exemplos de performance e otimização."""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_example(self):
        """Teste exemplo de requisições concorrentes."""
        with patch('fusion_client.FusionClient') as MockClient:
            mock_client = MockClient.return_value
            
            # Mock das respostas
            responses = [
                TestData.get_test_chat_response(),
                TestData.get_test_chat_response(),
                TestData.get_test_chat_response()
            ]
            
            mock_client.send_message = AsyncMock(side_effect=responses)
            
            # Código do exemplo
            client = FusionClient(api_key="your-api-key")
            
            # Criar múltiplas tarefas
            tasks = []
            for i in range(3):
                task = client.send_message(
                    agent_id="test-agent",
                    message=f"Question {i + 1}: What is AI?"
                )
                tasks.append(task)
            
            # Executar concorrentemente
            results = await asyncio.gather(*tasks)
            
            # Verificações
            assert len(results) == 3
            assert all(isinstance(r, ChatResponse) for r in results)
            assert mock_client.send_message.call_count == 3
    
    @pytest.mark.asyncio
    async def test_caching_example(self):
        """Teste exemplo de cache."""
        with patch('fusion_client.FusionClient') as MockClient:
            mock_client = MockClient.return_value
            mock_client.list_agents = AsyncMock()
            
            # Mock da resposta
            agents = TestData.get_multiple_agents(count=3)
            mock_client.list_agents.return_value = agents
            
            # Código do exemplo
            client = FusionClient(
                api_key="your-api-key",
                enable_cache=True
            )
            
            # Primeira chamada - deve fazer requisição
            agents1 = await client.list_agents()
            
            # Segunda chamada - deve usar cache (mas no mock sempre chama)
            agents2 = await client.list_agents()
            
            # Verificações
            assert len(agents1) == 3
            assert len(agents2) == 3
            assert agents1[0].id == agents2[0].id  # Mesmos agentes 