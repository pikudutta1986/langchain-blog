# LangChain Blog Automation

An autonomous blog-writing pipeline powered by the **Gemini API**. With no human input, the system discovers a trending topic, researches it on the web, writes a full blog post, generates a matching header image, and persists everything to a MySQL database — all orchestrated with LangChain inside Docker.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                       docker-compose                         │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  app/  (Orchestrator)                  │  │
│  │                                                        │  │
│  │   ResearchAgent                                        │  │
│  │   ├─ pytrends (Google Trends)                         │  │
│  │   ├─ DuckDuckGo search                                │  │
│  │   └─ Gemini gemini-2.0-flash (LangChain)             │  │
│  │          │                                            │  │
│  │   WritingAgent                                        │  │
│  │   └─ Gemini gemini-2.0-flash (LangChain)             │  │
│  │          │                                            │  │
│  │   ImageAgent                                          │  │
│  │   └─ Gemini Imagen 3 API → /app/images volume        │  │
│  │          │                                            │  │
│  │   DatabaseAgent                                       │  │
│  │   └─ SQLAlchemy → MySQL                              │  │
│  └────────────────────────────┬───────────────────────────┘  │
│                               │                              │
│                        ┌──────▼──────┐                       │
│                        │    mysql    │                       │
│                        │  MySQL 8.0  │                       │
│                        └─────────────┘                       │
└──────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
langchain-blog/
├── docker-compose.yml           # Two services: app + mysql
├── .env.example                 # Copy to .env and add your Gemini API key
├── init.sql                     # MySQL schema (auto-applied on first run)
│
└── app/                         # LangChain workflow orchestrator
    ├── Dockerfile
    ├── requirements.txt
    ├── config.py                # Pydantic settings (reads .env)
    ├── main.py                  # Pipeline entry point
    └── agents/
        ├── research_agent.py    # Agent 1 – trend discovery & research
        ├── writing_agent.py     # Agent 2 – blog post writing
        ├── image_agent.py       # Agent 3 – header image generation
        └── db_agent.py          # Agent 4 – MySQL persistence
```

---

## Services

| Service | Technology | Port | Role |
|---|---|---|---|
| `mysql` | MySQL 8.0 | 3306 | Stores blog posts, research logs, pipeline run history |
| `app` | Python + LangChain + Gemini API | — | Runs the 4-agent pipeline |

---

## Pipeline Workflow

The pipeline runs sequentially through four agents. Each has a single responsibility.

### Step 1 — Research Agent

**File:** `app/agents/research_agent.py`

1. Calls **Google Trends** (`pytrends`) to fetch the top 5 trending US topics.
2. Asks **Gemini** (`gemini-2.0-flash` via LangChain) to pick the most relevant topic for an AI/tech blog.
3. Runs a **DuckDuckGo** web search on the chosen topic to gather the latest news and insights.
4. Sends the search results back to **Gemini** for summarisation, producing:
   - A suggested blog title
   - Five key talking points
   - A target-audience description
   - A description for the header image

```
Google Trends ──► Gemini (topic selection)
                        │
                  DuckDuckGo search
                        │
                  Gemini (summarisation)
                        │
                  research_data dict
```

---

### Step 2 — Writing Agent

**File:** `app/agents/writing_agent.py`

Receives `research_data` from Step 1 and makes three calls to **Gemini** (`gemini-2.0-flash`):

1. **Full blog post** — an 800–1200 word Markdown article with H1 title, introduction, multiple H2 sections, and a conclusion.
2. **One-sentence summary** — used as the post excerpt stored in the database.
3. **Imagen image prompt** — a detailed visual description passed to the Image Agent.

```
research_data
      │
 Gemini gemini-2.0-flash
      ├── Full Markdown blog post
      ├── One-sentence summary
      └── Imagen image prompt
```

---

### Step 3 — Image Agent

**File:** `app/agents/image_agent.py`

Sends the image prompt (from Step 2) to the **Gemini Imagen 3 API** (`imagen-3.0-generate-002`):

1. Imagen 3 generates a **768×512 PNG** blog header image.
2. The image is **saved to the `blog_images` Docker volume** (`/app/images/`).
3. The filename and base64-encoded data are returned for database storage.

```
image_prompt
      │
 Gemini Imagen 3 API
      │
  ┌───▼──────────────┐
  │ /app/images/     │  ← Docker volume (persisted on host)
  │ blog_<hash>.png  │
  └──────────────────┘
      │
  { filename, saved_path, image_base64 }
```

> If image generation fails, the pipeline continues and saves the blog post without an image rather than aborting.

---

### Step 4 — Database Agent

**File:** `app/agents/db_agent.py`

Persists all artefacts to MySQL across three tables:

| Table | What is stored |
|---|---|
| `research_logs` | Raw search results + Gemini insights for every run |
| `blog_posts` | Title, slug, full Markdown content, summary, image path/base64, status |
| `pipeline_runs` | Run ID, start/end timestamps, status (`running` / `completed` / `failed`), error messages |

---

## AI Models Used

| Agent | Model | API |
|---|---|---|
| Research Agent | `gemini-2.0-flash` | Gemini API (via LangChain) |
| Writing Agent | `gemini-2.0-flash` | Gemini API (via LangChain) |
| Image Agent | `imagen-3.0-generate-002` | Gemini Imagen API |

All models are accessed via the **Gemini API** — no local GPU or model downloads required.

---

## Database Schema

```sql
-- Published blog posts
blog_posts (id, title, slug, topic, content, summary,
            image_path, image_b64, status, created_at, updated_at)

-- Raw research data per pipeline run
research_logs (id, topic, raw_data, insights, created_at)

-- Execution audit trail
pipeline_runs (id, run_id, status, blog_post_id,
               error_message, started_at, finished_at)
```

---

## Getting Started

### 1. Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) with Compose v2
- A **Gemini API key** — get one free at [aistudio.google.com](https://aistudio.google.com/app/apikey)

### 2. Configure environment

```bash
copy .env.example .env
```

Open `.env` and set your Gemini API key:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Build and start

```bash
docker compose up --build
```

On the **first run**, Docker will:
- Pull the MySQL 8.0 image
- Build the `app` image and install all Python requirements
- Apply the database schema via `init.sql`

The `app` container then runs the full pipeline and exits cleanly with a log summary.

### 4. Subsequent runs

```bash
docker compose up
```

---

## Configuration Reference

All settings are controlled via `.env`:

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Your Gemini API key |
| `GEMINI_TEXT_MODEL` | `gemini-2.0-flash` | Gemini model for research + writing |
| `GEMINI_IMAGE_MODEL` | `imagen-3.0-generate-002` | Imagen model for header images |
| `MYSQL_ROOT_PASSWORD` | `rootpassword` | MySQL root password |
| `MYSQL_DATABASE` | `blog_db` | Database name |
| `MYSQL_USER` | `blog_user` | Application DB user |
| `MYSQL_PASSWORD` | `blog_password` | Application DB password |
