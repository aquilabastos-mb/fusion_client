"""Testes unitários para os serviços."""

import pytest
import httpx
import respx
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from pathlib import Path

from fusion_client.services import ChatService, AgentService, FileService
from fusion_client.models import ChatResponse, Agent, Message
from fusion_client.core.exceptions import ValidationError, AgentNotFoundError
from tests.fixtures.test_data import TestData


class TestChatService:
    """Testes para ChatService."""
    
    @pytest.fixture
    def chat_service(self):
        """Fixture para ChatService."""
        http_client = MagicMock()
        return ChatService(http_client)
    
    @pytest.mark.asyncio
    async def test_create_chat_success(self, chat_service, mock_api_responses):
        """Teste criação de chat com sucesso."""
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_responses["create_chat"]
        
        chat_service._http_client.post = AsyncMock(return_value=mock_response)
        
        response = await chat_service.create_chat(
            agent_id="550e8400-e29b-41d4-a716-446655440001",
            message="Hello",
            folder=None
        )
        
        assert isinstance(response, ChatResponse)
        assert len(response.messages) == 2
        chat_service._http_client.post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_chat_with_folder(self, chat_service, mock_api_responses):
        """Teste criação de chat com pasta."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_responses["create_chat"]
        
        chat_service._http_client.post = AsyncMock(return_value=mock_response)
        
        response = await chat_service.create_chat(
            agent_id="550e8400-e29b-41d4-a716-446655440001",
            message="Work question",
            folder="work"
        )
        
        assert isinstance(response, ChatResponse)
        
        # Verificar que folder foi incluída na chamada
        call_args = chat_service._http_client.post.call_args
        assert "folder" in call_args[1]["json"]
        assert call_args[1]["json"]["folder"] == "work"
    
    @pytest.mark.asyncio
    async def test_send_message_to_existing_chat(self, chat_service, mock_api_responses):
        """Teste envio de mensagem para chat existente."""
        chat_id = "550e8400-e29b-41d4-a716-446655440000"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_responses["create_chat"]
        
        chat_service._http_client.post = AsyncMock(return_value=mock_response)
        
        response = await chat_service.send_message(
            chat_id=chat_id,
            message="Follow up question",
            files=None
        )
        
        assert isinstance(response, ChatResponse)
        
        # Verificar endpoint correto
        call_args = chat_service._http_client.post.call_args
        assert f"/chat/{chat_id}/message" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_send_message_with_files(self, chat_service, mock_api_responses):
        """Teste envio de mensagem com arquivos."""
        chat_id = "550e8400-e29b-41d4-a716-446655440000"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_responses["create_chat"]
        
        chat_service._http_client.post = AsyncMock(return_value=mock_response)
        
        response = await chat_service.send_message(
            chat_id=chat_id,
            message="Analyze these files",
            files=["file1.pdf", "file2.jpg"]
        )
        
        assert isinstance(response, ChatResponse)
        
        # Verificar que files foram incluídos
        call_args = chat_service._http_client.post.call_args
        assert "files" in call_args[1]["json"]
        assert call_args[1]["json"]["files"] == ["file1.pdf", "file2.jpg"]
    
    @pytest.mark.asyncio
    async def test_get_chat_success(self, chat_service, mock_api_responses):
        """Teste recuperação de chat."""
        chat_id = "550e8400-e29b-41d4-a716-446655440000"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_responses["create_chat"]
        
        chat_service._http_client.get = AsyncMock(return_value=mock_response)
        
        response = await chat_service.get_chat(chat_id)
        
        assert isinstance(response, ChatResponse)
        assert str(response.chat.id) == chat_id
        
        # Verificar endpoint correto
        call_args = chat_service._http_client.get.call_args
        assert f"/chat/{chat_id}" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_get_messages_success(self, chat_service):
        """Teste recuperação de mensagens."""
        chat_id = "550e8400-e29b-41d4-a716-446655440000"
        
        mock_messages = [
            {
                "id": "msg-1",
                "chat_id": chat_id,
                "message": "Hello",
                "message_type": "user",
                "created_at": "2024-01-01T00:00:00Z",
                "files": []
            },
            {
                "id": "msg-2",
                "chat_id": chat_id,
                "message": "Hi there!",
                "message_type": "agent",
                "created_at": "2024-01-01T00:00:01Z",
                "files": []
            }
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_messages
        
        chat_service._http_client.get = AsyncMock(return_value=mock_response)
        
        messages = await chat_service.get_messages(chat_id)
        
        assert isinstance(messages, list)
        assert len(messages) == 2
        assert all(isinstance(msg, Message) for msg in messages)
    
    @pytest.mark.asyncio
    async def test_validation_error_empty_message(self, chat_service):
        """Teste erro de validação com mensagem vazia."""
        with pytest.raises(ValidationError, match="Message cannot be empty"):
            await chat_service.create_chat(
                agent_id="550e8400-e29b-41d4-a716-446655440001",
                message="",  # Mensagem vazia
                folder=None
            )
    
    @pytest.mark.asyncio
    async def test_validation_error_message_too_long(self, chat_service):
        """Teste erro de validação com mensagem muito longa."""
        long_message = "x" * 50000  # 50k caracteres
        
        with pytest.raises(ValidationError, match="Message too long"):
            await chat_service.create_chat(
                agent_id="550e8400-e29b-41d4-a716-446655440001",
                message=long_message,
                folder=None
            )


class TestAgentService:
    """Testes para AgentService."""
    
    @pytest.fixture
    def agent_service(self):
        """Fixture para AgentService."""
        http_client = MagicMock()
        return AgentService(http_client)
    
    @pytest.mark.asyncio
    async def test_list_agents_success(self, agent_service, mock_api_responses):
        """Teste listagem de agentes."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_responses["agents_list"]
        
        agent_service._http_client.get = AsyncMock(return_value=mock_response)
        
        agents = await agent_service.list_agents()
        
        assert isinstance(agents, list)
        assert len(agents) == 2
        assert all(isinstance(agent, Agent) for agent in agents)
        assert agents[0].name == "General Assistant"
        assert agents[1].name == "Code Helper"
    
    @pytest.mark.asyncio
    async def test_list_agents_with_filters(self, agent_service, mock_api_responses):
        """Teste listagem de agentes com filtros."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_responses["agents_list"]
        
        agent_service._http_client.get = AsyncMock(return_value=mock_response)
        
        agents = await agent_service.list_agents(
            status="active",
            system_only=False
        )
        
        assert isinstance(agents, list)
        
        # Verificar que filtros foram aplicados
        call_args = agent_service._http_client.get.call_args
        assert "params" in call_args[1]
        assert call_args[1]["params"]["status"] == "active"
        assert call_args[1]["params"]["system_only"] is False
    
    @pytest.mark.asyncio
    async def test_get_agent_success(self, agent_service, mock_api_responses):
        """Teste recuperação de agente específico."""
        agent_id = "550e8400-e29b-41d4-a716-446655440001"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_responses["agents_list"][0]
        
        agent_service._http_client.get = AsyncMock(return_value=mock_response)
        
        agent = await agent_service.get_agent(agent_id)
        
        assert isinstance(agent, Agent)
        assert str(agent.id) == agent_id
        assert agent.name == "General Assistant"
        
        # Verificar endpoint correto
        call_args = agent_service._http_client.get.call_args
        assert f"/agents/{agent_id}" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, agent_service):
        """Teste agente não encontrado."""
        agent_id = "nonexistent-agent"
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "Agent not found"}
        
        agent_service._http_client.get = AsyncMock(return_value=mock_response)
        
        with pytest.raises(AgentNotFoundError):
            await agent_service.get_agent(agent_id)
    
    @pytest.mark.asyncio
    async def test_search_agents(self, agent_service, mock_api_responses):
        """Teste busca de agentes."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [mock_api_responses["agents_list"][1]]  # Apenas Code Helper
        
        agent_service._http_client.get = AsyncMock(return_value=mock_response)
        
        agents = await agent_service.search_agents("code")
        
        assert isinstance(agents, list)
        assert len(agents) == 1
        assert agents[0].name == "Code Helper"
        
        # Verificar parâmetro de busca
        call_args = agent_service._http_client.get.call_args
        assert "params" in call_args[1]
        assert call_args[1]["params"]["search"] == "code"
    
    @pytest.mark.asyncio
    async def test_get_agent_capabilities(self, agent_service):
        """Teste recuperação de capacidades do agente."""
        agent_id = "550e8400-e29b-41d4-a716-446655440001"
        
        mock_capabilities = {
            "can_analyze_files": True,
            "can_generate_code": True,
            "can_web_search": False,
            "supported_file_types": ["pdf", "txt", "docx"],
            "max_file_size": 10485760  # 10MB
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_capabilities
        
        agent_service._http_client.get = AsyncMock(return_value=mock_response)
        
        capabilities = await agent_service.get_agent_capabilities(agent_id)
        
        assert isinstance(capabilities, dict)
        assert capabilities["can_analyze_files"] is True
        assert "supported_file_types" in capabilities
        
        # Verificar endpoint correto
        call_args = agent_service._http_client.get.call_args
        assert f"/agents/{agent_id}/capabilities" in call_args[0][0]


class TestFileService:
    """Testes para FileService."""
    
    @pytest.fixture
    def file_service(self):
        """Fixture para FileService."""
        http_client = MagicMock()
        return FileService(http_client)
    
    @pytest.mark.asyncio
    async def test_upload_file_success(self, file_service, mock_api_responses, sample_pdf_file):
        """Teste upload de arquivo com sucesso."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_responses["file_upload"]
        
        file_service._http_client.post = AsyncMock(return_value=mock_response)
        
        response = await file_service.upload_file(str(sample_pdf_file))
        
        assert response["file_id"] == "file-12345"
        assert response["filename"] == "test-document.pdf"
        assert response["content_type"] == "application/pdf"
        
        # Verificar que o arquivo foi enviado como multipart
        call_args = file_service._http_client.post.call_args
        assert "files" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_upload_file_to_chat(self, file_service, mock_api_responses, sample_pdf_file):
        """Teste upload de arquivo para chat específico."""
        chat_id = "550e8400-e29b-41d4-a716-446655440000"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_responses["file_upload"]
        
        file_service._http_client.post = AsyncMock(return_value=mock_response)
        
        response = await file_service.upload_file(
            str(sample_pdf_file),
            chat_id=chat_id
        )
        
        assert response["file_id"] == "file-12345"
        
        # Verificar endpoint correto
        call_args = file_service._http_client.post.call_args
        assert f"/chat/{chat_id}/files" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_upload_file_with_metadata(self, file_service, mock_api_responses, sample_pdf_file):
        """Teste upload de arquivo com metadados."""
        metadata = {
            "description": "Test document",
            "tags": ["test", "pdf"],
            "category": "documents"
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            **mock_api_responses["file_upload"],
            "metadata": metadata
        }
        
        file_service._http_client.post = AsyncMock(return_value=mock_response)
        
        response = await file_service.upload_file(
            str(sample_pdf_file),
            metadata=metadata
        )
        
        assert response["file_id"] == "file-12345"
        assert response["metadata"] == metadata
    
    @pytest.mark.asyncio
    async def test_upload_file_not_found(self, file_service):
        """Teste upload de arquivo não encontrado."""
        with pytest.raises(FileNotFoundError):
            await file_service.upload_file("nonexistent-file.pdf")
    
    @pytest.mark.asyncio
    async def test_upload_file_too_large(self, file_service, tmp_path):
        """Teste upload de arquivo muito grande."""
        # Criar arquivo muito grande (simulado)
        large_file = tmp_path / "large_file.txt"
        large_file.write_text("x" * (100 * 1024 * 1024))  # 100MB
        
        with pytest.raises(ValidationError, match="File too large"):
            await file_service.upload_file(str(large_file))
    
    @pytest.mark.asyncio
    async def test_upload_unsupported_file_type(self, file_service, tmp_path):
        """Teste upload de tipo de arquivo não suportado."""
        # Criar arquivo com extensão não suportada
        unsupported_file = tmp_path / "test.exe"
        unsupported_file.write_bytes(b"fake executable")
        
        with pytest.raises(ValidationError, match="Unsupported file type"):
            await file_service.upload_file(str(unsupported_file))
    
    @pytest.mark.asyncio
    async def test_download_file_success(self, file_service):
        """Teste download de arquivo."""
        file_id = "file-12345"
        file_content = b"PDF content here"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = file_content
        mock_response.headers = {"content-type": "application/pdf"}
        
        file_service._http_client.get = AsyncMock(return_value=mock_response)
        
        content, content_type = await file_service.download_file(file_id)
        
        assert content == file_content
        assert content_type == "application/pdf"
        
        # Verificar endpoint correto
        call_args = file_service._http_client.get.call_args
        assert f"/files/{file_id}/download" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_get_file_info(self, file_service, mock_api_responses):
        """Teste recuperação de informações do arquivo."""
        file_id = "file-12345"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_api_responses["file_upload"]
        
        file_service._http_client.get = AsyncMock(return_value=mock_response)
        
        file_info = await file_service.get_file_info(file_id)
        
        assert file_info["file_id"] == file_id
        assert file_info["filename"] == "test-document.pdf"
        assert file_info["size"] == 2048
        
        # Verificar endpoint correto
        call_args = file_service._http_client.get.call_args
        assert f"/files/{file_id}" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_delete_file_success(self, file_service):
        """Teste exclusão de arquivo."""
        file_id = "file-12345"
        
        mock_response = MagicMock()
        mock_response.status_code = 204  # No Content
        
        file_service._http_client.delete = AsyncMock(return_value=mock_response)
        
        success = await file_service.delete_file(file_id)
        
        assert success is True
        
        # Verificar endpoint correto
        call_args = file_service._http_client.delete.call_args
        assert f"/files/{file_id}" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_list_files_success(self, file_service):
        """Teste listagem de arquivos."""
        mock_files = [
            {
                "file_id": "file-1",
                "filename": "doc1.pdf",
                "size": 1024,
                "created_at": "2024-01-01T00:00:00Z"
            },
            {
                "file_id": "file-2",
                "filename": "doc2.txt",
                "size": 512,
                "created_at": "2024-01-01T01:00:00Z"
            }
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_files
        
        file_service._http_client.get = AsyncMock(return_value=mock_response)
        
        files = await file_service.list_files()
        
        assert isinstance(files, list)
        assert len(files) == 2
        assert files[0]["filename"] == "doc1.pdf"
        assert files[1]["filename"] == "doc2.txt"
    
    @pytest.mark.asyncio
    async def test_list_files_with_filters(self, file_service):
        """Teste listagem de arquivos com filtros."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        
        file_service._http_client.get = AsyncMock(return_value=mock_response)
        
        files = await file_service.list_files(
            file_type="pdf",
            limit=10,
            offset=0
        )
        
        assert isinstance(files, list)
        
        # Verificar que filtros foram aplicados
        call_args = file_service._http_client.get.call_args
        assert "params" in call_args[1]
        assert call_args[1]["params"]["file_type"] == "pdf"
        assert call_args[1]["params"]["limit"] == 10
        assert call_args[1]["params"]["offset"] == 0 