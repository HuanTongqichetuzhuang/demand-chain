from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://dc:dc_dev_2026@localhost:5432/demand_chain"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    log_level: str = "INFO"
    worker_interval_seconds: int = 60
    smtp_host: str = "smtp.qiye.163.com"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
