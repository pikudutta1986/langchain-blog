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
| `google-cloud-aiplatform[preview]` | Vertex AI Imagen image generation |
| `langchain-community` + `ddgs` | DuckDuckGo search tool |
| `pytrends` | Google Trends topic discovery |
| `pydantic-settings` | Environment-based config |
| `Pillow` | Image file handling |

---

## WordPress Integration — `generate.php`

`generate.php` sits at the **WordPress root** (same folder as `wp-load.php`). It calls the `/generate` API, then inserts the result directly into WordPress as a published post with a featured image — no plugin required.

### How to use

Copy `generate.php` to your WordPress root, then call it from a browser or cron job:

```
http://your-site.com/generate.php?category=artificial+intelligence
```

The `category` query parameter is passed straight to the API. If omitted it defaults to `artificial intelligence`.

---

### What it does internally

```
Browser / cron
      │
      │  GET ?category=finance
      ▼
generate.php  (WordPress root)
      │
      │  POST /generate  { "category": "finance" }
      ▼
LangChain API  (localhost:8000)
      │
      │  BlogResponse JSON
      ▼
generate.php
      ├── markdown_to_html($blog['content'])
      │
      ├── wp_insert_post()
      │     post_title    → $blog['title']
      │     post_content  → converted HTML
      │     post_excerpt  → $blog['summary']
      │     post_category → resolved / created category
      │     tags_input    → $blog['topic']
      │
      └── Featured Image pipeline
            base64_decode($blog['image_base64'])
                  │
            wp_upload_bits()       → saves PNG to /wp-content/uploads/
                  │
            wp_insert_attachment() → registers in Media Library
                  │
            wp_generate_attachment_metadata()  → creates all thumbnail sizes
                  │
            set_post_thumbnail()   → sets as post Featured Image
```

---

### Step-by-step breakdown

**Step 1 — Bootstrap WordPress**

```php
require_once __DIR__ . '/wp-load.php';
```

Loads the full WordPress environment so all core functions (`wp_insert_post`, `wp_upload_bits`, etc.) are available.

---

**Step 2 — Call the API**

Sends a `POST /generate` request with `{ "category": "..." }` to the LangChain API using cURL. Timeout is set to 300 seconds to allow for the full pipeline (research → write → image). If cURL fails or the API returns a non-200 response, `wp_die()` is called with the error message.

---

**Step 3 — Markdown → HTML conversion**

The `content` field returned by the API is in **Markdown format**. The built-in `markdown_to_html()` function converts it to clean HTML before inserting into WordPress. Supported syntax:

| Markdown | Output |
|---|---|
| `# Heading` | `<h1>` – `<h6>` |
| `**bold**`, `*italic*` | `<strong>`, `<em>` |
| `` `code` `` | `<code>` |
| ` ```fenced block``` ` | `<pre><code>` |
| `- item` / `1. item` | `<ul><li>` |
| `> quote` | `<blockquote>` |
| `[text](url)` | `<a href>` |

No external Markdown library is needed — the converter is self-contained in the file.

---

**Step 4 — Resolve or create the WordPress category**

```php
$cat_id = get_cat_ID($cat_name);
if (!$cat_id) {
    $cat_id = wp_create_category($cat_name);
}
```

Checks whether the category already exists in WordPress. If not, it is created automatically. The category name is derived from `$blog['category']` (title-cased).

---

**Step 5 — Insert the WordPress post**

```php
wp_insert_post([
    'post_title'    => $blog['title'],
    'post_content'  => $post_content,   // HTML
    'post_excerpt'  => $blog['summary'],
    'post_status'   => 'publish',
    'post_type'     => 'post',
    'post_category' => [$cat_id],
    'tags_input'    => [$blog['topic']],
]);
```

The post is created with status `publish` so it is immediately live. The specific topic (e.g. `"AI Agents in 2026"`) is added as a tag.

---

**Step 6 — Upload the featured image**

The `image_base64` field (a base64-encoded PNG generated by Vertex AI Imagen) is processed in four steps:

| Step | Function | What it does |
|---|---|---|
| 1 | `base64_decode()` | Converts base64 string to raw PNG bytes |
| 2 | `wp_upload_bits()` | Saves the PNG file into `/wp-content/uploads/YYYY/MM/` |
| 3 | `wp_insert_attachment()` | Registers the file as a Media Library item attached to the post |
| 4 | `wp_generate_attachment_metadata()` | Generates all registered image sizes (thumbnail, medium, large, etc.) |
| 5 | `set_post_thumbnail()` | Sets the attachment as the post's Featured Image |

---

### Output

After a successful run, `print_r()` outputs:

```
Array
(
    [post_id]            => 42
    [post_url]           => https://your-site.com/how-ai-agents-are-rewriting-software/
    [title]              => How AI Agents Are Rewriting the Rules of Software
    [category]           => Artificial Intelligence
    [topic]              => AI Agents in 2026
    [summary]            => AI agents are transforming software by autonomously executing complex tasks.
    [featured_image_id]  => 87
    [featured_image_url] => https://your-site.com/wp-content/uploads/2026/03/blog-3f2a1c.png
)
```

Use `$post_id` and `$featured_image_id` to do any further processing (e.g. updating custom fields, sending notifications, triggering other workflows).

---

### Requirements

- PHP 8.0+ with the `curl` extension enabled
- WordPress 5.0+
- The LangChain API must be reachable at `http://localhost:8000` from the server running WordPress (adjust `$API_URL` at the top of the file if they run on different hosts)
