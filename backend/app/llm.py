"""LLM-backed adverse-action generation with a deterministic legal template fallback."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import date, datetime, timezone
from typing import Any

import httpx
from pydantic import ValidationError

from .config import settings
from .schemas import (
    AdverseActionRequest,
    ComplianceLetter,
    CustomerExplanation,
    FactorDisclosure,
    GeneratedDisclosure,
)

logger = logging.getLogger("credenceiq.llm")

DISCLAIMER = (
    "CredenceIQ generates a draft disclosure from live analytical data. It is not legal "
    "advice. A qualified compliance reviewer must approve the final notice before it is "
    "sent to a consumer."
)

BASE_APPEAL_RIGHTS = [
    "You have the right to obtain a free copy of your consumer report from the consumer "
    "reporting agency named in this notice within 60 days of this decision.",
    "You have the right to dispute inaccurate or incomplete information directly with the "
    "consumer reporting agency.",
    "You have the right to request a written statement of the specific reasons for this "
    "decision, and to ask for a review by a person rather than an automated system.",
    "You have the right to provide additional information that may affect the decision.",
    "CredenceIQ does not discriminate on the basis of race, color, religion, national origin, "
    "sex, marital status, age, or receipt of public assistance.",
]


def _fmt_money(value: float) -> str:
    return f"${value:,.0f}"


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _top_factors(detail: dict[str, Any], limit: int = 4) -> list[dict[str, Any]]:
    factors = detail.get("eligibility", {}).get("factors", [])
    negatives = sorted(
        [factor for factor in factors if factor.get("is_negative")],
        key=lambda factor: factor.get("contribution", 0.0),
    )
    if len(negatives) < 3:
        remainder = [
            factor
            for factor in sorted(factors, key=lambda item: item.get("contribution", 0.0))
            if factor not in negatives
        ]
        negatives.extend(remainder[: 3 - len(negatives)])
    return negatives[:limit]


def _disclosures(detail: dict[str, Any]) -> list[FactorDisclosure]:
    return [
        FactorDisclosure(
            factor_code=str(factor["factor_code"]),
            factor_name=str(factor["factor_name"]),
            finding=str(factor.get("plain_language") or factor.get("reason") or ""),
            regulation=str(factor.get("regulation_ref") or "Reg B 12 CFR 1002.9"),
            impact=f"Reduced the eligibility score by {abs(float(factor.get('contribution', 0))):.1f} points.",
        )
        for factor in _top_factors(detail)
    ]


def _recipient(detail: dict[str, Any]) -> str:
    applicant = detail["applicant"]
    return f"{applicant['first_name']} {applicant['last_name']}, {applicant['city']}, {applicant['state']}"


def _letter_body(detail: dict[str, Any], disclosures: list[FactorDisclosure]) -> str:
    application = detail["application"]
    applicant = detail["applicant"]
    decision = application["decision"]
    reasons = "\n".join(
        f"{index}. {item.finding}" for index, item in enumerate(disclosures, start=1)
    )
    if decision == "REFERRED":
        outcome = (
            "We are unable to approve your application on the terms requested at this time. "
            "Your application has been referred for additional manual review."
        )
    else:
        outcome = (
            "We are unable to approve your application on the terms requested. This decision "
            "was based on the principal reasons listed below."
        )
    bureau = detail.get("bureau_records") or []
    bureau_line = (
        f"The consumer reporting agency that supplied information used in this decision: "
        f"{bureau[0]['bureau_name']}. Your reported score was {bureau[0]['bureau_score']}."
        if bureau
        else "We used information from a consumer reporting agency in making this decision."
    )
    return (
        f"Dear {applicant['first_name']} {applicant['last_name']},\n\n"
        f"Thank you for your application for a {application['product_type'].replace('_', ' ').lower()} "
        f"in the amount of {_fmt_money(application['requested_amount'])} "
        f"(application {application['application_id']}).\n\n"
        f"{outcome}\n\n"
        f"Principal reasons:\n{reasons}\n\n"
        f"{bureau_line}\n\n"
        "You have the right to obtain a free copy of your consumer report from the consumer "
        "reporting agency within 60 days and to dispute any inaccurate or incomplete information "
        "it contains. You also have the right to request a statement of the specific reasons for "
        "this decision and to have the decision reviewed by a person.\n\n"
        "If you believe there is an error in the information we used, please contact us using the "
        "details below. We will investigate and, where appropriate, reconsider your application.\n\n"
        f"Sincerely,\n{settings.lender_name}\n{settings.lender_address}\n{settings.lender_phone}"
    )


def _customer_explanation(detail: dict[str, Any], disclosures: list[FactorDisclosure]) -> CustomerExplanation:
    application = detail["application"]
    eligibility = detail["eligibility"]
    decision = application["decision"]
    if decision == "REFERRED":
        headline = "Your application needs a closer look"
        summary = (
            f"We could not approve your {application['product_type'].replace('_', ' ').lower()} "
            "application on the terms you requested, so a person will review it. The main "
            "reasons are below, along with practical next steps."
        )
    else:
        headline = "Why we could not approve your application"
        summary = (
            f"We reviewed your application for {_fmt_money(application['requested_amount'])} "
            f"and could not approve it at this time. The main reasons are below. You can ask "
            "for a review or take steps to strengthen a future application."
        )
    what_this_means = [item.finding for item in disclosures]
    next_steps = []
    codes = {item.factor_code for item in disclosures}
    if "UTILIZATION" in codes or "DTI_RATIO" in codes:
        next_steps.append(
            "Reduce revolving balances and avoid taking on new monthly obligations. Even a "
            "modest paydown can lower your utilization and debt-to-income ratio."
        )
    if "EXPOSURE_MISMATCH" in codes:
        next_steps.append(
            "Ask us to reconcile the balance difference between our core, card, and microloan "
            "systems. A corrected balance may change the decision."
        )
    if "DELINQUENCY_12M" in codes or "DAYS_PAST_DUE" in codes:
        next_steps.append(
            "Bring any past-due accounts current and request updated reporting from the lender."
        )
    if "HARD_INQUIRY_6M" in codes:
        next_steps.append("Limit new credit applications for the next few months.")
    if "BUREAU_SCORE" in codes:
        next_steps.append(
            "Request your free credit reports, correct any errors, and allow time for the "
            "updated information to be reported."
        )
    next_steps.append(
        f"You can request a manual review or submit additional documentation. "
        f"Your current score is {eligibility['score']:.0f}; the approval guideline is "
        f"{eligibility['approve_threshold']:.0f}."
    )
    return CustomerExplanation(
        headline=headline,
        summary=summary,
        what_this_means=what_this_means[:5],
        next_steps=next_steps[:5],
    )


def build_template(detail: dict[str, Any], request: AdverseActionRequest) -> GeneratedDisclosure:
    disclosures = _disclosures(detail)
    application = detail["application"]
    letter = ComplianceLetter(
        title="Adverse Action Notice",
        recipient=_recipient(detail),
        body=_letter_body(detail, disclosures),
        factor_disclosures=disclosures,
        appeal_rights=BASE_APPEAL_RIGHTS
        + (
            [
                "This notice is provided under the Fair Credit Reporting Act (FCRA) and the "
                "Equal Credit Opportunity Act (ECOA). State-specific disclosures may apply."
            ]
            if request.include_state_disclosure
            else []
        ),
        contact=(
            f"{settings.lender_name} | {settings.lender_phone} | {settings.lender_email} | "
            f"{settings.lender_address}"
        ),
        issued_date=date.today(),
    )
    return GeneratedDisclosure(
        compliance_letter=letter,
        customer_explanation=_customer_explanation(detail, disclosures),
    )


def _prompt(detail: dict[str, Any], request: AdverseActionRequest, reference: GeneratedDisclosure) -> str:
    applicant = detail["applicant"]
    application = detail["application"]
    eligibility = detail["eligibility"]
    reconciliation = detail["reconciliation"]
    factors = [
        {
            "factor_code": factor["factor_code"],
            "factor_name": factor["factor_name"],
            "observed": factor["observed"],
            "benchmark": factor["benchmark"],
            "contribution": factor["contribution"],
            "regulation": factor["regulation_ref"],
            "finding": factor["plain_language"],
        }
        for factor in _top_factors(detail, limit=5)
    ]
    payload = {
        "lender": {
            "name": settings.lender_name,
            "address": settings.lender_address,
            "phone": settings.lender_phone,
            "email": settings.lender_email,
        },
        "applicant": {
            "name": f"{applicant['first_name']} {applicant['last_name']}",
            "city": applicant["city"],
            "state": applicant["state"],
            "annual_income": applicant["annual_income"],
        },
        "application": {
            "application_id": application["application_id"],
            "product_type": application["product_type"],
            "requested_amount": application["requested_amount"],
            "decision": application["decision"],
            "decision_date": application["decision_date"],
            "score": eligibility["score"],
            "approval_threshold": eligibility["approve_threshold"],
            "score_gap": eligibility["score_gap_to_approval"],
        },
        "reconciliation": {
            "status": reconciliation["status"],
            "reported_total": reconciliation["reported_total"],
            "reconciled_total": reconciliation["reconciled_total"],
            "variance": reconciliation["variance"],
            "variance_ratio": reconciliation["variance_ratio"],
            "conflicted_facilities": reconciliation["conflicted_facilities"],
        },
        "factors": factors,
        "tone": request.tone,
        "include_state_disclosure": request.include_state_disclosure,
        "reference_draft": reference.model_dump(mode="json"),
    }
    return (
        "You are a senior consumer-compliance analyst at a regulated lender. Draft an "
        "adverse-action notice and a plain-English customer explanation using ONLY the facts "
        "in the input. Comply with FCRA 15 U.S.C. Sec. 1681m and ECOA / Regulation B 12 CFR "
        "1002.9. Do not invent agencies, account numbers, dates, reasons, or promises of "
        "approval. Do not mention protected characteristics. Keep the letter concise, "
        "specific, and professional. The reference draft is a factual baseline; improve the "
        "wording but do not add facts or remove the disclosed factors.\n\n"
        "Return a single JSON object with exactly this shape:\n"
        "{\n"
        '  "compliance_letter": {\n'
        '    "title": "Adverse Action Notice",\n'
        '    "recipient": "Name, City, State",\n'
        '    "body": "full letter text with newlines",\n'
        '    "factor_disclosures": [{"factor_code": "...", "factor_name": "...", '
        '"finding": "...", "regulation": "...", "impact": "..."}],\n'
        '    "appeal_rights": ["..."],\n'
        '    "contact": "...",\n'
        '    "issued_date": "YYYY-MM-DD"\n'
        "  },\n"
        '  "customer_explanation": {\n'
        '    "headline": "...",\n'
        '    "summary": "...",\n'
        '    "what_this_means": ["..."],\n'
        '    "next_steps": ["..."]\n'
        "  }\n"
        "}\n\n"
        f"INPUT JSON:\n{json.dumps(payload, default=str, indent=2)}"
    )


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        value = json.loads(cleaned[start : end + 1])
        if isinstance(value, dict):
            return value
    raise ValueError("LLM did not return a JSON object")


async def _call_openai(prompt: str, model: str, base_url: str, api_key: str) -> str:
    system = (
        "You are a compliance writing assistant. Return strict JSON only. Never add facts "
        "that are not present in the input."
    )
    body: dict[str, Any] = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    base = base_url.rstrip("/")
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(url, json=body, headers=headers)
        if response.status_code == 400 and "response_format" in body:
            body.pop("response_format")
            response = await client.post(url, json=body, headers=headers)
        response.raise_for_status()
        data = response.json()
    return str(data["choices"][0]["message"]["content"])


async def _call_anthropic(prompt: str, model: str) -> str:
    base = settings.anthropic_base_url.rstrip("/")
    url = f"{base}/messages" if base.endswith("/v1") else f"{base}/v1/messages"
    body = {
        "model": model,
        "max_tokens": 2200,
        "temperature": 0.2,
        "system": (
            "You are a compliance writing assistant. Return strict JSON only. Never add facts "
            "that are not present in the input."
        ),
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": settings.anthropic_version,
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        response = await client.post(url, json=body, headers=headers)
        response.raise_for_status()
        data = response.json()
    blocks = data.get("content") or []
    return "".join(str(block.get("text", "")) for block in blocks if block.get("type") == "text")


async def generate_disclosure(
    detail: dict[str, Any], request: AdverseActionRequest
) -> tuple[GeneratedDisclosure, str, str, str, float]:
    """Return disclosure, provider, model, mode, latency_ms."""

    reference = build_template(detail, request)
    provider = settings.llm_provider.strip().lower()
    if not settings.llm_enabled:
        return reference, "template", "deterministic-template", "template", 0.0

    started = time.perf_counter()
    prompt = _prompt(detail, request, reference)
    model = settings.resolved_llm_model
    try:
        if provider == "openai":
            text = await _call_openai(prompt, model, settings.openai_base_url, settings.openai_api_key)
        elif provider == "local":
            text = await _call_openai(
                prompt, model, settings.local_llm_base_url, settings.local_llm_api_key
            )
        elif provider == "anthropic":
            text = await _call_anthropic(prompt, model)
        else:
            return reference, "template", "deterministic-template", "template", 0.0

        parsed = _extract_json(text)
        disclosure = GeneratedDisclosure.model_validate(parsed)
        allowed_codes = {factor["factor_code"] for factor in _top_factors(detail, limit=5)}
        disclosed_codes = {item.factor_code for item in disclosure.compliance_letter.factor_disclosures}
        if not disclosed_codes.issubset(allowed_codes):
            raise ValueError("LLM introduced an undisclosed risk factor")
        latency = round((time.perf_counter() - started) * 1000, 2)
        return disclosure, provider, model, "llm", latency
    except (httpx.HTTPError, ValidationError, KeyError, ValueError, json.JSONDecodeError) as exc:
        latency = round((time.perf_counter() - started) * 1000, 2)
        logger.warning("LLM generation failed (%s); using deterministic template", exc)
        return reference, "template", "deterministic-template", "template", latency


def response_meta() -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc),
        "disclaimer": DISCLAIMER,
        "provider": settings.llm_provider,
        "model": settings.resolved_llm_model,
        "llm_enabled": settings.llm_enabled,
    }
