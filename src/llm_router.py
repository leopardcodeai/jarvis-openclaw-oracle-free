import base64
import httpx
import logging
from typing import AsyncGenerator
from dataclasses import dataclass

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    provider: str  # "gemini", "openrouter" or "ollama"
    model: str
    success: bool
    error: str | None = None


class LLMRouter:
    """Routes LLM requests: Gemini (primary) -> OpenRouter -> Ollama (fallback)."""
    
    def __init__(self):
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
        self.ollama_url = f"{settings.ollama_host}/api/chat"
        self.timeout = httpx.Timeout(60.0, connect=10.0)
    
    async def chat(self, messages: list[dict], system_prompt: str | None = None) -> LLMResponse:
        """Send chat request: Gemini -> OpenRouter -> Ollama fallback chain."""
        
        # Prepare messages with system prompt
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)
        
        # Try Gemini first (if configured)
        if settings.gemini_api_key:
            response = await self._call_gemini(full_messages, system_prompt)
            if response.success:
                return response
            logger.warning(f"Gemini failed: {response.error}. Trying OpenRouter.")
        
        # Try OpenRouter
        response = await self._call_openrouter(full_messages)
        if response.success:
            return response
        
        logger.warning(f"OpenRouter failed: {response.error}. Falling back to Ollama.")
        
        # Fallback to Ollama
        return await self._call_ollama(full_messages)
    
    async def _call_gemini(self, messages: list[dict], system_prompt: str | None = None) -> LLMResponse:
        """Call Google Gemini API."""
        try:
            # Convert messages to Gemini format
            contents = []
            for msg in messages:
                if msg["role"] == "system":
                    continue  # System prompt handled separately
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})
            
            url = f"{self.gemini_url}/{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
            
            payload = {"contents": contents}
            if system_prompt:
                payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                
                if response.status_code != 200:
                    return LLMResponse(
                        content="",
                        provider="gemini",
                        model=settings.gemini_model,
                        success=False,
                        error=f"HTTP {response.status_code}: {response.text}"
                    )
                
                data = response.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                
                return LLMResponse(
                    content=content,
                    provider="gemini",
                    model=settings.gemini_model,
                    success=True
                )
                
        except Exception as e:
            return LLMResponse(
                content="",
                provider="gemini",
                model=settings.gemini_model,
                success=False,
                error=str(e)
            )
    
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
    
    async def chat_with_vision(
        self,
        prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Send a vision request with an image. Uses Gemini first, then OpenRouter."""
        b64 = base64.b64encode(image_bytes).decode()

        # Try Gemini (best vision support)
        if settings.gemini_api_key:
            response = await self._call_gemini_vision(prompt, b64, mime_type, system_prompt)
            if response.success:
                return response
            logger.warning(f"Gemini vision failed: {response.error}. Trying OpenRouter.")

        # Fallback: OpenRouter with a vision-capable model
        return await self._call_openrouter_vision(prompt, b64, mime_type, system_prompt)

    async def _call_gemini_vision(
        self, prompt: str, b64: str, mime_type: str, system_prompt: str | None
    ) -> LLMResponse:
        try:
            url = f"{self.gemini_url}/{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
            payload = {
                "contents": [{
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime_type, "data": b64}},
                    ]
                }]
            }
            if system_prompt:
                payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                return LLMResponse("", "gemini", settings.gemini_model, False,
                                   f"HTTP {resp.status_code}: {resp.text[:200]}")
            content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return LLMResponse(content, "gemini", settings.gemini_model, True)
        except Exception as e:
            return LLMResponse("", "gemini", settings.gemini_model, False, str(e))

    async def _call_openrouter_vision(
        self, prompt: str, b64: str, mime_type: str, system_prompt: str | None
    ) -> LLMResponse:
        """OpenRouter vision via a free vision-capable model."""
        vision_model = "google/gemini-2.0-flash-exp:free"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
            ]
        })
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    self.openrouter_url,
                    headers={
                        "Authorization": f"Bearer {settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/openclaw",
                        "X-Title": "OpenClaw Assistant",
                    },
                    json={"model": vision_model, "messages": messages, "max_tokens": 1024},
                )
            if resp.status_code != 200:
                return LLMResponse("", "openrouter", vision_model, False,
                                   f"HTTP {resp.status_code}: {resp.text[:200]}")
            content = resp.json()["choices"][0]["message"]["content"]
            return LLMResponse(content, "openrouter", vision_model, True)
        except Exception as e:
            return LLMResponse("", "openrouter", vision_model, False, str(e))

    async def health_check(self) -> dict:
        """Check health of all LLM providers."""
        results = {
            "gemini": False,
            "openrouter": False,
            "ollama": False
        }
        
        # Check Gemini
        if settings.gemini_api_key:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                    url = f"{self.gemini_url}?key={settings.gemini_api_key}"
                    response = await client.get(url)
                    results["gemini"] = response.status_code == 200
            except:
                pass
        
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
