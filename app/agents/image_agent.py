"""
Image Agent
- Uses the Gemini Imagen 3 API to generate a blog header image
- Saves the PNG to /app/images/ (Docker volume for persistence)
- Returns filename, saved path, and base64 data for database storage
"""
import base64
import hashlib
import logging
import os
from google import genai
from google.genai import types
from config import settings

logger = logging.getLogger(__name__)

OUTPUT_DIR = "/app/images"


class ImageAgent:
    def __init__(self) -> None:
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.gemini_image_model

    def run(self, image_prompt: str, topic: str) -> dict:
        logger.info(f"Generating image for: {image_prompt[:80]}...")

        enhanced_prompt = (
            f"{image_prompt}, professional blog header image, "
            "high quality, 4k, modern design, technology theme, no text"
        )

        response = self.client.models.generate_images(
            model=self.model,
            prompt=enhanced_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",
                safety_filter_level="BLOCK_MEDIUM_AND_ABOVE",
                person_generation="DONT_ALLOW",
            ),
        )

        image_bytes = response.generated_images[0].image.image_bytes

        slug = hashlib.md5(topic.encode()).hexdigest()[:12]
        filename = f"blog_{slug}.png"
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        saved_path = os.path.join(OUTPUT_DIR, filename)

        with open(saved_path, "wb") as f:
            f.write(image_bytes)

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        logger.info(f"Image saved to {saved_path}")
        return {
            "filename": filename,
            "saved_path": saved_path,
            "image_base64": image_base64,
        }
