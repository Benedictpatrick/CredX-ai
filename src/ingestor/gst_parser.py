"""
GST Return Parser — Extracts structured GST summaries.
Cross-references GSTR-1, GSTR-3B, GSTR-2A/2B for mismatch detection.
"""
from __future__ import annotations

from loguru import logger

from src.utils.llm_client import llm_client
from src.models.schemas import (
    ExtractedDocument,
    GSTSummary,
    CounterpartyFlow,
)


GST_PARSE_PROMPT = """Analyze this GST return data and extract:

1. GSTIN
2. Filing period
3. GSTR-1 reported turnover (in Crores)
4. GSTR-3B reported turnover (in Crores)
5. GSTR-2A inward supplies / purchases (in Crores)
6. GSTR-2B inward supplies / purchases (in Crores)
7. ITC claimed vs eligible
8. Turnover mismatch % between GSTR-1 and GSTR-3B
9. Top suppliers and buyers by value

Output as JSON:
{
    "gstin": "...",
    "period": "...",
    "gstr1_turnover_cr": 0.0,
    "gstr3b_turnover_cr": 0.0,
    "gstr2a_purchases_cr": 0.0,
    "gstr2b_purchases_cr": 0.0,
    "itc_claimed_cr": 0.0,
    "itc_eligible_cr": 0.0,
    "turnover_mismatch_pct": 0.0,
    "top_suppliers": [{"name": "...", "total_amount_cr": 0.0, "transaction_count": 0}],
    "top_buyers": [{"name": "...", "total_amount_cr": 0.0, "transaction_count": 0}]
}

Indian GST Rules:
- GSTR-1 = Outward supplies (sales reported by taxpayer)
- GSTR-3B = Summary return (self-declared sales + tax)
- GSTR-2A = Auto-populated inward supplies from seller's GSTR-1
- GSTR-2B = Static statement of ITC available
- Mismatch between 1 and 3B > 10% is a red flag
- ITC claimed > ITC eligible in 2B = potential fake invoicing"""


class GSTParser:
    """Parse GST return documents into structured summaries."""

    async def parse(self, doc: ExtractedDocument) -> GSTSummary:
        logger.info(f"Parsing GST return: {doc.source_file}")

        context = doc.extracted_text[:6000]
        if doc.tables:
            for t in doc.tables[:10]:
                context += f"\n\nTable ({t.table_type}):\n"
                if t.headers:
                    context += " | ".join(t.headers) + "\n"
                for row in t.rows[:30]:
                    context += " | ".join(str(v) for v in row) + "\n"

        try:
            result = await llm_client.generate_json(
                prompt=f"GST return data:\n{context}\n\n{GST_PARSE_PROMPT}",
                system_prompt="You are an Indian GST compliance expert.",
            )

            def parse_counterparties(items: list) -> list[CounterpartyFlow]:
                return [
                    CounterpartyFlow(
                        name=cp.get("name", "Unknown"),
                        gstin=cp.get("gstin"),
                        total_amount_cr=float(cp.get("total_amount_cr", 0)),
                        transaction_count=int(cp.get("transaction_count", 0)),
                    )
                    for cp in (items or [])
                ]

            return GSTSummary(
                gstin=result.get("gstin", "N/A"),
                period=result.get("period", "N/A"),
                gstr1_turnover_cr=float(result.get("gstr1_turnover_cr", 0)),
                gstr3b_turnover_cr=float(result.get("gstr3b_turnover_cr", 0)),
                gstr2a_purchases_cr=float(result.get("gstr2a_purchases_cr", 0)),
                gstr2b_purchases_cr=float(result.get("gstr2b_purchases_cr", 0)),
                itc_claimed_cr=float(result.get("itc_claimed_cr", 0)),
                itc_eligible_cr=float(result.get("itc_eligible_cr", 0)),
                turnover_mismatch_pct=float(result.get("turnover_mismatch_pct", 0)),
                top_suppliers=parse_counterparties(result.get("top_suppliers")),
                top_buyers=parse_counterparties(result.get("top_buyers")),
            )

        except Exception as e:
            logger.error(f"GST parsing failed: {e}")
            return GSTSummary(gstin="N/A", period="N/A")
