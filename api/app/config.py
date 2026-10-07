from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./lextabularum-dev.db"
    app_secret: str = "development-only-change-this-secret"
    public_origin: str = "http://localhost:8080"
    session_cookie_secure: bool = False
    session_hours: int = 12
    evidence_dir: Path = Path("./storage/evidence")
    max_upload_bytes: int = 10 * 1024 * 1024
    gitlab_verify_ssl: bool = False


settings = Settings()
