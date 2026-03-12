"""
Research Agent
- Discovers trending topics via Google Trends (pytrends) + DuckDuckGo search
- Sends analysis prompts to the textgen microservice for LLM reasoning
- Returns structured research data for the Writing Agent
"""
import logging
import httpx
from langchain_community.tools import DuckDuckGoSearchRun
from pytrends.request import TrendReq
from config import settings

logger = logging.getLogger(__name__)

TEXTGEN_TIMEOUT = 180


class ResearchAgent:
    def __init__(self) -> None:
        self.search = DuckDuckGoSearchRun()
        self.pytrends = TrendReq(hl="en-US", tz=360)

    # ── Internal: call textgen microservice ────────────────────────────────────

    def _llm(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        payload = {
            "model": settings.research_model,
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

    # ── Trending topics ────────────────────────────────────────────────────────

    def get_trending_topics(self, n: int = 5) -> list[str]:
        try:
            df = self.pytrends.trending_searches(pn="united_states")
            topics = df[0].tolist()[:n]
            logger.info(f"Trending topics: {topics}")
            return topics
        except Exception as exc:
            logger.warning(f"pytrends failed ({exc}); using fallback topics.")
            return ["artificial intelligence", "machine learning", "LangChain", "open source LLMs", "AI agents"]

    # ── Research a topic ───────────────────────────────────────────────────────

    def research_topic(self, topic: str) -> dict:
        logger.info(f"Researching: {topic}")
        search_results = self.search.run(f"latest insights and news about {topic} 2026")

        insights = self._llm(
            system_prompt=(
                "You are an expert research assistant for a technology blog. "
                "Analyse the provided search results and return a structured summary."
            ),
            user_prompt=(
                f"Topic: {topic}\n\n"
                f"Search results:\n{search_results}\n\n"
                "Please provide:\n"
                "1. A compelling blog title\n"
                "2. Five key insights or talking points\n"
                "3. A brief target-audience description\n"
                "4. Suggested image description for the blog header"
            ),
        )
        return {"topic": topic, "raw_research": search_results, "insights": insights}

    # ── Full run: pick best topic then research it ─────────────────────────────

    def run(self) -> dict:
        topics = self.get_trending_topics(n=5)

        chosen = self._llm(
            system_prompt=(
                "You are a senior tech-blog editor. "
                "Pick the single topic most relevant for an AI/tech blog audience."
            ),
            user_prompt=(
                "Choose the best topic from this list for an AI/technology blog post.\n"
                + "\n".join(f"{i + 1}. {t}" for i, t in enumerate(topics))
                + "\n\nRespond with ONLY the topic name, nothing else."
            ),
        ).strip()

        logger.info(f"Topic chosen: {chosen}")
        return self.research_topic(chosen)
