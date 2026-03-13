"""
Writing Agent
- Receives research data from the Research Agent
- Uses Gemini (gemini-2.0-flash) via LangChain to write a full blog post,
  generate a one-sentence summary, and produce a Gemini Imagen image prompt
"""
import logging
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from config import settings

logger = logging.getLogger(__name__)

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
        self.llm = ChatGoogleGenerativeAI(
            model=settings.gemini_text_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.7,
        )

    def run(self, research_data: dict) -> dict:
        topic = research_data["topic"]
        insights = research_data["insights"]
        logger.info(f"Writing blog post for: {topic}")

        content = self.llm.invoke([
            SystemMessage(content=WRITING_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Write a comprehensive blog post on the following topic.\n\n"
                    f"Topic: {topic}\n\n"
                    f"Research insights:\n{insights}\n\n"
                    "Return the full Markdown blog post."
                )
            ),
        ]).content

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
        return self.llm.invoke([
            SystemMessage(content="You are a copywriter. Write a single-sentence summary of the blog post below."),
            HumanMessage(content=content[:3000]),
        ]).content.strip()

    def _generate_image_prompt(self, topic: str, insights: str) -> str:
        return self.llm.invoke([
            SystemMessage(
                content=(
                    "You are a prompt engineer for an AI image generation model. "
                    "Create a vivid, detailed prompt for a blog header image. "
                    "Focus on visual elements, style, and lighting. No text in the image. Max 120 words."
                )
            ),
            HumanMessage(
                content=f"Blog topic: {topic}\n\nKey insights:\n{insights[:500]}\n\nGenerate the image prompt."
            ),
        ]).content.strip()
