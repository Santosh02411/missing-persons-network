from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import admin, auth, cases, sightings
from app.core.config import settings
from app.db.session import engine

app = FastAPI(
    title="National Missing Persons & Reunification Network",
    version="0.1.0",
    description=(
        "Backend API for registering missing person cases, submitting sighting "
        "reports, and coordinating verification by authorities/NGOs."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health_check() -> dict:
    """Basic liveness check + DB connectivity check."""
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "environment": settings.ENVIRONMENT,
    }


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(cases.router, prefix="/api/v1/cases", tags=["cases"])
app.include_router(sightings.router, prefix="/api/v1/sightings", tags=["sightings"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])

# NOTE (Phase 3): none of the routes above enforce role-based access yet —
# every route that should be authority/admin-only is marked with a
# `TODO(phase-3)` docstring at its definition. See docs/SECURITY_AND_ACCESS.md
# for the full RBAC matrix this will enforce.
