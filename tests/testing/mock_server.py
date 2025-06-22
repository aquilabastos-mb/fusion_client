"""Mock server para testes de integração."""

import json
import asyncio
from typing import Dict, Any, Optional
from aiohttp import web, WSMsgType
from aiohttp.web import Application, Request, Response, WebSocketResponse
import threading
import time
from uuid import uuid4

from tests.fixtures.test_data import TestData, API_ENDPOINTS


class MockFusionServer:
    """Servidor mock da API Fusion para testes."""
    
    def __init__(self, host: str = "localhost", port: int = 8888):
        self.host = host
        self.port = port
        self.app: Optional[Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self.server_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Estado do servidor
        self.chats: Dict[str, Dict] = {}
        self.agents: Dict[str, Dict] = {}
        self.files: Dict[str, Dict] = {}
        self.messages: Dict[str, list] = {}
        
        # Configurações
        self.response_delay = 0.1  # Delay para simular latência
        self.error_rate = 0.0  # Taxa de erro (0.0 = sem erros, 1.0 = sempre erro)
        self.rate_limit_enabled = False
        self.rate_limit_calls = 100
        self.rate_limit_window = 60
        self._request_counts = {}
        
        # Inicializar dados de teste
        self._init_test_data()
    
    def _init_test_data(self):
        """Inicializar dados de teste."""
        # Agentes de teste
        agents = TestData.get_multiple_agents(count=5)
        for agent in agents:
            self.agents[str(agent.id)] = agent.model_dump()
        
        # Files de exemplo
        self.files = {
            "file-123": {
                "file_id": "file-123",
                "filename": "test.pdf",
                "size": 2048,
                "content_type": "application/pdf",
                "created_at": "2024-01-01T00:00:00Z"
            }
        }
    
    async def create_app(self) -> Application:
        """Criar aplicação aiohttp."""
        app = web.Application()
        
        # Rotas da API
        app.router.add_get("/agents", self.list_agents)
        app.router.add_get("/agents/{agent_id}", self.get_agent)
        app.router.add_post("/chat", self.create_chat)
        app.router.add_get("/chat/{chat_id}", self.get_chat)
        app.router.add_post("/chat/{chat_id}/message", self.send_message)
        app.router.add_get("/chat/{chat_id}/messages", self.get_messages)
        app.router.add_post("/chat/{chat_id}/files", self.upload_file_to_chat)
        app.router.add_post("/files", self.upload_file)
        app.router.add_get("/files/{file_id}", self.get_file_info)
        app.router.add_get("/files/{file_id}/download", self.download_file)
        app.router.add_delete("/files/{file_id}", self.delete_file)
        
        # Rota de streaming
        app.router.add_post("/chat/stream", self.stream_chat)
        app.router.add_post("/chat/{chat_id}/message/stream", self.stream_message)
        
        # Middleware
        app.middlewares.append(self.auth_middleware)
        app.middlewares.append(self.rate_limit_middleware)
        app.middlewares.append(self.delay_middleware)
        app.middlewares.append(self.error_injection_middleware)
        
        return app
    
    # Middleware
    
    @web.middleware
    async def auth_middleware(self, request: Request, handler):
        """Middleware de autenticação."""
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            if request.path.startswith("/health"):
                return await handler(request)
            return web.json_response(
                {"error": "Unauthorized", "message": "Invalid API key"},
                status=401
            )
        
        api_key = auth_header[7:]  # Remove "Bearer "
        if api_key == "invalid-key":
            return web.json_response(
                {"error": "Unauthorized", "message": "Invalid API key"},
                status=401
            )
        
        return await handler(request)
    
    @web.middleware
    async def rate_limit_middleware(self, request: Request, handler):
        """Middleware de rate limiting."""
        if not self.rate_limit_enabled:
            return await handler(request)
        
        client_ip = request.remote
        now = time.time()
        
        if client_ip not in self._request_counts:
            self._request_counts[client_ip] = []
        
        # Remover requisições antigas
        self._request_counts[client_ip] = [
            req_time for req_time in self._request_counts[client_ip]
            if now - req_time < self.rate_limit_window
        ]
        
        # Verificar limite
        if len(self._request_counts[client_ip]) >= self.rate_limit_calls:
            return web.json_response(
                {
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Try again in {self.rate_limit_window} seconds",
                    "retry_after": self.rate_limit_window
                },
                status=429,
                headers={"Retry-After": str(self.rate_limit_window)}
            )
        
        # Adicionar requisição atual
        self._request_counts[client_ip].append(now)
        
        return await handler(request)
    
    @web.middleware
    async def delay_middleware(self, request: Request, handler):
        """Middleware para simular latência."""
        if self.response_delay > 0:
            await asyncio.sleep(self.response_delay)
        return await handler(request)
    
    @web.middleware
    async def error_injection_middleware(self, request: Request, handler):
        """Middleware para injeção de erros."""
        import random
        
        if self.error_rate > 0 and random.random() < self.error_rate:
            return web.json_response(
                {"error": "Internal server error", "message": "Simulated error"},
                status=500
            )
        
        return await handler(request)
    
    # Handlers da API
    
    async def list_agents(self, request: Request) -> Response:
        """Listar agentes."""
        status = request.query.get("status")
        system_only = request.query.get("system_only")
        
        agents = list(self.agents.values())
        
        # Filtros
        if status == "active":
            agents = [a for a in agents if a["status"]]
        elif status == "inactive":
            agents = [a for a in agents if not a["status"]]
        
        if system_only == "true":
            agents = [a for a in agents if a["system_agent"]]
        elif system_only == "false":
            agents = [a for a in agents if not a["system_agent"]]
        
        return web.json_response(agents)
    
    async def get_agent(self, request: Request) -> Response:
        """Obter agente específico."""
        agent_id = request.match_info["agent_id"]
        
        if agent_id not in self.agents:
            return web.json_response(
                {"error": "Agent not found", "message": "The specified agent does not exist"},
                status=404
            )
        
        return web.json_response(self.agents[agent_id])
    
    async def create_chat(self, request: Request) -> Response:
        """Criar novo chat."""
        data = await request.json()
        
        agent_id = data.get("agent_id")
        message = data.get("message", "")
        folder = data.get("folder")
        
        if not agent_id or agent_id not in self.agents:
            return web.json_response(
                {"error": "Agent not found", "message": "The specified agent does not exist"},
                status=404
            )
        
        if not message.strip():
            return web.json_response(
                {"error": "Validation error", "message": "Message cannot be empty"},
                status=422
            )
        
        # Criar chat
        chat_id = str(uuid4())
        chat_data = {
            "id": chat_id,
            "agent": self.agents[agent_id],
            "user": {"email": "test@example.com", "full_name": "Test User"},
            "folder": folder,
            "message": message,
            "knowledge": [],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "system_chat": False
        }
        
        # Criar mensagens
        user_msg = {
            "id": str(uuid4()),
            "chat_id": chat_id,
            "message": message,
            "message_type": "user",
            "created_at": "2024-01-01T00:00:00Z",
            "files": data.get("files", [])
        }
        
        agent_msg = {
            "id": str(uuid4()),
            "chat_id": chat_id,
            "message": f"Hello! I'm {self.agents[agent_id]['name']}. How can I help you today?",
            "message_type": "agent",
            "created_at": "2024-01-01T00:00:01Z",
            "files": []
        }
        
        messages = [user_msg, agent_msg]
        
        # Armazenar
        self.chats[chat_id] = chat_data
        self.messages[chat_id] = messages
        
        return web.json_response({
            "chat": chat_data,
            "messages": messages
        })
    
    async def get_chat(self, request: Request) -> Response:
        """Obter chat existente."""
        chat_id = request.match_info["chat_id"]
        
        if chat_id not in self.chats:
            return web.json_response(
                {"error": "Chat not found", "message": "The specified chat does not exist"},
                status=404
            )
        
        return web.json_response({
            "chat": self.chats[chat_id],
            "messages": self.messages.get(chat_id, [])
        })
    
    async def send_message(self, request: Request) -> Response:
        """Enviar mensagem para chat existente."""
        chat_id = request.match_info["chat_id"]
        data = await request.json()
        
        if chat_id not in self.chats:
            return web.json_response(
                {"error": "Chat not found", "message": "The specified chat does not exist"},
                status=404
            )
        
        message = data.get("message", "")
        if not message.strip():
            return web.json_response(
                {"error": "Validation error", "message": "Message cannot be empty"},
                status=422
            )
        
        # Adicionar mensagem do usuário
        user_msg = {
            "id": str(uuid4()),
            "chat_id": chat_id,
            "message": message,
            "message_type": "user",
            "created_at": "2024-01-01T00:00:02Z",
            "files": data.get("files", [])
        }
        
        # Gerar resposta do agente
        agent_response = f"Thank you for your message: '{message}'. I'm processing your request."
        agent_msg = {
            "id": str(uuid4()),
            "chat_id": chat_id,
            "message": agent_response,
            "message_type": "agent",
            "created_at": "2024-01-01T00:00:03Z",
            "files": []
        }
        
        # Adicionar às mensagens
        if chat_id not in self.messages:
            self.messages[chat_id] = []
        
        self.messages[chat_id].extend([user_msg, agent_msg])
        
        return web.json_response({
            "chat": self.chats[chat_id],
            "messages": self.messages[chat_id]
        })
    
    async def get_messages(self, request: Request) -> Response:
        """Obter mensagens de um chat."""
        chat_id = request.match_info["chat_id"]
        
        if chat_id not in self.chats:
            return web.json_response(
                {"error": "Chat not found", "message": "The specified chat does not exist"},
                status=404
            )
        
        return web.json_response(self.messages.get(chat_id, []))
    
    async def stream_chat(self, request: Request) -> WebSocketResponse:
        """Streaming para novo chat."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        # Simular stream de tokens
        tokens = ["Hello", " there!", " This", " is", " a", " streaming", " response", "."]
        
        for token in tokens:
            data = {"token": token}
            await ws.send_text(f"data: {json.dumps(data)}\n\n")
            await asyncio.sleep(0.1)
        
        await ws.send_text("data: [DONE]\n\n")
        await ws.close()
        
        return ws
    
    async def stream_message(self, request: Request) -> WebSocketResponse:
        """Streaming para mensagem em chat existente."""
        return await self.stream_chat(request)
    
    async def upload_file(self, request: Request) -> Response:
        """Upload de arquivo."""
        # Simular upload
        file_id = str(uuid4())
        file_data = {
            "file_id": file_id,
            "filename": "uploaded_file.pdf",
            "size": 2048,
            "content_type": "application/pdf",
            "upload_url": f"https://storage.example.com/files/{file_id}",
            "created_at": "2024-01-01T00:00:00Z"
        }
        
        self.files[file_id] = file_data
        return web.json_response(file_data)
    
    async def upload_file_to_chat(self, request: Request) -> Response:
        """Upload de arquivo para chat específico."""
        chat_id = request.match_info["chat_id"]
        
        if chat_id not in self.chats:
            return web.json_response(
                {"error": "Chat not found", "message": "The specified chat does not exist"},
                status=404
            )
        
        return await self.upload_file(request)
    
    async def get_file_info(self, request: Request) -> Response:
        """Obter informações do arquivo."""
        file_id = request.match_info["file_id"]
        
        if file_id not in self.files:
            return web.json_response(
                {"error": "File not found", "message": "The specified file does not exist"},
                status=404
            )
        
        return web.json_response(self.files[file_id])
    
    async def download_file(self, request: Request) -> Response:
        """Download de arquivo."""
        file_id = request.match_info["file_id"]
        
        if file_id not in self.files:
            return web.json_response(
                {"error": "File not found", "message": "The specified file does not exist"},
                status=404
            )
        
        # Simular conteúdo do arquivo
        content = b"Fake PDF content for testing"
        
        return web.Response(
            body=content,
            content_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=test.pdf"}
        )
    
    async def delete_file(self, request: Request) -> Response:
        """Deletar arquivo."""
        file_id = request.match_info["file_id"]
        
        if file_id not in self.files:
            return web.json_response(
                {"error": "File not found", "message": "The specified file does not exist"},
                status=404
            )
        
        del self.files[file_id]
        return web.Response(status=204)
    
    # Métodos de controle do servidor
    
    async def start(self):
        """Iniciar servidor."""
        if self._running:
            return
        
        self.app = await self.create_app()
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        
        self._running = True
        print(f"Mock Fusion server started at http://{self.host}:{self.port}")
    
    async def stop(self):
        """Parar servidor."""
        if not self._running:
            return
        
        if self.site:
            await self.site.stop()
        
        if self.runner:
            await self.runner.cleanup()
        
        self._running = False
        print("Mock Fusion server stopped")
    
    def start_background(self):
        """Iniciar servidor em background thread."""
        def run_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.start())
            try:
                loop.run_forever()
            except KeyboardInterrupt:
                pass
            finally:
                loop.run_until_complete(self.stop())
                loop.close()
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        # Aguardar servidor iniciar
        time.sleep(0.5)
    
    def stop_background(self):
        """Parar servidor em background."""
        if self.server_thread and self.server_thread.is_alive():
            # Sinalizar parada através do loop
            asyncio.run_coroutine_threadsafe(self.stop(), asyncio.get_event_loop())
            self.server_thread.join(timeout=5)
    
    @property
    def base_url(self) -> str:
        """URL base do servidor."""
        return f"http://{self.host}:{self.port}"
    
    # Métodos de configuração para testes
    
    def set_error_rate(self, rate: float):
        """Configurar taxa de erro."""
        self.error_rate = max(0.0, min(1.0, rate))
    
    def set_response_delay(self, delay: float):
        """Configurar delay de resposta."""
        self.response_delay = max(0.0, delay)
    
    def enable_rate_limiting(self, calls: int = 100, window: int = 60):
        """Habilitar rate limiting."""
        self.rate_limit_enabled = True
        self.rate_limit_calls = calls
        self.rate_limit_window = window
    
    def disable_rate_limiting(self):
        """Desabilitar rate limiting."""
        self.rate_limit_enabled = False
    
    def reset_state(self):
        """Resetar estado do servidor."""
        self.chats.clear()
        self.messages.clear()
        self.files.clear()
        self._request_counts.clear()
        self._init_test_data()


# Context manager para uso em testes
class MockServerContext:
    """Context manager para servidor mock."""
    
    def __init__(self, **kwargs):
        self.server = MockFusionServer(**kwargs)
    
    async def __aenter__(self):
        await self.server.start()
        return self.server
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.server.stop()


# Exemplo de uso
if __name__ == "__main__":
    async def main():
        async with MockServerContext() as server:
            print(f"Server running at {server.base_url}")
            await asyncio.sleep(60)  # Manter por 1 minuto
    
    asyncio.run(main()) 