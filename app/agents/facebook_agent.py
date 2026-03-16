"""
Facebook Agent
- Posts to a Facebook Page using the Graph API
- Uploads the blog header image with a caption containing the title and link
- Requires a Page Access Token with pages_manage_posts + pages_read_engagement permissions
"""
import logging
import os
from pathlib import Path

import requests

from config import settings

logger = logging.getLogger(__name__)

# Graph API version
_API_VERSION = "v19.0"
_GRAPH_BASE = f"https://graph.facebook.com/{_API_VERSION}"


class FacebookAgent:
    """Post blog content (image + title + link) to a Facebook Page."""

    def __init__(self) -> None:
        self.access_token = settings.facebook_access_token
        self.page_id = settings.facebook_page_id

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _build_caption(self, title: str, link: str) -> str:
        return f"{title}\n\n{link}"

    def _upload_photo(self, image_path: str, caption: str) -> dict:
        """Upload a local image to the page's photo feed with the given caption."""
        url = f"{_GRAPH_BASE}/{self.page_id}/photos"
        with open(image_path, "rb") as fh:
            resp = requests.post(
                url,
                data={"caption": caption, "access_token": self.access_token},
                files={"source": fh},
                timeout=60,
            )
        resp.raise_for_status()
        return resp.json()

    def _post_link_with_image_url(self, caption: str, image_url: str) -> dict:
        """Post to the feed using a public image URL (alternative when no local file)."""
        url = f"{_GRAPH_BASE}/{self.page_id}/photos"
        resp = requests.post(
            url,
            data={
                "url": image_url,
                "caption": caption,
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
        Post to Facebook.

        Args:
            title:      Blog post title used as the photo caption header.
            image_path: Absolute path to the local image file (PNG/JPEG).
            link:       Public URL to the blog post, appended to the caption.
            image_url:  Public image URL — used as fallback when image_path is
                        unavailable or empty.

        Returns:
            dict with keys: platform, success, post_id, post_url, error (on failure).
        """
        if not self.access_token or not self.page_id:
            logger.error("Facebook credentials are not configured.")
            return {
                "platform": "facebook",
                "success": False,
                "error": "FACEBOOK_ACCESS_TOKEN or FACEBOOK_PAGE_ID is not set.",
            }

        caption = self._build_caption(title, link)
        logger.info(f"[Facebook] Posting: '{title}'")

        try:
            if image_path and Path(image_path).is_file():
                data = self._upload_photo(image_path, caption)
            elif image_url:
                data = self._post_link_with_image_url(caption, image_url)
            else:
                # Text-only fallback via /feed endpoint
                resp = requests.post(
                    f"{_GRAPH_BASE}/{self.page_id}/feed",
                    data={"message": caption, "access_token": self.access_token},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()

            post_id = data.get("id", "")
            post_url = (
                f"https://www.facebook.com/{post_id.replace('_', '/posts/')}"
                if "_" in post_id
                else f"https://www.facebook.com/{self.page_id}/posts/"
            )

            logger.info(f"[Facebook] Posted successfully — id: {post_id}")
            return {
                "platform": "facebook",
                "success": True,
                "post_id": post_id,
                "post_url": post_url,
            }

        except requests.HTTPError as exc:
            error_body = exc.response.text if exc.response is not None else str(exc)
            logger.error(f"[Facebook] HTTP error: {error_body}")
            return {"platform": "facebook", "success": False, "error": error_body}
        except Exception as exc:
            logger.exception(f"[Facebook] Unexpected error: {exc}")
            return {"platform": "facebook", "success": False, "error": str(exc)}
