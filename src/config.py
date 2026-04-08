from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str
    
    # OpenRouter (Primary LLM)
    openrouter_api_key: str
    openrouter_model: str = "meta-llama/llama-3.2-3b-instruct:free"
    
    # Ollama (Fallback LLM)
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma2:2b"
    
    # Bot Settings
    allowed_user_ids: Optional[str] = None
    max_history_length: int = 10
    
    @property
    def allowed_users(self) -> list[int]:
        if not self.allowed_user_ids:
            return []
        return [int(uid.strip()) for uid in self.allowed_user_ids.split(",") if uid.strip()]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
