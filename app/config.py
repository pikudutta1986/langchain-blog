from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Gemini API ─────────────────────────────────────────────────────────────
    gemini_api_key: str
    gemini_text_model: str = "gemini-2.0-flash"      # Research + Writing agents
    gemini_image_model: str = "imagen-3.0-generate-002"  # Image agent

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
