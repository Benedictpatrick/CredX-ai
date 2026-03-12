"""
Risk Scorer — Ensemble scoring model with XAI integration.

Uses a weighted feature-based scoring model (XGBoost-inspired heuristic)
to produce a CreditDecision with risk grade, loan amount, and interest rate.
Exposes feature importance for SHAP-style explainability.
"""
from __future__ import annotations

from typing import Any

import numpy as np
from loguru import logger

from src.models.schemas import (
    CreditDecision,
    FiveCsAssessment,
    FraudReport,
    FraudSeverity,
    LoanDecision,
    ResearchReport,
    RiskGrade,
)
from config.settings import settings


# Feature weights (emulate a trained gradient boosting model)
FEATURE_WEIGHTS = {
    "character_score": 0.18,
    "capacity_score": 0.20,
    "capital_score": 0.15,
    "collateral_score": 0.12,
    "conditions_score": 0.10,
    "primary_diligence_score": 0.10,
    "fraud_score_inv": 0.12,        # inverted: lower fraud = better
    "litigation_score_inv": 0.06,    # inverted
    "news_sentiment_norm": 0.04,
    "sector_outlook_norm": 0.03,
}


class RiskScorer:
    """
    Produces a CreditDecision from Five Cs + fraud + research data.
    Returns (CreditDecision, shap_dict) for XAI explainability.
    """

    async def score(
        self, state: dict[str, Any], five_cs: FiveCsAssessment
    ) -> tuple[CreditDecision, dict]:
        app = state.get("application")
        fraud: FraudReport | None = state.get("fraud_report")
        research: ResearchReport | None = state.get("research_report")
        primary_diligence_score = self._compute_primary_diligence_score(state)

        logger.info("RiskScorer: Computing credit decision with XAI features")

        # --- Build feature vector ---
        features = {
            "character_score": five_cs.character_score,
            "capacity_score": five_cs.capacity_score,
            "capital_score": five_cs.capital_score,
            "collateral_score": five_cs.collateral_score,
            "conditions_score": five_cs.conditions_score,
            "primary_diligence_score": primary_diligence_score,
            "fraud_score_inv": 1.0 - (fraud.overall_fraud_score if fraud else 0.0),
            "litigation_score_inv": 1.0 - (research.litigation_score if research else 0.0),
            "news_sentiment_norm": (
                (research.news_sentiment + 1.0) / 2.0 if research else 0.5
            ),
            "sector_outlook_norm": (
                (research.sector_outlook_score + 1.0) / 2.0 if research else 0.5
            ),
        }

        # --- Weighted aggregate score ---
        total_weight = sum(FEATURE_WEIGHTS.values())
        composite = sum(
            features[k] * FEATURE_WEIGHTS[k] for k in FEATURE_WEIGHTS
        ) / total_weight

        # --- SHAP-like feature contributions ---
        baseline = 0.5  # expected value (neutral)
        shap_values = {}
        for k, w in FEATURE_WEIGHTS.items():
            contribution = (features[k] - baseline) * w / total_weight
            shap_values[k] = round(contribution, 4)

        shap_data = {
            "feature_values": {k: round(v, 4) for k, v in features.items()},
            "shap_values": shap_values,
            "baseline": baseline,
            "composite_score": round(composite, 4),
            "top_positive": sorted(
                [(k, v) for k, v in shap_values.items() if v > 0],
                key=lambda x: x[1], reverse=True
            )[:5],
            "top_negative": sorted(
                [(k, v) for k, v in shap_values.items() if v < 0],
                key=lambda x: x[1]
            )[:5],
        }

        # --- Hard rejection rules (circuit breakers) ---
        rejection_reasons = []
        if fraud and fraud.severity == FraudSeverity.CRITICAL:
            rejection_reasons.append(
                f"CRITICAL fraud severity (score: {fraud.overall_fraud_score:.2f})"
            )
        if fraud and fraud.circular_trading_detected:
            rejection_reasons.append("Circular trading detected in transaction graph")
        if five_cs.character_score < 0.2:
            rejection_reasons.append(
                f"Character score critically low: {five_cs.character_score:.2f}"
            )
        if research and research.litigation_score > 0.85:
            rejection_reasons.append(
                f"Extreme litigation risk: {research.litigation_score:.2f}"
            )

        # --- Decision logic ---
        if rejection_reasons:
            decision = LoanDecision.REJECTED
            risk_grade = RiskGrade.D
            approved_amount = None
            risk_premium = settings.MAX_RISK_PREMIUM
        elif composite >= 0.75:
            decision = LoanDecision.APPROVED
            risk_grade = self._score_to_grade(composite)
            approved_amount = app.requested_amount_cr if app else None
            risk_premium = self._compute_premium(composite)
        elif composite >= 0.55:
            decision = LoanDecision.CONDITIONAL
            risk_grade = self._score_to_grade(composite)
            # Reduce approved amount for conditional
            approved_amount = (
                app.requested_amount_cr * (composite / 0.75) if app else None
            )
            risk_premium = self._compute_premium(composite)
        elif composite >= 0.40:
            decision = LoanDecision.REFERRED
            risk_grade = self._score_to_grade(composite)
            approved_amount = None
            risk_premium = self._compute_premium(composite)
        else:
            decision = LoanDecision.REJECTED
            risk_grade = self._score_to_grade(composite)
            approved_amount = None
            risk_premium = settings.MAX_RISK_PREMIUM
            rejection_reasons.append(
                f"Composite score below threshold: {composite:.3f}"
            )

        interest_rate = settings.BASE_LENDING_RATE + risk_premium

        # Conditions for conditional approval
        conditions = []
        if decision == LoanDecision.CONDITIONAL:
            if fraud and fraud.overall_fraud_score > 0.4:
                conditions.append(
                    "Require forensic audit of GST/bank transaction patterns"
                )
            if research and research.litigation_score > 0.5:
                conditions.append(
                    "Obtain legal opinion on pending litigation liability exposure"
                )
            if five_cs.collateral_score < 0.5:
                conditions.append(
                    "Provide additional collateral to achieve 1.25x coverage"
                )
            if five_cs.capacity_score < 0.5:
                conditions.append(
                    "Submit revised cash flow projections with quarterly monitoring"
                )

        credit_decision = CreditDecision(
            decision=decision,
            approved_amount_cr=round(approved_amount, 2) if approved_amount else None,
            interest_rate_pct=round(interest_rate, 2),
            risk_premium_pct=round(risk_premium, 2),
            risk_grade=risk_grade,
            tenure_months=app.loan_tenure_months if app else 60,
            conditions=conditions,
            rejection_reasons=rejection_reasons,
        )

        logger.info(
            f"RiskScorer: {decision.value}, Grade={risk_grade.value}, "
            f"Composite={composite:.3f}, Premium={risk_premium:.2f}%"
        )

        return credit_decision, shap_data

    def _compute_primary_diligence_score(self, state: dict[str, Any]) -> float:
        """Convert site-visit and interview inputs into an explicit decision feature."""
        site_visits = state.get("site_visits", [])
        interviews = state.get("management_interviews", [])

        score = 0.5

        cap_utils = [
            visit.capacity_utilization_pct / 100.0
            for visit in site_visits
            if getattr(visit, "capacity_utilization_pct", None) is not None
        ]
        if cap_utils:
            avg_util = sum(cap_utils) / len(cap_utils)
            if avg_util >= 0.75:
                score += 0.18
            elif avg_util >= 0.55:
                score += 0.06
            elif avg_util < 0.40:
                score -= 0.2

        infra_scores = []
        for visit in site_visits:
            quantified = getattr(visit, "quantified_scores", {}) or {}
            numeric = [float(value) for value in quantified.values() if isinstance(value, (int, float))]
            if numeric:
                infra_scores.append(sum(numeric) / len(numeric))
        if infra_scores:
            score += (sum(infra_scores) / len(infra_scores) - 0.5) * 0.2

        integrity_scores = [
            interview.integrity_score
            for interview in interviews
            if getattr(interview, "integrity_score", None) is not None
        ]
        if integrity_scores:
            avg_integrity = sum(integrity_scores) / len(integrity_scores)
            score += (avg_integrity - 0.5) * 0.4

        return round(max(0.0, min(1.0, score)), 4)

    def _score_to_grade(self, score: float) -> RiskGrade:
        if score >= 0.85:
            return RiskGrade.AAA
        elif score >= 0.75:
            return RiskGrade.AA
        elif score >= 0.65:
            return RiskGrade.A
        elif score >= 0.55:
            return RiskGrade.BBB
        elif score >= 0.45:
            return RiskGrade.BB
        elif score >= 0.35:
            return RiskGrade.B
        elif score >= 0.25:
            return RiskGrade.C
        return RiskGrade.D

    def _compute_premium(self, composite: float) -> float:
        """Higher composite → lower premium. Linear interpolation."""
        # Invert: score 1.0 → min premium, score 0.0 → max premium
        premium = settings.MAX_RISK_PREMIUM - (
            composite * (settings.MAX_RISK_PREMIUM - settings.MIN_RISK_PREMIUM)
        )
        return max(settings.MIN_RISK_PREMIUM, min(settings.MAX_RISK_PREMIUM, premium))
