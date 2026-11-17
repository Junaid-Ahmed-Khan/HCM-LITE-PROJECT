
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    EnvSettingsSource,
    DotEnvSettingsSource,
)


class Settings(BaseSettings):
        # Groq AI
    groq_api_key: SecretStr = Field(default=SecretStr(""))
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"
    """Centralized, validated application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        class CustomEnvSettingsSource(EnvSettingsSource):
            def prepare_field_value(
                self, field_name, field, field_value, value_is_complex
            ):
                if field_name == "cors_origins":
                    return field_value
                return super().prepare_field_value(
                    field_name, field, field_value, value_is_complex
                )

        class CustomDotEnvSettingsSource(DotEnvSettingsSource):
            def prepare_field_value(
                self, field_name, field, field_value, value_is_complex
            ):
                if field_name == "cors_origins":
                    return field_value
                return super().prepare_field_value(
                    field_name, field, field_value, value_is_complex
                )

        return (
            init_settings,
            CustomEnvSettingsSource(settings_cls),
            CustomDotEnvSettingsSource(settings_cls),
            file_secret_settings,
        )

    # Application
    app_name: str = "HCM Lite"
    app_env: Literal["development", "testing", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # JWT
    secret_key: SecretStr = Field(
        default=SecretStr(""),
        description="Strong random secret used to sign JWTs.",
    )
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=15, ge=1, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=90)

    # MongoDB
    mongodb_uri: SecretStr = Field(
        default=SecretStr("mongodb://localhost:27017")
    )
    mongodb_database: str = "hcm_lite"

    # CORS
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # OpenAI
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    openai_model: str = "gpt-4.1-mini"

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value.startswith("/"):
            raise ValueError("API_V1_PREFIX must start with '/'.")
        return value

    @field_validator("mongodb_database")
    @classmethod
    def validate_database_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("MONGODB_DATABASE cannot be empty.")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            value = value.strip()

            if value.startswith("["):
                import json
                value = json.loads(value)
            else:
                value = value.split(",")

        if isinstance(value, list):
            return [
                str(origin).strip().rstrip("/")
                for origin in value
                if str(origin).strip()
            ]

        return value

    def validate_runtime_configuration(self) -> None:
        """Reject unsafe configuration before serving requests."""

        if self.app_env == "production":
            if self.debug:
                raise ValueError("DEBUG must be false in production.")

            secret = self.secret_key.get_secret_value()
            if len(secret) < 32 or secret == (
                "replace-with-a-long-random-secret-before-use"
            ):
                raise ValueError(
                    "Production SECRET_KEY must be a strong, "
                    "random secret of at least 32 characters."
                )

            if any(
                origin.startswith("http://")
                for origin in self.cors_origins
            ):
                raise ValueError(
                    "Production CORS origins must use HTTPS."
                )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()


settings = get_settings()
