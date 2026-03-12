"""
Reflexion engine — Plan-Act-Reflect-Repeat loop.

After each pipeline run, the Critic agent reviews the draft CAM
and either approves or requests re-analysis with specific feedback.
"""
from __future__ import annotations

from loguru import logger

from src.utils.llm_client import llm_client
from src.models.schemas import AgentMessage, AuditEntry, AgentRole


CRITIC_SYSTEM_PROMPT = """You are a Senior Credit Risk Reviewer at a top-tier Indian bank.
You are reviewing a draft Credit Appraisal Memo (CAM) produced by an AI system.

Your job is to CHALLENGE the reasoning. Look for:
1. Gaps in data: Are there missing financial years? Unexplained jumps in revenue?
2. Inconsistencies: Does the fraud analysis contradict the financial analysis?
3. Missing research: Were litigation records checked? Were promoter interlocks analyzed?
4. Logical leaps: Does the risk grade match the evidence?
5. Indian-context errors: GSTR-2A vs 3B reconciliation done? CIBIL checked?

If you find issues, respond with JSON:
{
    "approved": false,
    "issues": ["issue1", "issue2"],
    "recheck_modules": ["fraud_engine", "research_agent"],
    "feedback": "Detailed feedback on what to fix"
}

If the analysis is solid, respond with:
{
    "approved": true,
    "issues": [],
    "recheck_modules": [],
    "feedback": "Analysis is comprehensive and well-supported."
}"""


async def run_reflexion(state: dict) -> dict:
    """
    Evaluate the current pipeline state and decide whether
    another iteration is needed.
    """
    iteration = state.get("iteration", 0)
    max_iterations = 3  # Cap reflexion loops

    if iteration >= max_iterations:
        logger.info(f"Reflexion: Max iterations ({max_iterations}) reached, finalizing.")
        return {
            "reflexion_needed": False,
            "reflexion_feedback": "",
            "messages": [AgentMessage(
                agent=AgentRole.CRITIC,
                content=f"Max reflexion iterations ({max_iterations}) reached. Proceeding with current analysis.",
            )],
        }

    # Build a summary of current state for the critic
    summary_parts = []

    app = state.get("application")
    if app:
        summary_parts.append(
            f"Company: {app.company.name} (CIN: {app.company.cin})\n"
            f"Requested: ₹{app.requested_amount_cr} Cr for {app.loan_purpose}"
        )

    fraud = state.get("fraud_report")
    if fraud:
        summary_parts.append(
            f"Fraud Score: {fraud.overall_fraud_score:.2f} ({fraud.severity.value})\n"
            f"Circular Trading: {fraud.circular_trading_detected}\n"
            f"GST-Bank Mismatch: {fraud.gst_bank_mismatch_pct:.1f}%"
        )

    research = state.get("research_report")
    if research:
        summary_parts.append(
            f"Litigation Score: {research.litigation_score:.2f}\n"
            f"Cases Found: {len(research.litigation_records)}\n"
            f"News Sentiment: {research.news_sentiment:.2f}\n"
            f"Director Interlocks: {len(research.director_interlocks)}"
        )

    five_cs = state.get("five_cs")
    if five_cs:
        summary_parts.append(
            f"Five Cs Composite: {five_cs.composite_score:.2f}\n"
            f"Character: {five_cs.character_score:.2f} | "
            f"Capacity: {five_cs.capacity_score:.2f} | "
            f"Capital: {five_cs.capital_score:.2f} | "
            f"Collateral: {five_cs.collateral_score:.2f} | "
            f"Conditions: {five_cs.conditions_score:.2f}"
        )

    decision = state.get("decision")
    if decision:
        summary_parts.append(
            f"Decision: {decision.decision.value}\n"
            f"Risk Grade: {decision.risk_grade.value}\n"
            f"Approved Amount: ₹{decision.approved_amount_cr} Cr\n"
            f"Interest Rate: {decision.interest_rate_pct}%"
        )

    metrics = state.get("financial_metrics", [])
    if metrics:
        latest = metrics[-1]
        summary_parts.append(
            f"Latest Financials ({latest.fiscal_year}):\n"
            f"Revenue: ₹{latest.revenue_cr} Cr | EBITDA: ₹{latest.ebitda_cr} Cr\n"
            f"D/E: {latest.debt_equity_ratio} | ICR: {latest.interest_coverage_ratio}\n"
            f"DSCR: {latest.dscr} | Current Ratio: {latest.current_ratio}"
        )

    if not summary_parts:
        return {
            "reflexion_needed": False,
            "reflexion_feedback": "No analysis to review yet.",
            "messages": [],
        }

    prompt = (
        f"Review this Credit Appraisal (Iteration {iteration + 1}):\n\n"
        + "\n\n---\n\n".join(summary_parts)
    )

    try:
        result = await llm_client.generate_json(
            prompt=prompt,
            system_prompt=CRITIC_SYSTEM_PROMPT,
        )

        approved = result.get("approved", False)
        issues = result.get("issues", [])
        feedback = result.get("feedback", "")
        recheck = result.get("recheck_modules", [])

        logger.info(
            f"Reflexion (iter {iteration + 1}): "
            f"{'APPROVED' if approved else 'NEEDS REVISION'} — "
            f"{len(issues)} issues found"
        )

        return {
            "reflexion_needed": not approved,
            "reflexion_feedback": feedback,
            "iteration": iteration + 1,
            "messages": [AgentMessage(
                agent=AgentRole.CRITIC,
                content=f"{'APPROVED' if approved else 'REVISION NEEDED'}: {feedback}",
                metadata={"issues": issues, "recheck_modules": recheck},
            )],
            "audit_trail": [AuditEntry(
                agent=AgentRole.CRITIC,
                action="reflexion_review",
                input_summary=f"Iteration {iteration + 1} review",
                output_summary=f"{'Approved' if approved else f'Revision needed: {len(issues)} issues'}",
                reasoning_trace=feedback,
            )],
        }
    except Exception as e:
        logger.error(f"Reflexion failed: {e}")
        issues = []
        fraud = state.get("fraud_report")
        decision = state.get("decision")
        research = state.get("research_report")
        five_cs = state.get("five_cs")

        if fraud and fraud.overall_fraud_score > 0.8 and decision and decision.decision.value != "REJECTED":
            issues.append("Fraud severity suggests stronger adverse action than current recommendation.")
        if research and research.litigation_score > 0.75:
            issues.append("High litigation exposure requires explicit committee commentary.")
        if five_cs and five_cs.composite_score < 0.4 and decision and decision.decision.value == "APPROVED":
            issues.append("Score-to-decision alignment check failed for low composite score.")

        approved = not issues
        feedback = (
            "Deterministic critic fallback approved the analysis because core score, risk, and decision signals are aligned."
            if approved else
            "Deterministic critic fallback flagged the analysis for revision: " + "; ".join(issues)
        )
        return {
            "reflexion_needed": not approved,
            "reflexion_feedback": feedback,
            "iteration": iteration + 1,
            "messages": [AgentMessage(
                agent=AgentRole.CRITIC,
                content=("APPROVED" if approved else "REVISION NEEDED") + f": {feedback}",
                metadata={"fallback": True, "issues": issues},
            )],
            "audit_trail": [AuditEntry(
                agent=AgentRole.CRITIC,
                action="reflexion_fallback_review",
                input_summary=f"Iteration {iteration + 1} deterministic fallback",
                output_summary="Approved" if approved else f"Revision needed: {len(issues)} issues",
                reasoning_trace=feedback,
            )],
        }
