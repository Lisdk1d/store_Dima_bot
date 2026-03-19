from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    '''
    DB_USER: str
    DB_PASS: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_ROOT_NAME: str
    '''

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
