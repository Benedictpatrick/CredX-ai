"""
Synthetic Data Generator — Creates realistic Indian corporate loan data for testing.

Generates:
- Company profiles with realistic CIN, GSTIN, promoters
- Loan applications with various risk profiles
- Bank statement summaries with counterparty flows
- GST summaries with GSTR-1/3B data
- Site visit observations
- Management interview records

Supports three risk profiles: CLEAN, RISKY, FRAUDULENT.
"""
from __future__ import annotations

import json
import random
import string
from datetime import date, datetime, timedelta
from pathlib import Path

from src.models.schemas import (
    BankStatementSummary,
    CompanyProfile,
    CounterpartyFlow,
    GSTSummary,
    LoanApplication,
    ManagementInterview,
    PromoterInfo,
    SiteVisitObservation,
)

SECTORS = [
    "Manufacturing", "Infrastructure", "NBFC", "Textiles", "Pharmaceuticals",
    "IT Services", "Real Estate", "Agriculture", "Chemicals", "Steel",
    "Auto Components", "FMCG", "Logistics", "Renewable Energy", "Fintech",
]

INDIAN_CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad", "Pune",
    "Ahmedabad", "Kolkata", "Indore", "Jaipur", "Surat", "Lucknow",
]

BANKS = [
    "State Bank of India", "HDFC Bank", "ICICI Bank", "Axis Bank",
    "Bank of Baroda", "Punjab National Bank", "Kotak Mahindra Bank",
    "Yes Bank", "IndusInd Bank", "Union Bank of India",
]

COMPANY_SUFFIXES = [
    "Industries Ltd", "Technologies Pvt Ltd", "Infra Ltd",
    "Enterprises Pvt Ltd", "Manufacturing Ltd", "Solutions Pvt Ltd",
    "Chemicals Ltd", "Steel Ltd", "Textiles Ltd", "Pharma Pvt Ltd",
]

FIRST_NAMES = [
    "Rajesh", "Sunil", "Amit", "Priya", "Deepak", "Anita", "Vikram",
    "Meera", "Sanjay", "Kavita", "Rahul", "Sunita", "Arun", "Neha",
]

LAST_NAMES = [
    "Sharma", "Patel", "Gupta", "Singh", "Agarwal", "Jain", "Mehta",
    "Reddy", "Nair", "Verma", "Malhotra", "Desai", "Iyer", "Khanna",
]


def _random_cin() -> str:
    """Generate realistic CIN: L{5digit}{2char}{4year}PLC{6digit}"""
    prefix = random.choice(["L", "U"])
    code = "".join(random.choices(string.digits, k=5))
    state = random.choice(["MH", "DL", "KA", "TN", "GJ", "RJ", "UP", "WB"])
    year = random.randint(1990, 2020)
    plc = random.choice(["PLC", "PTC"])
    num = "".join(random.choices(string.digits, k=6))
    return f"{prefix}{code}{state}{year}{plc}{num}"


def _random_gstin(state_code: str = "27") -> str:
    """Generate realistic GSTIN: 2-digit state + 10-char PAN + 1Z + check"""
    pan = "".join(random.choices(string.ascii_uppercase, k=5))
    pan += "".join(random.choices(string.digits, k=4))
    pan += random.choice(string.ascii_uppercase)
    return f"{state_code}{pan}1Z{random.choice(string.digits)}"


def _random_din() -> str:
    return "".join(random.choices(string.digits, k=8))


def _random_pan() -> str:
    return (
        "".join(random.choices(string.ascii_uppercase, k=5))
        + "".join(random.choices(string.digits, k=4))
        + random.choice(string.ascii_uppercase)
    )


def _random_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def generate_company(
    risk_profile: str = "CLEAN",
    sector: str | None = None,
) -> CompanyProfile:
    """Generate a realistic Indian company profile."""
    sector = sector or random.choice(SECTORS)
    name = f"{random.choice(FIRST_NAMES[:7])}{random.choice(LAST_NAMES[:7])} {random.choice(COMPANY_SUFFIXES)}"

    num_promoters = random.randint(2, 5)
    promoters = []
    for _ in range(num_promoters):
        disqualified = (risk_profile == "FRAUDULENT" and random.random() < 0.3)
        cibil = {
            "CLEAN": random.randint(720, 850),
            "RISKY": random.randint(600, 720),
            "FRAUDULENT": random.randint(450, 650),
        }[risk_profile]

        other_boards = [_random_cin() for _ in range(random.randint(0, 6))]

        promoters.append(PromoterInfo(
            din=_random_din(),
            name=_random_name(),
            designation=random.choice(["Managing Director", "Director", "Whole-time Director", "CEO"]),
            shareholding_pct=round(random.uniform(5, 45), 2),
            other_directorships=other_boards,
            disqualified=disqualified,
            cibil_score=cibil,
        ))

    turnover = {
        "CLEAN": random.uniform(50, 500),
        "RISKY": random.uniform(20, 200),
        "FRAUDULENT": random.uniform(100, 800),
    }[risk_profile]

    return CompanyProfile(
        cin=_random_cin(),
        name=name,
        incorporation_date=date(random.randint(1995, 2018), random.randint(1, 12), 1),
        registered_address=f"{random.randint(1, 500)}, {random.choice(INDIAN_CITIES)}",
        sector=sector,
        sub_sector=f"{sector} - General",
        gstin=_random_gstin(),
        pan=_random_pan(),
        promoters=promoters,
        annual_turnover_cr=round(turnover, 2),
        net_worth_cr=round(turnover * random.uniform(0.2, 0.8), 2),
    )


def generate_loan_application(
    risk_profile: str = "CLEAN",
    sector: str | None = None,
) -> LoanApplication:
    """Generate a complete loan application."""
    company = generate_company(risk_profile, sector)

    amount_factor = {
        "CLEAN": random.uniform(0.1, 0.4),
        "RISKY": random.uniform(0.3, 0.7),
        "FRAUDULENT": random.uniform(0.5, 1.2),
    }[risk_profile]

    requested = round(company.annual_turnover_cr * amount_factor, 2)

    collateral_ratio = {
        "CLEAN": random.uniform(1.2, 2.0),
        "RISKY": random.uniform(0.6, 1.2),
        "FRAUDULENT": random.uniform(0.3, 0.8),
    }[risk_profile]

    return LoanApplication(
        company=company,
        requested_amount_cr=requested,
        loan_purpose=random.choice([
            "Working Capital", "Term Loan for Expansion",
            "Capex Financing", "Debt Refinancing",
            "Equipment Purchase", "Project Finance",
        ]),
        loan_tenure_months=random.choice([12, 24, 36, 48, 60, 84]),
        collateral_description=random.choice([
            "Factory land and building",
            "Commercial property in Mumbai",
            "Plant and machinery",
            "Inventory and receivables",
            "Residential property",
            "Fixed deposits and securities",
        ]),
        collateral_value_cr=round(requested * collateral_ratio, 2),
    )


def generate_bank_summaries(
    company: CompanyProfile,
    risk_profile: str = "CLEAN",
) -> list[BankStatementSummary]:
    """Generate bank statement summaries."""
    num_accounts = random.randint(1, 3)
    summaries = []

    for _ in range(num_accounts):
        turnover = company.annual_turnover_cr or 100
        monthly_avg = turnover / 12

        bounces = {
            "CLEAN": random.randint(0, 1),
            "RISKY": random.randint(2, 6),
            "FRAUDULENT": random.randint(3, 12),
        }[risk_profile]

        num_counterparties = random.randint(3, 8)
        counterparties = []
        for i in range(num_counterparties):
            is_related = (
                risk_profile == "FRAUDULENT" and random.random() < 0.5
            ) or random.random() < 0.1

            amount = round(turnover * random.uniform(0.02, 0.25), 2)
            counterparties.append(CounterpartyFlow(
                name=f"{_random_name()} Enterprises" if not is_related else f"Related Co {i+1}",
                gstin=_random_gstin() if random.random() > 0.3 else None,
                total_amount_cr=amount,
                transaction_count=random.randint(5, 50),
                is_related_party=is_related,
            ))

        summaries.append(BankStatementSummary(
            bank_name=random.choice(BANKS),
            account_number=f"{''.join(random.choices(string.digits, k=14))}",
            period_from=date(2024, 4, 1),
            period_to=date(2025, 3, 31),
            avg_monthly_balance_cr=round(monthly_avg * random.uniform(0.3, 1.5), 2),
            total_credits_cr=round(turnover * random.uniform(0.8, 1.2), 2),
            total_debits_cr=round(turnover * random.uniform(0.75, 1.15), 2),
            peak_utilization_pct=round(random.uniform(50, 95), 1),
            mandate_bounces=bounces,
            inward_return_count=random.randint(0, bounces),
            top_counterparties=counterparties,
        ))

    return summaries


def generate_gst_summaries(
    company: CompanyProfile,
    risk_profile: str = "CLEAN",
) -> list[GSTSummary]:
    """Generate GST filing summaries."""
    turnover = company.annual_turnover_cr or 100

    mismatch = {
        "CLEAN": random.uniform(0, 8),
        "RISKY": random.uniform(10, 25),
        "FRAUDULENT": random.uniform(20, 50),
    }[risk_profile]

    gstr3b = turnover
    gstr1 = gstr3b * (1 + mismatch / 100 * random.choice([-1, 1]))

    itc_eligible = turnover * random.uniform(0.05, 0.15)
    itc_inflation = {
        "CLEAN": random.uniform(0, 5),
        "RISKY": random.uniform(5, 15),
        "FRAUDULENT": random.uniform(15, 40),
    }[risk_profile]
    itc_claimed = itc_eligible * (1 + itc_inflation / 100)

    return [GSTSummary(
        gstin=company.gstin or _random_gstin(),
        period="2024-25",
        gstr1_turnover_cr=round(gstr1, 2),
        gstr3b_turnover_cr=round(gstr3b, 2),
        gstr2a_purchases_cr=round(turnover * random.uniform(0.4, 0.7), 2),
        gstr2b_purchases_cr=round(turnover * random.uniform(0.35, 0.65), 2),
        itc_claimed_cr=round(itc_claimed, 2),
        itc_eligible_cr=round(itc_eligible, 2),
        turnover_mismatch_pct=round(mismatch, 2),
        top_suppliers=[
            CounterpartyFlow(
                name=f"Supplier {i+1}",
                gstin=_random_gstin(),
                total_amount_cr=round(turnover * random.uniform(0.05, 0.2), 2),
                transaction_count=random.randint(10, 100),
            )
            for i in range(random.randint(3, 6))
        ],
        top_buyers=[
            CounterpartyFlow(
                name=f"Buyer {i+1}",
                gstin=_random_gstin(),
                total_amount_cr=round(turnover * random.uniform(0.05, 0.2), 2),
                transaction_count=random.randint(10, 80),
            )
            for i in range(random.randint(3, 6))
        ],
    )]


def generate_site_visit(risk_profile: str = "CLEAN") -> SiteVisitObservation:
    """Generate a site visit observation."""
    capacity = {
        "CLEAN": random.uniform(65, 90),
        "RISKY": random.uniform(35, 65),
        "FRAUDULENT": random.uniform(20, 45),
    }[risk_profile]

    notes = {
        "CLEAN": "Factory well-maintained, all production lines operational. Workers appear skilled. Inventory levels consistent with order book.",
        "RISKY": "Some machinery under maintenance. Capacity underutilized. Management cited delayed orders for current low output.",
        "FRAUDULENT": "Factory found operating at very low capacity. Several production lines idle. Inventory appears staged. Workers seemed unfamiliar with processes.",
    }[risk_profile]

    return SiteVisitObservation(
        observer_name=_random_name(),
        visit_date=date.today() - timedelta(days=random.randint(1, 30)),
        location=random.choice(INDIAN_CITIES),
        notes=notes,
        capacity_utilization_pct=round(capacity, 1),
        quantified_scores={
            "infrastructure": round(random.uniform(0.4, 0.9), 2),
            "labor_quality": round(random.uniform(0.3, 0.9), 2),
            "inventory_mgmt": round(random.uniform(0.3, 0.9), 2),
            "maintenance": round(random.uniform(0.3, 0.9), 2),
        },
        ai_assessment=f"Capacity utilization at {capacity:.0f}%. "
        + ("Consistent with reported production." if risk_profile == "CLEAN"
           else "Below reported levels."),
    )


def generate_management_interview(risk_profile: str = "CLEAN") -> ManagementInterview:
    """Generate a management interview record."""
    integrity = {
        "CLEAN": random.uniform(0.7, 0.95),
        "RISKY": random.uniform(0.4, 0.7),
        "FRAUDULENT": random.uniform(0.2, 0.45),
    }[risk_profile]

    return ManagementInterview(
        interviewee=_random_name(),
        designation=random.choice(["CFO", "Managing Director", "CEO", "COO"]),
        interview_date=date.today() - timedelta(days=random.randint(1, 14)),
        key_points=[
            "Discussed expansion plans and order pipeline",
            "Reviewed working capital management practices",
            "Assessed promoter commitment and stake",
        ],
        integrity_score=round(integrity, 2),
        ai_assessment=(
            "Management appears competent and transparent."
            if risk_profile == "CLEAN"
            else "Some inconsistencies in management responses."
        ),
    )


def generate_full_test_case(risk_profile: str = "CLEAN") -> dict:
    """Generate a complete test case with all data types."""
    app = generate_loan_application(risk_profile)
    bank = generate_bank_summaries(app.company, risk_profile)
    gst = generate_gst_summaries(app.company, risk_profile)
    site = generate_site_visit(risk_profile)
    interview = generate_management_interview(risk_profile)

    return {
        "application": app,
        "bank_summaries": bank,
        "gst_summaries": gst,
        "site_visits": [site],
        "management_interviews": [interview],
    }


def save_test_cases(output_dir: str | Path = "data/synthetic", count: int = 3):
    """Generate and save multiple test cases to JSON files."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    profiles = ["CLEAN", "RISKY", "FRAUDULENT"]
    for i, profile in enumerate(profiles[:count]):
        case = generate_full_test_case(profile)
        filename = output / f"test_case_{profile.lower()}.json"

        serializable = {
            "risk_profile": profile,
            "application": case["application"].model_dump(mode="json"),
            "bank_summaries": [b.model_dump(mode="json") for b in case["bank_summaries"]],
            "gst_summaries": [g.model_dump(mode="json") for g in case["gst_summaries"]],
            "site_visits": [s.model_dump(mode="json") for s in case["site_visits"]],
            "management_interviews": [m.model_dump(mode="json") for m in case["management_interviews"]],
        }

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, default=str)

        print(f"Generated: {filename} ({profile})")


if __name__ == "__main__":
    save_test_cases()
