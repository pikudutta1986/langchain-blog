from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── textgen microservice (wraps Ollama) ────────────────────────────────────
    textgen_url: str = "http://textgen:8000"
    research_model: str = "llama3.2"   # model used by the Research Agent
    writing_model: str = "mistral"     # model used by the Writing Agent

    # ── imagegen microservice (Stable Diffusion) ───────────────────────────────
    imagegen_url: str = "http://imagegen:8001"

    # ── MySQL ──────────────────────────────────────────────────────────────────
    mysql_host: str = "mysql"
    mysql_port: int = 3306
    mysql_database: str = "blog_db"
    mysql_user: str = "blog_user"
    mysql_password: str = "blog_password"

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )


settings = Settings()
