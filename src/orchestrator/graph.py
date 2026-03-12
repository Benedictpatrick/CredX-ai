"""
Titan-Credit Orchestrator — Hierarchical Swarm with Reflexion.

This is the CEO Agent that decomposes the loan application into
parallel sub-tasks, dispatches them to departmental agents, and
runs the Plan-Act-Reflect-Repeat loop until the Critic approves.

Architecture:
    ┌────────────────────────────────────────────────────┐
    │                   ORCHESTRATOR                      │
    │                  (CEO Agent)                        │
    ├────────────────────────────────────────────────────┤
    │  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
    │  │ Ingestor │  │  Fraud   │  │ Research │  (parallel)
    │  │ (Vision) │  │ (GNN)    │  │ (Scholar)│        │
    │  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
    │       └──────────────┼──────────────┘              │
    │                      ▼                              │
    │            ┌─────────────────┐                      │
    │            │   Underwriter   │                      │
    │            │ (Five Cs + XAI) │                      │
    │            └────────┬────────┘                      │
    │                     ▼                               │
    │            ┌─────────────────┐                      │
    │            │  Bull-Bear      │                      │
    │            │  Debate Loop    │                      │
    │            └────────┬────────┘                      │
    │                     ▼                               │
    │            ┌─────────────────┐                      │
    │            │   Reflexion     │◄──── Critic Agent    │
    │            │   (Approve?)    │                      │
    │            └────────┬────────┘                      │
    │                     │                               │
    │              ┌──────┴──────┐                        │
    │              ▼             ▼                        │
    │         [Approved]   [Revise] → Loop back           │
    │              │                                      │
    │              ▼                                      │
    │         CAM Generator                               │
    │         + Guardian Audit                             │
    └────────────────────────────────────────────────────┘
"""
from __future__ import annotations

from langgraph.graph import StateGraph, START, END  # type: ignore[reportMissingImports]
from loguru import logger

from src.orchestrator.state import OrchestratorState
from src.orchestrator.reflexion import run_reflexion
from src.models.schemas import AgentMessage, AuditEntry, AgentRole, FinancialMetrics


# ──────────────────────────────────────────────
# Node Functions (each wraps a module)
# ──────────────────────────────────────────────

async def initialize_node(state: OrchestratorState) -> dict:
    """Set up initial state and validate inputs."""
    logger.info("═══ TITAN-CREDIT PIPELINE START ═══")
    app = state.get("application")
    if not app:
        return {
            "errors": ["No loan application provided"],
            "current_phase": "error",
        }
    logger.info(f"Processing: {app.company.name} (CIN: {app.company.cin})")
    logger.info(f"Requested: ₹{app.requested_amount_cr} Cr for {app.loan_purpose}")
    return {
        "current_phase": "ingestion",
        "iteration": 0,
        "reflexion_needed": False,
        "messages": [AgentMessage(
            agent=AgentRole.ORCHESTRATOR,
            content=f"Started processing application for {app.company.name}",
        )],
    }


def _synthesize_financial_metrics(state: OrchestratorState) -> list[FinancialMetrics]:
    """Create a conservative financial snapshot when structured statements are absent."""
    app = state.get("application")
    if not app:
        return []

    bank_summaries = state.get("bank_summaries", [])
    gst_summaries = state.get("gst_summaries", [])
    existing_metrics = state.get("financial_metrics", [])
    if existing_metrics:
        return existing_metrics

    revenue_candidates = [
        value for value in [
            app.company.annual_turnover_cr,
            sum(item.gstr3b_turnover_cr for item in gst_summaries) or None,
            sum(item.total_credits_cr for item in bank_summaries) or None,
        ] if value
    ]
    if not revenue_candidates:
        return []

    revenue_cr = sum(revenue_candidates) / len(revenue_candidates)
    net_worth_cr = app.company.net_worth_cr or max(revenue_cr * 0.28, app.requested_amount_cr * 0.6)
    total_bank_inflows = sum(item.total_credits_cr for item in bank_summaries)
    total_bounces = sum(item.mandate_bounces for item in bank_summaries)
    avg_turnover_mismatch = (
        sum(item.turnover_mismatch_pct for item in gst_summaries) / len(gst_summaries)
        if gst_summaries else 0.0
    )

    margin_penalty = min(avg_turnover_mismatch / 100, 0.08) + min(total_bounces * 0.01, 0.08)
    ebitda_margin = max(0.07, 0.18 - margin_penalty)
    ebitda_cr = revenue_cr * ebitda_margin
    pat_cr = ebitda_cr * 0.56
    total_assets_cr = max(net_worth_cr * 2.1, revenue_cr * 0.7, app.requested_amount_cr * 1.4)
    total_liabilities_cr = max(total_assets_cr - net_worth_cr, app.requested_amount_cr * 0.5)
    debt_equity_ratio = total_liabilities_cr / max(net_worth_cr, 0.01)
    interest_cover = ebitda_cr / max(app.requested_amount_cr * 0.12, 0.25)
    dscr = (ebitda_cr * 0.8) / max(app.requested_amount_cr * 0.18, 0.3)
    current_ratio = max(0.9, min(2.2, 1.45 - min(total_bounces * 0.03, 0.35)))
    tol_tnw = total_liabilities_cr / max(net_worth_cr, 0.01)
    working_capital_cr = revenue_cr * 0.18
    cfo_cr = max(pat_cr * 0.9, 0.1)

    if total_bank_inflows:
        revenue_cr = (revenue_cr + total_bank_inflows) / 2

    return [FinancialMetrics(
        fiscal_year="2024-25 (synthesized)",
        revenue_cr=round(revenue_cr, 2),
        ebitda_cr=round(ebitda_cr, 2),
        pat_cr=round(pat_cr, 2),
        total_assets_cr=round(total_assets_cr, 2),
        total_liabilities_cr=round(total_liabilities_cr, 2),
        net_worth_cr=round(net_worth_cr, 2),
        current_ratio=round(current_ratio, 2),
        debt_equity_ratio=round(debt_equity_ratio, 2),
        interest_coverage_ratio=round(interest_cover, 2),
        dscr=round(dscr, 2),
        tol_tnw=round(tol_tnw, 2),
        working_capital_cr=round(working_capital_cr, 2),
        cash_flow_from_operations_cr=round(cfo_cr, 2),
    )]


async def ingest_documents_node(state: OrchestratorState) -> dict:
    """Module 1: Vision-Native Document Ingestion."""
    logger.info("── Module 1: Vision-Native Ingestor ──")
    from src.ingestor.vision_parser import VisionParser
    from src.ingestor.bank_statement import BankStatementParser
    from src.ingestor.gst_parser import GSTParser

    parser = VisionParser()
    bank_parser = BankStatementParser()
    gst_parser = GSTParser()

    documents = list(state.get("documents", []))
    financial_metrics = list(state.get("financial_metrics", []))
    bank_summaries = list(state.get("bank_summaries", []))
    gst_summaries = list(state.get("gst_summaries", []))

    uploaded = state.get("uploaded_files", [])
    for file_path in uploaded:
        try:
            doc = await parser.parse(file_path)
            documents.append(doc)

            if doc.doc_type == "bank_statement":
                summary = await bank_parser.parse(doc)
                bank_summaries.append(summary)
            elif doc.doc_type == "gst_return":
                gst = await gst_parser.parse(doc)
                gst_summaries.append(gst)
            elif doc.doc_type in ("annual_report", "financial_statement"):
                metrics = await parser.extract_financials(doc)
                if metrics:
                    financial_metrics.extend(metrics)
        except Exception as e:
            logger.error(f"Ingestion failed for {file_path}: {e}")

    if not financial_metrics:
        financial_metrics = _synthesize_financial_metrics({
            **state,
            "bank_summaries": bank_summaries,
            "gst_summaries": gst_summaries,
            "financial_metrics": financial_metrics,
        })

    return {
        "documents": documents,
        "financial_metrics": financial_metrics,
        "bank_summaries": bank_summaries,
        "gst_summaries": gst_summaries,
        "current_phase": "analysis",
        "messages": [AgentMessage(
            agent=AgentRole.INGESTOR,
            content=(
                f"Prepared {len(documents)} documents, {len(financial_metrics)} financial records, "
                f"{len(bank_summaries)} bank summaries, {len(gst_summaries)} GST summaries"
            ),
        )],
        "audit_trail": [AuditEntry(
            agent=AgentRole.INGESTOR,
            action="document_ingestion",
            output_summary=(
                f"{len(documents)} docs, {len(financial_metrics)} financial snapshots, "
                f"{len(bank_summaries)} bank stmts, {len(gst_summaries)} GST"
            ),
        )],
    }


async def fraud_analysis_node(state: OrchestratorState) -> dict:
    """Module 2: Sherlock Fraud Engine (Temporal GNN)."""
    logger.info("── Module 2: Sherlock Fraud Engine ──")
    from src.fraud_engine.fraud_scorer import FraudScorer

    scorer = FraudScorer()
    fraud_report = await scorer.analyze(
        application=state.get("application"),
        bank_summaries=state.get("bank_summaries", []),
        gst_summaries=state.get("gst_summaries", []),
    )

    return {
        "fraud_report": fraud_report,
        "messages": [AgentMessage(
            agent=AgentRole.FRAUD_ANALYST,
            content=f"Fraud score: {fraud_report.overall_fraud_score:.2f} ({fraud_report.severity.value})",
        )],
        "audit_trail": [AuditEntry(
            agent=AgentRole.FRAUD_ANALYST,
            action="fraud_analysis",
            output_summary=f"Score={fraud_report.overall_fraud_score:.2f}, Circular={fraud_report.circular_trading_detected}",
        )],
    }


async def research_analysis_node(state: OrchestratorState) -> dict:
    """Module 3: Scholar Research Agent."""
    logger.info("── Module 3: Scholar Research Agent ──")
    from src.research_agent.research_orchestrator import ResearchOrchestrator

    researcher = ResearchOrchestrator()
    research_report = await researcher.investigate(
        application=state.get("application"),
    )

    return {
        "research_report": research_report,
        "messages": [AgentMessage(
            agent=AgentRole.RESEARCHER,
            content=(
                f"Research complete: Litigation={research_report.litigation_score:.2f}, "
                f"Sentiment={research_report.news_sentiment:.2f}, "
                f"Interlocks={len(research_report.director_interlocks)}"
            ),
        )],
        "audit_trail": [AuditEntry(
            agent=AgentRole.RESEARCHER,
            action="secondary_research",
            output_summary=f"Litigation={research_report.litigation_score:.2f}, Cases={len(research_report.litigation_records)}",
        )],
    }


async def underwriter_node(state: OrchestratorState) -> dict:
    """Module 4: Underwriter — Five Cs + Risk Scoring + XAI."""
    logger.info("── Module 4: Underwriter Engine ──")
    from src.recommendation.five_cs_analyzer import FiveCsAnalyzer
    from src.recommendation.risk_scorer import RiskScorer
    from src.recommendation.xai_engine import XAIEngine

    # Five Cs evaluation
    analyzer = FiveCsAnalyzer()
    state_payload = dict(state)
    five_cs = await analyzer.evaluate(state_payload)

    # Risk scoring with XAI
    risk_scorer = RiskScorer()
    decision, shap_data = await risk_scorer.score(state_payload, five_cs)
    xai_engine = XAIEngine()
    xai_payload = await xai_engine.explain(decision, shap_data, state_payload)
    xai_payload.update(shap_data)

    return {
        "five_cs": five_cs,
        "decision": decision,
        "shap_explanation": xai_payload,
        "current_phase": "debate",
        "messages": [AgentMessage(
            agent=AgentRole.UNDERWRITER,
            content=f"Five Cs Composite: {five_cs.composite_score:.2f}, Decision: {decision.decision.value}",
        )],
        "audit_trail": [AuditEntry(
            agent=AgentRole.UNDERWRITER,
            action="underwriting",
            output_summary=(
                f"5Cs={five_cs.composite_score:.2f}, Grade={decision.risk_grade.value}, "
                f"Decision={decision.decision.value}"
            ),
        )],
    }


async def bull_bear_debate_node(state: OrchestratorState) -> dict:
    """Bull-Bear consensus debate on the risk premium."""
    logger.info("── Bull-Bear Debate ──")
    from src.recommendation.bull_bear_debate import BullBearDebate

    debate = BullBearDebate()
    result = await debate.run(dict(state))

    # Update decision with debated risk premium
    decision = state.get("decision")
    if decision and result.consensus_reached:
        decision.risk_premium_pct = result.final_risk_premium
        from config.settings import settings
        decision.interest_rate_pct = settings.BASE_LENDING_RATE + result.final_risk_premium

    return {
        "debate_result": result,
        "decision": decision,
        "current_phase": "reflexion",
        "messages": [AgentMessage(
            agent=AgentRole.ORCHESTRATOR,
            content=f"Debate: {'Consensus' if result.consensus_reached else 'No consensus'} at {result.final_risk_premium:.2f}% premium",
        )],
    }


async def reflexion_node(state: OrchestratorState) -> dict:
    """Critic reviews the entire analysis and decides if revision is needed."""
    logger.info("── Reflexion: Critic Review ──")
    return await run_reflexion(dict(state))


async def generate_cam_node(state: OrchestratorState) -> dict:
    """Generate the final Credit Appraisal Memo."""
    logger.info("── CAM Generation ──")
    from src.recommendation.cam_generator import CAMGenerator

    generator = CAMGenerator()
    cam = await generator.generate(dict(state))

    return {
        "cam_report": cam,
        "current_phase": "complete",
        "messages": [AgentMessage(
            agent=AgentRole.ORCHESTRATOR,
            content=f"CAM generated: {cam.cam_id}",
        )],
        "audit_trail": [AuditEntry(
            agent=AgentRole.ORCHESTRATOR,
            action="cam_generation",
            output_summary=f"CAM {cam.cam_id} generated successfully",
        )],
    }


async def guardian_audit_node(state: OrchestratorState) -> dict:
    """Module 5: Guardian agent performs trace-level safety audit."""
    logger.info("── Guardian Safety Audit ──")
    from src.safety.guardian_agent import GuardianAgent

    guardian = GuardianAgent()
    audit_result = await guardian.audit_trace(dict(state))

    return {
        "messages": [AgentMessage(
            agent=AgentRole.GUARDIAN,
            content=f"Guardian: {audit_result}",
        )],
        "audit_trail": [AuditEntry(
            agent=AgentRole.GUARDIAN,
            action="safety_audit",
            output_summary=audit_result,
        )],
    }


# ──────────────────────────────────────────────
# Routing Logic
# ──────────────────────────────────────────────

def should_revise(state: OrchestratorState) -> str:
    """Route: after reflexion, either revise or finalize."""
    if state.get("reflexion_needed", False):
        logger.info("Reflexion: Revision required, looping back to analysis.")
        return "revise"
    return "finalize"


# ──────────────────────────────────────────────
# Build the Graph
# ──────────────────────────────────────────────

def build_orchestrator_graph() -> StateGraph:
    """Construct the hierarchical LangGraph swarm."""

    graph = StateGraph(OrchestratorState)

    # Add nodes
    graph.add_node("initialize", initialize_node)
    graph.add_node("ingest_documents", ingest_documents_node)
    graph.add_node("fraud_analysis", fraud_analysis_node)
    graph.add_node("research_analysis", research_analysis_node)
    graph.add_node("underwriter", underwriter_node)
    graph.add_node("bull_bear_debate", bull_bear_debate_node)
    graph.add_node("reflexion", reflexion_node)
    graph.add_node("generate_cam", generate_cam_node)
    graph.add_node("guardian_audit", guardian_audit_node)

    # Edges: START → Initialize → Ingest
    graph.add_edge(START, "initialize")
    graph.add_edge("initialize", "ingest_documents")

    # Parallel fan-out: Ingest → [Fraud, Research] (run concurrently)
    graph.add_edge("ingest_documents", "fraud_analysis")
    graph.add_edge("ingest_documents", "research_analysis")

    # Fan-in: [Fraud, Research] → Underwriter
    graph.add_edge("fraud_analysis", "underwriter")
    graph.add_edge("research_analysis", "underwriter")

    # Underwriter → Bull-Bear Debate → Reflexion
    graph.add_edge("underwriter", "bull_bear_debate")
    graph.add_edge("bull_bear_debate", "reflexion")

    # Conditional: Reflexion → Revise (loop) or Finalize
    graph.add_conditional_edges(
        "reflexion",
        should_revise,
        {
            "revise": "fraud_analysis",  # Loop back for re-analysis
            "finalize": "generate_cam",
        },
    )

    # CAM → Guardian Audit → END
    graph.add_edge("generate_cam", "guardian_audit")
    graph.add_edge("guardian_audit", END)

    return graph


def get_compiled_graph():
    """Return a compiled, runnable graph."""
    graph = build_orchestrator_graph()
    return graph.compile()
