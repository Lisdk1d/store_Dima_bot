from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Known insecure placeholder values that must never reach production.
_INSECURE_API_KEYS = {"", "change-me-in-production"}
_INSECURE_DB_PASSWORDS = {"", "gorba_secret"}
_MIN_API_KEY_LENGTH = 16


class Settings(BaseSettings):
    # Deployment environment. "production" (default) enforces strict secret
    # hygiene; set ENV=development for local runs with placeholder secrets.
    ENV: str = "production"

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
    # Admin panel auth: "initdata" (Telegram WebApp, default) | "devkey" (dev only).
    ADMIN_AUTH_MODE: str = "initdata"
    # Max age of Telegram WebApp initData accepted by the API (anti-replay).
    INIT_DATA_MAX_AGE: int = 86400
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

    @property
    def is_production(self) -> bool:
        return self.ENV.strip().lower() in {"production", "prod"}

    def webhook_preconditions(self) -> list[str]:
        """Blocking config errors for webhook mode (empty when OK).

        A webhook without a secret token lets anyone POST forged updates to the
        public /webhook path, so the secret is mandatory in webhook mode.
        """
        errors: list[str] = []
        if self.BOT_MODE.strip().lower() == "webhook":
            if not self.WEBHOOK_HOST:
                errors.append("WEBHOOK_HOST is required for webhook mode")
            if not self.WEBHOOK_SECRET:
                errors.append("WEBHOOK_SECRET must be set (non-empty) for webhook mode")
        return errors

    @model_validator(mode="after")
    def _enforce_secret_hygiene(self) -> "Settings":
        """Refuse to start in production with empty, default, or weak secrets.

        Real user-supplied values are never rejected — only the known
        placeholders, empty strings, or too-short keys. Set ENV=development
        to bypass for local runs.
        """
        auth_mode = self.ADMIN_AUTH_MODE.strip().lower()
        if auth_mode not in {"initdata", "devkey"}:
            raise ValueError("ADMIN_AUTH_MODE must be 'initdata' or 'devkey'")

        if not self.is_production:
            return self

        problems: list[str] = []
        if auth_mode == "devkey":
            problems.append("ADMIN_AUTH_MODE=devkey is not allowed in production (use initdata)")
        if self.DB_PASS in _INSECURE_DB_PASSWORDS:
            problems.append("DB_PASS is empty or a known default; set a strong unique password")
        if self.API_SECRET_KEY in _INSECURE_API_KEYS:
            problems.append("API_SECRET_KEY is empty or the placeholder; generate a strong random key")
        elif len(self.API_SECRET_KEY) < _MIN_API_KEY_LENGTH:
            problems.append(f"API_SECRET_KEY is too short (min {_MIN_API_KEY_LENGTH} chars)")

        if problems:
            raise ValueError(
                "Insecure configuration for ENV=production: "
                + "; ".join(problems)
                + ". (Set ENV=development for local runs with placeholder secrets.)"
            )
        return self

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")


settings = Settings()
