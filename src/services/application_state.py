# pyright: reportAssignmentType=false, reportArgumentType=false, reportAttributeAccessIssue=false
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence, cast

from pydantic import BaseModel
from sqlalchemy import select

from src.models.schemas import (
    BankStatementSummary,
    CAMReport,
    CreditDecision,
    DebateResult,
    FiveCsAssessment,
    FinancialMetrics,
    FraudReport,
    GSTSummary,
    LoanApplication,
    ManagementInterview,
    ResearchReport,
    SiteVisitObservation,
)
from src.utils.db import PipelineStateRecord, async_session_factory, init_db


@dataclass(slots=True)
class ApplicationState:
    application: LoanApplication
    status: str
    current_phase: str
    started_at: str | None
    completed_at: str | None
    uploaded_files: list[str]
    financial_metrics: list[FinancialMetrics]
    bank_summaries: list[BankStatementSummary]
    gst_summaries: list[GSTSummary]
    site_visits: list[SiteVisitObservation]
    management_interviews: list[ManagementInterview]
    decision: CreditDecision | None
    cam_report: CAMReport | None
    fraud_report: FraudReport | None
    research_report: ResearchReport | None
    five_cs: FiveCsAssessment | None
    debate_result: DebateResult | None
    shap_explanation: dict[str, object] | None
    messages: list[dict[str, object]]
    audit_trail: list[dict[str, object]]
    errors: list[str]


def _dump_model(value: BaseModel | None) -> dict[str, object] | None:
    if value is None:
        return None
    return cast(dict[str, object], value.model_dump(mode="json"))


def _dump_model_list(values: Sequence[BaseModel | dict[str, object]]) -> list[dict[str, object]]:
    dumped: list[dict[str, object]] = []
    for value in values:
        if isinstance(value, BaseModel):
            dumped.append(cast(dict[str, object], value.model_dump(mode="json")))
        else:
            dumped.append(value)
    return dumped


class ApplicationStateService:
    def __init__(self) -> None:
        self._cache: dict[str, ApplicationState] = {}
        self._db_ready = False

    async def _ensure_db_ready(self) -> None:
        if not self._db_ready:
            await init_db()
            self._db_ready = True

    async def create_application(self, application: LoanApplication) -> None:
        state = ApplicationState(
            application=application,
            status="submitted",
            current_phase="submitted",
            started_at=datetime.utcnow().isoformat(),
            completed_at=None,
            uploaded_files=[],
            financial_metrics=[],
            bank_summaries=[],
            gst_summaries=[],
            site_visits=[],
            management_interviews=[],
            decision=None,
            cam_report=None,
            fraud_report=None,
            research_report=None,
            five_cs=None,
            debate_result=None,
            shap_explanation=None,
            messages=[],
            audit_trail=[],
            errors=[],
        )
        await self._persist_state(state)
        self._cache[application.application_id] = state

    async def create_demo_case(
        self,
        application: LoanApplication,
        bank_summaries: list[BankStatementSummary],
        gst_summaries: list[GSTSummary],
        site_visits: list[SiteVisitObservation],
        management_interviews: list[ManagementInterview],
    ) -> None:
        state = ApplicationState(
            application=application,
            status="submitted",
            current_phase="submitted",
            started_at=datetime.utcnow().isoformat(),
            completed_at=None,
            uploaded_files=[],
            financial_metrics=[],
            bank_summaries=bank_summaries,
            gst_summaries=gst_summaries,
            site_visits=site_visits,
            management_interviews=management_interviews,
            decision=None,
            cam_report=None,
            fraud_report=None,
            research_report=None,
            five_cs=None,
            debate_result=None,
            shap_explanation=None,
            messages=[],
            audit_trail=[],
            errors=[],
        )
        await self._persist_state(state)
        self._cache[application.application_id] = state

    async def get_state(self, app_id: str) -> ApplicationState | None:
        await self._ensure_db_ready()
        cached = self._cache.get(app_id)
        if cached is not None:
            return cached

        async with async_session_factory() as session:
            record = await session.get(PipelineStateRecord, app_id)
            if record is None:
                return None
            state = self._record_to_state(record)
            self._cache[app_id] = state
            return state

    async def require_state(self, app_id: str) -> ApplicationState:
        state = await self.get_state(app_id)
        if state is None:
            raise KeyError(app_id)
        return state

    async def add_uploaded_file(self, app_id: str, file_path: str) -> None:
        state = await self.require_state(app_id)
        state.uploaded_files.append(file_path)
        await self._persist_state(state)

    async def add_site_visit(self, app_id: str, visit: SiteVisitObservation) -> None:
        state = await self.require_state(app_id)
        state.site_visits.append(visit)
        await self._persist_state(state)

    async def add_management_interview(self, app_id: str, interview: ManagementInterview) -> None:
        state = await self.require_state(app_id)
        state.management_interviews.append(interview)
        await self._persist_state(state)

    async def mark_running(self, app_id: str) -> ApplicationState:
        state = await self.require_state(app_id)
        state.status = "running"
        state.current_phase = "initializing"
        state.errors = []
        await self._persist_state(state)
        return state

    async def persist_pipeline_result(self, app_id: str, result: dict[str, object]) -> ApplicationState:
        state = await self.require_state(app_id)
        state.status = "completed"
        state.current_phase = cast(str, result.get("current_phase", "complete"))
        state.completed_at = datetime.utcnow().isoformat()
        state.cam_report = cast(CAMReport | None, result.get("cam_report"))
        state.decision = cast(CreditDecision | None, result.get("decision"))
        state.fraud_report = cast(FraudReport | None, result.get("fraud_report"))
        state.research_report = cast(ResearchReport | None, result.get("research_report"))
        state.five_cs = cast(FiveCsAssessment | None, result.get("five_cs"))
        state.debate_result = cast(DebateResult | None, result.get("debate_result"))
        state.shap_explanation = cast(dict[str, object] | None, result.get("shap_explanation"))
        state.messages = _dump_model_list(cast(list[BaseModel] | list[dict[str, object]], result.get("messages", [])))
        state.audit_trail = _dump_model_list(cast(list[BaseModel] | list[dict[str, object]], result.get("audit_trail", [])))
        state.errors = [str(item) for item in cast(list[object], result.get("errors", []))]

        state.financial_metrics = [
            item if isinstance(item, FinancialMetrics) else FinancialMetrics.model_validate(item)
            for item in cast(list[object], result.get("financial_metrics", []))
        ]
        state.bank_summaries = [
            item if isinstance(item, BankStatementSummary) else BankStatementSummary.model_validate(item)
            for item in cast(list[object], result.get("bank_summaries", state.bank_summaries))
        ]
        state.gst_summaries = [
            item if isinstance(item, GSTSummary) else GSTSummary.model_validate(item)
            for item in cast(list[object], result.get("gst_summaries", state.gst_summaries))
        ]
        await self._persist_state(state)
        return state

    async def mark_failed(self, app_id: str, error_message: str) -> None:
        state = await self.require_state(app_id)
        state.status = "failed"
        state.errors = [error_message]
        await self._persist_state(state)

    async def list_application_summaries(self) -> list[dict[str, object]]:
        await self._ensure_db_ready()
        async with async_session_factory() as session:
            result = await session.execute(select(PipelineStateRecord).order_by(PipelineStateRecord.updated_at.desc()))
            rows = result.scalars().all()
        return [self._summary_from_record(row) for row in rows]

    def build_initial_state(self, state: ApplicationState) -> dict[str, object]:
        return {
            "application": state.application,
            "uploaded_files": state.uploaded_files,
            "financial_metrics": state.financial_metrics,
            "bank_summaries": state.bank_summaries,
            "gst_summaries": state.gst_summaries,
            "site_visits": state.site_visits,
            "management_interviews": state.management_interviews,
        }

    async def _persist_state(self, state: ApplicationState) -> None:
        await self._ensure_db_ready()
        async with async_session_factory() as session:
            record = await session.get(PipelineStateRecord, state.application.application_id)
            if record is None:
                record = PipelineStateRecord(application_id=state.application.application_id)
                session.add(record)

            record.company_cin = state.application.company.cin
            record.company_name = state.application.company.name
            record.application_json = cast(dict[str, object], state.application.model_dump(mode="json"))
            record.status = state.status
            record.current_phase = state.current_phase
            record.started_at = state.started_at
            record.completed_at = state.completed_at
            record.uploaded_files_json = state.uploaded_files
            record.financial_metrics_json = _dump_model_list(state.financial_metrics)
            record.bank_summaries_json = _dump_model_list(state.bank_summaries)
            record.gst_summaries_json = _dump_model_list(state.gst_summaries)
            record.site_visits_json = _dump_model_list(state.site_visits)
            record.management_interviews_json = _dump_model_list(state.management_interviews)
            record.decision_json = _dump_model(state.decision)
            record.cam_json = _dump_model(state.cam_report)
            record.fraud_json = _dump_model(state.fraud_report)
            record.research_json = _dump_model(state.research_report)
            record.five_cs_json = _dump_model(state.five_cs)
            record.debate_json = _dump_model(state.debate_result)
            record.shap_json = state.shap_explanation
            record.messages_json = state.messages
            record.audit_json = state.audit_trail
            record.errors_json = state.errors
            record.updated_at = datetime.utcnow()
            await session.commit()

    def _record_to_state(self, record: PipelineStateRecord) -> ApplicationState:
        application = LoanApplication.model_validate(record.application_json or {})
        financial_metrics = [FinancialMetrics.model_validate(item) for item in (record.financial_metrics_json or [])]
        bank_summaries = [BankStatementSummary.model_validate(item) for item in (record.bank_summaries_json or [])]
        gst_rows = [GSTSummary.model_validate(item) for item in (record.gst_summaries_json or [])]
        site_visits = [SiteVisitObservation.model_validate(item) for item in (record.site_visits_json or [])]
        interviews = [ManagementInterview.model_validate(item) for item in (record.management_interviews_json or [])]

        decision_json = cast(dict[str, object] | None, record.decision_json)
        cam_json = cast(dict[str, object] | None, record.cam_json)
        fraud_json = cast(dict[str, object] | None, record.fraud_json)
        research_json = cast(dict[str, object] | None, record.research_json)
        five_cs_json = cast(dict[str, object] | None, record.five_cs_json)
        debate_json = cast(dict[str, object] | None, record.debate_json)

        decision = CreditDecision.model_validate(decision_json) if decision_json is not None else None
        cam_report = CAMReport.model_validate(cam_json) if cam_json is not None else None
        fraud_report = FraudReport.model_validate(fraud_json) if fraud_json is not None else None
        research_report = ResearchReport.model_validate(research_json) if research_json is not None else None
        five_cs = FiveCsAssessment.model_validate(five_cs_json) if five_cs_json is not None else None
        debate_result = DebateResult.model_validate(debate_json) if debate_json is not None else None

        return ApplicationState(
            application=application,
            status=record.status,
            current_phase=record.current_phase,
            started_at=record.started_at,
            completed_at=record.completed_at,
            uploaded_files=list(record.uploaded_files_json or []),
            financial_metrics=financial_metrics,
            bank_summaries=bank_summaries,
            gst_summaries=gst_rows,
            site_visits=site_visits,
            management_interviews=interviews,
            decision=decision,
            cam_report=cam_report,
            fraud_report=fraud_report,
            research_report=research_report,
            five_cs=five_cs,
            debate_result=debate_result,
            shap_explanation=cast(dict[str, object] | None, record.shap_json),
            messages=list(record.messages_json or []),
            audit_trail=list(record.audit_json or []),
            errors=[str(item) for item in (record.errors_json or [])],
        )

    def _summary_from_record(self, record: PipelineStateRecord) -> dict[str, object]:
        decision_json = cast(dict[str, object] | None, record.decision_json)
        application_json = cast(dict[str, object] | None, record.application_json)
        requested_amount = 0.0
        if application_json is not None:
            raw_amount = application_json.get("requested_amount_cr", 0.0)
            if isinstance(raw_amount, (int, float, str)):
                requested_amount = float(raw_amount)

        return {
            "application_id": record.application_id,
            "company": record.company_name,
            "status": record.status,
            "current_phase": record.current_phase,
            "requested_amount_cr": requested_amount,
            "decision": decision_json.get("decision") if decision_json else None,
            "started_at": record.started_at,
        }


application_state_service = ApplicationStateService()
