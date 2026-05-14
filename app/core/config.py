from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_title: str = "IntelliTicket API"
    database_url: str

    secret_key: str
    access_token_expire_minutes: int = 60

    service_manager_email: str
    service_manager_password: str
    service_manager_full_name: str = "Менеджер сервисного обслуживания"

    frontend_url: str = "http://localhost:3000"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "hf.co/NidAll/supergemma4-e4b-abliterated-Q4_K_M-GGUF:Q4_K_M"

    ticket_auto_close_hours: int = 24
    ticket_auto_close_interval_minutes: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()