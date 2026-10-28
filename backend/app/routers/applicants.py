"""Applicant 360, reconciliation, adverse-action, and simulation endpoints."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from ..config import settings
from ..db import pool
from ..llm import DISCLAIMER, generate_disclosure
from ..repository import (
    get_applicant_detail,
    new_report_id,
    persist_report,
    simulate,
)
from ..schemas import (
    AdverseActionRequest,
    AdverseActionResponse,
    ApplicantDetailResponse,
    SimulationRequest,
    SimulationResponse,
)

logger = logging.getLogger("credenceiq.applicants")
router = APIRouter(tags=["applicant"])


@router.get(
    "/applicant/{customer_id}/reconciliation",
    response_model=ApplicantDetailResponse,
    summary="Cross-system reconciliation and explainability for one applicant",
)
def applicant_reconciliation(customer_id: int) -> dict:
    detail, _ = get_applicant_detail(pool, customer_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Applicant {customer_id} was not found")
    return detail


@router.post(
    "/applicant/{customer_id}/simulate",
    response_model=SimulationResponse,
    summary="Re-score an applicant against Exasol under what-if scenarios",
)
def applicant_simulation(customer_id: int, body: SimulationRequest) -> dict:
    result = simulate(pool, customer_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Applicant {customer_id} was not found")
    return result


@router.post(
    "/applicant/{customer_id}/adverse-action",
    response_model=AdverseActionResponse,
    summary="Generate a compliance-ready adverse-action notice",
)
async def adverse_action(customer_id: int, body: AdverseActionRequest) -> dict:
    detail, query_ms = await run_in_threadpool(get_applicant_detail, pool, customer_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Applicant {customer_id} was not found")
    application = detail["application"]
    if application["decision"] == "APPROVED":
        raise HTTPException(
            status_code=409,
            detail=(
                "Credit-decision notices are only available for declined or referred "
                "applications. This applicant is currently approved."
            ),
        )

    disclosure, provider, model, mode, llm_ms = await generate_disclosure(detail, body)
    report_id = new_report_id()
    generated_at = datetime.now(timezone.utc)
    payload = {
        "compliance_letter": disclosure.compliance_letter.model_dump(mode="json"),
        "customer_explanation": disclosure.customer_explanation.model_dump(mode="json"),
        "applicant": detail["applicant"],
        "application": detail["application"],
        "eligibility": {
            "score": detail["eligibility"]["score"],
            "decision": detail["eligibility"]["decision"],
            "approve_threshold": detail["eligibility"]["approve_threshold"],
        },
    }
    persisted = await run_in_threadpool(
        persist_report,
        pool,
        report_id=report_id,
        customer_id=customer_id,
        application_id=application["application_id"],
        generated_at=generated_at,
        provider=provider,
        model=model,
        generation_mode=mode,
        payload=payload,
    )

    return {
        "report_id": report_id,
        "generated_at": generated_at,
        "provider": provider,
        "model": model,
        "generation_mode": mode,
        "persisted": persisted,
        "applicant_name": f"{detail['applicant']['first_name']} {detail['applicant']['last_name']}",
        "decision": application["decision"],
        "score": detail["eligibility"]["score"],
        "compliance_letter": disclosure.compliance_letter,
        "customer_explanation": disclosure.customer_explanation,
        "disclaimer": DISCLAIMER,
        "query_ms": round(query_ms + llm_ms, 2),
        "llm_ms": llm_ms,
    }
