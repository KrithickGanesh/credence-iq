"""FastAPI configuration loaded from environment variables."""

from __future__ import annotations

import re
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "CredenceIQ API"
    api_version: str = "1.0.0"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    exasol_host: str = "127.0.0.1"
    exasol_port: int = 8563
    exasol_user: str = "sys"
    exasol_password: str = ""
    exasol_schema: str = "CREDENCEIQ"
    exasol_pool_size: int = Field(default=3, ge=1, le=5)
    exasol_query_timeout: int = 60
    exasol_tls_verify: bool = False

    llm_provider: str = "none"
    llm_model: str = ""
    llm_timeout_seconds: float = 45.0
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_version: str = "2023-06-01"
    local_llm_base_url: str = "http://localhost:11434/v1"
    local_llm_api_key: str = "local"

    lender_name: str = "CredenceIQ Finance Ltd."
    lender_address: str = "Bandra Kurla Complex, Mumbai, Maharashtra 400051"
    lender_phone: str = "+91-22-5550-0142"
    lender_email: str = "adverse.action@credenceiq.example"

    @field_validator("exasol_schema")
    @classmethod
    def validate_schema(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", value):
            raise ValueError("EXASOL_SCHEMA must be a simple SQL identifier")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def llm_enabled(self) -> bool:
        provider = self.llm_provider.strip().lower()
        if provider in {"", "none", "template", "off"}:
            return False
        if provider == "openai":
            return bool(self.openai_api_key)
        if provider == "anthropic":
            return bool(self.anthropic_api_key)
        if provider == "local":
            return bool(self.local_llm_base_url)
        return False

    @property
    def resolved_llm_model(self) -> str:
        if self.llm_model:
            return self.llm_model
        provider = self.llm_provider.strip().lower()
        if provider == "openai":
            return "gpt-4.1-mini"
        if provider == "anthropic":
            return "claude-3-5-sonnet-latest"
        if provider == "local":
            return "llama3.1"
        return "deterministic-template"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
