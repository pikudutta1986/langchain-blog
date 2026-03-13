from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Gemini API ─────────────────────────────────────────────────────────────
    gemini_api_key: str
    gemini_text_model: str = "gemini-2.0-flash"
    gemini_image_model: str = "imagen-3.0-generate-002"


settings = Settings()
