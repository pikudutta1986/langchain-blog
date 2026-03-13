# LangChain Blog Automation API

A **FastAPI service** that generates complete, AI-written blog posts on demand. Send a category, get back a full blog post — topic, title, Markdown content, one-line summary, and a generated header image — all in one JSON response. Powered entirely by the **Gemini API** and orchestrated with **LangChain**, running in Docker.

---

## How It Works

Call the single endpoint with a blog category. The service runs a three-step pipeline and returns the result:

```
POST /generate  { "category": "artificial intelligence" }
                          │
          ┌───────────────▼────────────────┐
          │        ResearchAgent           │
          │  pytrends → topic list         │
          │  DuckDuckGo → latest news      │
          │  Gemini → pick & summarise     │
          └───────────────┬────────────────┘
                          │  research_data
          ┌───────────────▼────────────────┐
          │         WritingAgent           │
          │  Gemini → full blog post       │
          │  Gemini → one-line summary     │
          │  Gemini → image prompt         │
          └───────────────┬────────────────┘
                          │  blog_data
          ┌───────────────▼────────────────┐
          │          ImageAgent            │
          │  Gemini Imagen 3 → PNG         │
          │  saved to /app/images volume   │
          └───────────────┬────────────────┘
                          │
               JSON response to caller
```

---

## Project Structure

```
langchain-blog/
├── docker-compose.yml       # Single service: app on port 8000
├── .env.example             # Copy to .env — only GEMINI_API_KEY required
├── logs/                    # pipeline_errors.log appears here on the host
│
└── app/
    ├── Dockerfile
    ├── requirements.txt
    ├── config.py            # Reads settings from .env
    ├── main.py              # FastAPI app — POST /generate, GET /health
    └── agents/
        ├── research_agent.py   # Trending topic discovery + research
        ├── writing_agent.py    # Blog post + summary + image prompt
        └── image_agent.py      # Imagen 3 image generation
```

---

## API Reference

### `POST /generate`

Runs the full pipeline and returns the completed blog post.

**Request**

```json
{
  "category": "artificial intelligence"
}
```

**Response**

```json
{
  "category": "artificial intelligence",
  "topic": "AI Agents in 2026",
  "title": "How AI Agents Are Rewriting the Rules of Software",
  "content": "# How AI Agents Are Rewriting the Rules of Software\n\n...(full Markdown, 800-1200 words)...",
  "summary": "AI agents are transforming software by autonomously executing complex multi-step tasks.",
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "image_filename": "blog_3f2a1c4d9e8b.png"
}
```

| Field | Type | Description |
|---|---|---|
| `category` | `string` | The category that was passed in |
| `topic` | `string` | The specific trending topic selected |
| `title` | `string` | The blog post title |
| `content` | `string` | Full blog post in Markdown format |
| `summary` | `string` | One-sentence excerpt |
| `image_base64` | `string \| null` | PNG header image encoded as base64 |
| `image_filename` | `string \| null` | Filename of the saved image |

**Error responses**

| Status | Meaning |
|---|---|
| `422` | Invalid request body (e.g. missing `category`) |
| `500` | Pipeline failed — error details in response body and in `./logs/pipeline_errors.log` |

---

### `GET /health`

Liveness check.

```json
{ "status": "ok" }
```

---

### Interactive docs

Swagger UI is available at **http://localhost:8000/docs** when the service is running.

---

## Agents

### ResearchAgent — `app/agents/research_agent.py`

Accepts the `category` string and returns a researched topic.

1. Calls **Google Trends** (`pytrends`) with the category as a seed keyword to get related trending queries for the past 7 days.
2. Falls back to a **DuckDuckGo** search (`top trending topics in {category} right now`) if pytrends returns no results, then uses Gemini to extract a clean topic list.
3. Asks **Gemini** (`gemini-2.0-flash`) to pick the single most interesting topic from the list for the given category.
4. Runs a second **DuckDuckGo** search for that specific topic and sends the results to **Gemini** for structured summarisation, producing:
   - A suggested blog title
   - Five key talking points
   - A target-audience description
   - A visual description for the header image

---

### WritingAgent — `app/agents/writing_agent.py`

Accepts `research_data` and makes three separate Gemini calls:

1. **Full blog post** — an 800–1200 word Markdown article with an H1 title, intro, multiple H2 sections, and a conclusion.
2. **One-sentence summary** — used as the excerpt in the API response.
3. **Imagen image prompt** — a detailed visual description (max 120 words, no text in image) passed to the Image Agent.

---

### ImageAgent — `app/agents/image_agent.py`

Accepts the image prompt generated by the Writing Agent.

1. Calls **Gemini Imagen 3** (`imagen-3.0-generate-002`) to generate a `16:9` PNG.
2. Saves the file to `/app/images/blog_<md5hash>.png` (Docker volume — persists across restarts).
3. Returns the filename and base64-encoded image bytes for inclusion in the API response.

> Image generation is **non-fatal**. If it fails, the endpoint still returns the blog text with `image_base64: null`.

---

## Error Logging

When a pipeline error occurs:
- The API returns an HTTP `500` with the error message in the response body.
- A structured JSON entry is appended to `./logs/pipeline_errors.log` on the host:

```json
{
  "timestamp": "2026-03-11T14:22:01.123456+00:00",
  "category": "finance",
  "error_type": "ValueError",
  "error_message": "..."
}
```

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) with Compose v2
- A **Gemini API key** — get one free at [aistudio.google.com](https://aistudio.google.com/app/apikey)

### 1. Configure environment

```bash
copy .env.example .env
```

Open `.env` and set your key:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2. Build and start

```bash
docker compose up --build
```

The API is ready when you see:

```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 3. Generate a blog post

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"category": "artificial intelligence"}'
```

Or open **http://localhost:8000/docs** to use the interactive Swagger UI.

### 4. Stop

```bash
docker compose down
```

---

## Configuration

All settings are in `.env`. Only `GEMINI_API_KEY` is required.

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Your Gemini API key |
| `GEMINI_TEXT_MODEL` | `gemini-2.0-flash` | Model used for research and writing |
| `GEMINI_IMAGE_MODEL` | `imagen-3.0-generate-002` | Model used for image generation |

---

## Dependencies

| Package | Purpose |
|---|---|
| `fastapi` + `uvicorn` | API server |
| `langchain`, `langchain-google-genai` | LangChain orchestration + Gemini text |
| `google-genai` | Gemini Imagen 3 image generation |
| `langchain-community` | DuckDuckGo search tool |
| `pytrends` | Google Trends topic discovery |
| `pydantic-settings` | Environment-based config |
| `Pillow` | Image file handling |
