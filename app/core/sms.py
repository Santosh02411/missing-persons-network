import logging

from app.core.config import settings

logger = logging.getLogger("app.sms")


def _send_console(to: str, body: str) -> None:
    """Default backend -- no setup required. Check the API container's logs
    to see 2FA codes during local development, the same way EMAIL_BACKEND=
    console works for email."""
    logger.info(
        "=== SMS (console -- not actually sent) ===\nTo: %s\n\n%s\n=========================================",
        to,
        body,
    )


def _send_twilio(to: str, body: str) -> None:
    """Sends a real text message via Twilio. Requires TWILIO_ACCOUNT_SID/
    AUTH_TOKEN/FROM_NUMBER to be set (see .env.example) -- a free Twilio
    trial account can send to a small number of verified numbers, enough to
    test this end to end without a paid plan. Any failure is logged, not
    raised -- a broken SMS provider shouldn't crash login or 2FA setup; the
    person just won't get the code and can retry."""
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_FROM_NUMBER:
        logger.error(
            "SMS_BACKEND=twilio but TWILIO_ACCOUNT_SID/TWILIO_FROM_NUMBER "
            "aren't set -- falling back to console. Fill in the TWILIO_* "
            "settings in .env."
        )
        _send_console(to, body)
        return

    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(to=to, from_=settings.TWILIO_FROM_NUMBER, body=body)
        logger.info("Sent SMS to %s", to)
    except Exception:
        logger.exception("Failed to send SMS to %s via Twilio", to)


def send_sms(to: str, body: str) -> None:
    """Single choke point for all outbound SMS in this app (currently just
    2FA codes) -- swap SMS_BACKEND in .env to change how it's sent, nothing
    else in the codebase needs to change. Mirrors core/email.py's
    send_email() the same way for the same reasons."""
    if settings.SMS_BACKEND == "twilio":
        _send_twilio(to, body)
    else:
        _send_console(to, body)
