"""
Database Agent
- Persists blog posts, research logs, and pipeline run records to MySQL
- Uses SQLAlchemy Core for lightweight, direct DB interaction
"""
import logging
import re
import uuid
from datetime import datetime
from sqlalchemy import create_engine, text
from config import settings

logger = logging.getLogger(__name__)


def _slug(title: str) -> str:
    base = re.sub(r"[^\w\s-]", "", title.lower())
    return re.sub(r"[\s_-]+", "-", base).strip("-")[:480]


class DatabaseAgent:
    def __init__(self) -> None:
        self.engine = create_engine(
            settings.mysql_url,
            pool_pre_ping=True,
            pool_recycle=3600,
        )

    # ── Research log ───────────────────────────────────────────────────────────

    def save_research(self, research_data: dict) -> int:
        sql = text(
            "INSERT INTO research_logs (topic, raw_data, insights) "
            "VALUES (:topic, :raw_data, :insights)"
        )
        with self.engine.begin() as conn:
            result = conn.execute(sql, {
                "topic": research_data["topic"],
                "raw_data": research_data.get("raw_research", ""),
                "insights": research_data.get("insights", ""),
            })
            row_id = result.lastrowid
        logger.info(f"Research log saved (id={row_id})")
        return row_id

    # ── Blog post ──────────────────────────────────────────────────────────────

    def save_blog_post(self, blog_data: dict, image_data: dict | None = None) -> int:
        title = blog_data.get("title", blog_data["topic"])
        slug = _slug(title)
        image_path = image_data.get("saved_path") if image_data else None
        image_b64 = image_data.get("image_base64") if image_data else None

        sql = text(
            "INSERT INTO blog_posts "
            "(title, slug, topic, content, summary, image_path, image_b64, status) "
            "VALUES (:title, :slug, :topic, :content, :summary, :image_path, :image_b64, 'published')"
        )
        with self.engine.begin() as conn:
            result = conn.execute(sql, {
                "title": title,
                "slug": slug,
                "topic": blog_data["topic"],
                "content": blog_data["content"],
                "summary": blog_data.get("summary", ""),
                "image_path": image_path,
                "image_b64": image_b64,
            })
            row_id = result.lastrowid
        logger.info(f"Blog post saved (id={row_id}, slug='{slug}')")
        return row_id

    # ── Pipeline run tracking ──────────────────────────────────────────────────

    def start_run(self) -> str:
        run_id = str(uuid.uuid4())
        sql = text("INSERT INTO pipeline_runs (run_id, status) VALUES (:run_id, 'running')")
        with self.engine.begin() as conn:
            conn.execute(sql, {"run_id": run_id})
        logger.info(f"Pipeline run started: {run_id}")
        return run_id

    def finish_run(self, run_id: str, blog_post_id: int | None = None, error: str | None = None) -> None:
        status = "failed" if error else "completed"
        sql = text(
            "UPDATE pipeline_runs "
            "SET status=:status, blog_post_id=:blog_post_id, error_message=:error, finished_at=:now "
            "WHERE run_id=:run_id"
        )
        with self.engine.begin() as conn:
            conn.execute(sql, {
                "status": status,
                "blog_post_id": blog_post_id,
                "error": error,
                "now": datetime.utcnow(),
                "run_id": run_id,
            })
        logger.info(f"Pipeline run {run_id} → {status}")

    # ── Queries ────────────────────────────────────────────────────────────────

    def get_recent_posts(self, limit: int = 10) -> list[dict]:
        sql = text(
            "SELECT id, title, topic, summary, status, created_at "
            "FROM blog_posts ORDER BY created_at DESC LIMIT :limit"
        )
        with self.engine.connect() as conn:
            rows = conn.execute(sql, {"limit": limit}).mappings().all()
        return [dict(r) for r in rows]
