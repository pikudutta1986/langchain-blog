"""
LangChain Blog Automation – FastAPI Service
────────────────────────────────────────────
POST /generate   { "category": "technology" }
→ runs the full pipeline and returns blog data as JSON

Pipeline:
  1. ResearchAgent  – finds the best trending topic within the given category
  2. WritingAgent   – writes a full Markdown blog post
  3. ImageAgent     – generates a Gemini Imagen 3 header image
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.research_agent import ResearchAgent
from agents.writing_agent import WritingAgent
from agents.image_agent import ImageAgent

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

ERROR_LOG = Path("/app/logs/pipeline_errors.log")


def _log_error(category: str, error: Exception) -> None:
    """Append pipeline error details to the error log file."""
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    with ERROR_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, indent=2))
        f.write("\n" + "-" * 80 + "\n")
    logger.error(f"Error logged to {ERROR_LOG}")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="LangChain Blog Automation API",
    description="Generates AI blog posts on demand using Gemini.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ───────────────────────────────────────────────────────────────────
class BlogRequest(BaseModel):
    category: str


class BlogResponse(BaseModel):
    category: str
    topic: str
    title: str
    content: str          # full Markdown blog post
    summary: str          # one-sentence excerpt
    image_base64: str | None = None   # PNG encoded as base64
    image_filename: str | None = None


# ── Routes ────────────────────────────────────────────────────────────────────
@app.post("/generate", response_model=BlogResponse)
def generate_blog(request: BlogRequest):
    """
    Run the full blog pipeline for a given category.

    - Discovers the best trending topic in that category
    - Writes a full Markdown blog post with Gemini
    - Generates a header image with Gemini Imagen 3
    - Returns everything in a single JSON response
    """
    category = request.category.strip()
    logger.info(f"Pipeline triggered | category='{category}'")

    try:
        # Step 1 – Research
        research_agent = ResearchAgent()
        research_data = research_agent.run(category=category)
        logger.info(f"  Topic selected: {research_data['topic']}")

        # Step 2 – Write
        writing_agent = WritingAgent()
        blog_data = writing_agent.run(research_data)
        logger.info(f"  Blog written: {blog_data['title']}")

        # Step 3 – Image (non-fatal if it fails)
        image_base64 = None
        image_filename = None
        try:
            image_agent = ImageAgent()
            image_data = image_agent.run(
                image_prompt=blog_data["image_prompt"],
                topic=blog_data["topic"],
            )
            image_base64 = image_data["image_base64"]
            image_filename = image_data["filename"]
            logger.info(f"  Image generated: {image_filename}")
        except Exception as img_exc:
            logger.warning(f"  Image generation skipped ({img_exc})")

        logger.info("Pipeline completed successfully.")
        return BlogResponse(
            category=category,
            topic=research_data["topic"],
            title=blog_data["title"],
            content=blog_data["content"],
            summary=blog_data["summary"],
            image_base64=image_base64,
            image_filename=image_filename,
        )

    except Exception as exc:
        _log_error(category, exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
def health():
    return {"status": "ok"}
