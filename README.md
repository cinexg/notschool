# Notschool OS — Multi-Agent AI Learning Architect

Built for the **Google Gen AI Academy APAC 2026 Hackathon** — Track 1: Agentic AI

---

## Overview

Most AI educational tools are stateless question-answering interfaces. Notschool OS is different — it is a fully automated, multi-agent pipeline that takes a single user goal and produces a complete, scheduled, resource-backed learning plan without any further input.

The system accepts a text goal or an image of a syllabus, textbook index, or job description. It then reasons over that input, constructs a structured 7-day curriculum, sources relevant video tutorials, fetches live industry trends, persists the plan to a database, and books the first study session directly into the user's Google Calendar — all in a single request.

---

## Hackathon Criteria Alignment

| Criterion | Implementation |
|---|---|
| Primary Agent + Sub-Agents | LangGraph orchestrates four specialized agents: Architect, Librarian, Scheduler, and DB Saver |
| Store and Retrieve Structured Data | SQLite tracks study sessions with status, event links, and timestamps; supports auto-rescheduling of missed sessions |
| Integrate Tools via MCP | YouTube search and Google Calendar creation are exposed as MCP tools via a FastMCP server over stdio transport |
| Multi-Step Workflow | Goal input → multimodal curriculum generation → resource retrieval → persistence → calendar scheduling |
| API-based System | All logic is served through a FastAPI backend with clearly defined REST endpoints |

---

## System Architecture

The pipeline is implemented as a directed LangGraph state machine. Each node is a stateless function that reads from and writes to a shared `NotschoolState` TypedDict. The graph executes linearly in the following order:

```
[User Request]
      |
      v
  Architect          Multimodal curriculum generation via Gemini 2.0 Flash.
      |              Accepts text or image input. Returns a structured 7-day
      |              JSON plan with topics, durations, and search queries.
      v
  Librarian          Resource curation agent. Queries the YouTube Data API
      |              for tutorial videos using the curriculum's search queries.
      |              In interview mode, additionally fetches live web trends
      |              via DuckDuckGo Search.
      v
  Scheduler          Reads the curriculum and creates a Google Calendar event
      |              for the first study session using the user's OAuth token.
      |              Uses dynamic duration from the curriculum JSON.
      v
  DB Saver           Persists the session record to SQLite with the goal,
      |              module name, scheduled time, and calendar event link.
      v
[Final State returned to FastAPI]
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph v0.0.26 |
| LLM | Gemini 2.0 Flash via `google-genai` SDK |
| Backend | FastAPI + Uvicorn |
| Frontend | HTML5, Tailwind CSS, Vanilla JS |
| Database | SQLite3 |
| Tool Integration | Model Context Protocol (MCP) over stdio via `FastMCP` |
| External APIs | YouTube Data API v3, Google Calendar API (OAuth 2.0) |
| Web Search | DuckDuckGo Search (`duckduckgo-search`) |
| Retry / Resilience | Tenacity (exponential backoff on Gemini 503/429 errors) |
| Deployment | Google Cloud Run |

---

## Agent Descriptions

### Architect (`agents/architect_node.py`)
The principal reasoning agent. Calls Gemini 2.0 Flash with either a text prompt or a multimodal prompt containing an uploaded image. Returns a normalized JSON curriculum with 7 daily modules, YouTube search queries, industry trends, and recommended certifications. Implements tenacity-based exponential backoff (2s, 4s, 8s, 16s) to handle Gemini API 503/429 spikes gracefully. Supports two modes: `learning` and `interview`.

### Librarian (`agents/librarian_node.py`)
The resource curation agent. Reads the `search_queries` field from the Architect's output and calls the YouTube Data API to retrieve one tutorial video per query. In `interview` mode, it additionally triggers a DuckDuckGo web search for live tech stack trends and certification requirements.

### Scheduler (`agents/scheduler_node.py`)
The calendar agent. Uses the user's OAuth 2.0 access token (passed at request time — no server-side token storage) to create a Google Calendar event for the first curriculum module. Event duration is derived from the `duration_hours` field in the curriculum JSON. If no token is provided, this step is skipped gracefully.

### DB Saver (`agents/db_node.py`)
The persistence agent. Writes the completed session record to SQLite, including the goal, module name, scheduled timestamp, and calendar event link. This record is later used by the `/api/reschedule` endpoint to detect and auto-reschedule missed sessions.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves the frontend UI (`index.html`) |
| `POST` | `/api/generate` | Triggers the full LangGraph pipeline. Accepts `goal`, `mode`, `access_token`, and an optional `image` file upload |
| `POST` | `/api/reschedule` | Scans the database for missed sessions and shifts them forward by one day in Google Calendar |
| `POST` | `/api/reset` | Clears all session records from the database (for demo purposes) |

---

## Project Structure

```
notschool/
├── main.py                   FastAPI application, route definitions, static file serving
├── requirements.txt
├── .env                      Environment variables (not committed)
│
├── core/
│   ├── config.py             Environment validation on startup
│   ├── graph.py              LangGraph state machine definition and compilation
│   └── state.py              NotschoolState TypedDict schema
│
├── agents/
│   ├── architect_node.py     Curriculum generation agent (Gemini 2.0 Flash, multimodal)
│   ├── librarian_node.py     Resource curation agent (YouTube + DuckDuckGo)
│   ├── scheduler_node.py     Google Calendar scheduling agent
│   └── db_node.py            SQLite persistence agent
│
├── tools/
│   ├── mcp_server.py         FastMCP server exposing YouTube search and Calendar tools
│   ├── youtube_client.py     YouTube Data API v3 wrapper
│   └── calendar_client.py    Google Calendar API OAuth wrapper
│
├── db/
│   ├── schema.py             SQLite schema initialization
│   └── crud.py               Database read/write operations
│
└── frontend/
    └── index.html            Single-page UI (Tailwind CSS, Vanilla JS)
```

---

## Setup

### Prerequisites

Obtain API credentials for the following:

- **Gemini:** Google AI Studio API key
- **YouTube:** YouTube Data API v3 key (Google Cloud Console)
- **Google Calendar:** OAuth 2.0 Client ID and Secret (Google Cloud Console, with Calendar API enabled)

### Local Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/cinexg/notschool-os.git
   cd notschool-os
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   YOUTUBE_API_KEY=your_youtube_api_key
   GOOGLE_CLIENT_ID=your_oauth_client_id
   GOOGLE_CLIENT_SECRET=your_oauth_client_secret
   ```

4. Start the server:
   ```bash
   uvicorn main:app --reload
   ```

5. Open `http://localhost:8000` in your browser.

### Cloud Run Deployment

The application is designed for containerized deployment on Google Cloud Run. Set all environment variables as Cloud Run secrets or environment variable configuration. The server binds to the `PORT` environment variable automatically via Uvicorn.

---

## Key Design Decisions

**Why LangGraph over a simple function chain?**
LangGraph provides a typed shared state (`NotschoolState`) that flows through every agent, making the data contract explicit and auditable. Each node function is independently testable and the graph is trivially extensible — adding a new agent is a matter of registering a new node and edge.

**Why MCP for tool integration?**
Exposing tools via the Model Context Protocol decouples the tool implementations from the agent logic. The same MCP server can be connected to any MCP-compatible client, making the toolset reusable outside of this specific pipeline.

**Why per-request OAuth tokens instead of server-stored credentials?**
The user's Google OAuth access token is passed with each request and used transiently. The server never stores or caches credentials, keeping the architecture stateless and avoiding the complexity and security surface of a token management layer.

**Why DuckDuckGo Search instead of Google Search?**
The `googlesearch-python` library scrapes Google directly and is rate-limited aggressively (HTTP 429) on shared cloud IPs. The `duckduckgo-search` library uses an unofficial API that is not subject to the same restrictions and does not require an API key.
