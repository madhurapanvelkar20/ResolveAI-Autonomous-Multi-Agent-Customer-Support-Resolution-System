
"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Provider = Literal["groq", "gemini", "ollama"]
ToolTransport = Literal["direct", "n8n"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "ResolveAI"
    app_version: str = "0.1.0"
    environment: str = "development"

    llm_provider_order: Annotated[list[Provider], NoDecode] = Field(
        default_factory=lambda: ["groq", "gemini", "ollama"]
    )

    groq_api_key: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")
    ollama_api_key: SecretStr = SecretStr("")

    groq_base_url: str = "https://api.groq.com/openai/v1"
    gemini_base_url: str = (
        "https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    ollama_base_url: str = "http://localhost:11434/v1"

    groq_model: str = ""
    gemini_model: str = ""
    ollama_model: str = ""

    llm_timeout_seconds: float = Field(default=30, gt=0, le=300)
    llm_max_retries: int = Field(default=2, ge=0, le=10)
    max_iterations: int = Field(default=12, ge=1, le=100)
    max_tool_calls: int = Field(default=20, ge=1, le=500)
    max_case_wall_time_seconds: float = Field(
        default=120, gt=0, le=3600
    )
    max_refund_amount: float = Field(default=1000.00, ge=0)

    trace_dir: str = "traces"
    tool_transport: ToolTransport = "direct"
    database_path: str = "data/resolveai.db"
    chroma_dir: str = "data/chroma"
    policy_dir: str = "docs/policies"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    rag_top_k: int = Field(default=3, ge=1, le=20)
    rag_relevance_threshold: float = Field(default=0.25, ge=0.0, le=1.0)

    @field_validator("llm_provider_order", mode="before")
    @classmethod
    def parse_provider_order(cls, value):
        if isinstance(value, str):
            return [
                item.strip().lower()
                for item in value.split(",")
                if item.strip()
            ]
        return value

    @field_validator("llm_provider_order")
    @classmethod
    def require_provider(cls, value):
        if not value:
            raise ValueError("At least one LLM provider is required")
        if len(value) != len(set(value)):
            raise ValueError("Provider order cannot contain duplicates")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
