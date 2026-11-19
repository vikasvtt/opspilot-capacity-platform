from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from time import perf_counter
import re
from uuid import uuid4
import logging
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import agent, approvals, audit, auth, inventory, metrics, reports, requests
from app.core.metrics import HTTP_ERRORS, HTTP_LATENCY, HTTP_REQUESTS
from app.core.logging_config import configure_logging, request_id_var
from app.api.auth import limiter
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.entities import User, UserRole
from app.services.demo_seed import seed_demo_data

configure_logging()
logger = logging.getLogger("opspilot.http")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Compose supplies these local-only accounts so the demo is usable after first boot.
    demo_accounts = [
        (settings.bootstrap_approver_email, settings.bootstrap_approver_password, UserRole.APPROVER),
        (settings.bootstrap_engineer_email, settings.bootstrap_engineer_password, UserRole.ENGINEER),
    ]
    with SessionLocal() as db:
        for email, password, role in demo_accounts:
            if email and password and db.query(User).filter(User.email == email.lower()).first() is None:
                db.add(User(email=email.lower(), password_hash=hash_password(password), role=role))
        db.commit()
        if settings.seed_demo and all((
            settings.bootstrap_approver_email,
            settings.bootstrap_approver_password,
            settings.bootstrap_engineer_email,
            settings.bootstrap_engineer_password,
        )):
            seed_demo_data(
                db,
                approver_email=settings.bootstrap_approver_email,
                approver_password=settings.bootstrap_approver_password,
                engineer_email=settings.bootstrap_engineer_email,
                engineer_password=settings.bootstrap_engineer_password,
            )
        elif settings.seed_demo:
            logger.warning("Demo seeding requested but bootstrap engineer/approver credentials are incomplete")
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    root_path="/api",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.include_router(auth.router)
app.include_router(inventory.router)
app.include_router(requests.router)
app.include_router(agent.router)
app.include_router(approvals.router)
app.include_router(metrics.router)
app.include_router(reports.router)
app.include_router(audit.router)


@app.middleware("http")
async def collect_http_metrics(request: Request, call_next):
    started = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        if request.url.path != "/metrics":
            method = request.method
            HTTP_REQUESTS.labels(method, str(status_code)).inc()
            HTTP_LATENCY.labels(method).observe(perf_counter() - started)
            if status_code >= 400:
                HTTP_ERRORS.labels(method, str(status_code)).inc()


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    supplied = request.headers.get("x-request-id", "")
    request_id = supplied if re.fullmatch(r"[A-Za-z0-9._-]{1,80}", supplied) else str(uuid4())
    context_token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info("http request", extra={"method": request.method, "path": request.url.path, "status": response.status_code})
        return response
    finally:
        request_id_var.reset(context_token)
