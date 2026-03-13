"""
LangChain Blog Automation – Workflow Orchestrator
──────────────────────────────────────────────────
Pipeline (all powered by Gemini API):
  1. ResearchAgent  → discovers a trending topic, gathers insights
                      (pytrends + DuckDuckGo + Gemini gemini-2.0-flash)
  2. WritingAgent   → writes a full Markdown blog post
                      (Gemini gemini-2.0-flash)
  3. ImageAgent     → generates a header image
                      (Gemini Imagen 3 → saved to /app/images volume)
  4. DatabaseAgent  → persists everything to MySQL
"""
import logging
import sys

from agents.research_agent import ResearchAgent
from agents.writing_agent import WritingAgent
from agents.image_agent import ImageAgent
from agents.db_agent import DatabaseAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run_pipeline() -> None:
    logger.info("=" * 60)
    logger.info("  LangChain Blog Automation – START")
    logger.info("=" * 60)

    research_agent = ResearchAgent()
    writing_agent = WritingAgent()
    image_agent = ImageAgent()
    db_agent = DatabaseAgent()

    run_id = db_agent.start_run()
    blog_post_id: int | None = None
    error_message: str | None = None

    try:
        # Step 1 ── Research ───────────────────────────────────────────────────
        logger.info("Step 1 › ResearchAgent")
        # Get trending topics using research_agent
        research_data = research_agent.run()
        # Save research data to database using db_agent
        db_agent.save_research(research_data)
        logger.info(f"  Topic: {research_data['topic']}")

        # Step 2 ── Write ──────────────────────────────────────────────────────
        logger.info("Step 2 › WritingAgent")
        # Write blog post using writing_agent
        blog_data = writing_agent.run(research_data)
        # Save blog post to database using db_agent
        db_agent.save_blog_post(blog_data)
        logger.info(f"  Title: {blog_data['title']}")

        # Step 3 ── Generate image ─────────────────────────────────────────────
        logger.info("Step 3 › ImageAgent")
        try:
            # Generate image using image_agent
            image_data = image_agent.run(
                image_prompt=blog_data["image_prompt"],
                topic=blog_data["topic"],
            )
            logger.info(f"  Image: {image_data['filename']}")
        except Exception as img_exc:
            logger.warning(f"  Image generation failed ({img_exc}); proceeding without image.")
            image_data = None

        # Step 4 ── Save to database ───────────────────────────────────────────
        logger.info("Step 4 › DatabaseAgent")
        # Save blog post to database using db_agent
        blog_post_id = db_agent.save_blog_post(blog_data, image_data)
        logger.info(f"  Saved blog_post id={blog_post_id}")

    except Exception as exc:
        error_message = str(exc)
        logger.error(f"Pipeline error: {exc}", exc_info=True)

    finally:
        # Finish run using db_agent
        db_agent.finish_run(run_id, blog_post_id=blog_post_id, error=error_message)

    status = "WITH ERRORS" if error_message else "successfully"
    logger.info(f"Pipeline finished {status}.")

    if not error_message:
        for post in db_agent.get_recent_posts(limit=3):
            logger.info(f"  DB › [{post['id']}] {post['title']} ({post['status']})")

    logger.info("=" * 60)


if __name__ == "__main__":
    run_pipeline()
