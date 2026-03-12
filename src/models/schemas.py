"""
Core Pydantic schemas for the entire Titan-Credit pipeline.
Every module consumes & produces these typed objects.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime, date
import uuid


# ────────────────────────────────────────────
# Enums
# ────────────────────────────────────────────
class RiskGrade(str, Enum):
    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    B = "B"
    C = "C"
    D = "D"


class LoanDecision(str, Enum):
    APPROVED = "APPROVED"
    CONDITIONAL = "CONDITIONAL_APPROVAL"
    REJECTED = "REJECTED"
    REFERRED = "REFERRED_TO_COMMITTEE"


class FraudSeverity(str, Enum):
    CLEAN = "CLEAN"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class LitigationType(str, Enum):
    CIVIL = "CIVIL"
    CRIMINAL = "CRIMINAL"
    CHEQUE_BOUNCE_138 = "NI_ACT_138"
    TAX_DISPUTE = "TAX_DISPUTE"
    ENVIRONMENTAL = "ENVIRONMENTAL"
    LABOUR = "LABOUR"
    INSOLVENCY = "IBC"


class AgentRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    INGESTOR = "ingestor"
    FRAUD_ANALYST = "fraud_analyst"
    RESEARCHER = "researcher"
    UNDERWRITER = "underwriter"
    GUARDIAN = "guardian"
    BULL = "bull_agent"
    BEAR = "bear_agent"
    CRITIC = "critic"


# ────────────────────────────────────────────
# Company & Application
# ────────────────────────────────────────────
class CompanyProfile(BaseModel):
    cin: str = Field(..., description="Corporate Identification Number")
    name: str
    incorporation_date: Optional[date] = None
    registered_address: Optional[str] = None
    sector: Optional[str] = None
    sub_sector: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    promoters: list[PromoterInfo] = Field(default_factory=list)
    annual_turnover_cr: Optional[float] = None
    net_worth_cr: Optional[float] = None


class PromoterInfo(BaseModel):
    din: str = Field(..., description="Director Identification Number")
    name: str
    designation: Optional[str] = None
    shareholding_pct: Optional[float] = None
    other_directorships: list[str] = Field(default_factory=list)
    disqualified: bool = False
    cibil_score: Optional[int] = None


class LoanApplication(BaseModel):
    application_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    company: CompanyProfile
    requested_amount_cr: float
    loan_purpose: str
    loan_tenure_months: int = 60
    collateral_description: Optional[str] = None
    collateral_value_cr: Optional[float] = None
    submitted_at: datetime = Field(default_factory=datetime.utcnow)


# ────────────────────────────────────────────
# Document Ingestion
# ────────────────────────────────────────────
class ExtractedDocument(BaseModel):
    doc_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    source_file: str
    doc_type: str  # annual_report, bank_statement, gst_return, etc.
    extracted_text: str = ""
    tables: list[ExtractedTable] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    extraction_confidence: float = 0.0
    finmm_corrections: list[str] = Field(default_factory=list)


class ExtractedTable(BaseModel):
    table_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    page_number: int
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    table_type: str = ""  # balance_sheet, pnl, cash_flow, gst_summary
    confidence: float = 0.0


# ────────────────────────────────────────────
# Financial Metrics (parsed from statements)
# ────────────────────────────────────────────
class FinancialMetrics(BaseModel):
    fiscal_year: str
    revenue_cr: Optional[float] = None
    ebitda_cr: Optional[float] = None
    pat_cr: Optional[float] = None
    total_assets_cr: Optional[float] = None
    total_liabilities_cr: Optional[float] = None
    net_worth_cr: Optional[float] = None
    current_ratio: Optional[float] = None
    debt_equity_ratio: Optional[float] = None
    interest_coverage_ratio: Optional[float] = None
    dscr: Optional[float] = None  # Debt Service Coverage Ratio
    tol_tnw: Optional[float] = None  # Total Outside Liabilities / Tangible Net Worth
    working_capital_cr: Optional[float] = None
    cash_flow_from_operations_cr: Optional[float] = None


class BankStatementSummary(BaseModel):
    bank_name: str
    account_number: str
    period_from: date
    period_to: date
    avg_monthly_balance_cr: float = 0.0
    total_credits_cr: float = 0.0
    total_debits_cr: float = 0.0
    peak_utilization_pct: Optional[float] = None
    mandate_bounces: int = 0
    inward_return_count: int = 0
    top_counterparties: list[CounterpartyFlow] = Field(default_factory=list)


class CounterpartyFlow(BaseModel):
    name: str
    gstin: Optional[str] = None
    total_amount_cr: float
    transaction_count: int
    is_related_party: bool = False


class GSTSummary(BaseModel):
    gstin: str
    period: str  # e.g., "2024-25"
    gstr1_turnover_cr: float = 0.0
    gstr3b_turnover_cr: float = 0.0
    gstr2a_purchases_cr: float = 0.0
    gstr2b_purchases_cr: float = 0.0
    itc_claimed_cr: float = 0.0
    itc_eligible_cr: float = 0.0
    turnover_mismatch_pct: float = 0.0  # 1 vs 3B divergence
    top_suppliers: list[CounterpartyFlow] = Field(default_factory=list)
    top_buyers: list[CounterpartyFlow] = Field(default_factory=list)


# ────────────────────────────────────────────
# Fraud Detection
# ────────────────────────────────────────────
class FraudSignal(BaseModel):
    signal_type: str  # circular_trading, revenue_inflation, staged_deposits, etc.
    severity: FraudSeverity
    confidence: float = Field(ge=0.0, le=1.0)
    description: str
    evidence: list[str] = Field(default_factory=list)
    entities_involved: list[str] = Field(default_factory=list)
    gnn_node_embeddings: Optional[dict] = None


class FraudReport(BaseModel):
    overall_fraud_score: float = Field(ge=0.0, le=1.0)
    severity: FraudSeverity
    signals: list[FraudSignal] = Field(default_factory=list)
    circular_trading_detected: bool = False
    revenue_inflation_detected: bool = False
    gst_bank_mismatch_pct: float = 0.0
    related_party_concentration_pct: float = 0.0
    network_risk_entities: list[str] = Field(default_factory=list)


# ────────────────────────────────────────────
# Research & Litigation
# ────────────────────────────────────────────
class LitigationRecord(BaseModel):
    case_number: str
    court: str
    case_type: LitigationType
    parties: list[str] = Field(default_factory=list)
    filing_date: Optional[date] = None
    status: str = ""  # pending, disposed, decreed
    potential_liability_cr: Optional[float] = None
    severity_score: float = Field(ge=0.0, le=1.0, default=0.0)
    summary: str = ""


class NewsIntelligence(BaseModel):
    headline: str
    source: str
    published_date: Optional[date] = None
    sentiment: float = Field(ge=-1.0, le=1.0, default=0.0)
    relevance_score: float = Field(ge=0.0, le=1.0, default=0.0)
    summary: str = ""
    url: Optional[str] = None


class MCAFiling(BaseModel):
    form_type: str  # DIR-12, CHG-1, MGT-7, AOC-4, ADT-1
    filing_date: Optional[date] = None
    description: str = ""
    red_flag: bool = False
    red_flag_reason: Optional[str] = None


class DirectorInterlock(BaseModel):
    din: str
    name: str
    companies: list[str] = Field(default_factory=list)
    failed_companies: list[str] = Field(default_factory=list)
    risk_score: float = Field(ge=0.0, le=1.0, default=0.0)


class ResearchReport(BaseModel):
    litigation_score: float = Field(ge=0.0, le=1.0, default=0.0)
    litigation_records: list[LitigationRecord] = Field(default_factory=list)
    news_sentiment: float = Field(ge=-1.0, le=1.0, default=0.0)
    news_items: list[NewsIntelligence] = Field(default_factory=list)
    mca_filings: list[MCAFiling] = Field(default_factory=list)
    director_interlocks: list[DirectorInterlock] = Field(default_factory=list)
    regulatory_alerts: list[str] = Field(default_factory=list)
    sector_outlook: str = ""
    sector_outlook_score: float = Field(ge=-1.0, le=1.0, default=0.0)


# ────────────────────────────────────────────
# Primary Due Diligence
# ────────────────────────────────────────────
class SiteVisitObservation(BaseModel):
    observation_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    observer_name: str = ""
    visit_date: Optional[date] = None
    location: str = ""
    notes: str = ""
    capacity_utilization_pct: Optional[float] = None
    photos: list[str] = Field(default_factory=list)  # file paths
    quantified_scores: dict = Field(default_factory=dict)
    ai_assessment: str = ""


class ManagementInterview(BaseModel):
    interviewee: str
    designation: str = ""
    interview_date: Optional[date] = None
    key_points: list[str] = Field(default_factory=list)
    integrity_score: float = Field(ge=0.0, le=1.0, default=0.5)
    ai_assessment: str = ""


# ────────────────────────────────────────────
# Five Cs of Credit
# ────────────────────────────────────────────
class FiveCsAssessment(BaseModel):
    character_score: float = Field(ge=0.0, le=1.0, default=0.5)
    character_rationale: str = ""
    capacity_score: float = Field(ge=0.0, le=1.0, default=0.5)
    capacity_rationale: str = ""
    capital_score: float = Field(ge=0.0, le=1.0, default=0.5)
    capital_rationale: str = ""
    collateral_score: float = Field(ge=0.0, le=1.0, default=0.5)
    collateral_rationale: str = ""
    conditions_score: float = Field(ge=0.0, le=1.0, default=0.5)
    conditions_rationale: str = ""

    @property
    def composite_score(self) -> float:
        weights = {"character": 0.25, "capacity": 0.25, "capital": 0.20,
                   "collateral": 0.15, "conditions": 0.15}
        return (
            self.character_score * weights["character"]
            + self.capacity_score * weights["capacity"]
            + self.capital_score * weights["capital"]
            + self.collateral_score * weights["collateral"]
            + self.conditions_score * weights["conditions"]
        )


# ────────────────────────────────────────────
# Bull-Bear Debate
# ────────────────────────────────────────────
class DebateRound(BaseModel):
    round_number: int
    bull_argument: str
    bull_score: float
    bear_argument: str
    bear_score: float
    divergence: float


class DebateResult(BaseModel):
    rounds: list[DebateRound] = Field(default_factory=list)
    consensus_reached: bool = False
    final_risk_premium: float = 0.0
    bull_final_score: float = 0.0
    bear_final_score: float = 0.0
    recommendation: str = ""


# ────────────────────────────────────────────
# Credit Appraisal Memo (CAM)
# ────────────────────────────────────────────
class CreditDecision(BaseModel):
    decision: LoanDecision
    approved_amount_cr: Optional[float] = None
    interest_rate_pct: Optional[float] = None
    risk_premium_pct: float = 0.0
    risk_grade: RiskGrade = RiskGrade.BBB
    tenure_months: Optional[int] = None
    conditions: list[str] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)


class CAMReport(BaseModel):
    """The final Credit Appraisal Memo output."""
    cam_id: str = Field(default_factory=lambda: f"CAM-{str(uuid.uuid4())[:8].upper()}")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    application: LoanApplication
    financial_metrics: list[FinancialMetrics] = Field(default_factory=list)
    bank_summaries: list[BankStatementSummary] = Field(default_factory=list)
    gst_summaries: list[GSTSummary] = Field(default_factory=list)
    fraud_report: Optional[FraudReport] = None
    research_report: Optional[ResearchReport] = None
    site_visits: list[SiteVisitObservation] = Field(default_factory=list)
    management_interviews: list[ManagementInterview] = Field(default_factory=list)
    five_cs: Optional[FiveCsAssessment] = None
    debate_result: Optional[DebateResult] = None
    decision: Optional[CreditDecision] = None
    shap_explanation: Optional[dict] = None
    executive_summary: str = ""
    risk_narrative: str = ""
    audit_trail: list[AuditEntry] = Field(default_factory=list)


# ────────────────────────────────────────────
# Orchestrator State
# ────────────────────────────────────────────
class AgentMessage(BaseModel):
    agent: AgentRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)


class AuditEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent: AgentRole
    action: str
    input_summary: str = ""
    output_summary: str = ""
    reasoning_trace: str = ""
    guardian_approved: bool = True
    drift_score: float = 0.0


class PipelineState(BaseModel):
    """The global state flowing through the LangGraph orchestrator."""
    application: Optional[LoanApplication] = None
    documents: list[ExtractedDocument] = Field(default_factory=list)
    financial_metrics: list[FinancialMetrics] = Field(default_factory=list)
    bank_summaries: list[BankStatementSummary] = Field(default_factory=list)
    gst_summaries: list[GSTSummary] = Field(default_factory=list)
    fraud_report: Optional[FraudReport] = None
    research_report: Optional[ResearchReport] = None
    site_visits: list[SiteVisitObservation] = Field(default_factory=list)
    management_interviews: list[ManagementInterview] = Field(default_factory=list)
    five_cs: Optional[FiveCsAssessment] = None
    debate_result: Optional[DebateResult] = None
    decision: Optional[CreditDecision] = None
    cam_report: Optional[CAMReport] = None
    messages: list[AgentMessage] = Field(default_factory=list)
    audit_trail: list[AuditEntry] = Field(default_factory=list)
    current_phase: str = "initialized"
    iteration: int = 0
    errors: list[str] = Field(default_factory=list)


# Fix forward references
CompanyProfile.model_rebuild()
CAMReport.model_rebuild()
