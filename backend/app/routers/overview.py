"""Portfolio-level risk and exposure analytics."""

from __future__ import annotations

from fastapi import APIRouter

from ..db import pool
from ..repository import get_overview
from ..schemas import OverviewResponse

router = APIRouter(tags=["analytics"])


@router.get("/overview", response_model=OverviewResponse, summary="Portfolio risk and exposure overview")
def overview() -> dict:
    return get_overview(pool)
