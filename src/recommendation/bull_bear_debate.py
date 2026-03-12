"""
Bull-Bear Debate Engine — Mimics an investment committee.

A "Bull Agent" argues for approval and a "Bear Agent" argues for rejection.
They debate for up to N rounds until convergence (divergence < threshold)
produces a mathematical consensus on the risk premium.
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from src.models.schemas import (
    CreditDecision,
    DebateResult,
    DebateRound,
    FiveCsAssessment,
    FraudReport,
    ResearchReport,
)
from src.utils.llm_client import llm_client
from config.settings import settings


BULL_SYSTEM = """You are the BULL AGENT on a corporate credit committee. Your role is to
ADVOCATE FOR LOAN APPROVAL. Find every reason to support the borrower.
Highlight strengths in financials, strong promoter track record, collateral coverage,
positive market conditions. Acknowledge risks but argue they are manageable.
Be persuasive but grounded in data."""

BEAR_SYSTEM = """You are the BEAR AGENT on a corporate credit committee. Your role is to
CHALLENGE THE LOAN APPLICATION. Find every risk, weakness, and red flag.
Highlight fraud signals, litigation exposure, weak financials, sector headwinds,
governance concerns. Push for higher risk premium or rejection.
Be rigorous and skeptical."""


class BullBearDebate:
    """
    Runs a structured multi-round debate between Bull and Bear agents.
    Each round produces arguments + a numerical risk premium proposal.
    Convergence = |bull_premium - bear_premium| < threshold.
    """

    async def run(self, state: dict[str, Any]) -> DebateResult:
        app = state.get("application")
        five_cs: FiveCsAssessment | None = state.get("five_cs")
        fraud: FraudReport | None = state.get("fraud_report")
        research: ResearchReport | None = state.get("research_report")
        decision: CreditDecision | None = state.get("decision")

        logger.info("Bull-Bear Debate: Starting deliberation")

        # Build context summary for both agents
        context = self._build_context(app, five_cs, fraud, research, decision)

        rounds: list[DebateRound] = []
        max_rounds = settings.BULL_BEAR_ROUNDS
        bull_premium = decision.risk_premium_pct if decision else 2.0
        bear_premium = bull_premium + 2.0  # Bear starts pessimistic

        conversation_history = ""

        for round_num in range(1, max_rounds + 1):
            logger.info(f"Debate Round {round_num}/{max_rounds}")

            # Bull argues
            bull_prompt = f"""{context}

Previous debate:
{conversation_history or 'This is the opening round.'}

Current proposed risk premium: {bull_premium:.2f}%
Bear's last proposal: {bear_premium:.2f}%

As the BULL AGENT, make your argument for Round {round_num}.
Propose a specific risk premium (lower = more favorable to borrower).

Respond with JSON:
{{
    "argument": "Your 2-3 sentence argument",
    "proposed_premium": <float>,
    "confidence": <float 0-1>
}}"""

            bear_prompt = f"""{context}

Previous debate:
{conversation_history or 'This is the opening round.'}

Current proposed risk premium: {bear_premium:.2f}%
Bull's last proposal: {bull_premium:.2f}%

As the BEAR AGENT, make your argument for Round {round_num}.
Propose a specific risk premium (higher = more cautious).

Respond with JSON:
{{
    "argument": "Your 2-3 sentence argument",
    "proposed_premium": <float>,
    "confidence": <float 0-1>
}}"""

            try:
                bull_resp = await llm_client.generate_json(
                    bull_prompt, system_prompt=BULL_SYSTEM
                )
                bear_resp = await llm_client.generate_json(
                    bear_prompt, system_prompt=BEAR_SYSTEM
                )
            except Exception as e:
                logger.warning(f"Debate round {round_num} LLM failed: {e}")
                # Use deterministic fallback
                bull_resp = {
                    "argument": "Based on adequate financials, approval is warranted.",
                    "proposed_premium": bull_premium,
                    "confidence": 0.6,
                }
                bear_resp = {
                    "argument": "Risk factors necessitate a higher premium.",
                    "proposed_premium": bear_premium,
                    "confidence": 0.6,
                }

            bull_arg = str(bull_resp.get("argument", ""))
            bull_new = float(bull_resp.get("proposed_premium", bull_premium))
            bull_conf = float(bull_resp.get("confidence", 0.5))

            bear_arg = str(bear_resp.get("argument", ""))
            bear_new = float(bear_resp.get("proposed_premium", bear_premium))
            bear_conf = float(bear_resp.get("confidence", 0.5))

            # Clamp premiums to valid range
            bull_premium = max(
                settings.MIN_RISK_PREMIUM,
                min(settings.MAX_RISK_PREMIUM, bull_new)
            )
            bear_premium = max(
                settings.MIN_RISK_PREMIUM,
                min(settings.MAX_RISK_PREMIUM, bear_new)
            )

            divergence = abs(bull_premium - bear_premium)

            round_data = DebateRound(
                round_number=round_num,
                bull_argument=bull_arg,
                bull_score=round(bull_conf, 3),
                bear_argument=bear_arg,
                bear_score=round(bear_conf, 3),
                divergence=round(divergence, 3),
            )
            rounds.append(round_data)

            conversation_history += (
                f"\nRound {round_num}:\n"
                f"BULL ({bull_premium:.2f}%): {bull_arg}\n"
                f"BEAR ({bear_premium:.2f}%): {bear_arg}\n"
            )

            logger.info(
                f"Round {round_num}: Bull={bull_premium:.2f}%, "
                f"Bear={bear_premium:.2f}%, Divergence={divergence:.3f}"
            )

            # Check convergence
            if divergence <= settings.CONSENSUS_THRESHOLD:
                logger.info(f"Consensus reached at round {round_num}!")
                break

            # Both adjust toward each other for next round (anchoring)
            if round_num < max_rounds:
                move = divergence * 0.2
                bull_premium = min(bull_premium + move, bear_premium)
                bear_premium = max(bear_premium - move, bull_premium)

        # Final consensus premium: weighted by confidence scores
        final_divergence = abs(bull_premium - bear_premium)
        consensus = final_divergence <= settings.CONSENSUS_THRESHOLD

        total_conf = bull_conf + bear_conf
        if total_conf > 0:
            final_premium = (
                bull_premium * bull_conf + bear_premium * bear_conf
            ) / total_conf
        else:
            final_premium = (bull_premium + bear_premium) / 2

        final_premium = max(
            settings.MIN_RISK_PREMIUM,
            min(settings.MAX_RISK_PREMIUM, final_premium)
        )

        # Recommendation narrative
        if consensus:
            recommendation = (
                f"Committee consensus reached: {final_premium:.2f}% risk premium "
                f"after {len(rounds)} rounds of deliberation."
            )
        else:
            recommendation = (
                f"No full consensus after {len(rounds)} rounds. "
                f"Midpoint premium: {final_premium:.2f}%. "
                f"Refer to senior credit committee for final decision."
            )

        result = DebateResult(
            rounds=rounds,
            consensus_reached=consensus,
            final_risk_premium=round(final_premium, 2),
            bull_final_score=round(bull_conf, 3),
            bear_final_score=round(bear_conf, 3),
            recommendation=recommendation,
        )

        logger.info(f"Debate Complete: {recommendation}")
        return result

    def _build_context(self, app, five_cs, fraud, research, decision) -> str:
        """Build a summary context string for both agents."""
        parts = ["=== Credit Application Summary ==="]

        if app:
            parts.append(
                f"Company: {app.company.name} ({app.company.cin})\n"
                f"Sector: {app.company.sector or 'N/A'}\n"
                f"Requested: ₹{app.requested_amount_cr} Cr, "
                f"Tenure: {app.loan_tenure_months} months\n"
                f"Collateral: ₹{app.collateral_value_cr or 'N/A'} Cr"
            )

        if five_cs:
            parts.append(
                f"\n--- Five Cs of Credit ---\n"
                f"Character: {five_cs.character_score:.2f} — {five_cs.character_rationale}\n"
                f"Capacity: {five_cs.capacity_score:.2f} — {five_cs.capacity_rationale}\n"
                f"Capital: {five_cs.capital_score:.2f} — {five_cs.capital_rationale}\n"
                f"Collateral: {five_cs.collateral_score:.2f} — {five_cs.collateral_rationale}\n"
                f"Conditions: {five_cs.conditions_score:.2f} — {five_cs.conditions_rationale}\n"
                f"Composite: {five_cs.composite_score:.3f}"
            )

        if fraud:
            parts.append(
                f"\n--- Fraud Analysis ---\n"
                f"Score: {fraud.overall_fraud_score:.2f} ({fraud.severity.value})\n"
                f"Circular Trading: {fraud.circular_trading_detected}\n"
                f"Revenue Inflation: {fraud.revenue_inflation_detected}\n"
                f"GST-Bank Mismatch: {fraud.gst_bank_mismatch_pct:.1f}%"
            )

        if research:
            parts.append(
                f"\n--- Research Intelligence ---\n"
                f"Litigation: {research.litigation_score:.2f} "
                f"({len(research.litigation_records)} cases)\n"
                f"News Sentiment: {research.news_sentiment:.2f}\n"
                f"Sector Outlook: {research.sector_outlook_score:.2f}\n"
                f"Director Interlocks: {len(research.director_interlocks)}\n"
                f"Regulatory Alerts: {len(research.regulatory_alerts)}"
            )

        if decision:
            parts.append(
                f"\n--- Initial Assessment ---\n"
                f"Preliminary Decision: {decision.decision.value}\n"
                f"Risk Grade: {decision.risk_grade.value}\n"
                f"Initial Premium: {decision.risk_premium_pct:.2f}%"
            )

        return "\n".join(parts)
