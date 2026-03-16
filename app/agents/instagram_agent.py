"""
Instagram Agent
- Posts to an Instagram Business / Creator account via the Instagram Graph API
- Creates a media container with a public image URL, then publishes it
- Requires an Instagram-connected Facebook App access token with
  instagram_basic, instagram_content_publish permissions
- NOTE: The Instagram Graph API requires a publicly accessible image URL.
  The image_url argument must point to a reachable HTTPS endpoint (e.g. the
  URL where the image was already uploaded to your WordPress media library).
"""
import logging
import time

import requests

from config import settings

logger = logging.getLogger(__name__)

_API_VERSION = "v19.0"
_GRAPH_BASE = f"https://graph.facebook.com/{_API_VERSION}"

# Max retries when waiting for the media container to become ready
_PUBLISH_POLL_RETRIES = 5
_PUBLISH_POLL_DELAY = 3  # seconds


class InstagramAgent:
    """Post blog content (image + caption) to an Instagram Business account."""

    def __init__(self) -> None:
        self.access_token = settings.instagram_access_token
        self.account_id = settings.instagram_account_id

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _build_caption(self, title: str, link: str) -> str:
        return f"{title}\n\n{link}"

    def _create_media_container(self, image_url: str, caption: str) -> str:
        """
        Step 1 of the Instagram publishing flow.
        Creates an IG media container and returns its creation_id.
        """
        url = f"{_GRAPH_BASE}/{self.account_id}/media"
        resp = requests.post(
            url,
            data={
                "image_url": image_url,
                "caption": caption,
                "access_token": self.access_token,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def _wait_until_ready(self, creation_id: str) -> bool:
        """
        Poll the container status until FINISHED or until retries are exhausted.
        Returns True when ready, False on timeout or error.
        """
        url = f"{_GRAPH_BASE}/{creation_id}"
        for attempt in range(1, _PUBLISH_POLL_RETRIES + 1):
            resp = requests.get(
                url,
                params={"fields": "status_code", "access_token": self.access_token},
                timeout=30,
            )
            resp.raise_for_status()
            status_code = resp.json().get("status_code", "")
            if status_code == "FINISHED":
                return True
            if status_code == "ERROR":
                logger.error(f"[Instagram] Media container error for id={creation_id}")
                return False
            logger.debug(
                f"[Instagram] Container {creation_id} status={status_code} "
                f"(attempt {attempt}/{_PUBLISH_POLL_RETRIES})"
            )
            time.sleep(_PUBLISH_POLL_DELAY)
        return False

    def _publish_container(self, creation_id: str) -> dict:
        """
        Step 2 of the Instagram publishing flow.
        Publishes the ready container and returns the API response.
        """
        url = f"{_GRAPH_BASE}/{self.account_id}/media_publish"
        resp = requests.post(
            url,
            data={
                "creation_id": creation_id,
                "access_token": self.access_token,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Main entry point ───────────────────────────────────────────────────────

    def run(
        self,
        title: str,
        image_path: str,
        link: str,
        image_url: str = "",
    ) -> dict:
        """
        Post to Instagram.

        Args:
            title:      Blog post title used as the beginning of the caption.
            image_path: Local path — not used directly; Instagram requires a
                        public URL. Pass image_url instead.
            link:       Public URL to the blog post, appended to the caption.
            image_url:  REQUIRED — publicly accessible HTTPS URL of the image
                        (e.g. the WordPress media library URL after uploading).

        Returns:
            dict with keys: platform, success, media_id, post_url, error (on failure).
        """
        if not self.access_token or not self.account_id:
            msg = "INSTAGRAM_ACCESS_TOKEN or INSTAGRAM_ACCOUNT_ID is not set."
            logger.error(f"[Instagram] {msg}")
            return {"platform": "instagram", "success": False, "error": msg}

        if not image_url:
            msg = (
                "image_url is required for Instagram posting. "
                "Provide the public HTTPS URL of the uploaded image "
                "(e.g. from your WordPress media library)."
            )
            logger.error(f"[Instagram] {msg}")
            return {"platform": "instagram", "success": False, "error": msg}

        caption = self._build_caption(title, link)
        logger.info(f"[Instagram] Posting: '{title}'")

        try:
            creation_id = self._create_media_container(image_url, caption)
            logger.debug(f"[Instagram] Container created — id: {creation_id}")

            if not self._wait_until_ready(creation_id):
                return {
                    "platform": "instagram",
                    "success": False,
                    "error": f"Media container {creation_id} did not become ready in time.",
                }

            data = self._publish_container(creation_id)
            media_id = data.get("id", "")
            post_url = f"https://www.instagram.com/p/{media_id}/"

            logger.info(f"[Instagram] Posted successfully — media_id: {media_id}")
            return {
                "platform": "instagram",
                "success": True,
                "media_id": media_id,
                "post_url": post_url,
            }

        except requests.HTTPError as exc:
            error_body = exc.response.text if exc.response is not None else str(exc)
            logger.error(f"[Instagram] HTTP error: {error_body}")
            return {"platform": "instagram", "success": False, "error": error_body}
        except Exception as exc:
            logger.exception(f"[Instagram] Unexpected error: {exc}")
            return {"platform": "instagram", "success": False, "error": str(exc)}
