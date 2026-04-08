import httpx
import logging
from typing import AsyncGenerator
from dataclasses import dataclass

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    provider: str  # "openrouter" or "ollama"
    model: str
    success: bool
    error: str | None = None


class LLMRouter:
    """Routes LLM requests to OpenRouter (primary) with Ollama fallback."""
    
    def __init__(self):
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
        self.ollama_url = f"{settings.ollama_host}/api/chat"
        self.timeout = httpx.Timeout(60.0, connect=10.0)
    
    async def chat(self, messages: list[dict], system_prompt: str | None = None) -> LLMResponse:
        """Send chat request, trying OpenRouter first, then Ollama fallback."""
        
        # Prepare messages with system prompt
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)
        
        # Try OpenRouter first
        response = await self._call_openrouter(full_messages)
        if response.success:
            return response
        
        logger.warning(f"OpenRouter failed: {response.error}. Falling back to Ollama.")
        
        # Fallback to Ollama
        return await self._call_ollama(full_messages)
    
    async def _call_openrouter(self, messages: list[dict]) -> LLMResponse:
        """Call OpenRouter API."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.openrouter_url,
                    headers={
                        "Authorization": f"Bearer {settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/openclaw",
                        "X-Title": "OpenClaw Assistant"
                    },
                    json={
                        "model": settings.openrouter_model,
                        "messages": messages,
                        "max_tokens": 2048,
                        "temperature": 0.7
                    }
                )
                
                if response.status_code != 200:
                    error_text = response.text
                    return LLMResponse(
                        content="",
                        provider="openrouter",
                        model=settings.openrouter_model,
                        success=False,
                        error=f"HTTP {response.status_code}: {error_text}"
                    )
                
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                return LLMResponse(
                    content=content,
                    provider="openrouter",
                    model=settings.openrouter_model,
                    success=True
                )
                
        except Exception as e:
            return LLMResponse(
                content="",
                provider="openrouter",
                model=settings.openrouter_model,
                success=False,
                error=str(e)
            )
    
    async def _call_ollama(self, messages: list[dict]) -> LLMResponse:
        """Call local Ollama instance."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.ollama_url,
                    json={
                        "model": settings.ollama_model,
                        "messages": messages,
                        "stream": False
                    }
                )
                
                if response.status_code != 200:
                    return LLMResponse(
                        content="",
                        provider="ollama",
                        model=settings.ollama_model,
                        success=False,
                        error=f"HTTP {response.status_code}: {response.text}"
                    )
                
                data = response.json()
                content = data["message"]["content"]
                
                return LLMResponse(
                    content=content,
                    provider="ollama",
                    model=settings.ollama_model,
                    success=True
                )
                
        except Exception as e:
            return LLMResponse(
                content="",
                provider="ollama",
                model=settings.ollama_model,
                success=False,
                error=str(e)
            )
    
    async def health_check(self) -> dict:
        """Check health of both LLM providers."""
        results = {
            "openrouter": False,
            "ollama": False
        }
        
        # Check OpenRouter
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {settings.openrouter_api_key}"}
                )
                results["openrouter"] = response.status_code == 200
        except:
            pass
        
        # Check Ollama
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{settings.ollama_host}/api/tags")
                results["ollama"] = response.status_code == 200
        except:
            pass
        
        return results


# Global router instance
router = LLMRouter()
