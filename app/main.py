"""
LangChain Blog Automation – Workflow Orchestrator
──────────────────────────────────────────────────
Pipeline:
  1. ResearchAgent  → discovers a trending topic, gathers insights
                      (uses pytrends + DuckDuckGo + textgen microservice)
  2. WritingAgent   → writes a full Markdown blog post
                      (uses textgen microservice)
  3. ImageAgent     → generates a Stable Diffusion header image
                      (calls imagegen microservice → image saved to volume)
  4. DatabaseAgent  → persists everything to MySQL
"""
import logging
import sys
import time

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

# Wait for imagegen service to be ready
def wait_for_imagegen(image_agent: ImageAgent, retries: int = 12, delay: int = 20) -> None:
    logger.info("Waiting for imagegen service (SD model loading)...")
    for attempt in range(1, retries + 1):
        if image_agent.health_check():
            logger.info("imagegen service ready.")
            return
        logger.info(f"  [{attempt}/{retries}] not ready – retrying in {delay}s...")
        time.sleep(delay)
    logger.warning("imagegen never became ready; image generation may fail.")

# Main pipeline function
def run_pipeline() -> None:
    logger.info("=" * 60)
    logger.info("  LangChain Blog Automation – START")
    logger.info("=" * 60)

    research_agent = ResearchAgent()
    writing_agent = WritingAgent()
    image_agent = ImageAgent()
    db_agent = DatabaseAgent()

    wait_for_imagegen(image_agent)

    run_id = db_agent.start_run()
    blog_post_id: int | None = None
    error_message: str | None = None

    try:
        # Step 1 ── Research ───────────────────────────────────────────────────
        logger.info("Step 1 › ResearchAgent")
        # Run the research agent
        research_data = research_agent.run()
        # Save the research data to the database
        db_agent.save_research(research_data)

        # Step 2 ── Write ──────────────────────────────────────────────────────
        logger.info("Step 2 › WritingAgent")
        # Run the writing agent
        blog_data = writing_agent.run(research_data)
        logger.info(f"  Title: {blog_data['title']}")

        # Step 3 ── Generate image ─────────────────────────────────────────────
        logger.info("Step 3 › ImageAgent")
        try:
            # Run the image agent
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
        # Save the blog post to the database
        blog_post_id = db_agent.save_blog_post(blog_data, image_data)
        logger.info(f"  Saved blog_post id={blog_post_id}")

    except Exception as exc:
        # Set the error message
        error_message = str(exc)
        logger.error(f"Pipeline error: {exc}", exc_info=True)

    finally:
        # Finish the run and save the results to the database
        db_agent.finish_run(run_id, blog_post_id=blog_post_id, error=error_message)

    # Set the status message
    status = "WITH ERRORS" if error_message else "successfully"
    logger.info(f"Pipeline finished {status}.")

    if not error_message:
        # Get the recent posts from the database
        for post in db_agent.get_recent_posts(limit=3):
            logger.info(f"  DB › [{post['id']}] {post['title']} ({post['status']})")

    logger.info("=" * 60)


if __name__ == "__main__":
    # Run the pipeline
    run_pipeline()
