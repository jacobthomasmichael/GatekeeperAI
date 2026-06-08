"""Unit tests for the risk engine — no DB needed."""
import pytest
from app.scanners.base import ScanResult
from app.scanners.risk_engine import compute_risk_tier


def _result(score, force_red=False, severity="low"):
    return ScanResult(
        scanner_name="test",
        status="complete",
        severity=severity,
        findings={},
        raw_output="",
        duration_ms=1,
        risk_score_contribution=score,
        force_red=force_red,
    )


def test_green_tier():
    tier, score = compute_risk_tier([_result(10), _result(5)])
    assert tier == "green"
    assert score == 15


def test_yellow_tier():
    tier, score = compute_risk_tier([_result(20), _result(15)])
    assert tier == "yellow"
    assert score == 35


def test_red_tier_by_score():
    tier, score = compute_risk_tier([_result(35), _result(30)])
    assert tier == "red"
    assert score == 65


def test_red_tier_forced():
    tier, score = compute_risk_tier([_result(5, force_red=True), _result(5)])
    assert tier == "red"
    assert score >= 70


def test_empty_results():
    tier, score = compute_risk_tier([])
    assert tier == "green"
    assert score == 0


def test_boundary_green_yellow():
    tier, _ = compute_risk_tier([_result(29)])
    assert tier == "green"

    tier, _ = compute_risk_tier([_result(30)])
    assert tier == "yellow"


def test_boundary_yellow_red():
    tier, _ = compute_risk_tier([_result(59)])
    assert tier == "yellow"

    tier, _ = compute_risk_tier([_result(60)])
    assert tier == "red"
