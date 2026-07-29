import redis

from app.core.config import settings

# decode_responses=True so we get str back instead of bytes everywhere
# that touches this client (refresh-token tracking here; rate limiting/
# caching in Phase 4 reuse the same client).
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
