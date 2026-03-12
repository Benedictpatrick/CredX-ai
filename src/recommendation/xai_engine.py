"""
XAI Engine — Explainable AI layer using SHAP-style additive feature attribution.

Provides human-readable explanations of why a credit decision was made.
Generates natural language narratives from SHAP values.
"""
from __future__ import annotations

from typing import Any, Optional

from loguru import logger

from src.models.schemas import CreditDecision, LoanDecision
from src.utils.llm_client import llm_client


# Human-readable feature names
FEATURE_DISPLAY_NAMES = {
    "character_score": "Promoter Character & Integrity",
    "capacity_score": "Repayment Capacity (Cash Flows & DSCR)",
    "capital_score": "Capital Strength (Net Worth & D/E Ratio)",
    "collateral_score": "Collateral Coverage",
    "conditions_score": "Market & Sector Conditions",
    "primary_diligence_score": "Primary Diligence (Site Visit & Management Inputs)",
    "fraud_score_inv": "Transaction Integrity (Fraud Analysis)",
    "litigation_score_inv": "Legal Risk Profile",
    "news_sentiment_norm": "Media & News Sentiment",
    "sector_outlook_norm": "Sector Outlook",
}


class XAIEngine:
    """
    Generates explainable narratives from SHAP data and credit decisions.
    Designed to "walk the judge through" the reasoning.
    """

    async def explain(
        self,
        decision: CreditDecision,
        shap_data: dict,
        state: Optional[dict[str, Any]] = None,
    ) -> dict:
        """
        Produce a structured explanation containing:
        - feature_importance: sorted list of (feature, value, shap, direction)
        - narrative: LLM-generated plain-English explanation
        - waterfall: data for SHAP waterfall chart
        """
        logger.info("XAI Engine: Generating explanations")

        features = shap_data.get("feature_values", {})
        shap_values = shap_data.get("shap_values", {})
        baseline = shap_data.get("baseline", 0.5)
        composite = shap_data.get("composite_score", 0.5)

        # Sort features by absolute SHAP contribution
        feature_importance = []
        for feat_key in sorted(
            shap_values.keys(), key=lambda k: abs(shap_values[k]), reverse=True
        ):
            display_name = FEATURE_DISPLAY_NAMES.get(feat_key, feat_key)
            val = features.get(feat_key, 0)
            shap_val = shap_values[feat_key]
            direction = "positive" if shap_val >= 0 else "negative"

            feature_importance.append({
                "feature": feat_key,
                "display_name": display_name,
                "value": round(val, 4),
                "shap_value": round(shap_val, 4),
                "direction": direction,
                "impact_pct": round(abs(shap_val) / max(abs(composite - baseline), 0.001) * 100, 1),
            })

        # Waterfall chart data
        waterfall = self._build_waterfall(baseline, shap_values, composite)

        # Generate LLM narrative
        narrative = await self._generate_narrative(
            decision, feature_importance, composite
        )

        return {
            "feature_importance": feature_importance,
            "waterfall": waterfall,
            "narrative": narrative,
            "composite_score": composite,
            "baseline": baseline,
            "decision": decision.decision.value,
            "risk_grade": decision.risk_grade.value,
        }

    def _build_waterfall(
        self, baseline: float, shap_values: dict, final: float
    ) -> list[dict]:
        """Build waterfall chart data (baseline → feature contributions → final)."""
        steps = [{"label": "Baseline", "value": baseline, "cumulative": baseline}]

        # Sort by absolute contribution for visual clarity
        sorted_feats = sorted(
            shap_values.items(), key=lambda x: abs(x[1]), reverse=True
        )

        cumulative = baseline
        for feat, shap_val in sorted_feats:
            cumulative += shap_val
            steps.append({
                "label": FEATURE_DISPLAY_NAMES.get(feat, feat),
                "value": round(shap_val, 4),
                "cumulative": round(cumulative, 4),
            })

        steps.append({"label": "Final Score", "value": final, "cumulative": final})
        return steps

    async def _generate_narrative(
        self, decision: CreditDecision, features: list[dict], composite: float
    ) -> str:
        """Use LLM to generate a human-readable explanation narrative."""
        top_positive = [f for f in features if f["direction"] == "positive"][:3]
        top_negative = [f for f in features if f["direction"] == "negative"][:3]

        pos_text = ", ".join(
            f"{f['display_name']} (score: {f['value']:.2f}, impact: +{f['shap_value']:.3f})"
            for f in top_positive
        ) or "None"

        neg_text = ", ".join(
            f"{f['display_name']} (score: {f['value']:.2f}, impact: {f['shap_value']:.3f})"
            for f in top_negative
        ) or "None"

        rejection_text = ""
        if decision.rejection_reasons:
            rejection_text = (
                f"\nRejection reasons: {'; '.join(decision.rejection_reasons)}"
            )

        conditions_text = ""
        if decision.conditions:
            conditions_text = (
                f"\nConditions: {'; '.join(decision.conditions)}"
            )

        prompt = f"""You are a senior credit analyst writing the final recommendation
narrative for a Credit Appraisal Memo (CAM). Write a clear, professional 3-4 paragraph
explanation of this credit decision.

Decision: {decision.decision.value}
Risk Grade: {decision.risk_grade.value}
Composite Score: {composite:.3f}
Approved Amount: ₹{decision.approved_amount_cr or 'N/A'} Cr
Interest Rate: {decision.interest_rate_pct or 'N/A'}%
Risk Premium: {decision.risk_premium_pct:.2f}%

Key POSITIVE factors: {pos_text}
Key NEGATIVE factors: {neg_text}
{rejection_text}
{conditions_text}

Write in first person as the AI underwriting system. Reference specific scores and
feature names. Explain WHY each factor contributed to the decision. Be specific and
use Indian banking terminology (DSCR, TOL/TNW, CIBIL, etc.).

Do NOT use markdown formatting. Write plain text paragraphs."""

        try:
            narrative = await llm_client.generate(prompt)
            return narrative.strip()
        except Exception as e:
            logger.warning(f"XAI narrative generation failed: {e}")
            return self._fallback_narrative(decision, features, composite)

    def _fallback_narrative(
        self, decision: CreditDecision, features: list[dict], composite: float
    ) -> str:
        """Deterministic fallback narrative if LLM fails."""
        lines = [
            f"Credit Decision: {decision.decision.value} "
            f"(Risk Grade: {decision.risk_grade.value}, "
            f"Composite Score: {composite:.3f})"
        ]

        pos = [f for f in features if f["direction"] == "positive"][:3]
        neg = [f for f in features if f["direction"] == "negative"][:3]

        if pos:
            lines.append(
                "Positive contributors: "
                + ", ".join(f"{f['display_name']} ({f['value']:.2f})" for f in pos)
            )
        if neg:
            lines.append(
                "Risk factors: "
                + ", ".join(f"{f['display_name']} ({f['value']:.2f})" for f in neg)
            )

        if decision.rejection_reasons:
            lines.append(
                "Rejected due to: " + "; ".join(decision.rejection_reasons)
            )

        return "\n\n".join(lines)
