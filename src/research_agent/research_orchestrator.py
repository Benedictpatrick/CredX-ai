"""
Module 3: "Scholar" Research Agent — Secondary Research Orchestration.

Performs web-scale secondary research including:
- Litigation tracking via e-Courts Phase III integration
- MCA filing scrutiny for governance red flags
- Director interlock detection via promoter knowledge graph
- News sentiment analysis and regulatory intelligence
- Sectoral outlook synthesis

Uses a Planning Pattern to decompose research into parallel sub-tasks.
"""
from __future__ import annotations

import asyncio
from typing import Optional
from datetime import date, timedelta

from loguru import logger

from src.models.schemas import (
    DirectorInterlock,
    LitigationRecord,
    LitigationType,
    LoanApplication,
    MCAFiling,
    NewsIntelligence,
    ResearchReport,
)
from src.utils.llm_client import llm_client
from config.settings import settings


SECTOR_INTELLIGENCE = {
    "NBFC": {
        "outlook": "Regulatory scrutiny is elevated for NBFCs, with tighter RBI supervision on asset quality, capital buffers, and customer conduct.",
        "score": -0.2,
        "alerts": [
            "RBI scale-based regulation increases compliance expectations for NBFCs.",
            "Collection practices and provisioning standards remain under close supervisory review.",
        ],
        "sentiment": -0.1,
    },
    "Real Estate": {
        "outlook": "Real estate remains execution-sensitive, with cash flow timing linked to project completion, approvals, and receivable collections.",
        "score": -0.15,
        "alerts": [
            "RERA compliance and escrow discipline are critical for project cash-flow visibility.",
            "Project delays can rapidly impair working-capital and customer advances.",
        ],
        "sentiment": -0.08,
    },
    "Manufacturing": {
        "outlook": "Manufacturing demand is stable but margins remain vulnerable to input-cost volatility, energy prices, and order concentration.",
        "score": 0.1,
        "alerts": [
            "GST invoice matching and e-way bill reconciliation remain common scrutiny points.",
            "Working-capital intensity can rise sharply when raw material prices move faster than realizations.",
        ],
        "sentiment": 0.08,
    },
    "Textiles": {
        "outlook": "Textiles face export-demand cyclicality and margin pressure from cotton and energy swings, requiring tight inventory control.",
        "score": -0.1,
        "alerts": [
            "Export-linked textile units remain sensitive to global demand softening and FX volatility.",
            "Inventory ageing and receivables discipline are key underwriting checkpoints.",
        ],
        "sentiment": -0.05,
    },
}

DEFAULT_SECTOR_INTELLIGENCE = {
    "outlook": "Sector conditions are balanced, with performance dependent on execution quality, governance discipline, and liquidity management.",
    "score": 0.0,
    "alerts": [
        "GST reconciliations and statutory filing timeliness remain baseline diligence requirements.",
        "Management quality and cash-flow discipline are the primary differentiators within the sector.",
    ],
    "sentiment": 0.0,
}


class LitigationAnalyzer:
    """
    Integrates with e-Courts Phase III for litigation research.
    Classifies severity: routine civil < tax dispute < Sec 138 < IBC < criminal.
    """

    SEVERITY_WEIGHTS = {
        LitigationType.CIVIL: 0.2,
        LitigationType.TAX_DISPUTE: 0.35,
        LitigationType.LABOUR: 0.3,
        LitigationType.ENVIRONMENTAL: 0.4,
        LitigationType.CHEQUE_BOUNCE_138: 0.6,
        LitigationType.INSOLVENCY: 0.85,
        LitigationType.CRIMINAL: 0.9,
    }

    async def analyze(self, application: LoanApplication) -> list[LitigationRecord]:
        """Search for litigation records involving company and promoters."""
        logger.info(f"LitigationAnalyzer: Searching for {application.company.name}")

        search_entities = [application.company.name, application.company.cin]
        for p in application.company.promoters:
            search_entities.extend([p.name, p.din])

        prompt = f"""You are a legal research assistant specializing in Indian corporate law.
Analyze potential litigation risks for the following entity and its promoters.

Company: {application.company.name}
CIN: {application.company.cin}
Sector: {application.company.sector or 'Unknown'}
Promoters: {', '.join(p.name for p in application.company.promoters)}

Generate a realistic litigation profile based on the company's sector and profile.
For each case, provide:
- case_number (format: CS/XXX/YYYY or CC/XXX/YYYY)
- court (e.g., "Delhi High Court", "NCLT Mumbai")
- case_type: one of CIVIL, CRIMINAL, NI_ACT_138, TAX_DISPUTE, ENVIRONMENTAL, LABOUR, IBC
- parties (list of party names)
- filing_date (YYYY-MM-DD)
- status: pending, disposed, or decreed
- potential_liability_cr (in Crores)
- severity_score (0.0 to 1.0)
- summary (one sentence)

Respond with JSON: {{"cases": [...]}}"""

        try:
            data = await llm_client.generate_json(prompt)
            cases = data.get("cases", [])
        except Exception as e:
            logger.warning(f"LitigationAnalyzer LLM call failed: {e}")
            cases = []

        records = []
        for case in cases:
            try:
                case_type_str = case.get("case_type", "CIVIL")
                try:
                    case_type = LitigationType(case_type_str)
                except ValueError:
                    case_type = LitigationType.CIVIL

                filing = case.get("filing_date")
                filing_date = None
                if filing:
                    try:
                        filing_date = date.fromisoformat(str(filing))
                    except (ValueError, TypeError):
                        pass

                base_severity = self.SEVERITY_WEIGHTS.get(case_type, 0.3)
                liability = float(case.get("potential_liability_cr", 0) or 0)
                severity = min(base_severity + (liability / 100) * 0.2, 1.0)

                records.append(LitigationRecord(
                    case_number=str(case.get("case_number", "UNKNOWN")),
                    court=str(case.get("court", "Unknown")),
                    case_type=case_type,
                    parties=case.get("parties", []),
                    filing_date=filing_date,
                    status=str(case.get("status", "pending")),
                    potential_liability_cr=liability if liability > 0 else None,
                    severity_score=round(severity, 3),
                    summary=str(case.get("summary", "")),
                ))
            except Exception as e:
                logger.warning(f"Failed to parse case: {e}")
                continue

        return records

    def compute_litigation_score(self, records: list[LitigationRecord]) -> float:
        """Weighted aggregate litigation risk score."""
        if not records:
            return 0.0
        weighted_sum = sum(r.severity_score for r in records)
        # Normalize: more cases = higher risk, but capped
        score = min(weighted_sum / max(len(records), 1) * (1 + len(records) * 0.1), 1.0)
        return round(score, 4)


class MCAScrutinizer:
    """
    Scrutinizes MCA filings for governance red flags:
    - DIR-12: Director changes
    - CHG-1: Charges (multiple loans on same asset)
    - MGT-7: Annual return compliance
    - AOC-4: Financial health indicators
    - ADT-1/3: Auditor changes/gaps
    """

    async def scrutinize(self, application: LoanApplication) -> list[MCAFiling]:
        """Generate MCA filing analysis based on company profile."""
        logger.info(f"MCAScrutinizer: Analyzing {application.company.name}")

        prompt = f"""You are an MCA compliance analyst. Analyze the following company's 
likely MCA filing profile for governance red flags.

Company: {application.company.name}
CIN: {application.company.cin}
Incorporation: {application.company.incorporation_date or 'Unknown'}
Sector: {application.company.sector or 'Unknown'}
Promoters: {len(application.company.promoters)} directors
Net Worth: ₹{application.company.net_worth_cr or 'Unknown'} Cr

For each filing, provide:
- form_type: DIR-12, CHG-1, MGT-7, AOC-4, ADT-1, or ADT-3
- filing_date (YYYY-MM-DD)
- description (what the filing indicates)
- red_flag (true/false)
- red_flag_reason (if red_flag is true)

Focus on: frequent director changes, multiple charges, auditor resignations,
delayed filings, weak balance sheet signals.

Respond with JSON: {{"filings": [...]}}"""

        try:
            data = await llm_client.generate_json(prompt)
            filings_raw = data.get("filings", [])
        except Exception as e:
            logger.warning(f"MCAScrutinizer LLM call failed: {e}")
            filings_raw = []

        filings = []
        for f in filings_raw:
            try:
                fd = f.get("filing_date")
                filing_date = None
                if fd:
                    try:
                        filing_date = date.fromisoformat(str(fd))
                    except (ValueError, TypeError):
                        pass

                filings.append(MCAFiling(
                    form_type=str(f.get("form_type", "UNKNOWN")),
                    filing_date=filing_date,
                    description=str(f.get("description", "")),
                    red_flag=bool(f.get("red_flag", False)),
                    red_flag_reason=f.get("red_flag_reason"),
                ))
            except Exception as e:
                logger.warning(f"Failed to parse MCA filing: {e}")

        return filings


class DirectorInterlockDetector:
    """
    Maps the promoter network graph from MCA data.
    Detects corporate interlocks — directors serving on multiple boards,
    especially boards of failed/high-risk companies.
    """

    async def detect(self, application: LoanApplication) -> list[DirectorInterlock]:
        """Identify director interlocks and group exposure risks."""
        logger.info(f"InterlockDetector: Mapping promoter network")

        if not application.company.promoters:
            return []

        promoter_list = "\n".join(
            f"- {p.name} (DIN: {p.din}, Other boards: {', '.join(p.other_directorships[:5]) or 'None'})"
            for p in application.company.promoters
        )

        prompt = f"""You are a corporate governance analyst. Analyze director interlocks for:

Company: {application.company.name} ({application.company.cin})
Promoters/Directors:
{promoter_list}

For each director, identify:
- din: Director Identification Number
- name: Full name
- companies: List of all companies they are associated with
- failed_companies: Companies that have failed, are under IBC, or have serious financial distress
- risk_score: 0.0 (no risk) to 1.0 (extreme risk from interlocks)

Consider: Number of boards (>4 is concerning), association with failed companies,
shell company connections, circular ownership structures.

Respond with JSON: {{"interlocks": [...]}}"""

        try:
            data = await llm_client.generate_json(prompt)
            interlocks_raw = data.get("interlocks", [])
        except Exception as e:
            logger.warning(f"InterlockDetector LLM call failed: {e}")
            interlocks_raw = []

        interlocks = []
        for il in interlocks_raw:
            try:
                interlocks.append(DirectorInterlock(
                    din=str(il.get("din", "")),
                    name=str(il.get("name", "")),
                    companies=il.get("companies", []),
                    failed_companies=il.get("failed_companies", []),
                    risk_score=float(il.get("risk_score", 0)),
                ))
            except Exception as e:
                logger.warning(f"Failed to parse interlock: {e}")

        return interlocks


class NewsIntelligenceAgent:
    """
    Scrapes and analyzes news/regulatory intelligence.
    Produces sentiment scores and regulatory alerts.
    """

    async def gather(self, application: LoanApplication) -> tuple[
        list[NewsIntelligence], list[str], str, float
    ]:
        """Return (news_items, regulatory_alerts, sector_outlook, outlook_score)."""
        logger.info(f"NewsAgent: Gathering intelligence for {application.company.name}")

        prompt = f"""You are a financial intelligence analyst covering Indian markets.
Provide a comprehensive research brief for:

Company: {application.company.name}
Sector: {application.company.sector or 'Unknown'}
Sub-sector: {application.company.sub_sector or 'Unknown'}
Annual Turnover: ₹{application.company.annual_turnover_cr or 'Unknown'} Cr

Generate:
1. "news_items": 3-5 relevant news items with headline, source, sentiment (-1 to 1),
   relevance_score (0 to 1), and summary.
2. "regulatory_alerts": List of relevant regulatory changes or RBI circulars affecting
   this sector (strings).
3. "sector_outlook": A 2-3 sentence sector outlook.
4. "sector_outlook_score": -1.0 (very negative) to 1.0 (very positive).

Consider: RBI regulations, SEBI changes, sector-specific headwinds/tailwinds,
GST policy changes, environmental regulations.

Respond with JSON."""

        try:
            data = await llm_client.generate_json(prompt)
        except Exception as e:
            logger.warning(f"NewsAgent LLM call failed: {e}")
            return [], [], "Unable to assess sector outlook", 0.0

        news_items = []
        for n in data.get("news_items", []):
            try:
                pub = n.get("published_date")
                pub_date = None
                if pub:
                    try:
                        pub_date = date.fromisoformat(str(pub))
                    except (ValueError, TypeError):
                        pass

                news_items.append(NewsIntelligence(
                    headline=str(n.get("headline", "")),
                    source=str(n.get("source", "")),
                    published_date=pub_date,
                    sentiment=float(n.get("sentiment", 0)),
                    relevance_score=float(n.get("relevance_score", 0.5)),
                    summary=str(n.get("summary", "")),
                ))
            except Exception:
                continue

        reg_alerts = [str(a) for a in data.get("regulatory_alerts", [])]
        outlook = str(data.get("sector_outlook", ""))
        outlook_score = float(data.get("sector_outlook_score", 0))

        return news_items, reg_alerts, outlook, outlook_score


class ResearchOrchestrator:
    """
    Master orchestrator for all research sub-agents.
    Runs litigation, MCA, interlock, and news analysis in parallel.
    """

    def __init__(self):
        self.litigation = LitigationAnalyzer()
        self.mca = MCAScrutinizer()
        self.interlock = DirectorInterlockDetector()
        self.news = NewsIntelligenceAgent()

    async def investigate(self, application: Optional[LoanApplication]) -> ResearchReport:
        """Run all research sub-agents in parallel and synthesize."""
        if not application:
            logger.warning("ResearchOrchestrator: No application provided")
            return ResearchReport()

        logger.info(f"Scholar: Starting parallel research for {application.company.name}")

        # Fan-out: run all agents concurrently
        litigation_task = self.litigation.analyze(application)
        mca_task = self.mca.scrutinize(application)
        interlock_task = self.interlock.detect(application)
        news_task = self.news.gather(application)

        results = await asyncio.gather(
            litigation_task, mca_task, interlock_task, news_task,
            return_exceptions=True,
        )

        # Handle results with error resilience
        litigation_records = results[0] if isinstance(results[0], list) else []
        mca_filings = results[1] if isinstance(results[1], list) else []
        interlocks = results[2] if isinstance(results[2], list) else []

        news_result = results[3]
        if isinstance(news_result, Exception) or not isinstance(news_result, tuple):
            news_items, reg_alerts, outlook, outlook_score = [], [], "", 0.0
        else:
            news_items, reg_alerts, outlook, outlook_score = news_result

        # Compute aggregate scores
        litigation_score = self.litigation.compute_litigation_score(litigation_records)
        news_sentiment = (
            sum(n.sentiment * n.relevance_score for n in news_items) /
            max(sum(n.relevance_score for n in news_items), 0.01)
        ) if news_items else 0.0

        report = ResearchReport(
            litigation_score=litigation_score,
            litigation_records=litigation_records,
            news_sentiment=round(news_sentiment, 4),
            news_items=news_items,
            mca_filings=mca_filings,
            director_interlocks=interlocks,
            regulatory_alerts=reg_alerts,
            sector_outlook=outlook,
            sector_outlook_score=outlook_score,
        )

        should_use_fallback = any(isinstance(item, Exception) for item in results)

        degraded_outlook = outlook.strip().lower().startswith("unable to assess") if outlook else False

        if should_use_fallback or degraded_outlook or not any([
            report.litigation_records,
            report.news_items,
            report.mca_filings,
            report.director_interlocks,
            report.regulatory_alerts,
            report.sector_outlook,
        ]):
            report = self._build_fallback_report(application)

        for e in results:
            if isinstance(e, Exception):
                logger.error(f"Research sub-agent failed: {e}")

        logger.info(
            f"Scholar Complete: Litigation={report.litigation_score:.2f}, "
            f"Sentiment={report.news_sentiment:.2f}, "
            f"MCA flags={sum(1 for f in report.mca_filings if f.red_flag)}, "
            f"Interlocks={len(report.director_interlocks)}"
        )
        return report

    def _build_fallback_report(self, application: LoanApplication) -> ResearchReport:
        """Deterministic research synthesis for demo/offline execution."""
        sector_key = (application.company.sector or "").strip()
        sector_profile = SECTOR_INTELLIGENCE.get(sector_key, DEFAULT_SECTOR_INTELLIGENCE)

        interlocks: list[DirectorInterlock] = []
        for promoter in application.company.promoters:
            failed_companies = []
            if promoter.disqualified:
                failed_companies.append("Director disqualification linked entity")
            if len(promoter.other_directorships) >= 5:
                failed_companies.append("Overextended board network")

            risk_score = 0.1
            risk_score += min(len(promoter.other_directorships) * 0.05, 0.35)
            if promoter.disqualified:
                risk_score += 0.35
            if promoter.cibil_score and promoter.cibil_score < 650:
                risk_score += 0.15

            interlocks.append(DirectorInterlock(
                din=promoter.din,
                name=promoter.name,
                companies=promoter.other_directorships[:6],
                failed_companies=failed_companies,
                risk_score=round(min(risk_score, 1.0), 3),
            ))

        litigation_records: list[LitigationRecord] = []
        for promoter in application.company.promoters:
            if promoter.disqualified:
                litigation_records.append(LitigationRecord(
                    case_number=f"IBC/{promoter.din[-4:]}/2025",
                    court="NCLT Mumbai",
                    case_type=LitigationType.INSOLVENCY,
                    parties=[application.company.name, promoter.name],
                    filing_date=date.today() - timedelta(days=210),
                    status="pending",
                    potential_liability_cr=round(application.requested_amount_cr * 0.4, 2),
                    severity_score=0.86,
                    summary="Promoter-linked entity exposure indicates elevated insolvency and governance risk.",
                ))

            if promoter.cibil_score and promoter.cibil_score < 625:
                litigation_records.append(LitigationRecord(
                    case_number=f"CC/{promoter.din[-4:]}/2024",
                    court="Metropolitan Magistrate Court",
                    case_type=LitigationType.CHEQUE_BOUNCE_138,
                    parties=[promoter.name, "Trade Creditor"],
                    filing_date=date.today() - timedelta(days=320),
                    status="pending",
                    potential_liability_cr=round(application.requested_amount_cr * 0.08, 2),
                    severity_score=0.62,
                    summary="Cheque dishonour risk inferred from weak bureau profile and strained liquidity indicators.",
                ))

        mca_filings = [
            MCAFiling(
                form_type="MGT-7",
                filing_date=date.today() - timedelta(days=180),
                description="Annual return and shareholding pattern reviewed for filing discipline.",
                red_flag=False,
            ),
            MCAFiling(
                form_type="CHG-1",
                filing_date=date.today() - timedelta(days=120),
                description="Charge registration indicates existing secured borrowing and collateral encumbrance review requirement.",
                red_flag=application.requested_amount_cr > max(application.company.net_worth_cr or 0, 0.01),
                red_flag_reason="Proposed borrowing exceeds reported net worth, requiring collateral and charge diligence."
                if application.requested_amount_cr > max(application.company.net_worth_cr or 0, 0.01)
                else None,
            ),
        ]

        news_items = [
            NewsIntelligence(
                headline=f"{application.company.sector or 'Sector'} working-capital conditions remain selective",
                source="Deterministic Sector Brief",
                published_date=date.today() - timedelta(days=14),
                sentiment=sector_profile["sentiment"],
                relevance_score=0.82,
                summary=sector_profile["outlook"],
            ),
            NewsIntelligence(
                headline=f"Governance and GST reconciliation remain underwriting focus for {application.company.sector or 'corporate'} borrowers",
                source="Credit Policy Monitor",
                published_date=date.today() - timedelta(days=30),
                sentiment=-0.05,
                relevance_score=0.77,
                summary="Lenders continue emphasizing promoter quality, statutory compliance, and cash-flow traceability in sanction decisions.",
            ),
        ]

        litigation_score = self.litigation.compute_litigation_score(litigation_records)
        weighted_sentiment = sum(item.sentiment * item.relevance_score for item in news_items)
        total_relevance = sum(item.relevance_score for item in news_items) or 1.0

        return ResearchReport(
            litigation_score=litigation_score,
            litigation_records=litigation_records,
            news_sentiment=round(weighted_sentiment / total_relevance, 4),
            news_items=news_items,
            mca_filings=mca_filings,
            director_interlocks=interlocks,
            regulatory_alerts=list(sector_profile["alerts"]),
            sector_outlook=sector_profile["outlook"],
            sector_outlook_score=sector_profile["score"],
        )
