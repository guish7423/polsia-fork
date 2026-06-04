<div align="center">

# CrossWave ⚡

**Self-hosted AI Agent Platform — Multi-Tenant, Production-Ready**

[![CI](https://github.com/guish7423/polsia-fork/actions/workflows/ci.yml/badge.svg)](https://github.com/guish7423/polsia-fork/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/downloads/release/python-312/)
[![Tests](https://img.shields.io/badge/tests-654%20passed-green.svg)](docs/architecture.md)

*CrossWave (formerly Polsia Fork) — AI-powered autonomous agent platform with multi-tenancy, MCP tool gateway, RAG knowledge base, A2A agent mesh, visual workflow builder, and enterprise production hardening.*

</div>

---

## Overview

CrossWave is an **open-source, self-hosted AI Agent PaaS** — a production-grade platform for building, deploying, and monitoring autonomous AI agents at scale. It provides the infrastructure layer (LLM abstraction, resource management, multi-tenant isolation), the orchestration layer (workflows, A2A agent mesh, scheduling), and the control plane (quotas, audit, observability, plugin system) needed to run AI-powered operations.

Born from an upstream fork of [Polsia](https://polsia.ai), CrossWave replaced Claude Code CLI integration with a universal LLM API abstraction (DeepSeek, OpenAI, or any compatible provider), then added 15+ modules spanning the full AI platform spectrum.

### Key Capabilities

| Category | Capabilities |
|----------|-------------|
| **🧠 LLM Provider Abstraction** | Dify-style ModelInstance: rate limiting, cost tracking, fallback chains, streaming, JSON mode |
| **🏢 Multi-Tenancy** | Tenant isolation at DB, API, and middleware layers; subscription plans; per-tenant quotas |
| **🔧 MCP Gateway** | Register, discover, and execute external tools via Model Context Protocol |
| **🤖 Agent Mesh (A2A)** | Agent-to-agent communication, capability-based discovery, Redis pub/sub routing |
| **📦 RAG Knowledge Base** | Document upload (PDF/TXT/MD/CSV), ChromaDB vector search, agent RAG context injection |
| **⚙️ Workflow Builder** | Visual DAG editor (ReactFlow), 4 node types (Agent/Tool/Trigger/Output), execution engine |
| **📊 Neural Hub Console** | Real-time alerts, system health, SSE agent streaming logs, Cmd+K global search, notification center |
| **🔐 Production Hardening** | Rate limiting, structured error handling, JSON logging, audit chain (SHA256), Docker sandbox |
| **🔄 Self-Optimization** | Auto-tune agent configs, performance analysis, config rollback with degradation detection |
| **📈 Prometheus Observability** | HTTP/Agent/LLM metrics, Grafana dashboards, /metrics endpoint |

## Quick Start

### Prerequisites
- Python 3.12+, Node.js 20+, Docker & Docker Compose

### 1. Clone & Backend Setup
```bash
git clone https://github.com/guish7423/polsia-fork.git
cd polsia-fork

# Backend dependencies
uv sync
cp .env.example .env

# Run tests (no API key needed — mock mode)
LLM_API_MOCK=true python3 -m pytest tests/unit/ -q
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm test -- --watchAll=false  # 135 frontend tests
npm run dev
```

### 3. Full Stack with Docker
```bash
make up       # Start all services
make migrate  # Run Alembic migrations
make seed     # Seed company configuration
```

Open http://localhost → Frontend Dashboard (API key: `dev-key-change-in-production`)

## Architecture

CrossWave follows a **four-layer model** inspired by operating system design principles:

```
┌──────────────────────────────────┐
│       Control Plane              │
│  Auth · Multi-Tenancy · Quotas   │
│  Audit Chain · Rate Limit        │
│  Alerts · Health · Prometheus    │
├──────────────────────────────────┤
│    Orchestration Engine          │
│  Workflow DAG · Agent Mesh/A2A   │
│  Supervisor · Scheduler          │
│  Celery Workers · Agent Lifecycle│
├──────────────────────────────────┤
│    Plugin / Protocol Layer       │
│  MCP Gateway · Plugin System     │
│  RAG (ChromaDB) · Tool Runner    │
│  Webhooks · Function Calling     │
├──────────────────────────────────┤
│    Kernel / Resource Layer       │
│  LLM Provider (ModelInstance)    │
│  Durable Checkpoint · Sandbox    │
│  Config Tuner · Self-Optimization│
└──────────────────────────────────┘
```

See [docs/architecture.md](docs/architecture.md) for detailed architecture diagrams and module map.

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.12, FastAPI (async), SQLAlchemy 2.0, Celery, Redis |
| **Frontend** | Next.js 14, React 18, TypeScript, Tailwind CSS, React Flow |
| **Database** | PostgreSQL 16 (production), SQLite (dev/test) |
| **LLM** | DeepSeek API, OpenAI-compatible APIs (any provider via `LLM_API_BASE_URL`) |
| **Vector DB** | ChromaDB (RAG knowledge base) |
| **Observability** | Prometheus, Grafana |
| **Auth** | API key (simple), multi-tenant JWT-ready architecture |
| **Sandbox** | Docker (agent code execution isolation) |
| **Package** | uv (Python), npm (Node.js), Docker Compose (deployment) |

## Project Structure

```
polsia-fork/
├── app/
│   ├── agents/          # 19+ AI agents + Supervisor
│   ├── api/v1/          # 16+ API routers
│   ├── core/            # Auth, LLM, Checkpoint, Metrics, Tenant
│   ├── models/          # 30+ SQLAlchemy ORM tables
│   └── services/        # Business logic services
├── celery_app/          # Celery workers + beat schedule
├── frontend/            # Next.js 14 dashboard (23+ pages)
├── tests/               # 485+ backend unit tests
├── docker/              # Prometheus, Grafana configs
├── docs/                # Architecture documentation
├── docker-compose.yml   # Full stack deployment (9 services)
└── nginx/               # Reverse proxy config
```

## API Endpoints

### Core
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check |
| POST | `/api/v1/tasks` | Create task |
| GET | `/api/v1/tasks` | List tasks |
| WS | `/api/v1/ws` | Real-time activity feed |

### Agents
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/agents/monitor` | Agent status dashboard |
| GET | `/api/v1/agents/runs` | Agent run history |
| GET | `/api/v1/agents/runs/{id}` | Run detail with telemetry |
| POST | `/api/v1/agents/{type}/trigger` | Trigger agent execution |
| GET | `/api/v1/agents/{type}/stream` | SSE agent streaming log |

### Dashboard & Analytics
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/dashboard/summary` | Dashboard metrics |
| GET | `/api/v1/dashboard/health` | System health check (5 dimensions) |
| GET | `/api/v1/usage/stats` | Model usage statistics |
| GET | `/api/v1/usage/recent` | Recent LLM calls |
| GET | `/api/v1/usage/costs` | Cost breakdown |
| GET | `/api/v1/usage/summary` | Usage summary |

### Multi-Tenancy & Quotas
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/tenants/{id}/quota` | Per-tenant quota usage |
| GET | `/api/v1/tenants` | List tenants (admin) |
| POST | `/api/v1/tenants` | Create tenant (admin) |

### MCP Gateway & Plugins
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/mcp/tools` | Register tool |
| GET | `/api/v1/mcp/tools` | List tools |
| DELETE | `/api/v1/mcp/tools/{id}` | Unregister tool |
| POST | `/api/v1/mcp/tools/{id}/execute` | Execute tool |
| POST | `/api/v1/mcp/tools/execute-by-name` | Execute tool by name |
| POST | `/api/v1/plugins` | Register plugin |
| GET | `/api/v1/plugins` | List plugins |
| PATCH | `/api/v1/plugins/{id}` | Update plugin |

### Agent Mesh (A2A)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/mesh/messages` | Send message |
| GET | `/api/v1/mesh/messages/outbox` | Sent messages |
| GET | `/api/v1/mesh/messages/inbox` | Received messages |
| POST | `/api/v1/mesh/messages/{id}/deliver` | Mark delivered |
| POST | `/api/v1/mesh/messages/{id}/read` | Mark read |
| GET | `/api/v1/mesh/capabilities` | Query agents by capability |

### RAG Knowledge Base
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/knowledge/upload` | Upload document |
| GET | `/api/v1/knowledge/documents` | List documents |
| DELETE | `/api/v1/knowledge/documents/{id}` | Delete document |
| GET | `/api/v1/knowledge/semantic-search` | Semantic search |

### Workflow Builder
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/workflows` | Create workflow |
| GET | `/api/v1/workflows` | List workflows |
| GET | `/api/v1/workflows/{id}` | Get workflow |
| PUT | `/api/v1/workflows/{id}` | Update workflow |
| DELETE | `/api/v1/workflows/{id}` | Delete workflow |
| POST | `/api/v1/workflows/{id}/run` | Execute workflow |
| GET | `/api/v1/workflows/{id}/runs` | Workflow run history |
| GET | `/api/v1/workflows/runs/{run_id}` | Run status |

### Alerts & Notifications
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/alerts/active` | Active alerts |
| POST | `/api/v1/alerts/{id}/dismiss` | Dismiss alert |
| GET | `/api/v1/notifications` | List notifications |
| GET | `/api/v1/notifications/unread-count` | Unread count |
| POST | `/api/v1/notifications/{id}/read` | Mark read |
| POST | `/api/v1/notifications/read-all` | Mark all read |

### Finance & Social
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/finance/summary` | Finance summary |
| GET | `/api/v1/social/posts` | Social media posts |
| POST | `/api/v1/social/posts` | Create post |

### Audit & Scheduler & Sandbox
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/audit/entries` | Audit chain entries |
| GET | `/api/v1/audit/verify` | Verify chain integrity |
| GET | `/api/v1/scheduler/status` | Scheduler status |
| POST | `/api/v1/scheduler/rebalance` | Trigger rebalance |
| GET | `/api/v1/mcp/tools` | View MCP tools |
| GET | `/api/v1/sandbox/summary` | Sandbox summary |
| GET | `/api/v1/sandbox/pending` | Pending executions |

### Supervisor
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/supervisor/plan` | Create execution plan |
| POST | `/api/v1/supervisor/execute` | Execute plan |
| GET | `/api/v1/supervisor/plan/{id}/status` | Plan status |

All endpoints require `X-API-Key` header (default: `dev-key-change-in-production`).

## Testing

```bash
# Backend unit tests (485+) — no Docker, no API key needed
LLM_API_MOCK=true python3 -m pytest tests/unit/ -v

# With coverage
LLM_API_MOCK=true python3 -m pytest tests/unit/ --cov=app --cov-report=term-missing

# Frontend tests (135+)
cd frontend && npm test -- --watchAll=false

# Frontend build
cd frontend && npm run build

# Integration tests (Docker, testcontainers)
CLAUDE_CLI_MOCK=true python3 -m pytest tests/integration/ -v -m integration
```

## Module Map

| # | Phase | Description | Status |
|---|-------|-------------|--------|
| 1 | **Kernel** (Phase 0-2) | Status Machine, Agent Schema, Checkpoint, HITL, Industry Packs | ✅ |
| 2 | **LLM Providers** (Phase 3-4) | Dify-style ModelInstance, cost tracking, streaming, usage analytics | ✅ |
| 3 | **Agent Observability** (Phase 5) | AgentRun telemetry, monitor API, execution spans | ✅ |
| 4 | **Supervisor** (Phase 6) | LLM-powered task planner, goal decomposition, smart routing | ✅ |
| 5 | **Production Hardening** (Phase 7-8) | Structured errors, JSON logging, rate limiting, test coverage | ✅ |
| 6 | **Dashboard** (Phase 9) | Agent dashboard, run history, activity feed, real-time monitoring | ✅ |
| 7 | **Platform OS** (Phase A) | Multi-tenancy, MCP gateway, resource quotas, durable checkpoint, plugins | ✅ |
| 8 | **Agent Mesh** (Phase B) | A2A protocol, capability registry, Redis pub/sub, REST API | ✅ |
| 9 | **True AI OS** (Phase C) | Docker sandbox, SHA256 audit chain, scheduler, marketplace, self-opt | ✅ |
| 10 | **Auto-Optimization** (Phase D) | Config tuner, base agent integration, rollback mechanism | ✅ |
| 11 | **Dashboard v2** | 8 new UI: Quota, MCP, Plugins, Audit, Scheduler, Sandbox, Marketplace | ✅ |
| 12 | **Neural Hub Console** | Alerts, system health, SSE logs, Cmd+K search, notifications | ✅ |
| 13 | **RAG Knowledge Base** | Document upload, ChromaDB, Agent RAG injection, knowledge UI | ✅ |
| 14 | **Function Calling** | ToolRunner, multi-round agent tool use, per-agent allowlists | ✅ |
| 15 | **Prometheus** | HTTP/Agent/LLM metrics, middleware, Grafana integration | ✅ |
| 16 | **Workflow Builder v1** | DAG engine, ReactFlow canvas, 4 node types, REST API | ✅ |

**Total: ~485 backend tests + ~135 frontend tests = ~654 tests** ✅

## Deployment

### Docker Compose (Production Stack)

```bash
# Full stack: postgres + redis + backend + celery + frontend + nginx + chroma + prometheus + grafana
docker compose up -d
docker compose exec backend alembic upgrade head
```

Services:
| Service | Port | Description |
|---------|------|-------------|
| `nginx` | 80 | Reverse proxy |
| `frontend` | (internal) | Next.js dashboard |
| `backend` | 8000 | FastAPI REST API |
| `celery_worker` | (internal) | Agent execution workers |
| `celery_beat` | (internal) | Scheduled task dispatcher |
| `postgres` | 5432 | Primary database |
| `redis` | 6379 | Queue + Pub/Sub |
| `chroma` | 8001 | Vector database (RAG) |
| `prometheus` | 9090 | Metrics collection |
| `grafana` | 3001 | Observability dashboards |

### Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY` | `dev-key-change-in-production` | API key for all requests |
| `LLM_API_MOCK` | `true` | Mock mode (no real LLM calls) |
| `LLM_API_BASE_URL` | `https://api.deepseek.com/v1` | LLM API endpoint |
| `LLM_MODEL` | `deepseek-chat` | Model name |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |
| `QUOTA_ENABLED` | `true` | Resource quota enforcement |
| `RAG_ENABLED` | `true` | RAG knowledge base |
| `SANDBOX_ENABLED` | `false` | Docker sandbox isolation |

Full reference: [.env.example](.env.example)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, branch strategy, testing requirements, and PR workflow.

## Project Status

CrossWave is **active and production-ready**. All 16 modules are complete and tested.

### Roadmap

| Feature | Priority | Status |
|---------|----------|--------|
| Plugin SDK v1 | Medium | 🔜 Planned |
| Visual Workflow Builder v2 | Medium | 🔜 Planned |
| K8s Native Deployment | Low | 🔜 Planned |
| Multi-Modal Agent Support | Low | 🔜 Planned |
| Public Agent Marketplace | Low | 🔜 Planned |

## License

[MIT](LICENSE) © 2025-2026 guish7423

## Acknowledgements

- [Polsia](https://polsia.ai) — The original upstream project this fork was built upon
- [Dify](https://github.com/langgenius/dify) — Inspiration for the ModelInstance provider abstraction and plugin architecture
- [CrewAI](https://github.com/crewAIInc/crewAI) — Inspiration for agent mesh / A2A interaction patterns
- [Temporal](https://temporal.io) — Inspiration for durable execution and checkpoint design
