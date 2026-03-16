"""
Twitter / X Agent
- Posts to Twitter/X using tweepy (v1.1 API for media upload + tweet creation)
- Attaches the blog header image, title, and a link in a single tweet
- Requires OAuth 1.0a credentials: API Key/Secret + Access Token/Secret
"""
import logging
from pathlib import Path

import tweepy

from config import settings

logger = logging.getLogger(__name__)

# Twitter enforces 280-char tweet limit; t.co wraps every URL to 23 chars
_TURL_LEN = 23
_MAX_TWEET = 280


class TwitterAgent:
    """Post blog content (image + title + link) to Twitter/X."""

    def __init__(self) -> None:
        self._api: tweepy.API | None = None

    # ── Lazy-initialised authenticated client ─────────────────────────────────

    @property
    def api(self) -> tweepy.API:
        if self._api is None:
            auth = tweepy.OAuth1UserHandler(
                settings.twitter_api_key,
                settings.twitter_api_secret,
                settings.twitter_access_token,
                settings.twitter_access_token_secret,
            )
            self._api = tweepy.API(auth, wait_on_rate_limit=True)
        return self._api

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _build_tweet_text(self, title: str, link: str) -> str:
        """
        Compose tweet text that fits within 280 characters.
        The link is counted as _TURL_LEN chars by Twitter regardless of its real length.
        """
        # Budget: 280 − 23 (URL) − 2 (newlines) = 255 chars for title
        max_title = _MAX_TWEET - _TURL_LEN - 2
        if len(title) > max_title:
            title = title[: max_title - 1] + "…"
        return f"{title}\n\n{link}"

    def _upload_media(self, image_path: str) -> int | None:
        """Upload image via v1.1 media/upload; returns media_id or None."""
        try:
            media = self.api.media_upload(filename=image_path)
            return media.media_id
        except Exception as exc:
            logger.warning(f"[Twitter] Media upload failed: {exc}")
            return None

    # ── Main entry point ───────────────────────────────────────────────────────

    def run(
        self,
        title: str,
        image_path: str,
        link: str,
        image_url: str = "",
    ) -> dict:
        """
        Post to Twitter/X.

        Args:
            title:      Blog post title used as the tweet body.
            image_path: Absolute path to the local image file (PNG/JPEG).
            link:       Public URL to the blog post, appended to the tweet.
            image_url:  Ignored — Twitter requires direct file upload.

        Returns:
            dict with keys: platform, success, tweet_id, tweet_url, error (on failure).
        """
        missing = [
            k
            for k, v in {
                "TWITTER_API_KEY": settings.twitter_api_key,
                "TWITTER_API_SECRET": settings.twitter_api_secret,
                "TWITTER_ACCESS_TOKEN": settings.twitter_access_token,
                "TWITTER_ACCESS_TOKEN_SECRET": settings.twitter_access_token_secret,
            }.items()
            if not v
        ]
        if missing:
            msg = f"Missing Twitter credentials: {', '.join(missing)}"
            logger.error(f"[Twitter] {msg}")
            return {"platform": "twitter", "success": False, "error": msg}

        tweet_text = self._build_tweet_text(title, link)
        logger.info(f"[Twitter] Posting: '{title}'")

        try:
            media_ids: list[int] = []
            if image_path and Path(image_path).is_file():
                mid = self._upload_media(image_path)
                if mid:
                    media_ids.append(mid)

            if media_ids:
                status = self.api.update_status(
                    status=tweet_text,
                    media_ids=media_ids,
                )
            else:
                status = self.api.update_status(status=tweet_text)

            tweet_id = str(status.id)
            screen_name = status.author.screen_name
            tweet_url = f"https://twitter.com/{screen_name}/status/{tweet_id}"

            logger.info(f"[Twitter] Posted successfully — id: {tweet_id}")
            return {
                "platform": "twitter",
                "success": True,
                "tweet_id": tweet_id,
                "tweet_url": tweet_url,
            }

        except tweepy.TweepyException as exc:
            logger.error(f"[Twitter] API error: {exc}")
            return {"platform": "twitter", "success": False, "error": str(exc)}
        except Exception as exc:
            logger.exception(f"[Twitter] Unexpected error: {exc}")
            return {"platform": "twitter", "success": False, "error": str(exc)}
