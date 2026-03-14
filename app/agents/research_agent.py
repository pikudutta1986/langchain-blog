"""
Research Agent
- Accepts a category (e.g. "technology", "finance", "health")
- Finds the best trending topic within that category using pytrends + DuckDuckGo
- Uses Gemini (gemini-2.0-flash) to select and summarise the topic
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

    # ── Trending topics within a category ─────────────────────────────────────

    def get_trending_topics(self, category: str, n: int = 10) -> list[str]:
        """Return up to n trending topics related to the given category."""
        try:
            # Seed pytrends with the category to get related trending queries
            self.pytrends.build_payload(kw_list=[category], timeframe="now 7-d")
            related = self.pytrends.related_queries()
            rising = related.get(category, {}).get("top")
            if rising is not None and not rising.empty:
                topics = rising["query"].tolist()[:n]
                logger.info(f"pytrends topics for '{category}': {topics}")
                return topics
        except Exception as exc:
            logger.warning(f"pytrends failed ({exc}); falling back to DuckDuckGo search.")

        # Fallback: search the web for trending topics in this category
        try:
            results = self.search.run(f"top trending topics in {category} right now 2026")
            # Ask Gemini to extract a list of topics from the search result
            response = self.llm.invoke([
                SystemMessage(content="You are a research assistant. Extract a numbered list of trending topics from the text below. Return only the topic names, one per line."),
                HumanMessage(content=results[:2000]),
            ])
            topics = [line.strip().lstrip("0123456789.-) ") for line in response.content.splitlines() if line.strip()]
            return topics[:n] if topics else [category]
        except Exception as exc:
            logger.warning(f"DuckDuckGo fallback also failed ({exc}); using category as topic.")
            return [category]

    # ── Research a specific topic ──────────────────────────────────────────────

    def research_topic(self, topic: str, category: str) -> dict:
        """Deep-dive a specific topic and return structured research data."""
        logger.info(f"Researching topic: '{topic}' (category: {category})")
        search_results = self.search.run(f"latest insights and news about {topic} in {category} 2026")

        response = self.llm.invoke([
            SystemMessage(
                content=(
                    "You are an expert research assistant for a technology blog. "
                    "Analyse the provided search results, latest news and return a structured summary."
                )
            ),
            HumanMessage(
                content=(
                    f"Category: {category}\n"
                    f"Topic: {topic}\n\n"
                    f"Search results:\n{search_results}\n\n"
                    "Please provide:\n"
                    "1. A compelling blog title\n"
                    "2. Five key insights or talking points\n"
                    "3. A brief target-audience description\n"
                    "4. Suggested image description for the blog header"
                )
            ),
        ])

        return {
            "category": category,
            "topic": topic,
            "raw_research": search_results,
            "insights": response.content,
        }

    # ── Main entry point ───────────────────────────────────────────────────────

    def run(self, category: str) -> dict:
        """Select the best trending topic for the given category and research it."""
        topics = self.get_trending_topics(category=category, n=10)

        chosen = self.llm.invoke([
            SystemMessage(
                content=(
                    f"You are a senior blog editor specialising in {category}. "
                    f"Pick the single most interesting and timely topic for a {category} blog post."
                )
            ),
            HumanMessage(
                content=(
                    f"Category: {category}\n\n"
                    "Choose the best topic from the list below for a blog post. "
                    "Respond with ONLY the topic name, nothing else.\n\n"
                    + "\n".join(f"{i + 1}. {t}" for i, t in enumerate(topics))
                )
            ),
        ]).content.strip()

        logger.info(f"Topic chosen: '{chosen}'")
        return self.research_topic(chosen, category)
