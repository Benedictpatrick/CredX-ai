"""
Orchestrator shared state — the typed dictionary that flows through
every node in the LangGraph.
"""
from __future__ import annotations

from typing import TypedDict, Optional, Annotated
from operator import add

from src.models.schemas import (
    LoanApplication,
    ExtractedDocument,
    FinancialMetrics,
    BankStatementSummary,
    GSTSummary,
    FraudReport,
    ResearchReport,
    SiteVisitObservation,
    ManagementInterview,
    FiveCsAssessment,
    DebateResult,
    CreditDecision,
    CAMReport,
    AgentMessage,
    AuditEntry,
)


class OrchestratorState(TypedDict, total=False):
    """
    Global state passed through the LangGraph hierarchical swarm.
    Uses Annotated[list, add] for append-only message accumulation.
    """
    # ── Input ────────────────────────────────────
    application: Optional[LoanApplication]
    uploaded_files: list[str]  # file paths

    # ── Module 1: Ingestion outputs ──────────────
    documents: Annotated[list[ExtractedDocument], add]
    financial_metrics: Annotated[list[FinancialMetrics], add]
    bank_summaries: Annotated[list[BankStatementSummary], add]
    gst_summaries: Annotated[list[GSTSummary], add]

    # ── Module 2: Fraud outputs ──────────────────
    fraud_report: Optional[FraudReport]

    # ── Module 3: Research outputs ───────────────
    research_report: Optional[ResearchReport]

    # ── Module 4: Primary insights ───────────────
    site_visits: Annotated[list[SiteVisitObservation], add]
    management_interviews: Annotated[list[ManagementInterview], add]

    # ── Module 5: Recommendation outputs ─────────
    five_cs: Optional[FiveCsAssessment]
    debate_result: Optional[DebateResult]
    decision: Optional[CreditDecision]
    cam_report: Optional[CAMReport]
    shap_explanation: Optional[dict]

    # ── Control flow ─────────────────────────────
    current_phase: str
    iteration: int
    reflexion_needed: bool
    reflexion_feedback: str
    errors: Annotated[list[str], add]

    # ── Observability ────────────────────────────
    messages: Annotated[list[AgentMessage], add]
    audit_trail: Annotated[list[AuditEntry], add]
