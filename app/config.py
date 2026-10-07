from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+aiomysql://lex_user:your_password@localhost/lex_tabularum"
    SECRET_KEY: str = "change-this-to-a-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12   # 12 hours

    # GitLab (for later)
    GITLAB_URL: str = "https://gitlab.yourdomain.local"
    GITLAB_TOKEN: str = ""
    GITLAB_PROJECT_ID: int = 0

    class Config:
        env_file = ".env"

settings = Settings()
