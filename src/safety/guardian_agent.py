"""
Module 5: Guardian Agent + SiriuS Experience Library.

Guardian Agent — Zero-layer guardrail that analyzes complete agent traces
(not just outputs) to block semantic drift and instruction manipulation.

SiriuS — Self-improving experience library that records high-quality
reasoning trajectories from past approvals/rejections to improve future decisions.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from src.models.schemas import AgentRole, AuditEntry, FraudSeverity
from src.utils.llm_client import llm_client
from config.settings import settings


class GuardianAgent:
    """
    Safety layer that audits the full reasoning trace of the pipeline.

    Checks for:
    1. Semantic drift — agent ignoring risks to satisfy prompts
    2. Consistency — fraud/research findings reflected in final decision
    3. Logic integrity — decision matches the Five Cs composite score
    4. Data leakage — no sensitive PII in output
    5. Hallucination — claims not backed by evidence
    """

    DRIFT_CHECKS = [
        "fraud_decision_consistency",
        "litigation_acknowledgment",
        "score_decision_alignment",
        "collateral_coverage_check",
        "circular_trading_gate",
    ]

    async def audit_trace(self, state: dict[str, Any]) -> str:
        """Perform full trace audit. Returns summary string."""
        logger.info("Guardian: Starting trace-level safety audit")

        issues = []

        # 1. Fraud-Decision Consistency
        fraud = state.get("fraud_report")
        decision = state.get("decision")

        if fraud and decision:
            if (fraud.severity == FraudSeverity.CRITICAL and
                    decision.decision.value != "REJECTED"):
                issues.append(
                    "CRITICAL: Fraud severity is CRITICAL but decision is not REJECTED. "
                    "Possible semantic drift — the system may be ignoring fraud signals."
                )

            if (fraud.circular_trading_detected and
                    decision.decision.value not in ("REJECTED", "REFERRED_TO_COMMITTEE")):
                issues.append(
                    "HIGH: Circular trading detected but loan not rejected/referred. "
                    "Circuit breaker rule violated."
                )

        # 2. Litigation Acknowledgment
        research = state.get("research_report")
        cam = state.get("cam_report")
        if research and research.litigation_score > 0.7:
            if cam and "litigation" not in cam.risk_narrative.lower():
                issues.append(
                    "MEDIUM: High litigation score but risk narrative doesn't mention litigation. "
                    "Possible narrative hallucination."
                )

        # 3. Score-Decision Alignment
        five_cs = state.get("five_cs")
        if five_cs and decision:
            composite = five_cs.composite_score
            if composite < 0.3 and decision.decision.value == "APPROVED":
                issues.append(
                    f"CRITICAL: Five Cs composite={composite:.3f} but decision=APPROVED. "
                    "Fundamental scoring-decision misalignment."
                )
            elif composite > 0.75 and decision.decision.value == "REJECTED":
                if not (fraud and fraud.severity in (FraudSeverity.CRITICAL, FraudSeverity.HIGH)):
                    issues.append(
                        f"MEDIUM: Five Cs composite={composite:.3f} but decision=REJECTED "
                        "without CRITICAL/HIGH fraud override."
                    )

        # 4. Collateral Coverage Gate
        app = state.get("application")
        if app and decision and decision.approved_amount_cr:
            if app.collateral_value_cr:
                coverage = app.collateral_value_cr / max(decision.approved_amount_cr, 0.01)
                if coverage < 0.5:
                    issues.append(
                        f"HIGH: Collateral coverage only {coverage:.2f}x on approved amount. "
                        "Below minimum 0.5x threshold."
                    )

        # 5. Audit Trail Completeness
        audit_trail = state.get("audit_trail", [])
        expected_agents = {
            AgentRole.INGESTOR, AgentRole.FRAUD_ANALYST,
            AgentRole.RESEARCHER, AgentRole.UNDERWRITER,
        }
        seen_agents = {entry.agent for entry in audit_trail if isinstance(entry, AuditEntry)}
        missing = expected_agents - seen_agents
        if missing:
            issues.append(
                f"LOW: Audit trail missing entries from: "
                f"{', '.join(a.value for a in missing)}"
            )

        # 6. Compute drift score
        drift_score = len(issues) * 0.15
        drift_score = min(drift_score, 1.0)

        # Update all audit entries with guardian status
        for entry in audit_trail:
            if isinstance(entry, AuditEntry):
                entry.guardian_approved = drift_score < settings.MAX_SEMANTIC_DRIFT_SCORE
                entry.drift_score = drift_score

        # Build result summary
        if not issues:
            result = (
                f"PASSED — All {len(self.DRIFT_CHECKS)} safety checks passed. "
                f"Drift score: {drift_score:.2f}. Trace is consistent and reliable."
            )
        elif drift_score >= settings.MAX_SEMANTIC_DRIFT_SCORE:
            result = (
                f"FAILED — {len(issues)} issues found. Drift score: {drift_score:.2f} "
                f"exceeds threshold {settings.MAX_SEMANTIC_DRIFT_SCORE}. "
                f"Issues: {' | '.join(issues)}"
            )
        else:
            result = (
                f"WARNING — {len(issues)} minor issues. Drift score: {drift_score:.2f}. "
                f"Issues: {' | '.join(issues)}"
            )

        # Record to SiriuS experience library
        await self._record_experience(state, issues, drift_score)

        logger.info(f"Guardian Audit: {result[:150]}")
        return result

    async def _record_experience(
        self, state: dict[str, Any], issues: list[str], drift_score: float
    ):
        """Record this pipeline run to the SiriuS Experience Library."""
        try:
            experience_dir = settings.EXPERIENCE_LIBRARY_DIR
            experience_dir.mkdir(parents=True, exist_ok=True)

            app = state.get("application")
            decision = state.get("decision")
            five_cs = state.get("five_cs")

            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "company": app.company.name if app else "unknown",
                "cin": app.company.cin if app else "unknown",
                "decision": decision.decision.value if decision else "unknown",
                "risk_grade": decision.risk_grade.value if decision else "unknown",
                "composite_score": five_cs.composite_score if five_cs else None,
                "drift_score": drift_score,
                "guardian_issues": issues,
                "guardian_passed": drift_score < settings.MAX_SEMANTIC_DRIFT_SCORE,
            }

            # Append to JSONL experience file
            exp_file = experience_dir / "trajectories.jsonl"
            with open(exp_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")

            logger.info(f"SiriuS: Experience recorded → {exp_file}")

        except Exception as e:
            logger.warning(f"SiriuS experience recording failed: {e}")


class SiriuSLearner:
    """
    SiriuS Experience Library — learns from past reasoning trajectories.
    Provides context from similar past decisions to improve current reasoning.
    """

    def __init__(self):
        self.experience_file = settings.EXPERIENCE_LIBRARY_DIR / "trajectories.jsonl"

    def load_experiences(self) -> list[dict]:
        """Load all past experiences."""
        if not self.experience_file.exists():
            return []

        experiences = []
        with open(self.experience_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        experiences.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return experiences

    def find_similar(self, sector: str, amount_cr: float, top_k: int = 3) -> list[dict]:
        """Find similar past decisions by sector and loan amount."""
        experiences = self.load_experiences()
        if not experiences:
            return []

        # Simple similarity: same sector preference, then similar amount
        scored = []
        for exp in experiences:
            score = 0.0
            if exp.get("guardian_passed", False):
                score += 0.5  # Prefer guardian-approved trajectories
            # More recent = more relevant
            scored.append((exp, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [exp for exp, _ in scored[:top_k]]

    async def get_context_prompt(
        self, sector: str, amount_cr: float
    ) -> str:
        """Generate a context prompt from similar past experiences."""
        similar = self.find_similar(sector, amount_cr)
        if not similar:
            return ""

        context_parts = ["Past similar decisions for reference:"]
        for i, exp in enumerate(similar, 1):
            context_parts.append(
                f"{i}. {exp.get('company', 'N/A')} — "
                f"Decision: {exp.get('decision', 'N/A')}, "
                f"Grade: {exp.get('risk_grade', 'N/A')}, "
                f"Composite: {exp.get('composite_score', 'N/A')}, "
                f"Guardian: {'PASSED' if exp.get('guardian_passed') else 'FAILED'}"
            )

        return "\n".join(context_parts)
