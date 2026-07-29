import os

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.v1 import admin, auth, cases, sightings, uploads
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

# Uploaded photos are served from here (see services/upload_service.py and
# api/v1/uploads.py). Created on startup since a fresh checkout won't have
# this directory yet -- StaticFiles raises if the directory is missing.
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.UPLOAD_DIR), name="media")


@app.get("/health", tags=["system"])
def health_check(response: Response) -> dict:
    """Basic liveness check + DB connectivity check.

    Returns HTTP 503 (not 200) when the database is unreachable — a 200 here
    used to be returned even on failure, which silently masked real
    connectivity problems. If you see 503 with "database": "unreachable",
    check DATABASE_URL in .env — inside Docker it must point at the service
    name "db", not "localhost". See README.md "Understanding the connections".
    """
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    if not db_ok:
        response.status_code = 503

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "environment": settings.ENVIRONMENT,
    }


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(cases.router, prefix="/api/v1/cases", tags=["cases"])
app.include_router(sightings.router, prefix="/api/v1/sightings", tags=["sightings"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(uploads.router, prefix="/api/v1/uploads", tags=["uploads"])
