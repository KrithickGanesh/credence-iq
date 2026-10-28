#!/usr/bin/env python3
"""CredenceIQ synthetic data engine for Exasol Personal.

The generator deliberately introduces cross-ledger exposure conflicts and
borderline underwriting profiles so the reconciliation and adverse-action
workflows have realistic signal to operate on.

Usage
-----
    python seed_data.py --reset --customers 30000
    python seed_data.py --if-empty
    python seed_data.py --dry-run --customers 5000

The script is idempotent when called with ``--if-empty``.  It never silently
overwrites an existing data set: pass ``--reset`` to rebuild from scratch.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import ssl
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Iterator

import numpy as np
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

# The scoring module is shared with the API.  Locally the package lives under
# backend/, while the Docker image places it at /app/app.
try:  # pragma: no cover - import path depends on how the script is launched
    from app.scoring import (
        FACTOR_DEFINITIONS,
        approval_threshold,
        build_score_sql,
        build_score_udf,
        decision_for,
        default_weights,
        grade_for,
        score_metrics,
    )
except ModuleNotFoundError:  # pragma: no cover
    sys.path.insert(0, str(ROOT / "backend"))
    from app.scoring import (
        FACTOR_DEFINITIONS,
        approval_threshold,
        build_score_sql,
        build_score_udf,
        decision_for,
        default_weights,
        grade_for,
        score_metrics,
    )

from faker import Faker

SCHEMA_DEFAULT = os.getenv("EXASOL_SCHEMA", "CREDENCEIQ")
SYSTEMS = ("CORE_BANKING", "CARD_ENGINE", "MICROCREDIT")

# City/state pairs keep the synthetic Indian addresses internally consistent.
# Faker's en_IN locale picks a city and a state independently, which produces
# implausible combinations (for example "Gudivada, Madhya Pradesh").
CITY_STATE_PAIRS: list[tuple[str, str]] = [
    ("Mumbai", "Maharashtra"),
    ("Pune", "Maharashtra"),
    ("Nagpur", "Maharashtra"),
    ("Nashik", "Maharashtra"),
    ("Vasai-Virar", "Maharashtra"),
    ("Thane", "Maharashtra"),
    ("New Delhi", "Delhi"),
    ("Delhi", "Delhi"),
    ("Gurugram", "Haryana"),
    ("Faridabad", "Haryana"),
    ("Panchkula", "Haryana"),
    ("Noida", "Uttar Pradesh"),
    ("Lucknow", "Uttar Pradesh"),
    ("Kanpur", "Uttar Pradesh"),
    ("Varanasi", "Uttar Pradesh"),
    ("Agra", "Uttar Pradesh"),
    ("Moradabad", "Uttar Pradesh"),
    ("Bulandshahr", "Uttar Pradesh"),
    ("Jaipur", "Rajasthan"),
    ("Jodhpur", "Rajasthan"),
    ("Udaipur", "Rajasthan"),
    ("Kota", "Rajasthan"),
    ("Ahmedabad", "Gujarat"),
    ("Surat", "Gujarat"),
    ("Vadodara", "Gujarat"),
    ("Rajkot", "Gujarat"),
    ("Bhavnagar", "Gujarat"),
    ("Bengaluru", "Karnataka"),
    ("Mysuru", "Karnataka"),
    ("Hubballi", "Karnataka"),
    ("Davanagere", "Karnataka"),
    ("Raichur", "Karnataka"),
    ("Bidar", "Karnataka"),
    ("Hyderabad", "Telangana"),
    ("Warangal", "Telangana"),
    ("Nizamabad", "Telangana"),
    ("Vijayawada", "Andhra Pradesh"),
    ("Visakhapatnam", "Andhra Pradesh"),
    ("Guntur", "Andhra Pradesh"),
    ("Gudivada", "Andhra Pradesh"),
    ("Tirupati", "Andhra Pradesh"),
    ("Nellore", "Andhra Pradesh"),
    ("Kakinada", "Andhra Pradesh"),
    ("Ongole", "Andhra Pradesh"),
    ("Narasaraopet", "Andhra Pradesh"),
    ("Chennai", "Tamil Nadu"),
    ("Coimbatore", "Tamil Nadu"),
    ("Madurai", "Tamil Nadu"),
    ("Tiruppur", "Tamil Nadu"),
    ("Nagercoil", "Tamil Nadu"),
    ("Kolkata", "West Bengal"),
    ("Howrah", "West Bengal"),
    ("Durgapur", "West Bengal"),
    ("Asansol", "West Bengal"),
    ("Siliguri", "West Bengal"),
    ("Naihati", "West Bengal"),
    ("Haldia", "West Bengal"),
    ("Bally", "West Bengal"),
    ("Patna", "Bihar"),
    ("Gaya", "Bihar"),
    ("Bhagalpur", "Bihar"),
    ("Muzaffarpur", "Bihar"),
    ("Darbhanga", "Bihar"),
    ("Arrah", "Bihar"),
    ("Katihar", "Bihar"),
    ("Saharsa", "Bihar"),
    ("Siwan", "Bihar"),
    ("Ranchi", "Jharkhand"),
    ("Jamshedpur", "Jharkhand"),
    ("Dhanbad", "Jharkhand"),
    ("Rourkela", "Odisha"),
    ("Bhubaneswar", "Odisha"),
    ("Cuttack", "Odisha"),
    ("Raipur", "Chhattisgarh"),
    ("Bhopal", "Madhya Pradesh"),
    ("Indore", "Madhya Pradesh"),
    ("Jabalpur", "Madhya Pradesh"),
    ("Rewa", "Madhya Pradesh"),
    ("Gwalior", "Madhya Pradesh"),
    ("Chandigarh", "Chandigarh"),
    ("Ludhiana", "Punjab"),
    ("Amritsar", "Punjab"),
    ("Patiala", "Punjab"),
    ("Jalandhar", "Punjab"),
    ("Dehradun", "Uttarakhand"),
    ("Shimla", "Himachal Pradesh"),
    ("Jammu", "Jammu and Kashmir"),
    ("Srinagar", "Jammu and Kashmir"),
    ("Guwahati", "Assam"),
    ("Dibrugarh", "Assam"),
    ("Bongaigaon", "Assam"),
    ("Aizawl", "Mizoram"),
    ("Agartala", "Tripura"),
    ("Imphal", "Manipur"),
    ("Shillong", "Meghalaya"),
    ("Kochi", "Kerala"),
    ("Thiruvananthapuram", "Kerala"),
    ("Kozhikode", "Kerala"),
    ("Thrissur", "Kerala"),
    ("Panaji", "Goa"),
    ("Puducherry", "Puducherry"),
    ("Aurangabad", "Maharashtra"),
    ("Kolhapur", "Maharashtra"),
    ("Solapur", "Maharashtra"),
    ("Nanded", "Maharashtra"),
    ("Akola", "Maharashtra"),
    ("Bhusawal", "Maharashtra"),
    ("Kalyan-Dombivli", "Maharashtra"),
    ("Avadi", "Tamil Nadu"),
    ("Hosur", "Tamil Nadu"),
    ("Dhule", "Maharashtra"),
    ("Phusro", "Jharkhand"),
    ("Mango", "Jharkhand"),
    ("Farrukhabad", "Uttar Pradesh"),
    ("Shahjahanpur", "Uttar Pradesh"),
    ("Bareilly", "Uttar Pradesh"),
]
SYSTEM_LABELS = {
    "CORE_BANKING": "Core Banking",
    "CARD_ENGINE": "Card Engine",
    "MICROCREDIT": "Micro-credit",
}

DDL_STATEMENTS = [
    """
    CREATE TABLE {schema}.CUSTOMERS (
        CUSTOMER_ID         DECIMAL(12,0) NOT NULL,
        FIRST_NAME          VARCHAR(60)   NOT NULL,
        LAST_NAME           VARCHAR(60)   NOT NULL,
        EMAIL               VARCHAR(160)  NOT NULL,
        PHONE               VARCHAR(40)   NOT NULL,
        DATE_OF_BIRTH       DATE          NOT NULL,
        CITY                VARCHAR(80)   NOT NULL,
        STATE_CODE          VARCHAR(40)   NOT NULL,
        POSTAL_CODE         VARCHAR(12)   NOT NULL,
        EMPLOYMENT_STATUS   VARCHAR(30)   NOT NULL,
        ANNUAL_INCOME       DECIMAL(14,2) NOT NULL,
        KYC_STATUS          VARCHAR(20)   NOT NULL,
        SEGMENT             VARCHAR(20)   NOT NULL,
        CUSTOMER_SINCE      DATE          NOT NULL,
        CONSTRAINT PK_CUSTOMERS PRIMARY KEY (CUSTOMER_ID),
        DISTRIBUTE BY CUSTOMER_ID
    )
    """,
    """
    CREATE TABLE {schema}.CREDIT_BUREAU_RECORDS (
        BUREAU_RECORD_ID      DECIMAL(14,0) NOT NULL,
        CUSTOMER_ID           DECIMAL(12,0) NOT NULL,
        BUREAU_NAME           VARCHAR(40)   NOT NULL,
        REPORT_DATE           DATE          NOT NULL,
        BUREAU_SCORE          DECIMAL(5,0)  NOT NULL,
        DELINQUENCIES_12M     DECIMAL(4,0)  NOT NULL,
        DELINQUENCIES_24M     DECIMAL(4,0)  NOT NULL,
        HARD_INQUIRIES_6M     DECIMAL(4,0)  NOT NULL,
        COLLECTIONS_COUNT     DECIMAL(4,0)  NOT NULL,
        BANKRUPTCIES          DECIMAL(4,0)  NOT NULL,
        CREDIT_HISTORY_MONTHS DECIMAL(5,0)  NOT NULL,
        UTILIZATION_RATIO     DECIMAL(6,4)  NOT NULL,
        TOTAL_ACCOUNTS        DECIMAL(4,0)  NOT NULL,
        CONSTRAINT PK_BUREAU PRIMARY KEY (BUREAU_RECORD_ID),
        DISTRIBUTE BY CUSTOMER_ID
    )
    """,
    """
    CREATE TABLE {schema}.SYSTEM_EXPOSURES (
        EXPOSURE_ID        DECIMAL(14,0) NOT NULL,
        CUSTOMER_ID        DECIMAL(12,0) NOT NULL,
        SOURCE_SYSTEM      VARCHAR(20)   NOT NULL,
        FACILITY_REF       VARCHAR(40)   NOT NULL,
        ACCOUNT_REF        VARCHAR(60)   NOT NULL,
        PRODUCT_TYPE       VARCHAR(30)   NOT NULL,
        OUTSTANDING_BALANCE DECIMAL(14,2) NOT NULL,
        SANCTIONED_LIMIT   DECIMAL(14,2) NOT NULL,
        DAYS_PAST_DUE      DECIMAL(5,0)  NOT NULL,
        ACCOUNT_STATUS     VARCHAR(20)   NOT NULL,
        LAST_REPORTED_DATE DATE          NOT NULL,
        CONSTRAINT PK_EXPOSURES PRIMARY KEY (EXPOSURE_ID),
        DISTRIBUTE BY CUSTOMER_ID
    )
    """,
    """
    CREATE TABLE {schema}.LOAN_APPLICATIONS (
        APPLICATION_ID       DECIMAL(14,0) NOT NULL,
        CUSTOMER_ID          DECIMAL(12,0) NOT NULL,
        APPLICATION_DATE     DATE          NOT NULL,
        DECISION_DATE        DATE          NOT NULL,
        REQUESTED_AMOUNT     DECIMAL(14,2) NOT NULL,
        PRODUCT_TYPE         VARCHAR(30)   NOT NULL,
        TENURE_MONTHS        DECIMAL(4,0)  NOT NULL,
        PURPOSE              VARCHAR(40)   NOT NULL,
        DECISION             VARCHAR(20)   NOT NULL,
        MODEL_SCORE          DECIMAL(6,1)  NOT NULL,
        RISK_GRADE           VARCHAR(2)    NOT NULL,
        DTI_RATIO            DECIMAL(6,4)  NOT NULL,
        INCOME_AT_APPLICATION DECIMAL(14,2) NOT NULL,
        EXISTING_OBLIGATIONS DECIMAL(14,2) NOT NULL,
        PROPOSED_EMI         DECIMAL(14,2) NOT NULL,
        DENIAL_FACTORS       VARCHAR(300),
        CHANNEL              VARCHAR(30)   NOT NULL,
        BRANCH_CODE          VARCHAR(20)   NOT NULL,
        MODEL_VERSION        VARCHAR(20)   NOT NULL,
        CONSTRAINT PK_APPLICATIONS PRIMARY KEY (APPLICATION_ID),
        DISTRIBUTE BY CUSTOMER_ID
    )
    """,
    """
    CREATE TABLE {schema}.RISK_FACTOR_WEIGHTS (
        FACTOR_CODE          VARCHAR(40)   NOT NULL,
        FACTOR_NAME          VARCHAR(100)  NOT NULL,
        CATEGORY             VARCHAR(40)   NOT NULL,
        WEIGHT               DECIMAL(12,4) NOT NULL,
        BENCHMARK_THRESHOLD  DECIMAL(12,4) NOT NULL,
        COMPARISON_OPERATOR  VARCHAR(10)   NOT NULL,
        SEVERITY             VARCHAR(10)   NOT NULL,
        REGULATION_REF       VARCHAR(160)  NOT NULL,
        ADVERSE_ACTION_REASON VARCHAR(500) NOT NULL,
        PLAIN_LANGUAGE_TEMPLATE VARCHAR(1000) NOT NULL,
        DISPLAY_ORDER        DECIMAL(4,0)  NOT NULL,
        IS_SCORED            DECIMAL(1,0)  NOT NULL,
        CONSTRAINT PK_RISK_WEIGHTS PRIMARY KEY (FACTOR_CODE),
        DISTRIBUTE BY FACTOR_CODE
    )
    """,
    """
    CREATE TABLE {schema}.APPLICATION_RISK_FACTORS (
        APPLICATION_ID  DECIMAL(14,0) NOT NULL,
        CUSTOMER_ID     DECIMAL(12,0) NOT NULL,
        FACTOR_CODE     VARCHAR(40)   NOT NULL,
        FACTOR_VALUE    DECIMAL(14,4) NOT NULL,
        CONTRIBUTION    DECIMAL(10,2) NOT NULL,
        SEVERITY        VARCHAR(10)   NOT NULL,
        RANK_NO         DECIMAL(2,0)  NOT NULL,
        CONSTRAINT PK_APP_FACTORS PRIMARY KEY (APPLICATION_ID, FACTOR_CODE),
        DISTRIBUTE BY CUSTOMER_ID
    )
    """,
    """
    CREATE TABLE {schema}.ADVERSE_ACTION_REPORTS (
        REPORT_ID       VARCHAR(36)    NOT NULL,
        CUSTOMER_ID     DECIMAL(12,0)  NOT NULL,
        APPLICATION_ID  DECIMAL(14,0)  NOT NULL,
        GENERATED_AT    TIMESTAMP      NOT NULL,
        PROVIDER        VARCHAR(40)    NOT NULL,
        MODEL           VARCHAR(120)   NOT NULL,
        GENERATION_MODE VARCHAR(20)    NOT NULL,
        LETTER_JSON     VARCHAR(2000000) NOT NULL,
        CONSTRAINT PK_ADVERSE_REPORTS PRIMARY KEY (REPORT_ID),
        DISTRIBUTE BY CUSTOMER_ID
    )
    """,
]


def _now() -> date:
    return date.today()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _money(value: float) -> float:
    return round(float(value), 2)


def _emi(principal: float, annual_rate: float, months: int) -> float:
    monthly_rate = annual_rate / 12.0
    if monthly_rate == 0:
        return principal / months
    growth = (1.0 + monthly_rate) ** months
    return principal * monthly_rate * growth / (growth - 1.0)


class DataFactory:
    """Generates all tables in a deterministic, reproducible order."""

    def __init__(self, customers: int, seed: int = 42) -> None:
        self.n = customers
        self.seed = seed
        self.random = random.Random(seed)
        self.np = np.random.default_rng(seed)
        self.fake = Faker("en_IN")
        Faker.seed(seed)
        self.today = _now()
        self.weights = default_weights()
        self.approve = approval_threshold(self.weights)
        self.refer = approval_threshold(self.weights) - 70.0
        self.bureau: dict[int, dict[str, Any]] = {}
        self.exposures: dict[int, dict[str, Any]] = {}
        self.risk_factor_rows: list[tuple[Any, ...]] = []
        self._exposure_seq = 0
        self._bureau_seq = 0
        self._application_seq = 0
        self._customers_built = False
        self._income = np.clip(
            self.np.lognormal(mean=math.log(1_200_000), sigma=0.55, size=customers),
            300_000,
            10_000_000,
        )
        self._risk = np.clip(self.np.normal(0, 1, size=customers), -3.0, 2.5)
        self._customers: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Customers
    # ------------------------------------------------------------------
    def customers(self) -> list[dict[str, Any]]:
        if self._customers_built:
            return self._customers

        fake = self.fake
        rng = self.random
        today = self.today
        employment = (
            ["SALARIED"] * 58
            + ["SELF_EMPLOYED"] * 18
            + ["CONTRACT"] * 10
            + ["RETIRED"] * 8
            + ["STUDENT"] * 6
        )
        for index in range(self.n):
            customer_id = 100_001 + index
            first = fake.first_name()
            last = fake.last_name()
            income = float(round(self._income[index] / 100.0) * 100.0)
            if income >= 2_500_000:
                segment = "AFFLUENT"
            elif income >= 1_000_000:
                segment = "PRIME"
            elif rng.random() < 0.08:
                segment = "SME"
            else:
                segment = "MASS"
            kyc_roll = rng.random()
            kyc = "VERIFIED" if kyc_roll < 0.91 else ("PENDING" if kyc_roll < 0.97 else "ENHANCED")
            email_name = "".join(ch for ch in f"{first}.{last}" if ch.isalnum() or ch in "._").lower()
            city, state = rng.choice(CITY_STATE_PAIRS)
            self._customers.append(
                {
                    "customer_id": customer_id,
                    "first_name": first[:60],
                    "last_name": last[:60],
                    "email": f"{email_name}{customer_id}@example.com"[:160],
                    "phone": fake.numerify("+91-9####-#####"),
                    "date_of_birth": fake.date_of_birth(minimum_age=21, maximum_age=72),
                    "city": city,
                    "state": state,
                    "postal_code": fake.postcode()[:12],
                    "employment_status": rng.choice(employment),
                    "annual_income": income,
                    "kyc_status": kyc,
                    "segment": segment,
                    "customer_since": today - timedelta(days=rng.randint(200, 5400)),
                    "risk_z": float(self._risk[index]),
                }
            )
        self._customers_built = True
        return self._customers

    @staticmethod
    def customer_tuple(row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            row["customer_id"],
            row["first_name"],
            row["last_name"],
            row["email"],
            row["phone"],
            row["date_of_birth"],
            row["city"],
            row["state"],
            row["postal_code"],
            row["employment_status"],
            row["annual_income"],
            row["kyc_status"],
            row["segment"],
            row["customer_since"],
        )

    # ------------------------------------------------------------------
    # Bureau
    # ------------------------------------------------------------------
    def _make_bureau(self, customer: dict[str, Any]) -> dict[str, Any]:
        rng = self.random
        stressed = max(0.0, -float(customer["risk_z"]))
        utilization = _clamp(0.10 + 0.20 * stressed + rng.gauss(0, 0.11), 0.01, 1.15)
        delinquency_12m = 0
        if rng.random() < 0.16 + 0.09 * stressed:
            delinquency_12m = rng.randint(1, 4)
        delinquency_24m = delinquency_12m + (1 if rng.random() < 0.15 else 0)
        inquiries = _clamp(round(rng.gauss(1.2 + 0.7 * stressed, 1.4)), 0, 9)
        collections = 1 if rng.random() < 0.055 + 0.045 * stressed else 0
        bankruptcies = 1 if rng.random() < 0.012 + 0.02 * stressed else 0
        history = rng.randint(6, 240)
        score = (
            805
            - 32 * delinquency_12m
            - 7 * inquiries
            - 45 * max(0.0, utilization - 0.30)
            - 45 * collections
            - 110 * bankruptcies
            - 18 * stressed
            + rng.gauss(0, 18)
        )
        bureau_score = int(_clamp(round(score), 350, 900))
        self._bureau_seq += 1
        return {
            "bureau_record_id": 500_001 + self._bureau_seq - 1,
            "customer_id": customer["customer_id"],
            "bureau_name": rng.choice(["CIBIL", "EXPERIAN", "EQUIFAX", "CRIF"]),
            "report_date": self.today - timedelta(days=rng.randint(0, 42)),
            "bureau_score": bureau_score,
            "delinquencies_12m": int(delinquency_12m),
            "delinquencies_24m": int(delinquency_24m),
            "hard_inquiries_6m": int(inquiries),
            "collections_count": int(collections),
            "bankruptcies": int(bankruptcies),
            "credit_history_months": int(history),
            "utilization_ratio": round(utilization, 4),
            "total_accounts": rng.randint(2, 19),
        }

    def bureau_rows(self) -> Iterator[tuple[Any, ...]]:
        for customer in self.customers():
            row = self._make_bureau(customer)
            self.bureau[customer["customer_id"]] = row
            yield (
                row["bureau_record_id"],
                row["customer_id"],
                row["bureau_name"],
                row["report_date"],
                row["bureau_score"],
                row["delinquencies_12m"],
                row["delinquencies_24m"],
                row["hard_inquiries_6m"],
                row["collections_count"],
                row["bankruptcies"],
                row["credit_history_months"],
                row["utilization_ratio"],
                row["total_accounts"],
            )

    # ------------------------------------------------------------------
    # Exposures
    # ------------------------------------------------------------------
    def _make_exposures(self, customer: dict[str, Any]) -> list[dict[str, Any]]:
        rng = self.random
        cid = customer["customer_id"]
        income = float(customer["annual_income"])
        stressed = max(0.0, -float(customer["risk_z"]))
        bureau = self.bureau[cid]

        core_limit = income * rng.uniform(0.12, 0.80) * (1.0 + 0.20 * stressed)
        core_balance = core_limit * _clamp(rng.uniform(0.25, 0.92) * (1.0 + 0.10 * stressed), 0.05, 0.99)
        card_limit = income * rng.uniform(0.015, 0.12)
        card_balance = card_limit * _clamp(
            float(bureau["utilization_ratio"]) + rng.gauss(0, 0.06), 0.02, 1.10
        )
        micro_limit = income * rng.uniform(0.008, 0.055)
        micro_balance = micro_limit * rng.uniform(0.30, 0.98)

        base_dpd = 0
        if rng.random() < 0.05 + 0.07 * stressed:
            base_dpd = rng.choice([15, 30, 45, 60, 90, 120])
        status = "CURRENT"
        if base_dpd >= 120 and rng.random() < 0.3:
            status = "CHARGED_OFF"
        elif base_dpd > 0:
            status = "DELINQUENT"

        reported = self.today - timedelta(days=rng.randint(0, 10))
        rows: list[dict[str, Any]] = []

        def add_row(
            source: str,
            facility_ref: str,
            product: str,
            balance: float,
            limit: float,
            dpd: int,
            acct_status: str,
            last_reported: date,
        ) -> None:
            self._exposure_seq += 1
            rows.append(
                {
                    "exposure_id": 1_000_000 + self._exposure_seq,
                    "customer_id": cid,
                    "source_system": source,
                    "facility_ref": facility_ref,
                    "account_ref": f"{source[:4]}-{cid}-{len(rows) + 1:02d}",
                    "product_type": product,
                    "outstanding_balance": _money(max(500.0, balance)),
                    "sanctioned_limit": _money(max(1_000.0, limit)),
                    "days_past_due": int(dpd),
                    "account_status": acct_status,
                    "last_reported_date": last_reported,
                }
            )

        add_row(
            "CORE_BANKING",
            f"CORE-{cid}-01",
            rng.choice(["PERSONAL_LOAN", "AUTO_LOAN", "HOME_LOAN", "BUSINESS_LOAN", "GOLD_LOAN"]),
            core_balance,
            core_limit,
            base_dpd,
            status,
            reported,
        )
        card_accounts = 2 if rng.random() < 0.42 else 1
        for card_number in range(1, card_accounts + 1):
            share = 1.0 if card_number == 1 else rng.uniform(0.25, 0.60)
            add_row(
                "CARD_ENGINE",
                f"CARD-{cid}-{card_number:02d}",
                rng.choice(["CREDIT_CARD", "CHARGE_CARD"]),
                max(500.0, card_balance * share),
                max(2_500.0, card_limit * share),
                base_dpd if card_number == 1 else 0,
                status if card_number == 1 else "CURRENT",
                self.today - timedelta(days=rng.randint(0, 12)),
            )
        add_row(
            "MICROCREDIT",
            f"MICRO-{cid}-01",
            rng.choice(["MICRO_LOAN", "BNPL", "GOLD_LOAN"]),
            micro_balance,
            micro_limit,
            max(0, base_dpd - 15) if base_dpd else 0,
            "DELINQUENT" if base_dpd >= 30 else "CURRENT",
            self.today - timedelta(days=rng.randint(0, 8)),
        )

        # Deliberate cross-ledger conflicts: the same facility is reported by a
        # second system with a different outstanding balance.
        conflict_roll = rng.random()
        conflicts = 1 if conflict_roll < 0.36 else 0
        if conflict_roll < 0.075:
            conflicts = 2
        for _ in range(conflicts):
            original = rng.choice(rows)
            target = {
                "CORE_BANKING": "MICROCREDIT",
                "CARD_ENGINE": "CORE_BANKING",
                "MICROCREDIT": "CARD_ENGINE",
            }[original["source_system"]]
            multiplier = rng.uniform(1.05, 1.30) if rng.random() < 0.72 else rng.uniform(0.70, 0.95)
            balance = max(500.0, float(original["outstanding_balance"]) * multiplier)
            limit = max(balance * 1.02, float(original["sanctioned_limit"]) * rng.uniform(0.85, 1.18))
            add_row(
                target,
                original["facility_ref"],
                original["product_type"],
                balance,
                limit,
                max(0, int(original["days_past_due"]) + rng.choice([-15, 0, 0, 15, 30])),
                "DELINQUENT" if original["days_past_due"] else "CURRENT",
                self.today - timedelta(days=rng.randint(14, 45)),
            )

        return rows

    @staticmethod
    def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        totals = {system: 0.0 for system in SYSTEMS}
        sanctioned = 0.0
        max_dpd = 0
        facilities: dict[str, dict[str, Any]] = {}
        for row in rows:
            source = row["source_system"]
            balance = float(row["outstanding_balance"])
            totals[source] += balance
            sanctioned += float(row["sanctioned_limit"])
            max_dpd = max(max_dpd, int(row["days_past_due"]))
            facility = facilities.setdefault(
                row["facility_ref"],
                {"max": balance, "min": balance, "systems": set()},
            )
            facility["max"] = max(facility["max"], balance)
            facility["min"] = min(facility["min"], balance)
            facility["systems"].add(source)
        gross = sum(totals.values())
        reconciled = sum(item["max"] for item in facilities.values())
        conflicted = sum(1 for item in facilities.values() if len(item["systems"]) > 1)
        spread = sum(item["max"] - item["min"] for item in facilities.values())
        variance_ratio = (gross - reconciled) / reconciled if reconciled > 0 else 0.0
        return {
            "core_exposure": totals["CORE_BANKING"],
            "card_exposure": totals["CARD_ENGINE"],
            "micro_exposure": totals["MICROCREDIT"],
            "gross_exposure": gross,
            "reconciled_exposure": reconciled,
            "total_sanctioned": sanctioned,
            "max_dpd": max_dpd,
            "systems_reporting": len({row["source_system"] for row in rows}),
            "exposure_accounts": len(rows),
            "conflicted_facilities": conflicted,
            "reported_balance_spread": spread,
            "variance_ratio": variance_ratio,
            "facility_count": len(facilities),
        }

    def exposure_rows(self) -> Iterator[tuple[Any, ...]]:
        for customer in self.customers():
            rows = self._make_exposures(customer)
            self.exposures[customer["customer_id"]] = self._summarize(rows)
            for row in rows:
                yield (
                    row["exposure_id"],
                    row["customer_id"],
                    row["source_system"],
                    row["facility_ref"],
                    row["account_ref"],
                    row["product_type"],
                    row["outstanding_balance"],
                    row["sanctioned_limit"],
                    row["days_past_due"],
                    row["account_status"],
                    row["last_reported_date"],
                )

    # ------------------------------------------------------------------
    # Applications
    # ------------------------------------------------------------------
    def application_rows(self) -> Iterator[tuple[Any, ...]]:
        rng = self.random
        today = self.today
        for customer in self.customers():
            cid = customer["customer_id"]
            bureau = self.bureau[cid]
            exposure = self.exposures[cid]
            monthly_income = float(customer["annual_income"]) / 12.0
            existing = float(exposure["gross_exposure"]) * 0.032
            n_apps = rng.choices([1, 2, 3], weights=[54, 36, 10], k=1)[0]
            age_windows = [(0, 190), (190, 520), (520, 900)]
            for index in range(n_apps):
                low, high = age_windows[min(index, len(age_windows) - 1)]
                app_date = today - timedelta(days=rng.randint(low, high))
                product = rng.choices(
                    ["PERSONAL_LOAN", "AUTO_LOAN", "CREDIT_CARD", "MICRO_LOAN", "HOME_LOAN", "GOLD_LOAN"],
                    weights=[36, 18, 20, 14, 7, 5],
                    k=1,
                )[0]
                requested = _money(
                    _clamp(
                        float(customer["annual_income"]) * rng.uniform(0.04, 0.55)
                        * (1.25 if rng.random() < 0.18 else 1.0),
                        25_000,
                        5_000_000,
                    )
                )
                tenure = rng.choice([12, 18, 24, 36, 48, 60, 72, 84])
                proposed_emi = _money(_emi(requested, 0.125, tenure))
                dti = _clamp((existing + proposed_emi) / max(1.0, monthly_income), 0.03, 1.35)
                metrics = {
                    "bureau_score": bureau["bureau_score"],
                    "dti_ratio": dti,
                    "delinquencies_12m": bureau["delinquencies_12m"],
                    "hard_inquiries_6m": bureau["hard_inquiries_6m"],
                    "utilization_ratio": (
                        exposure["gross_exposure"] / exposure["total_sanctioned"]
                        if exposure["total_sanctioned"] > 0
                        else 0.0
                    ),
                    "variance_ratio": exposure["variance_ratio"],
                    "max_dpd": exposure["max_dpd"],
                    "collections_count": bureau["collections_count"],
                    "bankruptcies": bureau["bankruptcies"],
                }
                result = score_metrics(metrics, self.weights)
                noisy_score = round(
                    _clamp(result.score + rng.gauss(0, 13), 300, 900), 1
                )
                decision = decision_for(noisy_score, self.weights)
                if 740 <= noisy_score <= 780 and rng.random() < 0.38:
                    decision = "REFERRED"
                grade = grade_for(noisy_score, self.weights)

                denial_codes: list[str] = []
                if decision != "APPROVED":
                    selected = result.negative_factors[:3]
                    if len(selected) < 2:
                        extra = [
                            c
                            for c in sorted(result.contributions, key=lambda item: item.contribution)
                            if c not in selected
                        ][: 2 - len(selected)]
                        selected.extend(extra)
                    for rank, contribution in enumerate(selected, start=1):
                        denial_codes.append(contribution.factor_code)
                        self.risk_factor_rows.append(
                            (
                                self._application_seq + 1,
                                cid,
                                contribution.factor_code,
                                round(contribution.observed, 4),
                                round(contribution.contribution, 2),
                                contribution.severity,
                                rank,
                            )
                        )

                self._application_seq += 1
                decision_date = min(today, app_date + timedelta(days=rng.randint(0, 5)))
                yield (
                    self._application_seq,
                    cid,
                    app_date,
                    decision_date,
                    requested,
                    product,
                    tenure,
                    rng.choice(
                        [
                            "DEBT_CONSOLIDATION",
                            "WORKING_CAPITAL",
                            "HOME_RENOVATION",
                            "MEDICAL",
                            "VEHICLE",
                            "EDUCATION",
                            "OTHER",
                        ]
                    ),
                    decision,
                    noisy_score,
                    grade,
                    round(dti, 4),
                    _money(float(customer["annual_income"]) * rng.uniform(0.97, 1.03)),
                    _money(existing),
                    proposed_emi,
                    ",".join(denial_codes)[:300],
                    rng.choice(["MOBILE", "WEB", "BRANCH", "PARTNER"]),
                    f"BR-{rng.randint(1, 240):03d}",
                    "credence-score-v1",
                )

    # ------------------------------------------------------------------
    # Factor weights
    # ------------------------------------------------------------------
    @staticmethod
    def weight_rows() -> Iterator[tuple[Any, ...]]:
        for item in sorted(FACTOR_DEFINITIONS, key=lambda row: row["display_order"]):
            yield (
                item["factor_code"],
                item["factor_name"],
                item["category"],
                float(item["weight"]),
                float(item["benchmark_threshold"]),
                item["comparison_operator"],
                item["severity"],
                item["regulation_ref"],
                item["adverse_action_reason"],
                item["plain_language_template"],
                int(item["display_order"]),
                int(item["is_scored"]),
            )

    def summary(self, application_rows: int, risk_factor_rows: int) -> dict[str, Any]:
        scores = sorted(
            float(exposure.get("variance_ratio", 0.0)) for exposure in self.exposures.values()
        )
        mismatch = sum(
            1
            for exposure in self.exposures.values()
            if exposure["variance_ratio"] > 0.08 or exposure["conflicted_facilities"] >= 2
        )
        return {
            "applications": application_rows,
            "risk_factor_rows": risk_factor_rows,
            "customers": len(self._customers),
            "bureau": len(self.bureau),
            "exposures": self._exposure_seq,
            "mismatch": mismatch,
            "mismatch_pct": mismatch / max(1, len(self.exposures)),
            "variance_p90": scores[int(len(scores) * 0.9)] if scores else 0,
        }


def _connect(args: argparse.Namespace):
    import pyexasol

    verify_tls = args.tls_verify
    return pyexasol.connect(
        dsn=f"{args.host}:{args.port}",
        user=args.user,
        password=args.password,
        compression=True,
        encryption=True,
        # Exasol Personal ships a self-signed local certificate by default.
        # Set EXASOL_TLS_VERIFY=true when connecting to a CA-signed endpoint.
        websocket_sslopt={"cert_reqs": ssl.CERT_REQUIRED if verify_tls else ssl.CERT_NONE},
        fetch_dict=True,
        lower_ident=True,
        connection_timeout=20,
        socket_timeout=120,
    )


def _count_existing(con, schema: str) -> int:
    try:
        stmt = con.execute(f"SELECT COUNT(*) AS C FROM {schema}.CUSTOMERS")
        row = stmt.fetchone()
        if not row:
            return 0
        return int(next(iter(row.values())) if isinstance(row, dict) else row[0])
    except Exception:
        return 0


def _create_schema_and_tables(con, schema: str, reset: bool) -> None:
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    if reset:
        print("  dropping existing objects ...", flush=True)
        con.execute(f"DROP VIEW IF EXISTS {schema}.V_RECONCILED_CREDIT_360")
        con.execute(f"DROP SCRIPT IF EXISTS {schema}.SCORE_PORTFOLIO")
        for table in (
            "ADVERSE_ACTION_REPORTS",
            "APPLICATION_RISK_FACTORS",
            "LOAN_APPLICATIONS",
            "SYSTEM_EXPOSURES",
            "CREDIT_BUREAU_RECORDS",
            "CUSTOMERS",
            "RISK_FACTOR_WEIGHTS",
        ):
            con.execute(f"DROP TABLE IF EXISTS {schema}.{table}")
    for statement in DDL_STATEMENTS:
        con.execute(statement.format(schema=schema))


def _import_rows(
    con,
    schema: str,
    table: str,
    rows: Iterable[tuple[Any, ...]],
    label: str,
) -> int:
    started = time.perf_counter()
    count = 0

    def counted() -> Iterator[tuple[Any, ...]]:
        nonlocal count
        for row in rows:
            count += 1
            yield row

    con.import_from_iterable(
        counted(),
        (schema, table),
        import_params={"format": "csv"},
    )
    elapsed = time.perf_counter() - started
    rate = count / elapsed if elapsed else 0
    print(f"  {label:<26} {count:>9,} rows  {elapsed:6.2f}s  ({rate:,.0f} rows/s)", flush=True)
    return count


def _view_sql(schema: str) -> str:
    weights = default_weights()
    score_expr = build_score_sql(weights)
    approve = approval_threshold(weights)
    refer = approve - 70.0
    return f"""
CREATE OR REPLACE VIEW {schema}.V_RECONCILED_CREDIT_360 AS
WITH facility_recon AS (
    SELECT
        customer_id,
        facility_ref,
        MAX(outstanding_balance) AS reconciled_balance,
        MIN(outstanding_balance) AS minimum_balance,
        MAX(outstanding_balance) - MIN(outstanding_balance) AS balance_spread,
        COUNT(DISTINCT source_system) AS systems_reporting,
        MAX(days_past_due) AS facility_dpd
    FROM {schema}.SYSTEM_EXPOSURES
    GROUP BY customer_id, facility_ref
),
system_rollup AS (
    SELECT
        customer_id,
        SUM(CASE WHEN source_system = 'CORE_BANKING' THEN outstanding_balance ELSE 0 END) AS core_exposure,
        SUM(CASE WHEN source_system = 'CARD_ENGINE' THEN outstanding_balance ELSE 0 END) AS card_exposure,
        SUM(CASE WHEN source_system = 'MICROCREDIT' THEN outstanding_balance ELSE 0 END) AS micro_exposure,
        SUM(outstanding_balance) AS gross_exposure,
        SUM(sanctioned_limit) AS total_sanctioned,
        MAX(days_past_due) AS max_dpd,
        COUNT(DISTINCT source_system) AS systems_reporting,
        COUNT(*) AS exposure_accounts
    FROM {schema}.SYSTEM_EXPOSURES
    GROUP BY customer_id
),
dedup AS (
    SELECT
        customer_id,
        SUM(reconciled_balance) AS reconciled_exposure,
        SUM(CASE WHEN systems_reporting > 1 THEN 1 ELSE 0 END) AS conflicted_facilities,
        SUM(CASE WHEN systems_reporting > 1 THEN balance_spread ELSE 0 END) AS reported_balance_spread
    FROM facility_recon
    GROUP BY customer_id
),
bureau AS (
    SELECT
        customer_id, bureau_name, report_date, bureau_score, delinquencies_12m,
        delinquencies_24m, hard_inquiries_6m, collections_count, bankruptcies,
        credit_history_months, utilization_ratio AS bureau_utilization_ratio, total_accounts
    FROM (
        SELECT
            b.*,
            ROW_NUMBER() OVER (
                PARTITION BY customer_id
                ORDER BY report_date DESC, bureau_record_id DESC
            ) AS rn
        FROM {schema}.CREDIT_BUREAU_RECORDS b
    ) ranked
    WHERE rn = 1
),
latest_app AS (
    SELECT
        customer_id, application_id, application_date, decision_date, requested_amount,
        product_type, tenure_months, purpose, decision, dti_ratio,
        income_at_application, proposed_emi, risk_grade, model_score, denial_factors,
        channel, branch_code
    FROM (
        SELECT
            a.*,
            ROW_NUMBER() OVER (
                PARTITION BY customer_id
                ORDER BY application_date DESC, application_id DESC
            ) AS rn
        FROM {schema}.LOAN_APPLICATIONS a
    ) ranked
    WHERE rn = 1
),
base AS (
    SELECT
        c.customer_id, c.first_name, c.last_name, c.email, c.phone, c.city, c.state_code AS "state",
        c.postal_code, c.segment, c.annual_income, c.employment_status, c.kyc_status,
        c.customer_since,
        b.bureau_name, b.report_date AS bureau_report_date, b.bureau_score,
        b.delinquencies_12m, b.delinquencies_24m, b.hard_inquiries_6m,
        b.collections_count, b.bankruptcies, b.credit_history_months,
        b.bureau_utilization_ratio, b.total_accounts AS bureau_total_accounts,
        s.core_exposure, s.card_exposure, s.micro_exposure, s.gross_exposure,
        s.total_sanctioned, s.max_dpd, s.systems_reporting, s.exposure_accounts,
        d.reconciled_exposure, d.conflicted_facilities, d.reported_balance_spread,
        a.application_id AS latest_application_id,
        a.application_date AS latest_application_date,
        a.decision_date AS latest_decision_date,
        a.decision AS latest_decision,
        a.requested_amount AS latest_requested_amount,
        a.product_type AS latest_product_type,
        a.tenure_months AS latest_tenure_months,
        a.purpose AS latest_purpose,
        a.dti_ratio AS latest_dti_ratio,
        a.income_at_application AS latest_income,
        a.proposed_emi AS latest_proposed_emi,
        a.risk_grade AS latest_risk_grade,
        a.model_score AS latest_model_score,
        COALESCE(a.denial_factors, '') AS latest_denial_factors,
        a.channel AS latest_channel,
        a.branch_code AS latest_branch_code
    FROM {schema}.CUSTOMERS c
    JOIN system_rollup s ON s.customer_id = c.customer_id
    JOIN dedup d ON d.customer_id = c.customer_id
    LEFT JOIN bureau b ON b.customer_id = c.customer_id
    LEFT JOIN latest_app a ON a.customer_id = c.customer_id
),
metrics AS (
    SELECT
        base.*,
        CAST(gross_exposure - reconciled_exposure AS DOUBLE) AS debt_variance,
        CASE WHEN reconciled_exposure > 0
             THEN CAST(gross_exposure - reconciled_exposure AS DOUBLE) / reconciled_exposure
             ELSE 0.0 END AS variance_ratio,
        CASE WHEN total_sanctioned > 0
             THEN CAST(gross_exposure AS DOUBLE) / total_sanctioned
             ELSE 0.0 END AS portfolio_utilization_ratio
    FROM base
),
percentiles AS (
    SELECT
        metrics.*,
        PERCENT_RANK() OVER (ORDER BY gross_exposure) AS exposure_percentile,
        PERCENT_RANK() OVER (
            ORDER BY CASE WHEN total_sanctioned > 0
                          THEN CAST(gross_exposure AS DOUBLE) / total_sanctioned
                          ELSE 0.0 END
        ) AS utilization_percentile
    FROM metrics
),
scored AS (
    SELECT
        p.*,
        {score_expr} AS eligibility_score
    FROM percentiles p
),
classified AS (
    SELECT
        s.*,
        CASE
            WHEN s.variance_ratio > 0.08 OR s.conflicted_facilities >= 2 THEN 'MISMATCH'
            WHEN s.variance_ratio > 0.02 OR s.conflicted_facilities = 1 THEN 'MINOR_VARIANCE'
            ELSE 'RECONCILED'
        END AS reconciliation_status
    FROM scored s
)
SELECT
    c.*,
    CASE WHEN c.reconciliation_status = 'RECONCILED' THEN 0 ELSE 1 END AS has_discrepancy,
    CASE WHEN c.eligibility_score >= {approve:.1f} THEN 'APPROVED'
         WHEN c.eligibility_score >= {refer:.1f} THEN 'REFERRED'
         ELSE 'DECLINED' END AS eligibility_decision,
    ROUND(GREATEST(0.0, {approve:.1f} - c.eligibility_score), 1) AS score_gap_to_approval,
    CASE WHEN c.eligibility_score >= {approve + 80:.1f} THEN 'A'
         WHEN c.eligibility_score >= {approve:.1f} THEN 'B'
         WHEN c.eligibility_score >= {approve - 40:.1f} THEN 'C'
         WHEN c.eligibility_score >= {refer:.1f} THEN 'D'
         ELSE 'E' END AS recomputed_grade
FROM classified c
"""


def _print_summary(factory: DataFactory, app_count: int, factor_count: int, elapsed: float) -> None:
    summary = factory.summary(app_count, factor_count)
    print("\n  Generated data summary")
    print(f"    customers .............. {summary['customers']:,}")
    print(f"    bureau records ......... {summary['bureau']:,}")
    print(f"    exposure rows .......... {summary['exposures']:,}")
    print(f"    applications ........... {summary['applications']:,}")
    print(f"    risk factor rows ....... {summary['risk_factor_rows']:,}")
    print(f"    mismatch customers ..... {summary['mismatch']:,} ({summary['mismatch_pct'] * 100:.1f}%)")
    print(f"    p90 exposure variance .. {summary['variance_p90'] * 100:.1f}%")
    print(f"    elapsed ................ {elapsed:.1f}s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed CredenceIQ into Exasol Personal")
    parser.add_argument("--host", default=os.getenv("EXASOL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("EXASOL_PORT", "8563")))
    parser.add_argument("--user", default=os.getenv("EXASOL_USER", "sys"))
    parser.add_argument("--password", default=os.getenv("EXASOL_PASSWORD", ""))
    parser.add_argument("--schema", default=SCHEMA_DEFAULT)
    parser.add_argument(
        "--tls-verify",
        action="store_true",
        default=os.getenv("EXASOL_TLS_VERIFY", "false").lower() in {"1", "true", "yes"},
        help="verify the Exasol TLS certificate (off by default for local Personal)",
    )
    parser.add_argument("--customers", type=int, default=int(os.getenv("SEED_CUSTOMERS", "30000")))
    parser.add_argument("--seed", type=int, default=int(os.getenv("SEED_RANDOM_SEED", "42")))
    parser.add_argument("--reset", action="store_true", help="drop and rebuild all objects")
    parser.add_argument(
        "--if-empty",
        action="store_true",
        help="exit successfully when the target schema already contains data",
    )
    parser.add_argument("--dry-run", action="store_true", help="generate locally without Exasol")
    args = parser.parse_args(argv)

    if args.customers < 100:
        parser.error("--customers must be at least 100")

    started = time.perf_counter()
    factory = DataFactory(customers=args.customers, seed=args.seed)
    print(f"CredenceIQ seed engine  schema={args.schema}  customers={args.customers:,}  seed={args.seed}")

    if args.dry_run:
        customers = factory.customers()
        bureau_count = sum(1 for _ in factory.bureau_rows())
        exposure_count = sum(1 for _ in factory.exposure_rows())
        decision_counts: dict[str, int] = {}
        scores: list[float] = []
        app_count = 0
        for row in factory.application_rows():
            app_count += 1
            decision_counts[row[8]] = decision_counts.get(row[8], 0) + 1
            scores.append(float(row[9]))
        scores.sort()
        _print_summary(factory, app_count, len(factory.risk_factor_rows), time.perf_counter() - started)
        print("\n  Decision mix")
        for decision in ("APPROVED", "REFERRED", "DECLINED"):
            count = decision_counts.get(decision, 0)
            print(f"    {decision:<10} {count:>7,}  {count / max(1, app_count) * 100:5.1f}%")
        print("\n  Eligibility score percentiles")
        for percentile in (10, 25, 50, 75, 90):
            value = scores[min(len(scores) - 1, int(len(scores) * percentile / 100))]
            print(f"    p{percentile:<2} ................. {value:.1f}")
        print("\n  Dry run only - no database connection was opened.")
        return 0

    if not args.password:
        parser.error(
            "EXASOL_PASSWORD is empty. Put the Personal credentials in .env "
            "(see .env.example) or pass --password."
        )

    print(f"  connecting to Exasol Personal at {args.host}:{args.port} ...", flush=True)
    con = _connect(args)
    try:
        existing = _count_existing(con, args.schema)
        if existing > 0:
            if args.if_empty:
                print(f"  {args.schema}.CUSTOMERS already has {existing:,} rows - skipping seed.")
                return 0
            if not args.reset:
                print(
                    f"ERROR: {args.schema}.CUSTOMERS already has {existing:,} rows.\n"
                    "       Re-run with --reset to rebuild, or --if-empty to skip.",
                    file=sys.stderr,
                )
                return 2

        print(f"  connecting ...")
        _create_schema_and_tables(con, args.schema, reset=args.reset)

        customers = factory.customers()
        _import_rows(
            con,
            args.schema,
            "CUSTOMERS",
            (factory.customer_tuple(customer) for customer in customers),
            "customers",
        )
        _import_rows(
            con, args.schema, "RISK_FACTOR_WEIGHTS", factory.weight_rows(), "risk factor weights"
        )
        _import_rows(con, args.schema, "CREDIT_BUREAU_RECORDS", factory.bureau_rows(), "credit bureau records")
        _import_rows(con, args.schema, "SYSTEM_EXPOSURES", factory.exposure_rows(), "cross-system exposures")
        app_count = _import_rows(
            con, args.schema, "LOAN_APPLICATIONS", factory.application_rows(), "loan applications"
        )
        factor_count = _import_rows(
            con,
            args.schema,
            "APPLICATION_RISK_FACTORS",
            (tuple(row) for row in factory.risk_factor_rows),
            "application risk factors",
        )
        print("  building analytical view ...", flush=True)
        view_started = time.perf_counter()
        con.execute(_view_sql(args.schema))
        print(f"  v_reconciled_credit_360 created in {time.perf_counter() - view_started:.2f}s")

        print("  installing in-database scoring UDF ...", flush=True)
        udf_started = time.perf_counter()
        con.execute(build_score_udf(default_weights(), schema=args.schema))
        print(f"  score_portfolio UDF created in {time.perf_counter() - udf_started:.2f}s")

        row = con.execute(
            f"SELECT COUNT(*) AS CUSTOMERS, "
            f"ROUND(AVG(eligibility_score), 1) AS AVG_SCORE, "
            f"SUM(has_discrepancy) AS DISCREPANCIES "
            f"FROM {args.schema}.V_RECONCILED_CREDIT_360"
        ).fetchone()
        if row:
            print(
                "  view sanity check ........ "
                f"customers={int(row['customers']):,} "
                f"avg_score={row['avg_score']} "
                f"discrepancies={int(row['discrepancies'] or 0):,}"
            )
        _print_summary(factory, app_count, factor_count, time.perf_counter() - started)
        print("\n  Done. Start the API with:  uvicorn app.main:app --reload  (from backend/)")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
