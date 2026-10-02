from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    database_url: str = "postgresql+psycopg://notetaker:notetaker@localhost:5432/notetaker"
    frontend_origin: str = "http://localhost:3000"
    public_api_url: str = "http://localhost:8000"
    webhook_secret: str = "change-me"
    meetingbaas_api_key: str = ""
    assemblyai_api_key: str = ""
    llm_provider: str = "ollama"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    read_only: bool = False  # blocks creating/deleting meetings on a public demo


settings = Settings()
