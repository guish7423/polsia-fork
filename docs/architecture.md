# CrossWave Architecture

## Four-Layer Model

CrossWave is built on a four-tier architecture, inspired by operating system design principles.

```mermaid
graph TB
    subgraph "Control Plane"
        TENANT[Multi-Tenancy & Auth]
        QUOTA[Resource Quotas & Rate Limits]
        AUDIT[Audit Chain & Compliance]
    end

    subgraph "Orchestration Engine"
        DAG[Workflow Builder DAG Engine]
        MESH[Agent Mesh / A2A Protocol]
        SUPERVISOR[Supervisor Agent & Task Planner]
        SCHEDULER[Resource-Aware Scheduler]
    end

    subgraph "Plugin / Protocol Layer"
        MCP[MCP Gateway & Tool Registry]
        PLUGIN[Plugin System v1 / Webhooks]
        RAG[RAG Knowledge Base / ChromaDB]
        FC[Function Calling / Tool Runner]
    end

    subgraph "Kernel / Resource Layer"
        LLM[LLM Provider Abstraction]
        MODEL[ModelInstance / ModelManager]
        CHECKPOINT[Durable Execution / Checkpoint]
        METRICS[Prometheus Observability]
        SANDBOX[Docker Sandbox Isolation]
        OPT[Self-Optimization / Config Tuner]
    end

    CONTROL_PLANE --> ORCHESTRATION_ENGINE
    ORCHESTRATION_ENGINE --> PLUGIN_PROTOCOL
    PLUGIN_PROTOCOL --> KERNEL_RESOURCE
```

## Module Map

| Module | Layer | Status | Tests |
|--------|-------|--------|-------|
| Phase 0-2: Status Machine, Agent Schema, Checkpoint, HITL | Kernel | ✅ | 65 |
| Industry Packs (Social, Finance, Ads, etc.) | Kernel | ✅ | 40 |
| Phase 3: LLM Provider Abstraction (Dify-style) | Kernel | ✅ | 17 |
| Phase 4: Usage Analytics (ModelCall ORM) | Kernel | ✅ | 15 |
| Phase 5: Agent Observability (AgentRun, Monitor API) | Orchestration | ✅ | 30 |
| Phase 6: Supervisor Agent & Task Planner | Orchestration | ✅ | 21 |
| Phase 7: Production Hardening (Errors, Logging, RateLimit) | Control Plane | ✅ | 29 |
| Phase 8: Test Coverage (ModelInstance, Self-Opt) | Cross-cutting | ✅ | 17 |
| Phase 9: Frontend Dashboard (Agents, Runs, Activity) | Control Plane | ✅ | 63 frontend |
| Phase A: Platform OS (Multi-Tenancy, MCP, Quotas, Checkpoint, Plugins) | Control + Plugin | ✅ | 68 |
| Phase B: Agent Mesh (A2A, Capability Registry, Mesh Bus, API) | Orchestration | ✅ | 43 |
| Phase C: True AI OS (Sandbox, Audit, Scheduler, Marketplace, Self-Opt) | Kernel | ✅ | 36 |
| Phase D: Auto-Optimization (ConfigTuner, Base Integration, Rollback) | Kernel | ✅ | 20 |
| Frontend Dashboard v2 (8 new UI pages) | Control Plane | ✅ | 70 frontend |
| Neural Hub Console (Alerts, Health, SSE Logs, Search, Notifications) | Control Plane | ✅ | 67 |
| RAG Knowledge Base (ChromaDB, Document Upload, Agent RAG) | Plugin | ✅ | 53 |
| Agent Function Calling (ToolRunner, Multi-Round, Allowlist) | Plugin | ✅ | 34 |
| Prometheus Observability (Metrics, Middleware, Dashboards) | Control Plane | ✅ | 5 |
| Workflow Builder v1 (DAG Engine, ReactFlow Canvas, API) | Orchestration | ✅ | 34 |
| **Total** | | **15/15** | **~654** |

## Key Data Flow

```mermaid
sequenceDiagram
    participant User
    participant FastAPI
    participant DB as PostgreSQL
    participant Celery
    participant LLM as LLM API
    participant Chroma
    participant MCP as MCP Tools

    User->>FastAPI: HTTP / WebSocket
    FastAPI->>DB: Auth + Quota Check
    FastAPI->>Celery: Dispatch Agent Task
    Celery->>LLM: call_llm() / call_llm_with_tools()
    LLM-->>Celery: Response / tool_calls
    Celery->>MCP: Execute Tool
    MCP-->>Celery: Tool Result
    Celery->>Chroma: RAG Retrieval
    Chroma-->>Celery: Knowledge Context
    Celery->>DB: Write AgentRun + ModelCall
    Celery-->>FastAPI: SSE Stream / Result
    FastAPI-->>User: JSON / SSE / WS Event
```

## Directory Structure

```
polsia-fork/
├── app/
│   ├── agents/          # 19+ AI agents + Supervisor
│   ├── api/v1/          # 16+ API routers
│   ├── core/            # Auth, LLM, Checkpoint, Metrics, Tenant
│   ├── models/          # 30+ SQLAlchemy ORM tables
│   └── services/        # Business logic services
├── celery_app/          # Celery workers + beat schedule
├── frontend/            # Next.js 14 dashboard
│   ├── src/app/         # 23+ page routes
│   └── src/components/  # Shared UI components
├── tests/               # 485+ backend unit tests
├── docker/              # Prometheus, Grafana configs
├── docs/                # Architecture documentation
├── docker-compose.yml   # Full stack deployment
└── nginx/               # Reverse proxy config
```
