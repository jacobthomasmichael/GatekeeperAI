from app.scanners.base import ScanResult

_GREEN_MAX = 29
_YELLOW_MAX = 59


def compute_risk_tier(results: list[ScanResult]) -> tuple[str, int]:
    """Aggregate scanner results into a risk tier and total score.

    Returns (tier, score) where tier is 'green' | 'yellow' | 'red'.
    """
    total_score = sum(r.risk_score_contribution for r in results)
    force_red = any(r.force_red for r in results)

    if force_red:
        return ("red", max(total_score, 70))

    if total_score <= _GREEN_MAX:
        return ("green", total_score)
    if total_score <= _YELLOW_MAX:
        return ("yellow", total_score)
    return ("red", total_score)
