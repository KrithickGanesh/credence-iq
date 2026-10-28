"""Exasol-native scoring: run the portfolio scoring model inside the database."""

from __future__ import annotations

from fastapi import APIRouter

from ..db import pool
from ..repository import portfolio_udf_check
from ..schemas import UdfScoringResponse

router = APIRouter(tags=["scoring"])


@router.get(
    "/scoring/udf",
    response_model=UdfScoringResponse,
    summary="Score the portfolio with the in-database Python UDF",
)
def udf_scoring() -> dict:
    return portfolio_udf_check(pool)
