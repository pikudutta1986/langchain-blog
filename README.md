# LangChain Blog Automation

An autonomous blog-writing pipeline powered entirely by open-source AI. Given no human input, the system discovers a trending topic, researches it, writes a full blog post, generates a matching header image, and persists everything to a MySQL database — all orchestrated with LangChain and running inside Docker.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        docker-compose                           │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    app/  (Orchestrator)                  │   │
│  │                                                          │   │
│  │  ResearchAgent ──► WritingAgent ──► ImageAgent           │   │
│  │       │                │               │                 │   │
│  │       │                │               │                 │   │
│  │       └────────────────┴───────────────┘                 │   │
│  │                        │                                 │   │
│  │                   DatabaseAgent                          │   │
│  └───────┬────────────────┬───────────────┬─────────────────┘   │
│          │                │               │                     │
│          ▼                ▼               ▼                     │
│   ┌────────────┐  ┌─────────────┐  ┌──────────┐                │
│   │  textgen/  │  │  imagegen/  │  │  mysql   │                │
│   │            │  │             │  │          │                │
│   │  FastAPI   │  │  FastAPI    │  │  MySQL   │                │
│   │  +         │  │  + Stable   │  │  8.0     │                │
│   │  Ollama    │  │  Diffusion  │  │          │                │
│   └─────┬──────┘  └──────┬──────┘  └──────────┘                │
│         │                │                                      │
│         ▼                ▼                                      │
│   ┌───────────┐   ┌───────────────────┐                        │
│   │  ollama   │   │    ai-models/     │                        │
│   │  service  │   │                   │                        │
│   │           │   │  ollama/          │ ← Ollama weights       │
│   │  llama3.2 │   │  stable-          │                        │
│   │  mistral  │   │  diffusion/       │ ← SD weights           │
│   └───────────┘   └───────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
langchain-blog/
├── docker-compose.yml           # Orchestrates all services
├── .env.example                 # Copy to .env and configure
├── init.sql                     # MySQL schema (auto-applied on first run)
│
├── ai-models/                   # Host-side model storage (bind-mounted)
│   ├── ollama/                  # Ollama model weights  → /root/.ollama
│   └── stable-diffusion/        # Stable Diffusion weights → /app/models
│
├── app/                         # LangChain workflow orchestrator
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.py                # Pydantic settings (reads .env)
│   ├── main.py                  # Pipeline entry point
│   └── agents/
│       ├── research_agent.py    # Agent 1 – trend discovery & research
│       ├── writing_agent.py     # Agent 2 – blog post writing
│       ├── image_agent.py       # Agent 3 – header image generation
│       └── db_agent.py          # Agent 4 – MySQL persistence
│
├── textgen/                     # AI Microservice – text generation
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py                   # FastAPI wrapper over Ollama
│
└── imagegen/                    # AI Microservice – image generation
    ├── Dockerfile
    ├── requirements.txt
    └── app.py                   # FastAPI + Stable Diffusion pipeline
```

---

## Services

| Service | Technology | Port | Role |
|---|---|---|---|
| `mysql` | MySQL 8.0 | 3306 | Stores blog posts, research logs, pipeline runs |
| `ollama` | Ollama | 11434 | Serves open-source LLMs (llama3.2, mistral) |
| `ollama-init` | curl (one-shot) | — | Pulls required models into Ollama on first start |
| `textgen` | FastAPI + httpx | 8000 | Text generation microservice (wraps Ollama) |
| `imagegen` | FastAPI + diffusers | 8001 | Image generation microservice (Stable Diffusion) |
| `app` | Python + LangChain | — | Workflow orchestrator, runs the 4-agent pipeline |

---

## Pipeline Workflow

The pipeline runs sequentially through four agents. Each agent has a single responsibility.

### Step 1 — Research Agent

**File:** `app/agents/research_agent.py`

1. Calls **Google Trends** (`pytrends`) to fetch the top 5 trending topics in the US.
2. Asks the **textgen microservice** (→ Ollama `llama3.2`) to pick the most relevant topic for a tech/AI blog.
3. Runs a **DuckDuckGo web search** on the chosen topic to gather the latest news and insights.
4. Sends the search results back to **textgen** for summarisation, producing:
   - A suggested blog title
   - Five key talking points
   - A target-audience description
   - A description for the header image

```
pytrends ──► LLM (topic selection)
                │
          DuckDuckGo search
                │
          LLM (summarisation)
                │
          research_data dict
```

---

### Step 2 — Writing Agent

**File:** `app/agents/writing_agent.py`

Receives the `research_data` dict from Step 1 and makes three calls to the **textgen microservice** (→ Ollama `mistral`):

1. **Full blog post** — a 800–1200 word Markdown article with H1 title, introduction, multiple H2 sections, and a conclusion.
2. **One-sentence summary** — used as the post excerpt in the database.
3. **Stable Diffusion image prompt** — a detailed visual description used in Step 3.

```
research_data
      │
 textgen (mistral)
      ├── Full Markdown blog post
      ├── One-sentence summary
      └── SD image prompt
```

---

### Step 3 — Image Agent

**File:** `app/agents/image_agent.py`

Sends the SD image prompt (from Step 2) as an HTTP `POST /generate` request to the **imagegen microservice**.

Inside `imagegen`:
1. Stable Diffusion (`runwayml/stable-diffusion-v1-5` by default) generates a 768×512 PNG.
2. The image is **saved directly to the shared `blog_images` Docker volume** (`/app/output/`).
3. The filename and base64-encoded image data are returned to the `app`.

```
image_prompt
      │
 imagegen microservice
      │   POST /generate
      ├── Generates PNG via Stable Diffusion
      ├── Saves PNG → blog_images volume
      └── Returns { filename, image_base64, saved_path }
```

> If image generation fails (e.g. model still loading), the pipeline continues without an image rather than aborting the whole run.

---

### Step 4 — Database Agent

**File:** `app/agents/db_agent.py`

Persists all artefacts to MySQL across three tables:

| Table | What is stored |
|---|---|
| `research_logs` | Raw search results + LLM insights for every run |
| `blog_posts` | Title, slug, full Markdown content, summary, image path/base64, status |
| `pipeline_runs` | Run ID, start/finish timestamps, status (`running` / `completed` / `failed`), error messages |

```
research_data + blog_data + image_data
              │
         DatabaseAgent
              ├── INSERT research_logs
              ├── INSERT blog_posts  (status = 'published')
              └── UPDATE pipeline_runs (status = 'completed')
```

---

## AI Models Used

| Agent | Model | Served by | Purpose |
|---|---|---|---|
| Research Agent | `llama3.2` (default) | Ollama → textgen | Topic selection & research summarisation |
| Writing Agent | `mistral` (default) | Ollama → textgen | Blog writing, summary, image prompt |
| Image Agent | `stable-diffusion-v1-5` (default) | imagegen | Header image generation |

All models are open-source and run fully locally — no external API keys required.

Model weights are stored on the **host machine** under `./ai-models/` and bind-mounted into the containers. This means models are downloaded only once and survive `docker compose down`.

---

## Database Schema

```sql
-- Published blog posts
blog_posts (id, title, slug, topic, content, summary,
            image_path, image_b64, status, created_at, updated_at)

-- Raw research data per run
research_logs (id, topic, raw_data, insights, created_at)

-- Pipeline execution audit trail
pipeline_runs (id, run_id, status, blog_post_id,
               error_message, started_at, finished_at)
```

---

## Getting Started

### 1. Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) with Compose v2
- 16 GB RAM recommended (Stable Diffusion on CPU is memory-intensive)
- NVIDIA GPU optional but strongly recommended for image generation

### 2. Configure environment

```bash
copy .env.example .env
```

Edit `.env` to set your MySQL credentials and optionally change the AI models.

### 3. Build and start

```bash
docker compose up --build
```

On the **first run**, Docker will:
- Pull the MySQL and Ollama base images
- Build the `app`, `textgen`, and `imagegen` images (installs all Python requirements)
- Download Ollama models (`llama3.2` + `mistral`) — approximately 8 GB total
- Download the Stable Diffusion model (`stable-diffusion-v1-5`) — approximately 4 GB

Subsequent runs skip all downloads because models are cached in `./ai-models/`.

### 4. Subsequent runs

```bash
docker compose up
```

The `app` container runs the pipeline once and exits cleanly with a log summary.

### 5. Enable GPU acceleration (optional)

Uncomment the `deploy` blocks in `docker-compose.yml` for both `ollama` and `imagegen`:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

---

## Configuration Reference

All settings are controlled via `.env`:

| Variable | Default | Description |
|---|---|---|
| `MYSQL_ROOT_PASSWORD` | `rootpassword` | MySQL root password |
| `MYSQL_DATABASE` | `blog_db` | Database name |
| `MYSQL_USER` | `blog_user` | Application DB user |
| `MYSQL_PASSWORD` | `blog_password` | Application DB password |
| `RESEARCH_MODEL` | `llama3.2` | Ollama model for the Research Agent |
| `WRITING_MODEL` | `mistral` | Ollama model for the Writing Agent |
| `SD_MODEL_ID` | `runwayml/stable-diffusion-v1-5` | HuggingFace SD model ID |
| `HF_TOKEN` | _(empty)_ | HuggingFace token (for gated models only) |

---

## Microservice API Reference

### textgen — `http://localhost:8000`

| Method | Path | Description |
|---|---|---|
| `POST` | `/generate` | Generate text from a prompt |
| `GET` | `/models` | List models available in Ollama |
| `GET` | `/health` | Liveness check |

**POST /generate payload:**
```json
{
  "model": "mistral",
  "system_prompt": "You are a tech blogger.",
  "user_prompt": "Write an intro about LLM agents.",
  "temperature": 0.7
}
```

### imagegen — `http://localhost:8001`

| Method | Path | Description |
|---|---|---|
| `POST` | `/generate` | Generate an image from a prompt |
| `GET` | `/health` | Liveness + model-loaded check |

**POST /generate payload:**
```json
{
  "prompt": "futuristic AI brain glowing blue circuits",
  "negative_prompt": "blurry, watermark, text",
  "width": 768,
  "height": 512,
  "num_inference_steps": 30,
  "guidance_scale": 7.5
}
```
