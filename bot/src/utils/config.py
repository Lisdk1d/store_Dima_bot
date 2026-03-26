from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str

    DB_USER: str
    DB_PASS: str
    DB_NAME: str
    MONGO_URL: str
    ADMIN_IDS: list[int]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
