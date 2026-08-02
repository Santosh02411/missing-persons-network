from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized app configuration, loaded from environment variables / .env.
    Keeping this in one place means no module reaches into os.environ directly —
    makes testing (override via env) and config auditing straightforward.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str
    TEST_DATABASE_URL: str | None = None

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # App
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Rate limiting
    SIGHTING_REPORT_RATE_LIMIT: str = "5/minute"

    # Frontend URL, used to build links in emails (verification, password reset)
    FRONTEND_URL: str = "http://localhost:5173"

<<<<<<< HEAD
    # Email sending. "console" (default) just logs emails -- no setup needed,
    # safe for anyone cloning this project. Switch to "smtp" and fill in the
    # SMTP_* settings to actually send real emails (see .env.example for a
    # Gmail App Password walkthrough).
    EMAIL_BACKEND: str = "console"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True

=======
>>>>>>> 0a84c8b8037ce65b90f512ff6a732d74ee3d7e30
    # Photo uploads
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024  # 5MB

    # Login lockout
    LOGIN_FAILURE_THRESHOLD: int = 5
    LOGIN_FAILURE_WINDOW_SECONDS: int = 15 * 60
    LOGIN_LOCKOUT_SECONDS: int = 15 * 60


settings = Settings()
