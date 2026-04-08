from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str
    
    # Google Gemini (Primary LLM)
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"
    
    # OpenRouter (Secondary LLM)
    openrouter_api_key: str
    openrouter_model: str = "nvidia/nemotron-3-nano-30b-a3b:free"
    
    # Ollama (Fallback LLM)
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma4:e2b"
    
    # GitHub
    github_token: Optional[str] = None
    github_default_owner: str = "alexanderbrunker-star"

    # YouTube
    youtube_channel_id: Optional[str] = None  # e.g. UCxxxxxxxxxxxxxxxxxxxxxxxx

    # Tailscale
    tailscale_auth_key: Optional[str] = None
    tailscale_hostname: str = "jarvis-oracle"
    
    # Bot Settings
    allowed_user_ids: Optional[str] = None
    max_history_length: int = 20
    
    @property
    def allowed_users(self) -> list[int]:
        if not self.allowed_user_ids:
            return []
        return [int(uid.strip()) for uid in self.allowed_user_ids.split(",") if uid.strip()]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
