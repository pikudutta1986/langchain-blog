from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler
import torch
from PIL import Image
import io
import base64
import os
import hashlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_ID = os.getenv("MODEL_ID", "runwayml/stable-diffusion-v1-5")
HF_TOKEN = os.getenv("HF_TOKEN", None)
# Models cached from host ./ai-models/stable-diffusion
MODEL_CACHE_DIR = "/app/models"
OUTPUT_DIR = "/app/output"

pipe = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipe
    logger.info(f"Loading model: {MODEL_ID}")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if device == "cuda" else torch.float32
    logger.info(f"Using device: {device}")

    pipe = StableDiffusionPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=torch_dtype,
        token=HF_TOKEN if HF_TOKEN else None,
        cache_dir=MODEL_CACHE_DIR,
    )
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
    pipe = pipe.to(device)

    if device == "cpu":
        pipe.enable_attention_slicing()
        logger.info("CPU mode: attention slicing enabled for memory efficiency")

    logger.info("Model loaded and ready.")
    yield
    pipe = None


app = FastAPI(title="Blog Image Generation Service", lifespan=lifespan)


class GenerateRequest(BaseModel):
    prompt: str
    negative_prompt: str = "blurry, low quality, distorted, watermark, text, ugly, bad anatomy"
    width: int = 512
    height: int = 512
    num_inference_steps: int = 25
    guidance_scale: float = 7.5


class GenerateResponse(BaseModel):
    image_base64: str
    filename: str
    saved_path: str


@app.post("/generate", response_model=GenerateResponse)
async def generate_image(request: GenerateRequest):
    if pipe is None:
        raise HTTPException(status_code=503, detail="Model is not loaded yet.")

    logger.info(f"Generating image for prompt: {request.prompt[:80]}...")

    result = pipe(
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        width=request.width,
        height=request.height,
        num_inference_steps=request.num_inference_steps,
        guidance_scale=request.guidance_scale,
    )
    image: Image.Image = result.images[0]

    slug = hashlib.md5(request.prompt.encode()).hexdigest()[:12]
    filename = f"blog_{slug}.png"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    saved_path = os.path.join(OUTPUT_DIR, filename)
    image.save(saved_path)

    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    logger.info(f"Image saved to {saved_path}")
    return GenerateResponse(image_base64=img_base64, filename=filename, saved_path=saved_path)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "model_loaded": pipe is not None,
        "model_id": MODEL_ID,
        "device": "cuda" if torch.cuda.is_available() else "cpu",
    }
