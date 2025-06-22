"""Authentication utilities for Fusion client."""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from .exceptions import AuthenticationError


class TokenProvider:
    """Base class for token providers."""
    
    async def get_token(self) -> str:
        """Get authentication token."""
        raise NotImplementedError
    
    async def refresh_token(self) -> str:
        """Refresh authentication token."""
        raise NotImplementedError


class StaticTokenProvider(TokenProvider):
    """Token provider that returns a static token."""
    
    def __init__(self, token: str):
        self.token = token
    
    async def get_token(self) -> str:
        if not self.token:
            raise AuthenticationError("No API token provided")
        return self.token
    
    async def refresh_token(self) -> str:
        return self.token


class EnvironmentTokenProvider(TokenProvider):
    """Token provider that reads token from environment variables."""
    
    def __init__(self, env_var: str = "FUSION_API_KEY"):
        self.env_var = env_var
        self._token: Optional[str] = None
    
    async def get_token(self) -> str:
        if self._token is None:
            self._token = os.getenv(self.env_var)
        
        if not self._token:
            raise AuthenticationError(
                f"No API token found in environment variable '{self.env_var}'"
            )
        
        return self._token
    
    async def refresh_token(self) -> str:
        # Re-read from environment
        self._token = os.getenv(self.env_var)
        return await self.get_token()


class FileTokenProvider(TokenProvider):
    """Token provider that reads token from file."""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path).expanduser()
        self._token: Optional[str] = None
    
    async def get_token(self) -> str:
        if self._token is None:
            await self._load_token()
        
        if not self._token:
            raise AuthenticationError(f"No valid token found in {self.file_path}")
        
        return self._token
    
    async def refresh_token(self) -> str:
        await self._load_token()
        return await self.get_token()
    
    async def _load_token(self) -> None:
        """Load token from file."""
        if not self.file_path.exists():
            raise AuthenticationError(f"Token file not found: {self.file_path}")
        
        try:
            content = self.file_path.read_text().strip()
            
            # Try to parse as JSON (for structured token files)
            try:
                data = json.loads(content)
                self._token = data.get("api_key") or data.get("token")
            except json.JSONDecodeError:
                # Treat as plain text token
                self._token = content
                
        except Exception as e:
            raise AuthenticationError(f"Failed to read token file: {e}")


class MultiSourceTokenProvider(TokenProvider):
    """Token provider that tries multiple sources in order."""
    
    def __init__(self, providers: list[TokenProvider]):
        self.providers = providers
        self._last_successful_provider: Optional[TokenProvider] = None
    
    async def get_token(self) -> str:
        # Try last successful provider first
        if self._last_successful_provider:
            try:
                token = await self._last_successful_provider.get_token()
                return token
            except AuthenticationError:
                self._last_successful_provider = None
        
        # Try all providers
        last_error = None
        for provider in self.providers:
            try:
                token = await provider.get_token()
                self._last_successful_provider = provider
                return token
            except AuthenticationError as e:
                last_error = e
                continue
        
        raise last_error or AuthenticationError("No valid token found from any source")
    
    async def refresh_token(self) -> str:
        if self._last_successful_provider:
            try:
                return await self._last_successful_provider.refresh_token()
            except AuthenticationError:
                self._last_successful_provider = None
        
        return await self.get_token()


class FusionAuth:
    """Authentication manager for Fusion client."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        env_var: str = "FUSION_API_KEY",
        token_file: Optional[str] = None
    ):
        """
        Initialize authentication manager.
        
        Args:
            api_key: Direct API key
            env_var: Environment variable name for API key
            token_file: Path to token file
        """
        self.token_provider = self._create_token_provider(api_key, env_var, token_file)
        self._cached_token: Optional[str] = None
    
    def _create_token_provider(
        self,
        api_key: Optional[str],
        env_var: str,
        token_file: Optional[str]
    ) -> TokenProvider:
        """Create appropriate token provider based on configuration."""
        providers = []
        
        # Add direct API key provider if provided
        if api_key:
            providers.append(StaticTokenProvider(api_key))
        
        # Add environment variable provider
        providers.append(EnvironmentTokenProvider(env_var))
        
        # Add file provider if specified
        if token_file:
            providers.append(FileTokenProvider(token_file))
        
        # Add default file locations
        default_files = [
            "~/.fusion/credentials",
            "~/.config/fusion/credentials",
            ".fusion_credentials"
        ]
        
        for file_path in default_files:
            if Path(file_path).expanduser().exists():
                providers.append(FileTokenProvider(file_path))
        
        if len(providers) == 1:
            return providers[0]
        else:
            return MultiSourceTokenProvider(providers)
    
    async def get_token(self) -> str:
        """Get authentication token."""
        if self._cached_token is None:
            self._cached_token = await self.token_provider.get_token()
        return self._cached_token
    
    async def refresh_token(self) -> str:
        """Refresh authentication token."""
        self._cached_token = await self.token_provider.refresh_token()
        return self._cached_token
    
    def get_auth_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        """Get authentication headers."""
        if token is None:
            # This is synchronous, so we can't await here
            # The caller should get the token first
            raise ValueError("Token must be provided or fetched asynchronously first")
        
        return {
            "Authorization": f"Bearer {token}"
        }
    
    def is_configured(self) -> bool:
        """Check if authentication is properly configured."""
        try:
            # Try to get token synchronously by checking sources
            # This is a best-effort check and may not be 100% accurate
            if hasattr(self.token_provider, 'token') and self.token_provider.token:
                return True
            if isinstance(self.token_provider, EnvironmentTokenProvider):
                return bool(os.getenv(self.token_provider.env_var))
            if isinstance(self.token_provider, FileTokenProvider):
                return self.token_provider.file_path.exists()
            if isinstance(self.token_provider, MultiSourceTokenProvider):
                return any(
                    (isinstance(p, StaticTokenProvider) and p.token) or
                    (isinstance(p, EnvironmentTokenProvider) and os.getenv(p.env_var)) or
                    (isinstance(p, FileTokenProvider) and p.file_path.exists())
                    for p in self.token_provider.providers
                )
            return False
        except Exception:
            return False 