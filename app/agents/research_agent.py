"""
Research Agent
- Discovers trending topics via Google Trends (pytrends) + DuckDuckGo search
- Uses Gemini (gemini-2.0-flash) via LangChain for topic selection and summarisation
"""
import logging
from pytrends.request import TrendReq
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from config import settings

logger = logging.getLogger(__name__)


class ResearchAgent:
    def __init__(self) -> None:
        self.llm = ChatGoogleGenerativeAI(
            model=settings.gemini_text_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.3,
        )
        self.search = DuckDuckGoSearchRun()
        self.pytrends = TrendReq(hl="en-US", tz=360)

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

    # ── Research a single topic ────────────────────────────────────────────────

    def research_topic(self, topic: str) -> dict:
        logger.info(f"Researching: {topic}")
        search_results = self.search.run(f"latest insights and news about {topic} 2026")

        messages = [
            SystemMessage(
                content=(
                    "You are an expert research assistant for a technology blog. "
                    "Analyse the provided search results and return a structured summary."
                )
            ),
            HumanMessage(
                content=(
                    f"Topic: {topic}\n\n"
                    f"Search results:\n{search_results}\n\n"
                    "Please provide:\n"
                    "1. A compelling blog title\n"
                    "2. Five key insights or talking points\n"
                    "3. A brief target-audience description\n"
                    "4. Suggested image description for the blog header"
                )
            ),
        ]
        insights = self.llm.invoke(messages).content
        return {"topic": topic, "raw_research": search_results, "insights": insights}

    # ── Full run: pick best topic, then research it ────────────────────────────

    def run(self) -> dict:
        topics = self.get_trending_topics(n=5)

        messages = [
            SystemMessage(
                content=(
                    "You are a senior tech-blog editor. "
                    "Pick the single topic most relevant for an AI/tech blog audience."
                )
            ),
            HumanMessage(
                content=(
                    "Choose the best topic from this list for an AI/technology blog post.\n"
                    + "\n".join(f"{i + 1}. {t}" for i, t in enumerate(topics))
                    + "\n\nRespond with ONLY the topic name, nothing else."
                )
            ),
        ]
        chosen = self.llm.invoke(messages).content.strip()
        logger.info(f"Topic chosen: {chosen}")
        return self.research_topic(chosen)
