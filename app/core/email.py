import logging
import mimetypes
import smtplib
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import parseaddr

from app.core.config import settings

logger = logging.getLogger("app.email")


def _send_console(
    to: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes]] | None = None,
    from_display_name: str | None = None,
    reply_to: str | None = None,
) -> None:
    """Default backend -- no setup required. Check the API container's logs
    (`docker compose logs -f api`) to see verification and password-reset
    links during local development."""
    attachment_note = ""
    if attachments:
        names = ", ".join(name for name, _ in attachments)
        attachment_note = f"\n[{len(attachments)} attachment(s): {names}]"
    from_note = f"\nFrom display name: {from_display_name}" if from_display_name else ""
    reply_note = f"\nReply-To: {reply_to}" if reply_to else ""
    logger.info(
        "=== EMAIL (console -- not actually sent) ===\nTo: %s\nSubject: %s%s%s\n\n%s%s\n=============================================",
        to,
        subject,
        from_note,
        reply_note,
        body,
        attachment_note,
    )


def _send_smtp(
    to: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes]] | None = None,
    from_display_name: str | None = None,
    reply_to: str | None = None,
    from_email: str | None = None,
) -> None:
    """Sends a real email via SMTP. Requires SMTP_HOST/PORT/USERNAME/PASSWORD/
    FROM_EMAIL to be set (see .env.example for a Gmail App Password
    walkthrough). Any failure is logged, not raised -- a broken email
    provider shouldn't crash registration or password reset; the person can
    still use the app, they just won't get the email.

    The sender ADDRESS is settings.SMTP_FROM_EMAIL unless from_email is
    given -- from_email only actually works (rather than being rejected or
    silently rewritten by the mail provider) if you're on a provider that
    does domain-level DKIM signing with SMTP_SENDING_DOMAIN verified there
    (SendGrid/Postmark/SES/Mailgun). Gmail SMTP + an App Password can only
    send as the one authenticated mailbox, so from_email is ignored there --
    see the from_email handling below.
      - from_display_name: the human-readable sender name shown in inboxes,
        e.g. "Asha Rao (Belagavi City Police)".
      - reply_to: hitting "Reply" in the recipient's mail client goes
        straight to this address instead of the platform's, so a real
        back-and-forth actually reaches the right person.
    """
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        logger.error(
            "EMAIL_BACKEND=smtp but SMTP_HOST/SMTP_FROM_EMAIL aren't set -- "
            "falling back to console. Fill in the SMTP_* settings in .env."
        )
        _send_console(to, subject, body, attachments, from_display_name, reply_to)
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    is_gmail_smtp = "gmail.com" in settings.SMTP_HOST.lower()
    if from_email and is_gmail_smtp:
        logger.warning(
            "Ignoring from_email=%s -- Gmail SMTP can only send as the "
            "authenticated mailbox (%s). Use a domain-verified provider "
            "(SendGrid/Postmark/SES/Mailgun) to actually send from "
            "per-authority addresses.",
            from_email,
            settings.SMTP_FROM_EMAIL,
        )
        from_email = None
    _, from_addr = parseaddr(from_email or settings.SMTP_FROM_EMAIL)
    if from_display_name:
        # Address() escapes/quotes the display name safely -- avoids header
        # injection from a user-controlled name (e.g. an authority's
        # full_name/org_name) containing characters like `"` or newlines.
        msg["From"] = str(Address(display_name=from_display_name, addr_spec=from_addr))
    else:
        msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)

    for filename, content in attachments or []:
        content_type, _ = mimetypes.guess_type(filename)
        maintype, subtype = (content_type or "application/octet-stream").split("/", 1)
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("Sent email to %s: %s", to, subject)
    except Exception:
        logger.exception("Failed to send email to %s via SMTP", to)


def sender_address_for(local_part: str) -> str | None:
    """Builds a per-sender address under SMTP_SENDING_DOMAIN, e.g.
    sender_address_for("belagavi-city-police-4f3a") ->
    "belagavi-city-police-4f3a@mail.reunificationnetwork.org". Returns None
    if SMTP_SENDING_DOMAIN isn't configured, so callers fall back to the
    single SMTP_FROM_EMAIL address."""
    if not settings.SMTP_SENDING_DOMAIN:
        return None
    return f"{local_part}@{settings.SMTP_SENDING_DOMAIN}"


def send_email(
    to: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes]] | None = None,
    from_display_name: str | None = None,
    reply_to: str | None = None,
    from_email: str | None = None,
) -> None:
    """Single choke point for all outbound email in this app (verification,
    password reset, case sharing) -- swap EMAIL_BACKEND in .env to change how
    it's sent, nothing else in the codebase needs to change.

    `attachments` is a list of (filename, raw_bytes) tuples -- used by
    case_service.share_case to send the case photo as a "soft copy"
    alongside the case details in the email body.

    `from_display_name` / `reply_to` / `from_email` let case_service.share_case
    make a shared case come from the sharing authority -- name shown in the
    inbox, replies routed to them, and (only with a domain-verified provider,
    via sender_address_for()) the address itself under your own domain. See
    the docstring on _send_smtp for the Gmail-SMTP caveat on from_email.
    """
    if settings.EMAIL_BACKEND == "smtp":
        _send_smtp(to, subject, body, attachments, from_display_name, reply_to, from_email)
    else:
        _send_console(to, subject, body, attachments, from_display_name, reply_to)
