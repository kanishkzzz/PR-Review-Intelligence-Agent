<div align="center">

<img src="https://img.shields.io/badge/BugBeGone-AI%20PR%20Reviewer-6366f1?style=for-the-badge&logo=github&logoColor=white" alt="BugBeGone"/>

# 🤖 BugBeGone

### Multi-agent AI that reviews your Pull Requests before humans do.

The moment a PR is opened — three specialized AI agents run in parallel, catching security vulnerabilities, logic bugs, and missing tests. Structured review posted as a GitHub comment. Zero manual steps.

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB)](https://react.dev/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-6C3EF4?style=flat-square)](https://www.trychroma.com/)
[![GitHub Models](https://img.shields.io/badge/GitHub%20Models-GPT--4o-181717?style=flat-square&logo=github)](https://github.com/marketplace/models)
[![Render](https://img.shields.io/badge/Deployed%20on-Render-46E3B7?style=flat-square)](https://render.com/)

**[Live Demo](https://pr-review-intelligence-agent.vercel.app)** · **[Report Bug](../../issues)** · **[Request Feature](../../issues)**

---

![BugBeGone Dashboard](./bugbegone-screenshot.png)

</div>

---

## What it does

You open a PR. BugBeGone immediately:

1. Fetches the diff and indexes the affected files into a vector store
2. Runs three specialist agents **in parallel** — each focused on one concern
3. A critic agent validates the findings — removing false positives, correcting severity
4. Posts a structured review comment directly on your PR

No polling. No waiting. Just open the PR and the review appears.

---

## Architecture

```
GitHub PR opened / updated
           │
           ▼
   FastAPI Webhook Listener
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
Fetch PR Diff   Index changed files
                → ChromaDB (RAG)
                → text-embedding-3-small
    │
    ▼
asyncio.gather() — 3 agents in parallel
    │
  ┌─┴──────────────┬──────────────────┐
  ▼                ▼                  ▼
Security         Logic/Bug        Test Coverage
Agent            Agent            Agent
  │                │                  │
  └────────────────┴──────────────────┘
                   │
                   ▼
           Critic Agent
        (validates findings,
         removes false positives)
                   │
                   ▼
        Post GitHub PR Comment
```

---

## Features

| Feature | Details |
|---|---|
| 🔒 **Security Agent** | Hardcoded secrets, auth bypass, SQL injection, exposed keys |
| 🐛 **Logic Agent** | Null checks, race conditions, silent error swallowing, edge cases |
| 🧪 **Test Agent** | Missing unit tests, untested error paths, integration gaps |
| 🎯 **Critic Agent** | Validates all findings — removes false positives, corrects severity |
| ⚡ **Streaming Response** | Real-time status updates as agents run — no blank loading screen |
| 🧠 **RAG Context** | ChromaDB + `text-embedding-3-small` — agents see function-level context, not just the raw diff |
| 🪝 **Webhook Integration** | Fully automated — zero manual steps after setup |
| 🖥️ **Web Dashboard** | Manually trigger and inspect any PR review |

---

## Tech Stack

**Backend**
- Python · FastAPI · Uvicorn
- GitHub Models API — `gpt-4o` (inference) + `text-embedding-3-small` (embeddings)
- ChromaDB — vector store for RAG
- `asyncio.gather()` — parallel agent execution
- GitHub REST API — diff fetching + comment posting

**Frontend**
- React + Vite
- Tailwind CSS v4
- `motion/react` — animations
- Lucide React — icons

**Infrastructure**
- Backend → Render
- Frontend → Vercel
- Embeddings + LLM → GitHub Models (free with Student Developer Pack)

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- GitHub Personal Access Token (with `repo` + `models:read` scope)

### Backend

```bash
cd server
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

Create `server/.env`:
```env
GITHUB_TOKEN=your_github_personal_access_token
```

Start the server:
```bash
uvicorn main:app --reload
```

### Frontend

```bash
cd client
npm install
npm run dev
```

Visit `http://localhost:5173`

### Webhook Setup

1. Deploy backend (or expose locally via [ngrok](https://ngrok.com): `ngrok http 8000`)
2. Go to your target repo → **Settings → Webhooks → Add webhook**
3. Payload URL: `<your-url>/webhook`
4. Content type: `application/json`
5. Events: **Pull requests only**

---

## API

| Endpoint | Method | Description |
|---|---|---|
| `/review` | `POST` | Manually trigger a review for any PR URL |
| `/webhook` | `POST` | GitHub webhook receiver — auto-triggers on PR open/sync |

**Request:**
```json
{
  "pr_url": "https://github.com/owner/repo/pull/123",
  "token": "optional_github_token"
}
```

**Response** (streamed as SSE):
```
data: {"status": "fetching", "message": "🔍 Fetching PR metadata..."}
data: {"status": "analyzing", "message": "🤖 Running 3 agents in parallel..."}
data: {"status": "complete", "result": { ... }}
```

---

## Roadmap

- [ ] N8N workflow orchestration — Slack + email alerts on HIGH risk
- [ ] Developer memory — track per-developer bug patterns across PRs
- [ ] Multi-repo dashboard with review history
- [ ] Custom rules engine — define team-specific review rules via YAML
- [ ] Auto-fix suggestions — agent proposes fixed code in diff format

---

## Why not just use GitHub Copilot review?

Copilot reviews one thing at a time, sequentially. BugBeGone runs specialist agents in parallel — each trained to look for one category of problem, deeply. The critic layer removes noise. The RAG layer gives agents full repo context, not just the changed lines. And it's fully open source.

---

<div align="center">

Built by [Kanishk Negi](https://github.com/kanishkzzz)

*B.Tech — Applied Physics, Delhi Technological University*

</div>