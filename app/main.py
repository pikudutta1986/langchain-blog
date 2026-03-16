"""
LangChain Blog Automation – FastAPI Service
────────────────────────────────────────────
POST /generate      { "category": "technology" }
→ runs the full pipeline and returns blog data as JSON

POST /post_social   { "title": "...", "link": "...", "image_url": "...", "image_path": "..." }
→ posts to Facebook, Twitter, Instagram, and Google Business in parallel

Pipeline:
  1. ResearchAgent  – finds the best trending topic within the given category
  2. WritingAgent   – writes a full Markdown blog post
  3. ImageAgent     – generates a Gemini Imagen 3 header image
"""
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.research_agent import ResearchAgent
from agents.writing_agent import WritingAgent
from agents.image_agent import ImageAgent
from agents.facebook_agent import FacebookAgent
from agents.twitter_agent import TwitterAgent
from agents.instagram_agent import InstagramAgent
from agents.google_business_agent import GoogleBusinessAgent

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


class SocialPostRequest(BaseModel):
    title: str
    link: str
    image_url: str = ""   # public HTTPS URL — required by Instagram & Google Business
    image_path: str = ""  # local filesystem path — used by Facebook & Twitter


class SocialPostResult(BaseModel):
    platform: str
    success: bool
    post_id: str | None = None    # Facebook photo id / Tweet id / Instagram media id
    post_url: str | None = None
    post_name: str | None = None  # Google Business resource name
    error: str | None = None


class SocialPostResponse(BaseModel):
    title: str
    link: str
    results: list[SocialPostResult]


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


@app.post("/post_social", response_model=SocialPostResponse)
def post_social(request: SocialPostRequest):
    """
    Publish a blog post to all four social media platforms simultaneously.

    All platforms are called in parallel. A failure on one platform does not
    block the others — each result carries its own success/error status.

    Payload:
        title      – Blog post title shown in the caption / tweet / post body.
        link       – Public URL to the blog post (used as CTA / appended to copy).
        image_url  – Publicly accessible HTTPS image URL (required for Instagram;
                     optional for Google Business; fallback for Facebook).
        image_path – Absolute path to the local image file (used by Facebook and
                     Twitter for direct file upload; optional if image_url is set).
    """
    title = request.title.strip()
    link = request.link.strip()
    image_url = request.image_url.strip()
    image_path = request.image_path.strip()

    logger.info(f"Social posting triggered | title='{title}' | link='{link}'")

    agents = [
        ("facebook",         FacebookAgent()),
        ("twitter",          TwitterAgent()),
        ("instagram",        InstagramAgent()),
        ("google_business",  GoogleBusinessAgent()),
    ]

    raw_results: dict[str, dict] = {}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(
                agent.run,
                title=title,
                image_path=image_path,
                link=link,
                image_url=image_url,
            ): name
            for name, agent in agents
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                raw_results[name] = future.result()
            except Exception as exc:
                logger.error(f"[{name}] Unhandled exception: {exc}")
                raw_results[name] = {
                    "platform": name,
                    "success": False,
                    "error": str(exc),
                }

    results: list[SocialPostResult] = []
    for _, data in raw_results.items():
        results.append(
            SocialPostResult(
                platform=data.get("platform", ""),
                success=data.get("success", False),
                post_id=data.get("post_id") or data.get("tweet_id") or data.get("media_id"),
                post_url=data.get("post_url"),
                post_name=data.get("post_name"),
                error=data.get("error"),
            )
        )
        status = "OK" if data.get("success") else f"FAILED — {data.get('error', '')}"
        logger.info(f"  [{data.get('platform', '?')}] {status}")

    return SocialPostResponse(title=title, link=link, results=results)


@app.get("/health")
def health():
    return {"status": "ok"}
