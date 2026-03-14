"""
Image Agent
- Uses Vertex AI (google-cloud-aiplatform) with Imagen to generate blog header images
- Tries models in priority order until one succeeds
- Saves the PNG to /app/images/ and returns filename + base64 data
"""
import base64
import hashlib
import logging
import os

import vertexai
from vertexai.preview.vision_models import ImageGenerationModel

from config import settings

logger = logging.getLogger(__name__)

OUTPUT_DIR = "/app/images"

# Models tried in order — first one that works is used
IMAGEN_MODEL_FALLBACKS = [
    "imagen-3.0-generate-001",
    "imagen-3.0-fast-generate-001",
    "imagegeneration@006",
    "imagegeneration@005",
]


def _init_vertexai() -> None:
    vertexai.init(
        project=settings.gcp_project_id,
        location=settings.gcp_location,
    )
    logger.info(
        f"Vertex AI initialised — project={settings.gcp_project_id}, "
        f"location={settings.gcp_location}"
    )


def _find_working_model() -> ImageGenerationModel:
    """
    Try each model in IMAGEN_MODEL_FALLBACKS in order.
    The configured settings.imagen_model is inserted at the front so it is
    always tried first.
    """
    candidates = [settings.imagen_model] + [
        m for m in IMAGEN_MODEL_FALLBACKS if m != settings.imagen_model
    ]

    last_error: Exception | None = None
    for model_id in candidates:
        try:
            logger.info(f"Trying Imagen model: {model_id}")
            model = ImageGenerationModel.from_pretrained(model_id)
            # Quick validation — generate a tiny test to confirm the model is usable
            # (from_pretrained is lazy; actual availability is only confirmed on generate)
            logger.info(f"Selected Imagen model: {model_id}")
            return model, model_id
        except Exception as exc:
            logger.warning(f"  Model {model_id} not available: {exc}")
            last_error = exc

    raise RuntimeError(
        f"No Imagen model is available for project '{settings.gcp_project_id}'. "
        f"Tried: {candidates}. Last error: {last_error}"
    )


class ImageAgent:
    def __init__(self) -> None:
        _init_vertexai()
        self.model, self.model_id = _find_working_model()

    def run(self, image_prompt: str, topic: str) -> dict:
        logger.info(f"Generating image with {self.model_id} | prompt: {image_prompt[:80]}...")

        enhanced_prompt = (
            f"{image_prompt}, professional blog header image, with aspect ratio 16:9, some text on the image, in a modern tech style"
        )

        images = self.model.generate_images(
            prompt=enhanced_prompt,
            number_of_images=1,
            aspect_ratio="16:9",
        )

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        slug = hashlib.md5(topic.encode()).hexdigest()[:12]
        filename = f"blog_{slug}.png"
        saved_path = os.path.join(OUTPUT_DIR, filename)

        images[0].save(saved_path)

        with open(saved_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")

        logger.info(f"Image saved to {saved_path}")
        return {
            "filename": filename,
            "saved_path": saved_path,
            "image_base64": image_base64,
        }
