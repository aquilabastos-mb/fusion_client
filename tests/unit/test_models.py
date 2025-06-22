"""Testes unitários para os modelos Pydantic."""

import pytest
from datetime import datetime
from uuid import UUID, uuid4
from typing import List

from fusion_client.models import Agent, User, Chat, Message, ChatResponse
from tests.fixtures.test_data import TestData


class TestAgent:
    """Testes para o modelo Agent."""
    
    def test_agent_creation_valid(self):
        """Teste criação de agente válido."""
        agent = Agent(
            id=uuid4(),
            name="Test Agent",
            description="A test agent",
            image=None,
            status=True,
            system_agent=False,
            transcription=None
        )
        
        assert isinstance(agent.id, UUID)
        assert agent.name == "Test Agent"
        assert agent.description == "A test agent"
        assert agent.image is None
        assert agent.status is True
        assert agent.system_agent is False
        assert agent.transcription is None
    
    def test_agent_with_image(self):
        """Teste agente com imagem."""
        agent = Agent(
            id=uuid4(),
            name="Visual Agent",
            description="Agent with image",
            image="https://example.com/agent.jpg",
            status=True,
            system_agent=False
        )
        
        assert agent.image == "https://example.com/agent.jpg"
    
    def test_agent_system_agent(self):
        """Teste agente do sistema."""
        agent = Agent(
            id=uuid4(),
            name="System Agent",
            description="System agent",
            status=True,
            system_agent=True,
            transcription="System capabilities"
        )
        
        assert agent.system_agent is True
        assert agent.transcription == "System capabilities"
    
    def test_agent_invalid_data(self):
        """Teste validação de dados inválidos."""
        with pytest.raises(ValueError):
            Agent(
                id="invalid-uuid",  # UUID inválido
                name="Test Agent",
                description="Test",
                status=True,
                system_agent=False
            )
    
    def test_agent_missing_required_fields(self):
        """Teste campos obrigatórios ausentes."""
        with pytest.raises(ValueError):
            Agent(
                # id ausente
                name="Test Agent",
                description="Test",
                status=True,
                system_agent=False
            )


class TestUser:
    """Testes para o modelo User."""
    
    def test_user_creation_valid(self):
        """Teste criação de usuário válido."""
        user = User(
            email="test@example.com",
            full_name="Test User"
        )
        
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
    
    def test_user_email_validation(self):
        """Teste validação de email."""
        # Email válido
        user = User(email="valid@example.com", full_name="User")
        assert user.email == "valid@example.com"
        
        # Email inválido deve falhar na validação do Pydantic
        with pytest.raises(ValueError):
            User(email="invalid-email", full_name="User")
    
    def test_user_empty_name(self):
        """Teste nome vazio."""
        with pytest.raises(ValueError):
            User(email="test@example.com", full_name="")


class TestMessage:
    """Testes para o modelo Message."""
    
    def test_message_creation_valid(self):
        """Teste criação de mensagem válida."""
        chat_id = uuid4()
        message = Message(
            id=uuid4(),
            chat_id=chat_id,
            message="Test message",
            message_type="user",
            created_at=datetime.now(),
            files=[]
        )
        
        assert isinstance(message.id, UUID)
        assert message.chat_id == chat_id
        assert message.message == "Test message"
        assert message.message_type == "user"
        assert isinstance(message.created_at, datetime)
        assert message.files == []
    
    def test_message_with_files(self):
        """Teste mensagem com arquivos."""
        message = Message(
            id=uuid4(),
            chat_id=uuid4(),
            message="Message with files",
            message_type="user",
            created_at=datetime.now(),
            files=["file1.pdf", "file2.jpg"]
        )
        
        assert message.files == ["file1.pdf", "file2.jpg"]
    
    def test_message_type_validation(self):
        """Teste validação do tipo de mensagem."""
        # Tipo válido - user
        message_user = Message(
            id=uuid4(),
            chat_id=uuid4(),
            message="User message",
            message_type="user",
            created_at=datetime.now(),
            files=[]
        )
        assert message_user.message_type == "user"
        
        # Tipo válido - agent
        message_agent = Message(
            id=uuid4(),
            chat_id=uuid4(),
            message="Agent message",
            message_type="agent",
            created_at=datetime.now(),
            files=[]
        )
        assert message_agent.message_type == "agent"
        
        # Tipo inválido
        with pytest.raises(ValueError):
            Message(
                id=uuid4(),
                chat_id=uuid4(),
                message="Invalid message",
                message_type="invalid",
                created_at=datetime.now(),
                files=[]
            )


class TestChat:
    """Testes para o modelo Chat."""
    
    def test_chat_creation_valid(self):
        """Teste criação de chat válido."""
        agent = TestData.get_test_agent()
        user = TestData.get_test_user()
        
        chat = Chat(
            id=uuid4(),
            agent=agent,
            user=user,
            folder=None,
            message="Initial message",
            knowledge=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            system_chat=False
        )
        
        assert isinstance(chat.id, UUID)
        assert chat.agent == agent
        assert chat.user == user
        assert chat.folder is None
        assert chat.message == "Initial message"
        assert chat.knowledge == []
        assert isinstance(chat.created_at, datetime)
        assert isinstance(chat.updated_at, datetime)
        assert chat.system_chat is False
    
    def test_chat_with_folder(self):
        """Teste chat com pasta."""
        agent = TestData.get_test_agent()
        user = TestData.get_test_user()
        
        chat = Chat(
            id=uuid4(),
            agent=agent,
            user=user,
            folder="work",
            message="Work related chat",
            knowledge=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            system_chat=False
        )
        
        assert chat.folder == "work"
    
    def test_chat_with_knowledge(self):
        """Teste chat com knowledge base."""
        agent = TestData.get_test_agent()
        user = TestData.get_test_user()
        
        chat = Chat(
            id=uuid4(),
            agent=agent,
            user=user,
            folder=None,
            message="Knowledge chat",
            knowledge=["doc1", "doc2"],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            system_chat=False
        )
        
        assert chat.knowledge == ["doc1", "doc2"]
    
    def test_system_chat(self):
        """Teste chat do sistema."""
        agent = TestData.get_test_agent(system_agent=True)
        user = TestData.get_test_user()
        
        chat = Chat(
            id=uuid4(),
            agent=agent,
            user=user,
            folder=None,
            message="System message",
            knowledge=[],
            created_at=datetime.now(),
            updated_at=datetime.now(),
            system_chat=True
        )
        
        assert chat.system_chat is True
        assert chat.agent.system_agent is True


class TestChatResponse:
    """Testes para o modelo ChatResponse."""
    
    def test_chat_response_creation_valid(self):
        """Teste criação de resposta de chat válida."""
        chat = TestData.get_test_chat()
        messages = TestData.get_test_messages(chat.id, count=3)
        
        response = ChatResponse(
            chat=chat,
            messages=messages
        )
        
        assert response.chat == chat
        assert response.messages == messages
        assert len(response.messages) == 3
    
    def test_last_message_property(self):
        """Teste propriedade last_message."""
        chat = TestData.get_test_chat()
        messages = TestData.get_test_messages(chat.id, count=3)
        
        response = ChatResponse(chat=chat, messages=messages)
        
        assert response.last_message == messages[-1]
        assert response.last_message.message == "Test message 3 from user"
    
    def test_last_message_empty_messages(self):
        """Teste last_message com lista vazia."""
        chat = TestData.get_test_chat()
        
        response = ChatResponse(chat=chat, messages=[])
        
        assert response.last_message is None
    
    def test_agent_messages_property(self):
        """Teste propriedade agent_messages."""
        chat = TestData.get_test_chat()
        messages = TestData.get_test_messages(chat.id, count=4)
        
        response = ChatResponse(chat=chat, messages=messages)
        agent_messages = response.agent_messages
        
        # Messages são alternados: user (0,2), agent (1,3)
        assert len(agent_messages) == 2
        assert all(msg.message_type == "agent" for msg in agent_messages)
        assert agent_messages[0].message == "Test message 2 from agent"
        assert agent_messages[1].message == "Test message 4 from agent"
    
    def test_agent_messages_empty(self):
        """Teste agent_messages sem mensagens de agente."""
        chat = TestData.get_test_chat()
        
        # Criar apenas mensagens de usuário
        user_message = Message(
            id=uuid4(),
            chat_id=chat.id,
            message="User only message",
            message_type="user",
            created_at=datetime.now(),
            files=[]
        )
        
        response = ChatResponse(chat=chat, messages=[user_message])
        
        assert response.agent_messages == []
    
    def test_chat_response_serialization(self):
        """Teste serialização da response."""
        response = TestData.get_test_chat_response()
        
        # Teste que pode ser serializado para dict
        response_dict = response.model_dump()
        
        assert "chat" in response_dict
        assert "messages" in response_dict
        # UUID pode ser serializado como string ou UUID object dependendo da configuração
        chat_id_serialized = response_dict["chat"]["id"]
        assert chat_id_serialized == response.chat.id or chat_id_serialized == str(response.chat.id)
        assert len(response_dict["messages"]) == len(response.messages)
    
    def test_chat_response_json_schema(self):
        """Teste schema JSON do modelo."""
        schema = ChatResponse.model_json_schema()
        
        assert "properties" in schema
        assert "chat" in schema["properties"]
        assert "messages" in schema["properties"]
        assert schema["required"] == ["chat", "messages"] 