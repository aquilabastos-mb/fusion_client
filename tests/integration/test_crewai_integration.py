"""Testes de integração com CrewAI."""

import pytest
import os
from unittest.mock import AsyncMock, MagicMock

try:
    from crewai import Agent, Task, Crew
    from crewai.agent import Agent as CrewAgent
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False

from fusion_client.integrations.crewai import FusionAgent
from fusion_client.models import ChatResponse
from tests.fixtures.test_data import TestData


pytestmark = pytest.mark.skipif(
    not CREWAI_AVAILABLE,
    reason="CrewAI not available"
)


@pytest.fixture
def mock_fusion_client():
    """Mock FusionClient para testes."""
    client = MagicMock()
    client.send_message = AsyncMock()
    client.create_chat = AsyncMock()
    client.list_agents = AsyncMock()
    return client


@pytest.fixture
def fusion_agent(mock_fusion_client):
    """Fixture para FusionAgent."""
    return FusionAgent(
        fusion_client=mock_fusion_client,
        fusion_agent_id="research-agent",
        role="Senior Research Analyst",
        goal="Conduct comprehensive research on given topics",
        backstory="Expert researcher with 10+ years of experience in data analysis and market research",
        verbose=True,
        allow_delegation=False
    )


@pytest.fixture
def sample_responses():
    """Respostas de exemplo para diferentes cenários."""
    return {
        "research": TestData.get_test_chat_response(
            chat=TestData.get_test_chat(
                message="Based on my research, artificial intelligence is rapidly evolving..."
            ),
            messages=TestData.get_test_messages(count=2)
        ),
        "analysis": TestData.get_test_chat_response(
            chat=TestData.get_test_chat(
                message="After analyzing the data, I found three key trends..."
            ),
            messages=TestData.get_test_messages(count=2)
        ),
        "summary": TestData.get_test_chat_response(
            chat=TestData.get_test_chat(
                message="In summary, the research indicates that..."
            ),
            messages=TestData.get_test_messages(count=2)
        )
    }


class TestFusionAgent:
    """Testes para FusionAgent."""
    
    def test_fusion_agent_initialization(self, mock_fusion_client):
        """Teste inicialização do FusionAgent."""
        agent = FusionAgent(
            fusion_client=mock_fusion_client,
            fusion_agent_id="test-agent",
            role="Test Agent",
            goal="Test goals",
            backstory="Test backstory",
            verbose=True,
            allow_delegation=False,
            max_iter=5,
            memory=True
        )
        
        assert agent.fusion_client == mock_fusion_client
        assert agent.fusion_agent_id == "test-agent"
        assert agent.role == "Test Agent"
        assert agent.goal == "Test goals"
        assert agent.backstory == "Test backstory"
        assert agent.verbose is True
        assert agent.allow_delegation is False
        assert agent.max_iter == 5
        assert agent.memory is True
    
    def test_fusion_agent_inheritance(self, fusion_agent):
        """Teste que FusionAgent herda de CrewAI Agent."""
        assert isinstance(fusion_agent, CrewAgent)
        assert hasattr(fusion_agent, 'role')
        assert hasattr(fusion_agent, 'goal')
        assert hasattr(fusion_agent, 'backstory')
    
    @pytest.mark.asyncio
    async def test_fusion_agent_execute_task(self, fusion_agent, sample_responses):
        """Teste execução de tarefa por FusionAgent."""
        # Configurar mock
        fusion_agent.fusion_client.send_message.return_value = sample_responses["research"]
        
        # Criar tarefa
        task_description = "Research the latest trends in artificial intelligence"
        
        # Executar tarefa (simulando o comportamento do CrewAI)
        response = await fusion_agent._execute_fusion_task(task_description)
        
        # Verificações
        assert isinstance(response, str)
        assert "artificial intelligence" in response.lower()
        
        # Verificar chamada para Fusion
        fusion_agent.fusion_client.send_message.assert_called_once()
        call_args = fusion_agent.fusion_client.send_message.call_args
        assert task_description in call_args[1]["message"]
    
    @pytest.mark.asyncio
    async def test_fusion_agent_with_context(self, fusion_agent, sample_responses):
        """Teste FusionAgent com contexto de tarefas anteriores."""
        # Configurar respostas sequenciais
        fusion_agent.fusion_client.send_message.side_effect = [
            sample_responses["research"],
            sample_responses["analysis"]
        ]
        
        # Primeira tarefa
        task1_result = await fusion_agent._execute_fusion_task(
            "Research AI market trends"
        )
        
        # Segunda tarefa com contexto
        task2_result = await fusion_agent._execute_fusion_task(
            "Analyze the research findings",
            context=task1_result
        )
        
        # Verificações
        assert isinstance(task1_result, str)
        assert isinstance(task2_result, str)
        assert task1_result != task2_result
        
        # Verificar que contexto foi incluído na segunda chamada
        second_call = fusion_agent.fusion_client.send_message.call_args_list[1]
        assert task1_result in second_call[1]["message"]
    
    @pytest.mark.asyncio
    async def test_fusion_agent_memory_persistence(self, fusion_agent, sample_responses):
        """Teste persistência de memória entre tarefas."""
        # Habilitar memória
        fusion_agent.memory = True
        
        # Configurar respostas
        fusion_agent.fusion_client.send_message.side_effect = [
            sample_responses["research"],
            sample_responses["analysis"]
        ]
        
        # Executar múltiplas tarefas
        await fusion_agent._execute_fusion_task("Task 1: Research topic")
        await fusion_agent._execute_fusion_task("Task 2: Analyze findings")
        
        # Verificar que memória foi mantida (chat_id reutilizado)
        calls = fusion_agent.fusion_client.send_message.call_args_list
        
        # Primeira chamada não deve ter chat_id
        assert calls[0][1].get("chat_id") is None
        
        # Segunda chamada deve usar o mesmo chat_id da primeira resposta
        expected_chat_id = str(sample_responses["research"].chat.id)
        assert calls[1][1].get("chat_id") == expected_chat_id


class TestFusionCrewIntegration:
    """Testes de integração com Crew do CrewAI."""
    
    @pytest.fixture
    def fusion_researcher(self, mock_fusion_client):
        """Agente pesquisador Fusion."""
        client_copy = MagicMock()
        client_copy.send_message = AsyncMock()
        return FusionAgent(
            fusion_client=client_copy,
            fusion_agent_id="researcher-agent",
            role="Senior Research Analyst",
            goal="Conduct thorough research on assigned topics",
            backstory="Expert researcher with access to comprehensive databases",
            verbose=True
        )
    
    @pytest.fixture
    def fusion_writer(self, mock_fusion_client):
        """Agente escritor Fusion."""
        client_copy = MagicMock()
        client_copy.send_message = AsyncMock()
        return FusionAgent(
            fusion_client=client_copy,
            fusion_agent_id="writer-agent",
            role="Content Writer",
            goal="Create engaging and informative content",
            backstory="Professional writer specialized in technical content",
            verbose=True
        )
    
    @pytest.mark.asyncio
    async def test_multi_agent_crew(self, fusion_researcher, fusion_writer, sample_responses):
        """Teste crew com múltiplos agentes Fusion."""
        # Configurar respostas dos agentes
        fusion_researcher.fusion_client.send_message.return_value = sample_responses["research"]
        fusion_writer.fusion_client.send_message.return_value = sample_responses["summary"]
        
        # Criar tarefas
        research_task = Task(
            description="Research the latest developments in quantum computing",
            agent=fusion_researcher
        )
        
        writing_task = Task(
            description="Write a comprehensive article based on the research",
            agent=fusion_writer,
            depends_on=[research_task]
        )
        
        # Criar crew
        crew = Crew(
            agents=[fusion_researcher, fusion_writer],
            tasks=[research_task, writing_task],
            verbose=True
        )
        
        # Executar crew (simulado)
        # Nota: Em testes reais, isso seria crew.kickoff()
        # Aqui simulamos a execução manual
        
        # Simular execução da primeira tarefa
        research_result = await fusion_researcher._execute_fusion_task(
            research_task.description
        )
        
        # Simular execução da segunda tarefa com dependência
        writing_result = await fusion_writer._execute_fusion_task(
            writing_task.description,
            context=research_result
        )
        
        # Verificações
        assert isinstance(research_result, str)
        assert isinstance(writing_result, str)
        assert research_result != writing_result
        
        # Verificar que ambos os agentes foram chamados
        fusion_researcher.fusion_client.send_message.assert_called_once()
        fusion_writer.fusion_client.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_agent_delegation(self, fusion_researcher, fusion_writer, sample_responses):
        """Teste delegação entre agentes."""
        # Habilitar delegação
        fusion_researcher.allow_delegation = True
        
        # Configurar respostas
        fusion_researcher.fusion_client.send_message.return_value = sample_responses["research"]
        
        # Simular delegação (o pesquisador passa trabalho para o escritor)
        research_result = await fusion_researcher._execute_fusion_task(
            "Research AI ethics and delegate writing to content writer"
        )
        
        # Verificar resultado
        assert isinstance(research_result, str)
        fusion_researcher.fusion_client.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_crew_error_handling(self, fusion_researcher, sample_responses):
        """Teste tratamento de erros em crew."""
        from fusion_client.core.exceptions import AgentNotFoundError
        
        # Configurar erro
        fusion_researcher.fusion_client.send_message.side_effect = AgentNotFoundError(
            "Fusion agent not found"
        )
        
        # Verificar que erro é propagado
        with pytest.raises(AgentNotFoundError):
            await fusion_researcher._execute_fusion_task("This should fail")


class TestFusionAgentCustomization:
    """Testes para customização de agentes Fusion."""
    
    @pytest.mark.asyncio
    async def test_agent_with_tools(self, mock_fusion_client, sample_responses):
        """Teste agente com ferramentas customizadas."""
        # Criar agente com ferramentas
        agent = FusionAgent(
            fusion_client=mock_fusion_client,
            fusion_agent_id="tool-agent",
            role="Data Analyst",
            goal="Analyze data using specialized tools",
            backstory="Expert in data analysis with access to advanced tools",
            tools=["calculator", "data_visualizer", "statistical_analyzer"]
        )
        
        # Configurar resposta
        mock_fusion_client.send_message.return_value = sample_responses["analysis"]
        
        # Executar tarefa
        result = await agent._execute_fusion_task(
            "Analyze sales data and create visualizations"
        )
        
        # Verificações
        assert isinstance(result, str)
        
        # Verificar que ferramentas foram mencionadas no contexto
        call_args = mock_fusion_client.send_message.call_args
        message = call_args[1]["message"]
        assert "tools" in message.lower() or "calculator" in message.lower()
    
    @pytest.mark.asyncio
    async def test_agent_with_custom_prompt(self, mock_fusion_client, sample_responses):
        """Teste agente com prompt customizado."""
        # Criar agente com prompt personalizado
        custom_prompt = """
        You are a specialized AI agent with the following characteristics:
        Role: {role}
        Goal: {goal}
        Background: {backstory}
        
        Always respond with structured analysis and clear recommendations.
        """
        
        agent = FusionAgent(
            fusion_client=mock_fusion_client,
            fusion_agent_id="custom-agent",
            role="Strategic Advisor",
            goal="Provide strategic business advice",
            backstory="Senior consultant with 20+ years experience",
            prompt_template=custom_prompt
        )
        
        # Configurar resposta
        mock_fusion_client.send_message.return_value = sample_responses["analysis"]
        
        # Executar tarefa
        result = await agent._execute_fusion_task(
            "Analyze market expansion opportunities"
        )
        
        # Verificações
        assert isinstance(result, str)
        
        # Verificar que prompt customizado foi usado
        call_args = mock_fusion_client.send_message.call_args
        message = call_args[1]["message"]
        assert "Strategic Advisor" in message
        assert "structured analysis" in message
    
    @pytest.mark.asyncio
    async def test_agent_performance_tracking(self, mock_fusion_client, sample_responses):
        """Teste rastreamento de performance do agente."""
        # Criar agente com métricas
        agent = FusionAgent(
            fusion_client=mock_fusion_client,
            fusion_agent_id="tracked-agent",
            role="Performance Tracker",
            goal="Track and analyze performance metrics",
            backstory="Expert in performance analysis",
            track_performance=True
        )
        
        # Configurar respostas
        mock_fusion_client.send_message.side_effect = [
            sample_responses["research"],
            sample_responses["analysis"],
            sample_responses["summary"]
        ]
        
        # Executar múltiplas tarefas
        tasks = [
            "Task 1: Initial research",
            "Task 2: Data analysis", 
            "Task 3: Final summary"
        ]
        
        results = []
        for task in tasks:
            result = await agent._execute_fusion_task(task)
            results.append(result)
        
        # Verificações
        assert len(results) == 3
        assert all(isinstance(r, str) for r in results)
        
        # Verificar métricas (se implementado)
        if hasattr(agent, 'performance_metrics'):
            assert agent.performance_metrics['total_tasks'] == 3
            assert 'average_response_time' in agent.performance_metrics


# Configuração para testes CrewAI
@pytest.fixture(autouse=True)
def setup_crewai_tests():
    """Setup para testes CrewAI."""
    if not CREWAI_AVAILABLE:
        pytest.skip("CrewAI integration tests require crewai package")
    
    # Configurar ambiente se necessário
    os.environ.setdefault("CREWAI_TELEMETRY", "false") 