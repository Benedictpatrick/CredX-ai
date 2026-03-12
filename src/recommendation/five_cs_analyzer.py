"""
Five Cs of Credit Analyzer — evaluates Character, Capacity, Capital, Collateral, Conditions.

Each C is scored 0.0–1.0 using a combination of quantitative metrics and LLM-driven
qualitative assessment, then combined with prescribed weights into a composite score.
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from src.models.schemas import (
    FiveCsAssessment,
    FraudReport,
    FraudSeverity,
    LoanApplication,
    ResearchReport,
)
from src.utils.llm_client import llm_client


class FiveCsAnalyzer:
    """Evaluates the Five Cs of Credit from all available pipeline data."""

    async def evaluate(self, state: dict[str, Any]) -> FiveCsAssessment:
        app: LoanApplication | None = state.get("application")
        fraud: FraudReport | None = state.get("fraud_report")
        research: ResearchReport | None = state.get("research_report")
        financials = state.get("financial_metrics", [])
        bank_summaries = state.get("bank_summaries", [])
        gst_summaries = state.get("gst_summaries", [])
        site_visits = state.get("site_visits", [])
        interviews = state.get("management_interviews", [])

        logger.info("FiveCsAnalyzer: Evaluating all five dimensions")

        # Run all five assessments (some use LLM, some are quantitative)
        character = await self._assess_character(app, fraud, research, interviews)
        capacity = await self._assess_capacity(app, financials, bank_summaries, site_visits)
        capital = self._assess_capital(app, financials)
        collateral = self._assess_collateral(app)
        conditions = await self._assess_conditions(app, research, gst_summaries)

        assessment = FiveCsAssessment(
            character_score=character[0],
            character_rationale=character[1],
            capacity_score=capacity[0],
            capacity_rationale=capacity[1],
            capital_score=capital[0],
            capital_rationale=capital[1],
            collateral_score=collateral[0],
            collateral_rationale=collateral[1],
            conditions_score=conditions[0],
            conditions_rationale=conditions[1],
        )

        logger.info(
            f"Five Cs: Character={assessment.character_score:.2f}, "
            f"Capacity={assessment.capacity_score:.2f}, "
            f"Capital={assessment.capital_score:.2f}, "
            f"Collateral={assessment.collateral_score:.2f}, "
            f"Conditions={assessment.conditions_score:.2f}, "
            f"Composite={assessment.composite_score:.3f}"
        )
        return assessment

    async def _assess_character(
        self, app, fraud, research, interviews
    ) -> tuple[float, str]:
        """Character: promoter integrity, litigation, fraud signals, CIBIL."""
        score = 0.7  # baseline optimistic

        rationale_parts = []

        # Fraud penalty
        if fraud:
            if fraud.severity == FraudSeverity.CRITICAL:
                score -= 0.5
                rationale_parts.append("CRITICAL fraud signals detected")
            elif fraud.severity == FraudSeverity.HIGH:
                score -= 0.3
                rationale_parts.append("HIGH fraud risk from transaction analysis")
            elif fraud.severity == FraudSeverity.MEDIUM:
                score -= 0.15
                rationale_parts.append("MEDIUM fraud indicators present")

        # Litigation penalty
        if research and research.litigation_score > 0.5:
            penalty = research.litigation_score * 0.3
            score -= penalty
            sec138 = [r for r in research.litigation_records
                      if r.case_type.value == "NI_ACT_138"]
            if sec138:
                score -= 0.1
                rationale_parts.append(
                    f"Section 138 (cheque bounce) cases: {len(sec138)}"
                )
            rationale_parts.append(
                f"Litigation risk score: {research.litigation_score:.2f}"
            )

        # Director interlocks
        if research and research.director_interlocks:
            risky = [il for il in research.director_interlocks if il.failed_companies]
            if risky:
                score -= len(risky) * 0.05
                rationale_parts.append(
                    f"{len(risky)} directors linked to failed companies"
                )

        # MCA red flags
        if research:
            red_flags = [f for f in research.mca_filings if f.red_flag]
            if red_flags:
                score -= len(red_flags) * 0.03
                rationale_parts.append(f"{len(red_flags)} MCA governance red flags")

        # Promoter CIBIL
        if app and app.company.promoters:
            cibil_scores = [p.cibil_score for p in app.company.promoters if p.cibil_score]
            if cibil_scores:
                avg_cibil = sum(cibil_scores) / len(cibil_scores)
                if avg_cibil < 650:
                    score -= 0.2
                    rationale_parts.append(f"Low avg CIBIL: {avg_cibil:.0f}")
                elif avg_cibil > 750:
                    score += 0.05
                    rationale_parts.append(f"Strong avg CIBIL: {avg_cibil:.0f}")

        # Disqualified promoters
        if app:
            disqualified = [p for p in app.company.promoters if p.disqualified]
            if disqualified:
                score -= 0.3
                rationale_parts.append(
                    f"DISQUALIFIED directors: {', '.join(p.name for p in disqualified)}"
                )

        # Management interviews
        if interviews:
            avg_integrity = sum(i.integrity_score for i in interviews) / len(interviews)
            if avg_integrity < 0.4:
                score -= 0.15
                rationale_parts.append(f"Low management integrity score: {avg_integrity:.2f}")
            elif avg_integrity > 0.7:
                score += 0.05

        score = max(0.0, min(1.0, score))
        rationale = "; ".join(rationale_parts) if rationale_parts else "No significant character concerns"
        return round(score, 3), rationale

    async def _assess_capacity(
        self, app, financials, bank_summaries, site_visits
    ) -> tuple[float, str]:
        """Capacity: cash flows, DSCR, bank conduct, capacity utilization."""
        score = 0.5
        parts = []

        # Financial ratios
        if financials:
            latest = financials[-1]
            if latest.dscr is not None:
                if latest.dscr >= 1.5:
                    score += 0.2
                    parts.append(f"Strong DSCR: {latest.dscr:.2f}")
                elif latest.dscr >= 1.2:
                    score += 0.1
                    parts.append(f"Adequate DSCR: {latest.dscr:.2f}")
                else:
                    score -= 0.2
                    parts.append(f"Weak DSCR: {latest.dscr:.2f}")

            if latest.interest_coverage_ratio is not None:
                if latest.interest_coverage_ratio >= 2.0:
                    score += 0.1
                elif latest.interest_coverage_ratio < 1.0:
                    score -= 0.15
                    parts.append(f"ICR below 1: {latest.interest_coverage_ratio:.2f}")

            if latest.revenue_cr and latest.ebitda_cr:
                margin = latest.ebitda_cr / latest.revenue_cr
                if margin > 0.15:
                    score += 0.1
                    parts.append(f"Healthy EBITDA margin: {margin:.1%}")
                elif margin < 0.05:
                    score -= 0.15
                    parts.append(f"Thin EBITDA margin: {margin:.1%}")

        # Bank conduct
        if bank_summaries:
            total_bounces = sum(bs.mandate_bounces for bs in bank_summaries)
            if total_bounces == 0:
                score += 0.1
                parts.append("Clean banking conduct: zero mandate bounces")
            elif total_bounces > 5:
                score -= 0.2
                parts.append(f"Poor banking conduct: {total_bounces} mandate bounces")

        # Site visit capacity utilization
        if site_visits:
            cap_utils = [sv.capacity_utilization_pct for sv in site_visits
                         if sv.capacity_utilization_pct is not None]
            if cap_utils:
                avg_util = sum(cap_utils) / len(cap_utils)
                if avg_util >= 70:
                    score += 0.1
                    parts.append(f"Good capacity utilization: {avg_util:.0f}%")
                elif avg_util < 40:
                    score -= 0.2
                    parts.append(f"LOW capacity utilization: {avg_util:.0f}%")

        score = max(0.0, min(1.0, score))
        rationale = "; ".join(parts) if parts else "Standard capacity assessment"
        return round(score, 3), rationale

    def _assess_capital(self, app, financials) -> tuple[float, str]:
        """Capital: net worth, D/E ratio, TOL/TNW, capital adequacy."""
        score = 0.5
        parts = []

        if financials:
            latest = financials[-1]
            if latest.debt_equity_ratio is not None:
                if latest.debt_equity_ratio <= 1.0:
                    score += 0.2
                    parts.append(f"Conservative D/E: {latest.debt_equity_ratio:.2f}")
                elif latest.debt_equity_ratio <= 2.0:
                    score += 0.05
                    parts.append(f"Moderate D/E: {latest.debt_equity_ratio:.2f}")
                else:
                    score -= 0.2
                    parts.append(f"High D/E: {latest.debt_equity_ratio:.2f}")

            if latest.tol_tnw is not None:
                if latest.tol_tnw <= 3.0:
                    score += 0.1
                elif latest.tol_tnw > 5.0:
                    score -= 0.15
                    parts.append(f"High TOL/TNW: {latest.tol_tnw:.2f}")

            if latest.net_worth_cr is not None and app:
                coverage = latest.net_worth_cr / max(app.requested_amount_cr, 0.01)
                if coverage >= 2.0:
                    score += 0.15
                    parts.append(f"Net worth covers loan {coverage:.1f}x")
                elif coverage < 0.5:
                    score -= 0.2
                    parts.append(f"Weak net worth coverage: {coverage:.1f}x")

        score = max(0.0, min(1.0, score))
        rationale = "; ".join(parts) if parts else "Standard capital assessment"
        return round(score, 3), rationale

    def _assess_collateral(self, app) -> tuple[float, str]:
        """Collateral: asset coverage ratio, collateral type."""
        if not app:
            return 0.5, "No application data"

        score = 0.5
        parts = []

        if app.collateral_value_cr and app.requested_amount_cr:
            coverage = app.collateral_value_cr / app.requested_amount_cr
            if coverage >= 1.5:
                score = 0.85
                parts.append(f"Strong collateral coverage: {coverage:.2f}x")
            elif coverage >= 1.0:
                score = 0.65
                parts.append(f"Adequate collateral: {coverage:.2f}x")
            elif coverage >= 0.5:
                score = 0.4
                parts.append(f"Partial collateral: {coverage:.2f}x")
            else:
                score = 0.2
                parts.append(f"Weak collateral: {coverage:.2f}x")
        else:
            score = 0.3
            parts.append("No collateral information provided")

        if app.collateral_description:
            desc = app.collateral_description.lower()
            if any(w in desc for w in ["property", "land", "building", "fixed asset"]):
                score += 0.05
                parts.append("Hard asset collateral")
            elif any(w in desc for w in ["receivable", "stock", "inventory"]):
                parts.append("Current asset collateral (higher risk)")
            elif any(w in desc for w in ["unsecured", "none"]):
                score -= 0.1
                parts.append("Unsecured or no tangible collateral")

        score = max(0.0, min(1.0, score))
        rationale = "; ".join(parts) if parts else "No collateral assessment"
        return round(score, 3), rationale

    async def _assess_conditions(
        self, app, research, gst_summaries
    ) -> tuple[float, str]:
        """Conditions: market/sector conditions, regulatory environment."""
        score = 0.5
        parts = []

        if research:
            # Sector outlook
            if research.sector_outlook_score > 0.3:
                score += 0.15
                parts.append(f"Positive sector outlook ({research.sector_outlook_score:.2f})")
            elif research.sector_outlook_score < -0.3:
                score -= 0.15
                parts.append(f"Negative sector outlook ({research.sector_outlook_score:.2f})")

            # News sentiment
            if research.news_sentiment > 0.3:
                score += 0.1
                parts.append("Positive news sentiment")
            elif research.news_sentiment < -0.3:
                score -= 0.1
                parts.append("Negative news sentiment")

            # Regulatory alerts
            if research.regulatory_alerts:
                score -= len(research.regulatory_alerts) * 0.03
                parts.append(f"{len(research.regulatory_alerts)} regulatory alerts")

        # GST trend (growth signal)
        if gst_summaries and len(gst_summaries) >= 2:
            recent = gst_summaries[-1].gstr3b_turnover_cr
            prior = gst_summaries[0].gstr3b_turnover_cr
            if prior > 0:
                growth = (recent - prior) / prior
                if growth > 0.1:
                    score += 0.1
                    parts.append(f"GST turnover growth: {growth:.1%}")
                elif growth < -0.1:
                    score -= 0.1
                    parts.append(f"GST turnover decline: {growth:.1%}")

        score = max(0.0, min(1.0, score))
        rationale = "; ".join(parts) if parts else "Standard conditions assessment"
        return round(score, 3), rationale
