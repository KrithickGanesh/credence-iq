"""Unit tests for the transparent underwriting model.

These tests intentionally avoid Exasol: the same scoring module drives both the
seed job and the API, so deterministic unit coverage here protects the numbers
the dashboard displays.
"""

from __future__ import annotations

import pytest

from app.scoring import (
    FACTOR_DEFINITIONS,
    MAX_SCORE,
    MIN_SCORE,
    approval_threshold,
    build_score_sql,
    coerce_weights,
    decision_for,
    default_weights,
    grade_for,
    refer_threshold,
    score_metrics,
)

PRIME = {
    "bureau_score": 780,
    "dti_ratio": 0.18,
    "delinquencies_12m": 0,
    "hard_inquiries_6m": 1,
    "utilization_ratio": 0.12,
    "variance_ratio": 0.005,
    "max_dpd": 0,
    "collections_count": 0,
    "bankruptcies": 0,
}

SUBPRIME = {
    "bureau_score": 566,
    "dti_ratio": 0.61,
    "delinquencies_12m": 3,
    "hard_inquiries_6m": 6,
    "utilization_ratio": 0.88,
    "variance_ratio": 0.14,
    "max_dpd": 45,
    "collections_count": 2,
    "bankruptcies": 1,
}


def test_prime_profile_is_approved_and_grade_b() -> None:
    result = score_metrics(PRIME)
    assert result.score == pytest.approx(757.0)
    assert result.decision == "APPROVED"
    assert result.grade == "B"


def test_subprime_profile_is_declined() -> None:
    result = score_metrics(SUBPRIME)
    assert result.score < 610
    assert result.decision == "DECLINED"
    assert result.grade == "E"


def test_score_is_clamped_to_model_bounds() -> None:
    catastrophic = {**SUBPRIME, "bankruptcies": 25, "max_dpd": 720, "collections_count": 30}
    assert score_metrics(catastrophic).score == MIN_SCORE

    aggressive = default_weights()
    aggressive["BUREAU_SCORE"]["weight"] = 2.0
    perfect = {
        **PRIME,
        "bureau_score": 850,
        "dti_ratio": 0.01,
        "utilization_ratio": 0.0,
        "variance_ratio": 0.0,
    }
    assert score_metrics(perfect, aggressive).score == MAX_SCORE


def test_decision_thresholds_are_inclusive() -> None:
    weights = default_weights()
    assert decision_for(680, weights) == "APPROVED"
    assert decision_for(679.9, weights) == "REFERRED"
    assert decision_for(610, weights) == "REFERRED"
    assert decision_for(609.9, weights) == "DECLINED"
    assert approval_threshold(weights) == 680
    assert refer_threshold(weights) == 610


def test_grade_bands_follow_thresholds() -> None:
    assert grade_for(760) == "A"
    assert grade_for(720) == "B"
    assert grade_for(680) == "C"
    assert grade_for(610) == "D"
    assert grade_for(609.9) == "E"


def test_contributions_reconcile_to_the_final_score() -> None:
    result = score_metrics(
        {
            **PRIME,
            "bureau_score": 690,
            "dti_ratio": 0.48,
            "delinquencies_12m": 1,
            "utilization_ratio": 0.66,
            "variance_ratio": 0.06,
            "max_dpd": 10,
            "collections_count": 1,
        }
    )
    weights = default_weights()
    base = float(weights["SCORE_BASE"]["weight"])
    assert base + sum(item.contribution for item in result.contributions) == pytest.approx(
        result.score, abs=0.1
    )


def test_every_scored_factor_is_present_once() -> None:
    result = score_metrics(SUBPRIME)
    codes = [item.factor_code for item in result.contributions]
    scored = [item["factor_code"] for item in FACTOR_DEFINITIONS if item["is_scored"]]
    assert sorted(codes) == sorted(scored)
    assert len(codes) == len(set(codes))


def test_negative_factors_are_sorted_worst_first() -> None:
    result = score_metrics(SUBPRIME)
    negatives = result.negative_factors
    assert negatives
    assert negatives == sorted(negatives, key=lambda item: item.contribution)
    assert all(item.contribution < 0 for item in negatives)
    assert all(item.plain_language for item in result.contributions)


def test_weight_override_changes_the_score() -> None:
    adjusted = default_weights()
    adjusted["BUREAU_SCORE"]["weight"] = 1.0
    profile = {**PRIME, "bureau_score": 760}
    baseline = score_metrics(profile)
    boosted = score_metrics(profile, adjusted)
    # 120 points above benchmark at +0.7 extra weight per point = +84.
    assert boosted.score - baseline.score == pytest.approx(84.0)


def test_coerce_weights_normalises_exasol_rows() -> None:
    rows = [
        {
            "factor_code": "bureau_score",
            "weight": "0.4",
            "benchmark_threshold": "650",
            "display_order": "10",
            "is_scored": "1",
        }
    ]
    weights = coerce_weights(rows)
    assert weights["BUREAU_SCORE"]["weight"] == pytest.approx(0.4)
    assert weights["BUREAU_SCORE"]["benchmark_threshold"] == pytest.approx(650.0)
    assert weights["BUREAU_SCORE"]["display_order"] == 10


def test_sql_expression_embeds_weights_and_columns() -> None:
    sql = build_score_sql(columns={"bureau_score": "b.bureau_score"})
    assert "LEAST(850.0" in sql
    assert "GREATEST(300.0" in sql
    assert "b.bureau_score" in sql
    assert "portfolio_utilization_ratio" in sql
    assert "0.300000" in sql
    assert sql.count("WHEN") == 3
