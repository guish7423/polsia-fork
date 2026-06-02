"""FastAPI application factory."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import settings


_redis_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — manages startup/shutdown events."""
    global _redis_task
    # Startup: initialize DB tables in debug mode
    if settings.debug:
        from app.core.database import init_db
        await init_db()
    from app.api.v1.ws import listen_redis
    try:
        _redis_task = asyncio.create_task(listen_redis())
    except Exception:
        _redis_task = None
    yield
    # Shutdown: cancel Redis listener
    if _redis_task:
        _redis_task.cancel()
        try:
            await _redis_task
        except asyncio.CancelledError:
            pass

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan
)

# CORS — allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root redirect to /docs
@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/docs")


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "app": settings.app_name}


# Global exception handler
@app.exception_handler(Exception)
async def global_exception(request: Request, exc: Exception):
    """Catch-all exception handler returning JSON."""
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "path": str(request.url)}
)


# Import and register API routers
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.agents import router as agents_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.finance import router as finance_router
from app.api.v1.config import router as config_router
from app.api.v1.memory import router as memory_router
from app.api.v1.social import router as social_router
from app.api.v1.activity import router as activity_router
from app.api.v1.leads import router as leads_router
from app.api.v1.orders_external import router as orders_external_router
from app.api.v1.sandbox import router as sandbox_router
from app.api.v1.proposals import router as proposals_router, public_proposal_router
from app.api.v1.quick_quote import router as quick_quote_router
from app.api.v1.payments import payment_router as payment_public_router
from app.api.v1.deploy_execution import router as deploy_execution_router
from app.api.v1.reports import router as reports_router
from app.api.v1.ws import router as ws_router

app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(finance_router, prefix="/api/v1")
app.include_router(config_router, prefix="/api/v1")
app.include_router(memory_router, prefix="/api/v1")
app.include_router(social_router, prefix="/api/v1")
app.include_router(activity_router, prefix="/api/v1")
app.include_router(leads_router, prefix="/api/v1")
app.include_router(orders_external_router, prefix="/api/v1")
app.include_router(sandbox_router, prefix="/api/v1")
app.include_router(proposals_router, prefix="/api/v1")
app.include_router(public_proposal_router, prefix="/api/v1")
app.include_router(quick_quote_router, prefix="/api/v1")
app.include_router(deploy_execution_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(payment_public_router, prefix="/api/v1")
app.include_router(ws_router)
