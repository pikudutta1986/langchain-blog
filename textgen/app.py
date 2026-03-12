"""
textgen – Text Generation Microservice
───────────────────────────────────────
Wraps the Ollama inference API behind a clean REST interface.

POST /generate   – send a prompt, receive generated text
GET  /models     – list models available in Ollama
GET  /health     – liveness / readiness check
"""
from contextlib import asynccontextmanager
import os
import logging
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "mistral")


# ── Schemas ────────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    model: str = DEFAULT_MODEL
    system_prompt: str = ""
    user_prompt: str
    temperature: float = 0.7
    max_tokens: int | None = None  # None = Ollama default


class GenerateResponse(BaseModel):
    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"textgen service starting – Ollama at {OLLAMA_BASE_URL}")
    yield
    logger.info("textgen service shutting down.")


app = FastAPI(title="Text Generation Microservice", lifespan=lifespan)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    """Send a prompt to Ollama and return the generated text."""
    messages = []
    if req.system_prompt:
        messages.append({"role": "system", "content": req.system_prompt})
    messages.append({"role": "user", "content": req.user_prompt})

    payload: dict = {
        "model": req.model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": req.temperature},
    }
    if req.max_tokens:
        payload["options"]["num_predict"] = req.max_tokens

    logger.info(f"Generating with model={req.model}, prompt_len={len(req.user_prompt)}")

    async with httpx.AsyncClient(timeout=300) as client:
        try:
            resp = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=502, detail=f"Ollama error: {exc.response.text}")
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Cannot reach Ollama: {exc}")

    data = resp.json()
    usage = data.get("usage", {})

    return GenerateResponse(
        text=data["message"]["content"],
        model=req.model,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
    )


@app.get("/models")
async def list_models():
    """Return the list of models pulled into Ollama."""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc))


@app.get("/health")
async def health():
    """Check whether Ollama is reachable."""
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            ollama_ok = resp.status_code == 200
        except Exception:
            ollama_ok = False

    return {
        "status": "healthy" if ollama_ok else "degraded",
        "ollama_connected": ollama_ok,
        "ollama_url": OLLAMA_BASE_URL,
    }
