"""Testes unitários para utilitários."""

import pytest
import asyncio
import time
import json
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncIterator

from fusion_client.utils.cache import FusionCache
from fusion_client.utils.retry import RateLimiter, with_retry
from fusion_client.utils.streaming import StreamingParser
from fusion_client.utils.validators import MessageValidator, FileValidator
from fusion_client.core.exceptions import ValidationError, RateLimitError


class TestFusionCache:
    """Testes para o sistema de cache."""
    
    def test_cache_initialization(self):
        """Teste inicialização do cache."""
        cache = FusionCache(ttl=300, max_size=1000)
        
        assert cache.ttl == 300
        assert cache.max_size == 1000
        assert len(cache._cache) == 0
    
    def test_cache_set_and_get(self):
        """Teste set e get básicos."""
        cache = FusionCache(ttl=300, max_size=100)
        
        key = "test_key"
        value = {"data": "test_value"}
        
        cache.set(key, value)
        retrieved_value = cache.get(key)
        
        assert retrieved_value == value
    
    def test_cache_expiration(self):
        """Teste expiração do cache."""
        cache = FusionCache(ttl=1, max_size=100)  # TTL de 1 segundo
        
        key = "test_key"
        value = {"data": "test_value"}
        
        cache.set(key, value)
        assert cache.get(key) == value
        
        # Esperar expirar
        time.sleep(1.1)
        assert cache.get(key) is None
    
    def test_cache_max_size_eviction(self):
        """Teste remoção por tamanho máximo."""
        cache = FusionCache(ttl=300, max_size=2)
        
        # Adicionar 3 itens (excede max_size)
        cache.set("key1", "value1")
        time.sleep(0.01)  # Pequeno delay para garantir ordem
        cache.set("key2", "value2")
        time.sleep(0.01)
        cache.set("key3", "value3")
        
        # key1 deve ter sido removido (mais antigo)
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
    
    def test_generate_cache_key(self):
        """Teste geração de chave de cache."""
        cache = FusionCache()
        
        key1 = cache._generate_key("GET", "/api/test", {"param": "value"})
        key2 = cache._generate_key("GET", "/api/test", {"param": "value"})
        key3 = cache._generate_key("GET", "/api/test", {"param": "other"})
        
        # Mesmos parâmetros devem gerar mesma chave
        assert key1 == key2
        # Parâmetros diferentes devem gerar chaves diferentes
        assert key1 != key3
    
    def test_cache_key_order_independence(self):
        """Teste que ordem dos parâmetros não afeta a chave."""
        cache = FusionCache()
        
        key1 = cache._generate_key("GET", "/api", {"a": "1", "b": "2"})
        key2 = cache._generate_key("GET", "/api", {"b": "2", "a": "1"})
        
        assert key1 == key2


class TestRateLimiter:
    """Testes para rate limiter."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_initialization(self):
        """Teste inicialização do rate limiter."""
        limiter = RateLimiter(max_calls=100, window=60)
        
        assert limiter.max_calls == 100
        assert limiter.window == 60
        assert len(limiter.calls) == 0
    
    @pytest.mark.asyncio
    async def test_rate_limiter_within_limit(self):
        """Teste chamadas dentro do limite."""
        limiter = RateLimiter(max_calls=5, window=60)
        
        # Fazer 3 chamadas rapidamente
        for _ in range(3):
            await limiter.acquire()
        
        assert len(limiter.calls) == 3
    
    @pytest.mark.asyncio
    async def test_rate_limiter_exceeds_limit(self):
        """Teste excesso de chamadas."""
        limiter = RateLimiter(max_calls=2, window=60)
        
        # Fazer 2 chamadas (dentro do limite)
        await limiter.acquire()
        await limiter.acquire()
        
        # 3ª chamada deve causar delay
        start_time = time.time()
        with patch('asyncio.sleep') as mock_sleep:
            await limiter.acquire()
            mock_sleep.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rate_limiter_window_reset(self):
        """Teste reset da janela de tempo."""
        limiter = RateLimiter(max_calls=2, window=1)  # Janela de 1 segundo
        
        # Fazer 2 chamadas
        await limiter.acquire()
        await limiter.acquire()
        
        # Simular passagem de tempo
        with patch('time.time') as mock_time:
            mock_time.return_value = time.time() + 2  # 2 segundos depois
            
            # Chamadas antigas devem ter sido removidas
            await limiter.acquire()
            assert len(limiter.calls) == 1


class TestRetryDecorator:
    """Testes para decorator de retry."""
    
    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self):
        """Teste sucesso na primeira tentativa (sem retry)."""
        call_count = 0
        
        @with_retry(max_attempts=3, backoff_factor=0.1)
        async def test_function():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await test_function()
        
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Teste sucesso após falhas (com retry)."""
        call_count = 0
        
        @with_retry(max_attempts=3, backoff_factor=0.01)
        async def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = await test_function()
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_max_attempts_exceeded(self):
        """Teste excesso de tentativas máximas."""
        call_count = 0
        
        @with_retry(max_attempts=2, backoff_factor=0.01)
        async def test_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent error")
        
        with pytest.raises(ValueError, match="Persistent error"):
            await test_function()
        
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_backoff_timing(self):
        """Teste timing do backoff exponencial."""
        call_times = []
        
        @with_retry(max_attempts=3, backoff_factor=0.1)
        async def test_function():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise ValueError("Error")
            return "success"
        
        await test_function()
        
        # Verificar que houve delays entre as chamadas
        assert len(call_times) == 3
        
        # Primeira tentativa para segunda (backoff = 0.1 * 2^0 = 0.1)
        delay1 = call_times[1] - call_times[0]
        assert delay1 >= 0.1  # Pelo menos 0.1 segundo
        
        # Segunda tentativa para terceira (backoff = 0.1 * 2^1 = 0.2)
        delay2 = call_times[2] - call_times[1]
        assert delay2 >= 0.2  # Pelo menos 0.2 segundos
    
    @pytest.mark.asyncio
    async def test_retry_specific_exceptions(self):
        """Teste retry apenas para exceções específicas."""
        call_count = 0
        
        @with_retry(max_attempts=3, exceptions=(ValueError,))
        async def test_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Retryable error")
            elif call_count == 2:
                raise TypeError("Non-retryable error")
            return "success"
        
        # TypeError não deve ser recuperável
        with pytest.raises(TypeError, match="Non-retryable error"):
            await test_function()
        
        assert call_count == 2


class TestStreamingParser:
    """Testes para parser de streaming."""
    
    @pytest.mark.asyncio
    async def test_streaming_parser_success(self, streaming_response_data):
        """Teste parser de streaming com sucesso."""
        async def mock_response():
            for chunk in streaming_response_data:
                yield chunk.encode('utf-8')
        
        parser = StreamingParser()
        tokens = []
        
        async for token in parser.parse_stream(mock_response()):
            tokens.append(token)
        
        expected_tokens = ["Hello", " there!", " How", " can", " I", " help?"]
        assert tokens == expected_tokens
    
    @pytest.mark.asyncio
    async def test_streaming_parser_done_signal(self):
        """Teste sinal de fim do streaming."""
        streaming_data = [
            "data: {\"token\": \"Hello\"}\n\n",
            "data: [DONE]\n\n"
        ]
        
        async def mock_response():
            for chunk in streaming_data:
                yield chunk.encode('utf-8')
        
        parser = StreamingParser()
        tokens = []
        
        async for token in parser.parse_stream(mock_response()):
            tokens.append(token)
        
        assert tokens == ["Hello"]
    
    @pytest.mark.asyncio
    async def test_streaming_parser_invalid_json(self):
        """Teste parser com JSON inválido (deve ignorar)."""
        streaming_data = [
            "data: {\"token\": \"Hello\"}\n\n",
            "data: invalid json\n\n",
            "data: {\"token\": \" World\"}\n\n",
            "data: [DONE]\n\n"
        ]
        
        async def mock_response():
            for chunk in streaming_data:
                yield chunk.encode('utf-8')
        
        parser = StreamingParser()
        tokens = []
        
        async for token in parser.parse_stream(mock_response()):
            tokens.append(token)
        
        # JSON inválido deve ser ignorado
        assert tokens == ["Hello", " World"]
    
    @pytest.mark.asyncio
    async def test_streaming_parser_partial_chunks(self):
        """Teste parser com chunks parciais."""
        # Simular chunks que chegam parcialmente
        streaming_data = [
            "data: {\"tok",  # Chunk parcial
            "en\": \"Hello\"}\n\n",  # Completar chunk
            "data: {\"token\": \" World\"}\n\n",
            "data: [DONE]\n\n"
        ]
        
        async def mock_response():
            for chunk in streaming_data:
                yield chunk.encode('utf-8')
        
        parser = StreamingParser()
        tokens = []
        
        async for token in parser.parse_stream(mock_response()):
            tokens.append(token)
        
        assert tokens == ["Hello", " World"]
    
    @pytest.mark.asyncio
    async def test_streaming_parser_empty_response(self):
        """Teste parser com resposta vazia."""
        async def mock_response():
            if False:  # Nunca executa
                yield b""
        
        parser = StreamingParser()
        tokens = []
        
        async for token in parser.parse_stream(mock_response()):
            tokens.append(token)
        
        assert tokens == []


class TestMessageValidator:
    """Testes para validador de mensagens."""
    
    def test_message_validator_valid_message(self):
        """Teste validação de mensagem válida."""
        validator = MessageValidator()
        
        # Não deve lançar exceção
        validator.validate_message("Hello, how are you?")
    
    def test_message_validator_empty_message(self):
        """Teste validação de mensagem vazia."""
        validator = MessageValidator()
        
        with pytest.raises(ValidationError, match="Message cannot be empty"):
            validator.validate_message("")
        
        with pytest.raises(ValidationError, match="Message cannot be empty"):
            validator.validate_message("   ")  # Apenas espaços
    
    def test_message_validator_message_too_long(self):
        """Teste validação de mensagem muito longa."""
        validator = MessageValidator(max_length=100)
        
        long_message = "x" * 101
        
        with pytest.raises(ValidationError, match="Message too long"):
            validator.validate_message(long_message)
    
    def test_message_validator_suspicious_content(self):
        """Teste validação de conteúdo suspeito."""
        validator = MessageValidator()
        
        suspicious_messages = [
            "<script>alert('xss')</script>",
            "javascript:void(0)",
            "eval(malicious_code)",
            "SELECT * FROM users"
        ]
        
        for message in suspicious_messages:
            with pytest.raises(ValidationError, match="Suspicious content detected"):
                validator.validate_message(message)
    
    def test_message_validator_valid_code_content(self):
        """Teste que código legítimo não é bloqueado."""
        validator = MessageValidator()
        
        legitimate_code = """
        Write a Python function:
        ```python
        def hello():
            print("Hello World")
        ```
        """
        
        # Não deve lançar exceção
        validator.validate_message(legitimate_code)
    
    def test_message_validator_agent_id(self):
        """Teste validação de ID do agente."""
        validator = MessageValidator()
        
        # IDs válidos
        valid_ids = [
            "550e8400-e29b-41d4-a716-446655440000",  # UUID
            "agent-123",
            "general_assistant",
            "code-helper-v2"
        ]
        
        for agent_id in valid_ids:
            validator.validate_agent_id(agent_id)  # Não deve lançar exceção
        
        # IDs inválidos
        invalid_ids = [
            "",
            "invalid/id",
            "id with spaces",
            "id@with#symbols",
            "x" * 100  # Muito longo
        ]
        
        for agent_id in invalid_ids:
            with pytest.raises(ValidationError):
                validator.validate_agent_id(agent_id)


class TestFileValidator:
    """Testes para validador de arquivos."""
    
    def test_file_validator_valid_file(self, sample_pdf_file):
        """Teste validação de arquivo válido."""
        validator = FileValidator()
        
        # Não deve lançar exceção
        validator.validate_file(str(sample_pdf_file))
    
    def test_file_validator_file_not_found(self):
        """Teste validação de arquivo não encontrado."""
        validator = FileValidator()
        
        with pytest.raises(FileNotFoundError):
            validator.validate_file("nonexistent_file.pdf")
    
    def test_file_validator_file_too_large(self, tmp_path):
        """Teste validação de arquivo muito grande."""
        validator = FileValidator(max_size=1024)  # 1KB máximo
        
        large_file = tmp_path / "large_file.txt"
        large_file.write_text("x" * 2048)  # 2KB
        
        with pytest.raises(ValidationError, match="File too large"):
            validator.validate_file(str(large_file))
    
    def test_file_validator_unsupported_type(self, tmp_path):
        """Teste validação de tipo não suportado."""
        validator = FileValidator(
            allowed_types=[".pdf", ".txt", ".docx"]
        )
        
        exe_file = tmp_path / "malware.exe"
        exe_file.write_bytes(b"fake executable")
        
        with pytest.raises(ValidationError, match="Unsupported file type"):
            validator.validate_file(str(exe_file))
    
    def test_file_validator_supported_types(self, tmp_path):
        """Teste validação de tipos suportados."""
        validator = FileValidator(
            allowed_types=[".pdf", ".txt", ".docx", ".jpg", ".png"]
        )
        
        supported_files = ["doc.pdf", "note.txt", "report.docx", "image.jpg", "chart.png"]
        
        for filename in supported_files:
            file_path = tmp_path / filename
            file_path.write_bytes(b"test content")
            
            # Não deve lançar exceção
            validator.validate_file(str(file_path))
    
    def test_file_validator_empty_file(self, tmp_path):
        """Teste validação de arquivo vazio."""
        validator = FileValidator(min_size=1)
        
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")
        
        with pytest.raises(ValidationError, match="File is empty"):
            validator.validate_file(str(empty_file))
    
    def test_file_validator_content_validation(self, tmp_path):
        """Teste validação de conteúdo do arquivo."""
        validator = FileValidator()
        
        # Arquivo com conteúdo malicioso simulado
        malicious_file = tmp_path / "malicious.txt"
        malicious_file.write_text("<script>alert('xss')</script>")
        
        with pytest.raises(ValidationError, match="Potentially malicious content"):
            validator.validate_file(str(malicious_file))
    
    def test_file_validator_batch_validation(self, tmp_path):
        """Teste validação em lote."""
        validator = FileValidator()
        
        # Criar vários arquivos válidos
        files = []
        for i in range(3):
            file_path = tmp_path / f"file_{i}.txt"
            file_path.write_text(f"Content of file {i}")
            files.append(str(file_path))
        
        # Validação em lote não deve lançar exceção
        validator.validate_files(files)
        
        # Adicionar arquivo inválido
        invalid_file = tmp_path / "invalid.exe"
        invalid_file.write_bytes(b"invalid content")
        files.append(str(invalid_file))
        
        # Deve lançar exceção para arquivo inválido
        with pytest.raises(ValidationError):
            validator.validate_files(files) 