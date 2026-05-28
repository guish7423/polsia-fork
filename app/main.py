"""FastAPI application factory — production-grade entrypoint."""

import asyncio
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import settings
from app.core.logging import setup_logging, get_logger

# ─── Initialize structured logging ─────────────────────────────────────────
setup_logging(level=settings.log_level, is_dev=settings.debug)
logger = get_logger(__name__)


_redis_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — manages startup/shutdown events."""
    global _redis_task
    logger.info("app_starting", extra={"debug": settings.debug})

    # Startup: initialize DB tables in debug mode
    if settings.debug:
        from app.core.database import init_db
        await init_db()
        logger.info("db_tables_created")

    # Startup: start Redis pub/sub listener for WebSocket
    from app.api.v1.ws import listen_redis
    _redis_task = asyncio.create_task(listen_redis())
    logger.info("redis_listener_started")

    yield

    # Shutdown
    if _redis_task:
        _redis_task.cancel()
        try:
            await _redis_task
        except asyncio.CancelledError:
            pass
        logger.info("redis_listener_stopped")

    logger.info("app_shutdown")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)


# ─── CORS ──────────────────────────────────────────────────────────────────
if settings.allowed_hosts == "*":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    origins = [h.strip() for h in settings.allowed_hosts.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ─── Rate Limiting (production only) ────────────────────────────────────────
if not settings.debug:
    from app.core.ratelimit import rate_limit_middleware
    app.middleware("http")(rate_limit_middleware)
    logger.info("rate_limiting_enabled", extra={"rate_per_minute": settings.rate_limit_per_minute})


# ─── Middleware: Request ID + Timing ───────────────────────────────────────
@app.middleware("http")
async def request_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.monotonic()
    response = await call_next(request)
    elapsed = int((time.monotonic() - start) * 1000)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": elapsed,
        },
    )
    return response


# ─── Global Exception Handler ──────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception(request: Request, exc: Exception):
    """Catch-all exception handler — safe error messages in production."""
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.error(
        "unhandled_exception",
        extra={
            "request_id": request_id,
            "path": str(request.url),
            "method": request.method,
            "error": str(exc),
        },
        exc_info=True,
    )
    if settings.debug:
        detail = str(exc)
    else:
        detail = "Internal server error"
    return JSONResponse(
        status_code=500,
        content={"detail": detail, "request_id": request_id},
    )


# ─── Health / Root ─────────────────────────────────────────────────────────
@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/docs")


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}


# ─── Routers ──────────────────────────────────────────────────────────────
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.agents import router as agents_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.finance import router as finance_router
from app.api.v1.config import router as config_router
from app.api.v1.social import router as social_router
from app.api.v1.memory import router as memory_router
from app.api.v1.ws import router as ws_router
from app.api.v1.usage import router as usage_router
from app.api.v1.auth import router as auth_router
from app.api.v1.billing import router as billing_router

app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(finance_router, prefix="/api/v1")
app.include_router(config_router, prefix="/api/v1")
app.include_router(social_router, prefix="/api/v1")
app.include_router(memory_router, prefix="/api/v1")
app.include_router(ws_router)
app.include_router(usage_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")
