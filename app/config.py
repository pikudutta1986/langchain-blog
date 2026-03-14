from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Get the environment variables from the .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Gemini API (text generation via LangChain) ─────────────────────────────
    gemini_api_key: str
    gemini_text_model: str = "gemini-2.0-flash"

    # ── Vertex AI (image generation via Imagen) ────────────────────────────────
    gcp_project_id: str
    gcp_location: str = "us-central1"
    # Preferred model — agent will fall back through IMAGEN_MODEL_FALLBACKS
    # if this one is unavailable for your project
    imagen_model: str = "imagen-3.0-generate-001"


settings = Settings()
