"""
Google Business Agent
- Posts a Standard Local Post to a Google Business Profile location
- Includes title (summary), a "Learn More" call-to-action pointing at the blog link,
  and optionally a header photo via a public image URL
- Authentication uses a short-lived OAuth 2.0 access token stored in the environment.
  Obtain one via the Google OAuth Playground or your own OAuth flow with the scope:
  https://www.googleapis.com/auth/business.manage
- API reference:
  https://developers.google.com/my-business/reference/rest/v4/accounts.locations.localPosts
"""
import logging

import requests

from config import settings

logger = logging.getLogger(__name__)

_API_BASE = "https://mybusiness.googleapis.com/v4"
_MAX_SUMMARY = 1500  # Google Business summary character limit


class GoogleBusinessAgent:
    """Post blog content (summary + CTA + optional image) to a Google Business Profile."""

    def __init__(self) -> None:
        self.access_token = settings.google_business_access_token
        self.account_id = settings.google_business_account_id
        self.location_id = settings.google_business_location_id

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _build_summary(self, title: str, link: str) -> str:
        """Compose the post summary (max 1500 chars)."""
        summary = f"{title}\n\n{link}"
        if len(summary) > _MAX_SUMMARY:
            max_title = _MAX_SUMMARY - len(link) - 2
            title = title[: max(0, max_title - 1)] + "…"
            summary = f"{title}\n\n{link}"
        return summary

    def _build_payload(self, title: str, link: str, image_url: str) -> dict:
        """Build the localPosts request body."""
        payload: dict = {
            "languageCode": "en-US",
            "summary": self._build_summary(title, link),
            "callToAction": {
                "actionType": "LEARN_MORE",
                "url": link,
            },
            "topicType": "STANDARD",
        }
        if image_url:
            payload["media"] = [
                {
                    "mediaFormat": "PHOTO",
                    "sourceUrl": image_url,
                }
            ]
        return payload

    def _post_url(self) -> str:
        return (
            f"{_API_BASE}/accounts/{self.account_id}"
            f"/locations/{self.location_id}/localPosts"
        )

    # ── Main entry point ───────────────────────────────────────────────────────

    def run(
        self,
        title: str,
        image_path: str,
        link: str,
        image_url: str = "",
    ) -> dict:
        """
        Post to Google Business Profile.

        Args:
            title:      Blog post title used as the post summary header.
            image_path: Local path — not used directly; Google Business requires a
                        public image URL. Pass image_url instead.
            link:       Public URL to the blog post; used as the CTA destination.
            image_url:  Optional publicly accessible HTTPS URL of the header image
                        (e.g. from your WordPress media library). Omit to post
                        text + CTA only.

        Returns:
            dict with keys: platform, success, post_name, post_url, error (on failure).
        """
        missing = [
            k
            for k, v in {
                "GOOGLE_BUSINESS_ACCESS_TOKEN": self.access_token,
                "GOOGLE_BUSINESS_ACCOUNT_ID": self.account_id,
                "GOOGLE_BUSINESS_LOCATION_ID": self.location_id,
            }.items()
            if not v
        ]
        if missing:
            msg = f"Missing Google Business credentials: {', '.join(missing)}"
            logger.error(f"[GoogleBusiness] {msg}")
            return {"platform": "google_business", "success": False, "error": msg}

        payload = self._build_payload(title, link, image_url)
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        logger.info(f"[GoogleBusiness] Posting: '{title}'")

        try:
            resp = requests.post(
                self._post_url(),
                json=payload,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            # "name" is the resource name: accounts/{id}/locations/{id}/localPosts/{id}
            post_name = data.get("name", "")
            search_url = (
                f"https://business.google.com/n/{self.location_id}/posts"
            )

            logger.info(f"[GoogleBusiness] Posted successfully — name: {post_name}")
            return {
                "platform": "google_business",
                "success": True,
                "post_name": post_name,
                "post_url": search_url,
            }

        except requests.HTTPError as exc:
            error_body = exc.response.text if exc.response is not None else str(exc)
            logger.error(f"[GoogleBusiness] HTTP error: {error_body}")
            return {
                "platform": "google_business",
                "success": False,
                "error": error_body,
            }
        except Exception as exc:
            logger.exception(f"[GoogleBusiness] Unexpected error: {exc}")
            return {"platform": "google_business", "success": False, "error": str(exc)}
