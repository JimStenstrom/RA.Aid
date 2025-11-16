"""Configuration management for vLLama."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Server config
    host: str = "0.0.0.0"
    port: int = 11434  # Ollama default port

    # vLLM backend
    vllm_url: str = "http://localhost:8000"
    vllm_api_key: str | None = None

    # Model defaults
    default_model: str = "meta-llama/Llama-3-8B"

    class Config:
        env_prefix = "VLLAMA_"
        env_file = ".env"


settings = Settings()
