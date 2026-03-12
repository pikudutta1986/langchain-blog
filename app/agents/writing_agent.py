"""
Writing Agent
- Receives research data from the Research Agent
- Sends writing prompts to the textgen microservice
- Returns a complete Markdown blog post with title, summary, and an SD image prompt
"""
import logging
import re
import httpx
from config import settings

logger = logging.getLogger(__name__)

TEXTGEN_TIMEOUT = 300

WRITING_SYSTEM_PROMPT = """You are an expert technology blogger and content writer.
Write engaging, well-structured blog posts in Markdown format.
Your posts must include:
- A compelling H1 title
- A short introduction paragraph
- Multiple H2 sections with detailed content
- A conclusion section
- Smooth transitions between sections
Keep the tone professional yet approachable. Aim for 800-1200 words."""


class WritingAgent:
    def __init__(self) -> None:
        pass

    # ── Internal: call textgen microservice ────────────────────────────────────

    def _llm(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        payload = {
            "model": settings.writing_model,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "temperature": temperature,
        }
        response = httpx.post(
            f"{settings.textgen_url}/generate",
            json=payload,
            timeout=TEXTGEN_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["text"]

    # ── Public run ─────────────────────────────────────────────────────────────

    def run(self, research_data: dict) -> dict:
        topic = research_data["topic"]
        insights = research_data["insights"]
        logger.info(f"Writing blog post for: {topic}")

        content = self._llm(
            system_prompt=WRITING_SYSTEM_PROMPT,
            user_prompt=(
                f"Write a comprehensive blog post on the following topic.\n\n"
                f"Topic: {topic}\n\n"
                f"Research insights:\n{insights}\n\n"
                "Return the full Markdown blog post."
            ),
        )

        title = self._extract_title(content, fallback=topic)
        summary = self._generate_summary(content)
        image_prompt = self._generate_image_prompt(topic, insights)

        return {
            "title": title,
            "topic": topic,
            "content": content,
            "summary": summary,
            "image_prompt": image_prompt,
        }

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _extract_title(self, content: str, fallback: str) -> str:
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        return match.group(1).strip() if match else fallback

    def _generate_summary(self, content: str) -> str:
        return self._llm(
            system_prompt="You are a copywriter. Write a single-sentence summary of the blog post below.",
            user_prompt=content[:3000],
            temperature=0.3,
        ).strip()

    def _generate_image_prompt(self, topic: str, insights: str) -> str:
        return self._llm(
            system_prompt=(
                "You are a prompt engineer for Stable Diffusion. "
                "Create a vivid, detailed image generation prompt for a blog header image. "
                "Focus on visual elements, style, and lighting. No text in the image. Max 120 words."
            ),
            user_prompt=f"Blog topic: {topic}\n\nKey insights:\n{insights[:500]}\n\nGenerate the image prompt.",
            temperature=0.6,
        ).strip()
