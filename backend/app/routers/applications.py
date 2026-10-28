"""Paginated application search with live exposure-disparity flags."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from ..db import pool
from ..repository import list_applications
from ..schemas import ApplicationsResponse

router = APIRouter(tags=["applications"])

SortField = Literal[
    "decision_date",
    "application_date",
    "variance",
    "exposure",
    "score",
    "applicant",
    "requested_amount",
]


@router.get("/applications", response_model=ApplicationsResponse, summary="Search applications")
def applications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=120),
    decision: Literal["APPROVED", "DECLINED", "REFERRED"] | None = Query(default=None),
    discrepancy_only: bool = Query(default=False),
    sort: SortField = Query(default="decision_date"),
    direction: Literal["asc", "desc"] = Query(default="desc"),
) -> dict:
    return list_applications(
        pool,
        page=page,
        page_size=page_size,
        search=search,
        decision=decision,
        discrepancy_only=discrepancy_only,
        sort=sort,
        direction=direction,
    )
