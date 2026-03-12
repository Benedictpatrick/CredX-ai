"""
Titan-Credit FastAPI Application — Main entry point.

Provides REST endpoints for:
- Submitting loan applications
- Running the full credit decisioning pipeline
- Querying pipeline status and results
- Credit Officer portal endpoints (primary insights)
- Health checks and monitoring
"""
from __future__ import annotations

import json
from io import BytesIO
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, cast

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel

from config.settings import settings
from src.models.schemas import (
    CompanyProfile,
    CreditDecision,
    LoanApplication,
    ManagementInterview,
    PromoterInfo,
    SiteVisitObservation,
)
from src.services.application_state import application_state_service
from src.utils.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Titan-Credit Engine starting up...")
    await init_db()
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (settings.DATA_DIR / "uploads").mkdir(exist_ok=True)
    settings.EXPERIENCE_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    yield
    logger.info("Titan-Credit Engine shutting down.")


app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="AI-Powered Credit Decisioning Engine for Indian Corporate Lending",
    lifespan=lifespan,
)

# CORS for Streamlit dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────

class ApplicationRequest(BaseModel):
    company_name: str
    cin: str
    sector: Optional[str] = None
    sub_sector: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    annual_turnover_cr: Optional[float] = None
    net_worth_cr: Optional[float] = None
    requested_amount_cr: float
    loan_purpose: str
    loan_tenure_months: int = 60
    collateral_description: Optional[str] = None
    collateral_value_cr: Optional[float] = None
    promoters: list[dict] = []


class SiteVisitRequest(BaseModel):
    application_id: str
    observer_name: str
    location: str
    notes: str
    capacity_utilization_pct: Optional[float] = None


class InterviewRequest(BaseModel):
    application_id: str
    interviewee: str
    designation: str
    key_points: list[str] = []
    integrity_score: float = 0.5


class PipelineStatus(BaseModel):
    application_id: str
    status: str
    current_phase: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


async def _require_state_or_404(app_id: str):
    try:
        return await application_state_service.require_state(app_id)
    except KeyError as exc:
        raise HTTPException(404, "Application not found") from exc


# ──────────────────────────────────────────────
# Health & Info
# ──────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "engine": "Titan-Credit", "version": settings.API_VERSION}


@app.get("/info")
async def info():
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "modules": [
            "Vision-Native Ingestor",
            "Sherlock Fraud Engine (Temporal GNN)",
            "Scholar Research Agent",
            "Underwriter (Five Cs + XAI)",
            "Bull-Bear Debate",
            "Guardian Safety Agent",
            "SiriuS Experience Library",
        ],
        "llm_model": settings.LLM_MODEL,
        "vision_model": settings.VISION_MODEL,
    }


# ──────────────────────────────────────────────
# Application Submission
# ──────────────────────────────────────────────

@app.post("/api/applications", response_model=dict)
async def submit_application(req: ApplicationRequest):
    """Submit a new loan application for processing."""
    promoters = [
        PromoterInfo(
            din=p.get("din", "00000000"),
            name=p.get("name", "Unknown"),
            designation=p.get("designation"),
            shareholding_pct=p.get("shareholding_pct"),
            other_directorships=p.get("other_directorships", []),
            disqualified=p.get("disqualified", False),
            cibil_score=p.get("cibil_score"),
        )
        for p in req.promoters
    ]

    company = CompanyProfile(
        cin=req.cin,
        name=req.company_name,
        sector=req.sector,
        sub_sector=req.sub_sector,
        gstin=req.gstin,
        pan=req.pan,
        promoters=promoters,
        annual_turnover_cr=req.annual_turnover_cr,
        net_worth_cr=req.net_worth_cr,
    )

    application = LoanApplication(
        company=company,
        requested_amount_cr=req.requested_amount_cr,
        loan_purpose=req.loan_purpose,
        loan_tenure_months=req.loan_tenure_months,
        collateral_description=req.collateral_description,
        collateral_value_cr=req.collateral_value_cr,
    )

    # Store initial state
    await application_state_service.create_application(application)

    return {
        "application_id": application.application_id,
        "status": "submitted",
        "company": company.name,
        "requested_amount_cr": req.requested_amount_cr,
    }


# ──────────────────────────────────────────────
# File Upload
# ──────────────────────────────────────────────

@app.post("/api/applications/{app_id}/upload")
async def upload_document(app_id: str, file: UploadFile = File(...)):
    """Upload a document (PDF, image) for an application."""
    await _require_state_or_404(app_id)

    upload_dir = settings.DATA_DIR / "uploads" / app_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = file.filename or "upload.bin"
    file_path = upload_dir / filename
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    await application_state_service.add_uploaded_file(app_id, str(file_path))

    return {"filename": filename, "path": str(file_path), "size": len(content)}


# ──────────────────────────────────────────────
# Primary Insights (Credit Officer Portal)
# ──────────────────────────────────────────────

@app.post("/api/applications/{app_id}/site-visit")
async def add_site_visit(app_id: str, req: SiteVisitRequest):
    """Add site visit observations (qualitative notes)."""
    await _require_state_or_404(app_id)

    visit = SiteVisitObservation(
        observer_name=req.observer_name,
        location=req.location,
        notes=req.notes,
        capacity_utilization_pct=req.capacity_utilization_pct,
    )

    await application_state_service.add_site_visit(app_id, visit)
    return {"status": "added", "observation_id": visit.observation_id}


@app.post("/api/applications/{app_id}/interview")
async def add_interview(app_id: str, req: InterviewRequest):
    """Add management interview notes."""
    await _require_state_or_404(app_id)

    interview = ManagementInterview(
        interviewee=req.interviewee,
        designation=req.designation,
        key_points=req.key_points,
        integrity_score=req.integrity_score,
    )

    await application_state_service.add_management_interview(app_id, interview)
    return {"status": "added", "interviewee": interview.interviewee}


# ──────────────────────────────────────────────
# Pipeline Execution
# ──────────────────────────────────────────────

@app.post("/api/applications/{app_id}/run")
async def run_pipeline(app_id: str):
    """Execute the full credit decisioning pipeline."""
    state_data = await _require_state_or_404(app_id)
    if state_data.status == "running":
        raise HTTPException(409, "Pipeline already running")

    state_data = await application_state_service.mark_running(app_id)

    try:
        from src.orchestrator.graph import get_compiled_graph

        graph = get_compiled_graph()

        # Build initial state for the LangGraph
        initial_state = application_state_service.build_initial_state(state_data)

        # Run the full pipeline
        result = await graph.ainvoke(initial_state)

        # Store results
        persisted_state = await application_state_service.persist_pipeline_result(app_id, cast(dict[str, object], result))

        final_decision = persisted_state.decision
        decision_value = "UNKNOWN"
        if final_decision is not None:
            decision_value = cast(CreditDecision, final_decision).decision.value

        return {
            "application_id": app_id,
            "status": "completed",
            "decision": decision_value,
        }

    except Exception as e:
        logger.error(f"Pipeline failed for {app_id}: {e}")
        await application_state_service.mark_failed(app_id, str(e))
        raise HTTPException(500, f"Pipeline execution failed: {e}")


# ──────────────────────────────────────────────
# Results & Monitoring
# ──────────────────────────────────────────────

@app.get("/api/applications/{app_id}/status")
async def get_status(app_id: str):
    """Get pipeline execution status."""
    data = await _require_state_or_404(app_id)
    return PipelineStatus(
        application_id=app_id,
        status=data.status,
        current_phase=data.current_phase,
        started_at=data.started_at,
        completed_at=data.completed_at,
    )


@app.get("/api/applications/{app_id}/decision")
async def get_decision(app_id: str):
    """Get the credit decision for an application."""
    data = await _require_state_or_404(app_id)
    decision = data.decision
    if not decision:
        raise HTTPException(404, "Decision not yet available")

    return decision.model_dump(mode="json") if hasattr(decision, "model_dump") else decision


@app.get("/api/applications/{app_id}/cam")
async def get_cam(app_id: str):
    """Get the full Credit Appraisal Memo."""
    data = await _require_state_or_404(app_id)
    cam = data.cam_report
    if not cam:
        raise HTTPException(404, "CAM not yet generated")

    return cam.model_dump(mode="json") if hasattr(cam, "model_dump") else cam


@app.get("/api/applications/{app_id}/cam.docx")
async def download_cam_docx(app_id: str):
    """Download the Credit Appraisal Memo as a DOCX file."""
    data = await _require_state_or_404(app_id)
    cam = data.cam_report
    if not cam:
        raise HTTPException(404, "CAM not yet generated")

    from src.recommendation.cam_generator import CAMGenerator

    generator = CAMGenerator()
    payload = generator.export_docx(cam)
    filename = f"{app_id}_credit_appraisal_memo.docx"

    return StreamingResponse(
        BytesIO(payload),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/applications/{app_id}/fraud")
async def get_fraud_report(app_id: str):
    """Get the fraud analysis report."""
    data = await _require_state_or_404(app_id)
    fraud = data.fraud_report
    if not fraud:
        raise HTTPException(404, "Fraud report not yet available")

    return fraud.model_dump(mode="json") if hasattr(fraud, "model_dump") else fraud


@app.get("/api/applications/{app_id}/research")
async def get_research_report(app_id: str):
    """Get the research & intelligence report."""
    data = await _require_state_or_404(app_id)
    report = data.research_report
    if not report:
        raise HTTPException(404, "Research report not yet available")

    return report.model_dump(mode="json") if hasattr(report, "model_dump") else report


@app.get("/api/applications/{app_id}/xai")
async def get_xai_explanation(app_id: str):
    """Get the SHAP-based explanation."""
    data = await _require_state_or_404(app_id)
    shap = data.shap_explanation
    if not shap:
        raise HTTPException(404, "XAI explanation not yet available")

    return shap


@app.get("/api/applications/{app_id}/debate")
async def get_debate_result(app_id: str):
    """Get the Bull-Bear debate result."""
    data = await _require_state_or_404(app_id)
    debate = data.debate_result
    if not debate:
        raise HTTPException(404, "Debate result not yet available")

    return debate.model_dump(mode="json") if hasattr(debate, "model_dump") else debate


@app.get("/api/applications/{app_id}/audit-trail")
async def get_audit_trail(app_id: str):
    """Get the full audit trail of agent actions."""
    data = await _require_state_or_404(app_id)
    return data.audit_trail


@app.get("/api/applications")
async def list_applications():
    """List all submitted applications."""
    return await application_state_service.list_application_summaries()


# ──────────────────────────────────────────────
# Demo: Synthetic Data Test Run
# ──────────────────────────────────────────────

@app.post("/api/demo/{risk_profile}")
async def run_demo(risk_profile: str):
    """Run a demo with synthetic data. Profiles: clean, risky, fraudulent."""
    from data.synthetic.generator import generate_full_test_case

    profile = risk_profile.upper()
    if profile not in ("CLEAN", "RISKY", "FRAUDULENT"):
        raise HTTPException(400, "Invalid profile. Use: clean, risky, fraudulent")

    case = generate_full_test_case(profile)
    app = case["application"]

    await application_state_service.create_demo_case(
        application=app,
        bank_summaries=case["bank_summaries"],
        gst_summaries=case["gst_summaries"],
        site_visits=case["site_visits"],
        management_interviews=case["management_interviews"],
    )

    return {
        "application_id": app.application_id,
        "company": app.company.name,
        "risk_profile": profile,
        "message": f"Demo case created. POST /api/applications/{app.application_id}/run to execute.",
    }
