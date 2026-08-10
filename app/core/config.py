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

    # Optional: lets case_service.share_case send each shared case from a
    # per-authority address under YOUR OWN verified domain, e.g.
    # "belagavi-city-police-4f3a@mail.reunificationnetwork.org" instead of
    # every share coming from the single SMTP_FROM_EMAIL address. This ONLY
    # works with an email provider that does domain-level DKIM signing
    # (SendGrid, Postmark, AWS SES, Mailgun, etc. with the domain verified)
    # -- NOT with Gmail SMTP + an App Password, which only lets you send as
    # the one authenticated mailbox (or an explicitly-verified "Send As"
    # alias in that account) and will reject or rewrite anything else.
    # Leave blank to keep using SMTP_FROM_EMAIL for everything (the default,
    # and the only option that works with plain Gmail SMTP).
    SMTP_SENDING_DOMAIN: str = ""

    # SMS sending, for SMS-based two-factor auth (app/core/sms.py). "console"
    # (default) just logs the code -- no setup needed, safe for anyone
    # cloning this project. Switch to "twilio" and fill in the TWILIO_*
    # settings to send real text messages. There's no free/no-signup SMS
    # option analogous to Gmail for email -- every real SMS provider requires
    # an account and a purchased/verified sending number, so "console" is
    # the only zero-setup option here (not a lesser default, just the honest
    # one for a project meant to run locally out of the box).
    SMS_BACKEND: str = "console"
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    # Photo uploads
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024  # 5MB

    # Login lockout
    LOGIN_FAILURE_THRESHOLD: int = 5
    LOGIN_FAILURE_WINDOW_SECONDS: int = 15 * 60
    LOGIN_LOCKOUT_SECONDS: int = 15 * 60


settings = Settings()
