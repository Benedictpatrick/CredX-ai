"""
Database connection layer using async SQLAlchemy.
Stores audit trails, experience library, and application state.
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, Float, Boolean, DateTime, Text, Integer, JSON
from datetime import datetime

from config.settings import settings


engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class ApplicationRecord(Base):
    __tablename__ = "applications"

    id = Column(String, primary_key=True)
    company_cin = Column(String, nullable=False, index=True)
    company_name = Column(String, nullable=False)
    requested_amount_cr = Column(Float)
    status = Column(String, default="pending")
    decision = Column(String, nullable=True)
    risk_grade = Column(String, nullable=True)
    approved_amount_cr = Column(Float, nullable=True)
    interest_rate_pct = Column(Float, nullable=True)
    fraud_score = Column(Float, nullable=True)
    litigation_score = Column(Float, nullable=True)
    five_cs_composite = Column(Float, nullable=True)
    cam_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(String, nullable=False, index=True)
    agent = Column(String, nullable=False)
    action = Column(String, nullable=False)
    input_summary = Column(Text, default="")
    output_summary = Column(Text, default="")
    reasoning_trace = Column(Text, default="")
    guardian_approved = Column(Boolean, default=True)
    drift_score = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=datetime.utcnow)


class ExperienceEntry(Base):
    __tablename__ = "experience_library"

    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(String, nullable=False)
    trajectory_type = Column(String)  # approval, rejection, conditional
    reasoning_chain = Column(Text)
    outcome_quality = Column(Float)  # 0-1 expert rating
    key_signals = Column(JSON)  # list of decisive factors
    created_at = Column(DateTime, default=datetime.utcnow)


class PipelineStateRecord(Base):
    __tablename__ = "pipeline_states"

    application_id = Column(String, primary_key=True)
    company_cin = Column(String, nullable=False, index=True)
    company_name = Column(String, nullable=False, index=True)
    application_json = Column(JSON, nullable=False)
    status = Column(String, default="submitted", nullable=False, index=True)
    current_phase = Column(String, default="submitted", nullable=False)
    started_at = Column(String, nullable=True)
    completed_at = Column(String, nullable=True)
    uploaded_files_json = Column(JSON, default=list)
    financial_metrics_json = Column(JSON, default=list)
    bank_summaries_json = Column(JSON, default=list)
    gst_summaries_json = Column(JSON, default=list)
    site_visits_json = Column(JSON, default=list)
    management_interviews_json = Column(JSON, default=list)
    decision_json = Column(JSON, nullable=True)
    cam_json = Column(JSON, nullable=True)
    fraud_json = Column(JSON, nullable=True)
    research_json = Column(JSON, nullable=True)
    five_cs_json = Column(JSON, nullable=True)
    debate_json = Column(JSON, nullable=True)
    shap_json = Column(JSON, nullable=True)
    messages_json = Column(JSON, default=list)
    audit_json = Column(JSON, default=list)
    errors_json = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


async def init_db():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
