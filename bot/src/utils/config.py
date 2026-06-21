from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str

    # PostgreSQL
    DB_USER: str = "gorba"
    DB_PASS: str = "gorba_secret"
    DB_HOST: str = "postgres"
    DB_PORT: int = 5432
    DB_NAME: str = "gorba_bot"

    ADMIN_IDS: list[int]
    ADMIN_PANEL_URL: str = "https://localhost:13000"

    # Bot runtime
    BOT_MODE: str = "polling"  # polling | webhook
    WEBHOOK_HOST: str = ""
    WEBHOOK_PATH: str = "/webhook"
    WEBHOOK_SECRET: str = ""
    WEBAPP_HOST: str = "0.0.0.0"
    WEBAPP_PORT: int = 8080

    # FastAPI admin API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_SECRET_KEY: str = "change-me-in-production"
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:13000",
        "http://localhost:3000",
        "http://localhost",
    ]

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def webhook_url(self) -> str:
        return f"{self.WEBHOOK_HOST.rstrip('/')}{self.WEBHOOK_PATH}"

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")


settings = Settings()
