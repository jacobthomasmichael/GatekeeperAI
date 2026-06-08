import logging

logger = logging.getLogger(__name__)


def notify_approvers(app_name: str, risk_tier: str, approval_id: str, sla_deadline: str) -> None:
    """Stub — wire up email/Slack in Phase 7 hardening."""
    logger.info(
        "NOTIFY approvers: app=%s tier=%s approval=%s deadline=%s",
        app_name, risk_tier, approval_id, sla_deadline,
    )


def notify_submitter_decision(
    submitter_email: str, app_name: str, decision: str, comment: str
) -> None:
    """Stub — wire up email in Phase 7 hardening."""
    logger.info(
        "NOTIFY submitter %s: app=%s decision=%s",
        submitter_email, app_name, decision,
    )
