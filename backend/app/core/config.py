from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    project_name: str = "mini-soar"
    database_url: str

    webhook_api_key: str = "dev-webhook-key"
    admin_api_key: str = "dev-admin-key"

    celery_broker_url: str
    celery_result_backend: str

    report_dir: str = "/data/reports"
    report_generate_pdf: bool = False


settings = Settings()
