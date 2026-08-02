from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings
from app.core.deps import get_current_user_optional
from app.core.redis_client import redis_client
from app.models.user import User

_PERIOD_SECONDS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}


def _parse_rate_limit(spec: str) -> tuple[int, int]:
    """Parse a spec like '5/minute' into (count, window_seconds)."""
    count_str, _, period = spec.partition("/")
    seconds = _PERIOD_SECONDS.get(period.strip().lower())
    if seconds is None:
        raise ValueError(f"Unrecognized rate limit period in '{spec}' — expected e.g. '5/minute'")
    return int(count_str), seconds


def sighting_rate_limiter(
    request: Request,
    current_user: User | None = Depends(get_current_user_optional),
) -> None:
    """Fixed-window rate limit on sighting submission (FR-7), backed by
    Redis INCR/EXPIRE. Keyed by user id when logged in, by client IP for
    anonymous tips — anonymous submission is a real requirement here (FR-6),
    so we can't just require auth to make rate limiting easier.

    Fixed-window (not sliding/token-bucket) is a deliberate simplicity choice
    for this portfolio scope: it can allow a short burst right at a window
    boundary, which is an acceptable tradeoff against a much simpler
    implementation. A token-bucket (e.g. via the `limits` library) would be
    the production upgrade if that boundary burst mattered.
    """
    limit, window_seconds = _parse_rate_limit(settings.SIGHTING_REPORT_RATE_LIMIT)

    if current_user is not None:
        identity = f"user:{current_user.id}"
    else:
        identity = f"ip:{request.client.host}" if request.client else "ip:unknown"

    key = f"ratelimit:sightings:{identity}"

    current_count = redis_client.incr(key)
    if current_count == 1:
        # First request in this window — set the window to expire.
        redis_client.expire(key, window_seconds)

    if current_count > limit:
        ttl = redis_client.ttl(key)
        retry_after = ttl if ttl and ttl > 0 else window_seconds
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You've submitted several sighting reports recently — please wait before trying again.",
            headers={"Retry-After": str(retry_after)},
        )
