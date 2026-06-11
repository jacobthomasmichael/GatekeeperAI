import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


def _send(to: list[str], subject: str, body_text: str, body_html: str) -> None:
    """Send an email. Silently no-ops if SMTP_HOST is not configured."""
    if not settings.SMTP_HOST or not to:
        logger.info("Email suppressed (SMTP not configured): %s → %s", subject, to)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = ", ".join(to)
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        if settings.SMTP_USE_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, to, msg.as_string())
        server.quit()
        logger.info("Email sent: %s → %s", subject, to)
    except Exception as exc:
        logger.error("Failed to send email '%s': %s", subject, exc)


def notify_approvers(
    app_name: str,
    risk_tier: str,
    approval_id: str,
    sla_deadline: str,
    approver_emails: list[str],
) -> None:
    tier_upper = risk_tier.upper()
    subject = f"[GatekeeperAI] {tier_upper} app needs review: {app_name}"

    dashboard_url = f"{settings.APP_BASE_URL}/approvals/{approval_id}"

    text = (
        f"A {tier_upper} risk app requires your review.\n\n"
        f"App: {app_name}\n"
        f"Risk tier: {tier_upper}\n"
        f"SLA deadline: {sla_deadline}\n\n"
        f"Review: {dashboard_url}\n"
    )

    html = f"""
    <p>A <strong>{tier_upper}</strong> risk app requires your review.</p>
    <table>
      <tr><td><b>App</b></td><td>{app_name}</td></tr>
      <tr><td><b>Risk tier</b></td><td>{tier_upper}</td></tr>
      <tr><td><b>SLA deadline</b></td><td>{sla_deadline}</td></tr>
    </table>
    <p><a href="{dashboard_url}">Open in GatekeeperAI →</a></p>
    """

    _send(approver_emails, subject, text, html)


def notify_submitter_decision(
    submitter_email: str,
    app_name: str,
    decision: str,
    comment: str,
) -> None:
    if not submitter_email:
        logger.warning("notify_submitter_decision: no submitter email for app %s", app_name)
        return

    action = "approved" if decision == "approved" else "rejected"
    subject = f"[GatekeeperAI] Your app '{app_name}' was {action}"

    dashboard_url = f"{settings.APP_BASE_URL}/dashboard"

    text = (
        f"Your app '{app_name}' has been {action}.\n\n"
        f"Reviewer notes:\n{comment}\n\n"
        f"View your apps: {dashboard_url}\n"
    )

    html = f"""
    <p>Your app <strong>{app_name}</strong> has been <strong>{action}</strong>.</p>
    <p><b>Reviewer notes:</b></p>
    <blockquote style="border-left:3px solid #ccc;padding-left:12px;color:#555">
      {comment.replace(chr(10), '<br>')}
    </blockquote>
    <p><a href="{dashboard_url}">View your apps →</a></p>
    """

    _send([submitter_email], subject, text, html)
