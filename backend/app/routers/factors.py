"""Risk factor metadata and model thresholds."""

from __future__ import annotations

from fastapi import APIRouter

from ..db import pool
from ..repository import list_factors
from ..schemas import FactorsResponse

router = APIRouter(tags=["metadata"])


@router.get("/factors", response_model=FactorsResponse, summary="Regulatory risk-factor weights")
def factors() -> dict:
    return list_factors(pool)
