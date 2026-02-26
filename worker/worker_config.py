from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    celery_broker_url: str
    celery_result_backend: str

    pushgateway_url: str = "http://pushgateway:9091"


settings = Settings()
