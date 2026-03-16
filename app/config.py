from typing import Optional

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

    # ── Facebook (Graph API) ───────────────────────────────────────────────────
    # Page Access Token with pages_manage_posts + pages_read_engagement scopes
    facebook_access_token: Optional[str] = None
    facebook_page_id: Optional[str] = None

    # ── Twitter / X (OAuth 1.0a) ───────────────────────────────────────────────
    twitter_api_key: Optional[str] = None
    twitter_api_secret: Optional[str] = None
    twitter_access_token: Optional[str] = None
    twitter_access_token_secret: Optional[str] = None

    # ── Instagram (Graph API via Facebook) ────────────────────────────────────
    # Instagram Business / Creator Account ID + access token
    # Requires instagram_basic + instagram_content_publish permissions
    instagram_access_token: Optional[str] = None
    instagram_account_id: Optional[str] = None

    # ── Google Business Profile (My Business API v4) ──────────────────────────
    # Short-lived OAuth 2.0 bearer token — obtain via Google OAuth Playground
    # Scope: https://www.googleapis.com/auth/business.manage
    google_business_access_token: Optional[str] = None
    google_business_account_id: Optional[str] = None   # accounts/{id}
    google_business_location_id: Optional[str] = None  # locations/{id}


settings = Settings()
