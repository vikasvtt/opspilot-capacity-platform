from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OpsPilot"
    database_url: str = "postgresql+psycopg://opspilot:opspilot@localhost:5432/opspilot"
    jwt_secret: str = "change-this-in-production"
    access_token_minutes: int = 20
    refresh_token_days: int = 7
    bootstrap_approver_email: str | None = None
    bootstrap_approver_password: str | None = None
    bootstrap_engineer_email: str | None = None
    bootstrap_engineer_password: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"

    @field_validator("database_url", mode="before")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        # Render supplies `postgresql://`; this project uses psycopg v3.
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    model_config = SettingsConfigDict(env_file=".env", env_prefix="OPSPILOT_", extra="ignore")


settings = Settings()
