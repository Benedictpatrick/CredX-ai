"""
Bank Statement Parser — Extracts structured summaries from bank statements.
Identifies counterparties, mandate bounces, and suspicious patterns.
"""
from __future__ import annotations

from loguru import logger
from datetime import date

from src.utils.llm_client import llm_client
from src.models.schemas import (
    ExtractedDocument,
    BankStatementSummary,
    CounterpartyFlow,
)


BANK_STATEMENT_PROMPT = """Analyze this Indian bank statement data and extract:

1. Bank name and account number
2. Statement period (from-to dates)
3. Average monthly balance (in Crores)
4. Total credits and debits (in Crores)
5. Mandate/ECS bounce count (EMI returns, cheque returns)
6. Inward return count
7. Top 10 counterparties by transaction value (name, amount, count)
8. Any related-party transactions you can identify

Output as JSON:
{
    "bank_name": "...",
    "account_number": "...",
    "period_from": "YYYY-MM-DD",
    "period_to": "YYYY-MM-DD",
    "avg_monthly_balance_cr": 0.0,
    "total_credits_cr": 0.0,
    "total_debits_cr": 0.0,
    "peak_utilization_pct": 0.0,
    "mandate_bounces": 0,
    "inward_return_count": 0,
    "top_counterparties": [
        {
            "name": "...",
            "total_amount_cr": 0.0,
            "transaction_count": 0,
            "is_related_party": false
        }
    ]
}

Rules:
- Convert all amounts to Crores (1 Cr = 100 Lakhs = 10 Million)
- "Mandate bounce" = EMI return, ECS return, NACH return
- "Inward return" = cheque return from deposited cheques
- Flag counterparties with same promoter surnames as potential related parties"""


class BankStatementParser:
    """Parse bank statement documents into structured summaries."""

    async def parse(self, doc: ExtractedDocument) -> BankStatementSummary:
        """Parse an extracted bank statement document."""
        logger.info(f"Parsing bank statement: {doc.source_file}")

        # Build context from extracted text and tables
        context = doc.extracted_text[:6000]
        if doc.tables:
            for t in doc.tables[:10]:
                context += f"\n\nTable:\n"
                if t.headers:
                    context += " | ".join(t.headers) + "\n"
                for row in t.rows[:30]:
                    context += " | ".join(str(v) for v in row) + "\n"

        try:
            result = await llm_client.generate_json(
                prompt=f"Bank statement data:\n{context}\n\n{BANK_STATEMENT_PROMPT}",
                system_prompt="You are an Indian banking analyst expert at reading bank statements.",
            )

            counterparties = [
                CounterpartyFlow(
                    name=cp.get("name", "Unknown"),
                    gstin=cp.get("gstin"),
                    total_amount_cr=float(cp.get("total_amount_cr", 0)),
                    transaction_count=int(cp.get("transaction_count", 0)),
                    is_related_party=bool(cp.get("is_related_party", False)),
                )
                for cp in result.get("top_counterparties", [])
            ]

            return BankStatementSummary(
                bank_name=result.get("bank_name", "Unknown"),
                account_number=result.get("account_number", "Unknown"),
                period_from=date.fromisoformat(result.get("period_from", "2024-01-01")),
                period_to=date.fromisoformat(result.get("period_to", "2024-12-31")),
                avg_monthly_balance_cr=float(result.get("avg_monthly_balance_cr", 0)),
                total_credits_cr=float(result.get("total_credits_cr", 0)),
                total_debits_cr=float(result.get("total_debits_cr", 0)),
                peak_utilization_pct=result.get("peak_utilization_pct"),
                mandate_bounces=int(result.get("mandate_bounces", 0)),
                inward_return_count=int(result.get("inward_return_count", 0)),
                top_counterparties=counterparties,
            )

        except Exception as e:
            logger.error(f"Bank statement parsing failed: {e}")
            return BankStatementSummary(
                bank_name="Parse Error",
                account_number="N/A",
                period_from=date(2024, 1, 1),
                period_to=date(2024, 12, 31),
            )
