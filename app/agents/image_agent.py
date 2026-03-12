"""
Image Agent
- Calls the imagegen microservice (Stable Diffusion)
- The microservice saves the image directly to the shared volume
- Returns filename and base64 data for database storage
"""
import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)

TIMEOUT = 300  # SD inference on CPU is slow


class ImageAgent:
    def __init__(self) -> None:
        self.base_url = settings.imagegen_url

    def run(self, image_prompt: str, topic: str) -> dict:
        logger.info(f"Requesting image for: {image_prompt[:80]}...")

        enhanced = (
            f"{image_prompt}, professional blog header, high quality, "
            "4k, detailed, modern design, technology theme"
        )

        payload = {
            "prompt": enhanced,
            "negative_prompt": "blurry, low quality, watermark, text, logo, distorted, ugly",
            "width": 768,
            "height": 512,
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
        }

        response = httpx.post(
            f"{self.base_url}/generate",
            json=payload,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        logger.info(f"Image generated and saved: {data['filename']}")
        return {
            "filename": data["filename"],
            "image_base64": data["image_base64"],
            "saved_path": data["saved_path"],
        }

    def health_check(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/health", timeout=10)
            return r.json().get("model_loaded", False)
        except Exception:
            return False
