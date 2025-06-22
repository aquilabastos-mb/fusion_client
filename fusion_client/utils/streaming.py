"""Streaming utilities for Server-Sent Events."""

import asyncio
import json
import re
from typing import AsyncIterator, Optional, Dict, Any
import httpx


class StreamingParser:
    """Parser for Server-Sent Events (SSE) streams."""
    
    def __init__(self):
        self.buffer = ""
        self.event_pattern = re.compile(r'^([^:]+):(.*)$', re.MULTILINE)
    
    async def parse_stream(
        self, 
        response: httpx.Response
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Parse SSE stream and yield events.
        
        Args:
            response: HTTPX response with streaming content
            
        Yields:
            Parsed SSE events as dictionaries
        """
        async for chunk in response.aiter_bytes():
            try:
                chunk_str = chunk.decode('utf-8')
                self.buffer += chunk_str
                
                # Process complete lines
                while '\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\n', 1)
                    line = line.rstrip('\r')
                    
                    if not line:  # Empty line indicates end of event
                        continue
                    
                    # Parse SSE event
                    event = self._parse_event_line(line)
                    if event:
                        yield event
                        
            except UnicodeDecodeError:
                # Skip invalid chunks
                continue
    
    def _parse_event_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single SSE event line."""
        if line.startswith('data: '):
            data = line[6:]  # Remove 'data: ' prefix
            
            # Handle special SSE termination
            if data.strip() == '[DONE]':
                return {"type": "done"}
            
            # Try to parse as JSON
            try:
                parsed_data = json.loads(data)
                return {
                    "type": "data",
                    "data": parsed_data
                }
            except json.JSONDecodeError:
                # Return as plain text if not JSON
                return {
                    "type": "data", 
                    "data": data
                }
        
        elif line.startswith('event: '):
            return {
                "type": "event",
                "event": line[7:]  # Remove 'event: ' prefix
            }
        
        elif line.startswith('id: '):
            return {
                "type": "id",
                "id": line[4:]  # Remove 'id: ' prefix
            }
        
        elif line.startswith('retry: '):
            try:
                retry_ms = int(line[7:])
                return {
                    "type": "retry",
                    "retry": retry_ms
                }
            except ValueError:
                pass
        
        return None


class TokenStreamer:
    """Stream tokens from Fusion API responses."""
    
    def __init__(self, parser: Optional[StreamingParser] = None):
        self.parser = parser or StreamingParser()
        self.tokens_received = 0
        self.total_response = ""
    
    async def stream_tokens(
        self, 
        response: httpx.Response
    ) -> AsyncIterator[str]:
        """
        Stream individual tokens from API response.
        
        Args:
            response: HTTPX streaming response
            
        Yields:
            Individual tokens as strings
        """
        async for event in self.parser.parse_stream(response):
            if event.get("type") == "done":
                break
            
            if event.get("type") == "data":
                token = self._extract_token(event["data"])
                if token:
                    self.tokens_received += 1
                    self.total_response += token
                    yield token
    
    def _extract_token(self, data: Any) -> Optional[str]:
        """Extract token from event data."""
        if isinstance(data, dict):
            # Common patterns for token extraction
            token_fields = ["token", "content", "text", "delta", "message"]
            
            for field in token_fields:
                if field in data:
                    token_data = data[field]
                    if isinstance(token_data, str):
                        return token_data
                    elif isinstance(token_data, dict) and "content" in token_data:
                        return token_data["content"]
        
        elif isinstance(data, str):
            return data
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get streaming statistics."""
        return {
            "tokens_received": self.tokens_received,
            "total_length": len(self.total_response),
            "average_token_length": len(self.total_response) / max(self.tokens_received, 1)
        }
    
    def reset(self) -> None:
        """Reset streaming state."""
        self.tokens_received = 0
        self.total_response = ""


class StreamBuffer:
    """Buffer for managing streaming data with backpressure."""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.buffer: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self.closed = False
    
    async def put(self, item: Any) -> None:
        """Add item to buffer."""
        if not self.closed:
            await self.buffer.put(item)
    
    async def get(self) -> Any:
        """Get item from buffer."""
        return await self.buffer.get()
    
    async def get_all(self) -> AsyncIterator[Any]:
        """Get all items from buffer."""
        while not self.closed or not self.buffer.empty():
            try:
                item = await asyncio.wait_for(self.buffer.get(), timeout=1.0)
                yield item
            except asyncio.TimeoutError:
                if self.closed:
                    break
                continue
    
    def close(self) -> None:
        """Close the buffer."""
        self.closed = True
    
    def is_full(self) -> bool:
        """Check if buffer is full."""
        return self.buffer.full()
    
    def size(self) -> int:
        """Get current buffer size."""
        return self.buffer.qsize() 