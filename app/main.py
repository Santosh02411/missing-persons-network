import logging
import os
import traceback

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.v1 import admin, authorities, auth, cases, sightings, uploads
from app.core.config import settings
from app.db.session import engine

logger = logging.getLogger("app.errors")

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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Without this, any unhandled exception becomes a generic, contentless
    "Internal Server Error" in the browser -- forcing a trip to
    `docker compose logs api` for every single 500 to see what actually
    broke. In non-production environments, this instead puts the real
    exception type/message/traceback directly in the response body, visible
    in the browser's Network tab. Production (ENVIRONMENT=production) still
    gets the generic message -- tracebacks can leak internals and shouldn't
    reach real users."""
    tb = traceback.format_exc()
    logger.error("Unhandled exception on %s %s:\n%s", request.method, request.url.path, tb)

    if settings.ENVIRONMENT == "production":
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

    return JSONResponse(
        status_code=500,
        content={
            "detail": f"{type(exc).__name__}: {exc}",
            "traceback": tb.splitlines()[-20:],
        },
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
app.include_router(authorities.router, prefix="/api/v1/authorities", tags=["authorities"])
