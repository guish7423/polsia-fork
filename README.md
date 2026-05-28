# Polsia Fork

AI-powered autonomous company operations platform. A fork of [Polsia](https://polsia.ai) — replaces Claude Code CLI with direct LLM API calls (DeepSeek-compatible).

## Architecture

```
Frontend (Next.js 14)  →  FastAPI Backend  →  Celery Workers (Agent Exec)
                                │                       │
                          PostgreSQL (Primary)      Redis (Queue+Pub/Sub)
```

### 10 AI Agents
| Agent | Role |
|-------|------|
| Orchestrator/CEO | Task planning, delegation, daily cycles |
| Business Planning | Market analysis, strategy recommendations |
| Competitor Research | Competitive intelligence tracking |
| Social Media | Content creation, posting, engagement |
| Email Outreach | Prospect sourcing, campaign management |
| Customer Support | Ticket triage, response generation |
| Ads Management | Campaign optimization, budget tracking |
| Code Generation | Development task automation |
| Finance | Revenue tracking, expense management |
| Deployment | Infrastructure management |

### Tech Stack
- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Celery, Redis
- **Frontend**: Next.js 14, React 18, TypeScript, Tailwind CSS
- **Database**: PostgreSQL 16 (production), SQLite (development/testing)
- **LLM**: DeepSeek API (Flash/Pro), compatible with any OpenAI-format API

## Quick Start

### Prerequisites
- Python 3.12+, Node.js 20+, Docker & Docker Compose

### Local Development
```bash
# Backend
cd backend
uv sync
cp .env.example .env
LLM_API_MOCK=true uv run uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### Docker (Full Stack)
```bash
make up       # Start all services
make migrate  # Run database migrations
make seed     # Seed company configuration
```

Open http://localhost → Frontend Dashboard

## Testing
```bash
LLM_API_MOCK=true uv run pytest tests/unit/ -v        # 66 unit tests
uv run pytest tests/unit/ --cov=app --cov-report=term-missing  # Coverage
```

## API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/health | Health check |
| GET | /api/v1/tasks | List tasks |
| POST | /api/v1/tasks | Create task |
| GET | /api/v1/agents/status | Agent status list |
| POST | /api/v1/agents/{type}/trigger | Trigger agent |
| GET | /api/v1/dashboard/summary | Dashboard metrics |
| GET | /api/v1/finance/summary | Finance summary |
| WS | /api/v1/ws | Activity feed |

All endpoints require `X-API-Key` header.

## Key Differences from Upstream
| Feature | Original Polsia | This Fork |
|---------|----------------|-----------|
| LLM Integration | Claude Code CLI subprocess | Direct LLM API (DeepSeek) |
| Python | 3.11 | 3.12 |
| Package Manager | pip + requirements.txt | uv |
| Test Mock | CLAUDE_CLI_MOCK | LLM_API_MOCK |

## Project Structure
```
app/           → agents/ (10), api/v1/ (8 routes), core/, models/ (17 tables), services/
celery_app/    → Task queue + beat schedule
tests/         → 66 unit tests
migrations/    → Alembic database migrations
frontend/      → Next.js 14 dashboard (13 pages)
```

## License
MIT
