"""Load the common working-directory .env without mutating process environment."""

from typing import Literal

from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class _EnvironmentSettings(BaseSettings):
    """Keep dotenv loading, secret handling, and environment precedence in utils."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )


class Settings(_EnvironmentSettings):
    """Listener, downstream services, and the explicitly selected routing model type."""

    model_config = SettingsConfigDict(env_prefix="DECK_ROUTER_")

    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=8000, ge=1, le=65535)
    public_url: HttpUrl = HttpUrl("http://localhost:8000")
    creator_url: HttpUrl | None = None
    editor_url: HttpUrl | None = None
    request_timeout: float = Field(default=120, gt=0, le=600)
    selector: Literal["decision", "llm"] = "decision"

    @field_validator("creator_url", "editor_url", mode="before")
    @classmethod
    def allow_unconfigured_endpoint(cls, value: object) -> object:
        """Allow empty dotenv placeholders without silently routing elsewhere."""
        return None if value == "" else value

    @field_validator("public_url")
    @classmethod
    def validate_public_origin(cls, value: HttpUrl) -> HttpUrl:
        """Reject URLs that do not identify this service's root endpoint."""
        if (
            value.username is not None
            or value.password is not None
            or value.path not in (None, "/")
            or value.query is not None
            or value.fragment is not None
        ):
            raise ValueError("public_url must be an HTTP(S) origin without credentials or a path")
        return value


class AzureSettings(_EnvironmentSettings):
    """GPT-style Azure deployments used by the general-purpose LLM client."""

    model_config = SettingsConfigDict(env_prefix="AZURE_OPENAI_")

    endpoint: HttpUrl | None = None
    api_key: SecretStr | None = None
    deployment: str = ""
    api_version: str = "2024-10-21"
    timeout: float = Field(default=60, gt=0, le=600)

    @field_validator("endpoint", mode="before")
    @classmethod
    def allow_unconfigured_endpoint(cls, value: object) -> object:
        """Let the service start for health checks before Azure is configured."""
        return None if value == "" else value


class DecisionSettings(_EnvironmentSettings):
    """Decision-family model connection settings, independent of routing policy."""

    model_config = SettingsConfigDict(env_prefix="DECISION_", populate_by_name=True)

    endpoint: HttpUrl | None = Field(default=None, validation_alias="AZURE_DECISION_ENDPOINT")
    api_key: SecretStr | None = None
    model: str = "Decision-1"
    timeout: float = Field(default=60, gt=0, le=600)

    @field_validator("endpoint", mode="before")
    @classmethod
    def allow_unconfigured_endpoint(cls, value: object) -> object:
        """Allow startup before a Decision endpoint is configured."""
        return None if value == "" else value
