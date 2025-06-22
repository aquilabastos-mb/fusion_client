"""Configuration settings for Fusion client."""

from typing import Optional
from pydantic_settings import BaseSettings


class FusionSettings(BaseSettings):
    """Configuration settings for the Fusion client."""
    
    # API Configuration
    fusion_api_key: str = ""
    fusion_base_url: str = "https://fusion.mb-common.mercadolitecoin.com.br/api"
    fusion_timeout: float = 30.0
    fusion_max_retries: int = 3
    
    # Cache Configuration  
    cache_enabled: bool = True
    cache_ttl: int = 300  # 5 minutes
    cache_max_size: int = 1000
    
    # Rate Limiting
    rate_limit_calls: int = 100
    rate_limit_window: int = 60  # seconds
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Observability
    enable_tracing: bool = False
    jaeger_endpoint: Optional[str] = None
    
    # Security
    max_message_length: int = 10000
    allowed_file_types: list[str] = [
        "txt", "pdf", "doc", "docx", "md", "csv", "json", "xml"
    ]
    max_file_size_mb: int = 10
    
    class Config:
        env_file = ".env"
        env_prefix = "FUSION_"
        case_sensitive = False 