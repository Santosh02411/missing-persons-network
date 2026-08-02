from app.core.redis_client import redis_client

CASES_LIST_VERSION_KEY = "cache:cases:list_version"
CASES_LIST_TTL_SECONDS = 30


def get_cases_list_version() -> int:
    version = redis_client.get(CASES_LIST_VERSION_KEY)
    return int(version) if version else 0


def bump_cases_list_version() -> None:
    """Called by case_service on any write (create/update/status
    change/claim). Bumping the version changes every subsequently-built cache
    key, which effectively invalidates all previously-cached list pages
    without needing a Redis SCAN+DEL over wildcard keys — simpler and safe
    under concurrent requests."""
    redis_client.incr(CASES_LIST_VERSION_KEY)


def cases_list_cache_key(status_filter: str | None, limit: int, offset: int) -> str:
    version = get_cases_list_version()
    return f"cache:cases:list:v{version}:{status_filter}:{limit}:{offset}"
