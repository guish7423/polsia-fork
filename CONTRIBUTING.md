# Contributing to CrossWave

## Development Setup

1. **Clone the repo**
   ```bash
   git clone https://github.com/guish7423/polsia-fork.git
   cd polsia-fork
   ```

2. **Backend**
   ```bash
   uv sync
   cp .env.example .env
   LLM_API_MOCK=true python3 -m pytest tests/unit/ -q  # verify setup
   ```

3. **Frontend**
   ```bash
   cd frontend
   npm install
   npm test -- --watchAll=false
   ```

4. **Full stack with Docker**
   ```bash
   docker compose up -d
   docker compose exec backend alembic upgrade head
   ```

## Branch Strategy

- `main` — stable, always passing CI
- Feature branches: `feat/<short-description>` (e.g., `feat/slack-integration`)
- Bug fixes: `fix/<short-description>` (e.g., `fix/agent-crash-on-empty-state`)
- Use conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`, `perf:`

## Before Making Changes

1. **Check existing issues** — someone might already be working on it
2. **Open an issue first** for non-trivial changes to discuss design
3. **Check the architecture doc** at `docs/architecture.md` to understand where your change fits

## Coding Standards

### Python
- **Style**: ruff (configured in pyproject.toml)
- **Type hints**: Required for all public functions
- **Testing**: Unit tests mandatory — run `LLM_API_MOCK=true python3 -m pytest tests/unit/ -q`
- **SQL**: All models must use `JSON` not `JSONB`/`ARRAY` (SQLite compatibility for tests)
- **Imports**: Lazy-import heavy deps inside functions (`chromadb`, `asyncpg`, etc.)
- **Database**: Use `await db.flush()` not `await db.commit()` in API handlers

### TypeScript / React
- **Style**: Standard TypeScript with strict mode
- **Components**: Use Tailwind CSS, lucide-react icons
- **Testing**: Jest + React Testing Library required for new components
- **i18n**: All user-facing strings via `useI18n()` hook

## Testing Requirements

All changes must maintain or improve test coverage (minimum 75%):

```bash
# Backend
LLM_API_MOCK=true python3 -m pytest tests/unit/ -v --cov=app

# Frontend
cd frontend && npm test -- --watchAll=false

# Build (verify no TypeScript errors)
cd frontend && npm run build
```

## Pull Request Process

1. Ensure all tests pass and lint is clean
2. Update README.md or docs if your change affects the public API
3. Use the PR template — fill in all sections
4. Request review from `@guish7423`
5. Squash-merge once approved

## Code of Conduct

Be respectful, constructive, and inclusive. This is a small project — every contribution matters.
