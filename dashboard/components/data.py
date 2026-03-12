# pyright: reportMissingImports=false, reportMissingModuleSource=false
"""API client, data loading, and formatting utilities."""
from __future__ import annotations

from datetime import datetime
import os
from typing import Any

import pandas as pd  # type: ignore[reportMissingImports,reportMissingModuleSource]
import requests  # type: ignore[reportMissingImports,reportMissingModuleSource]
import streamlit as st  # type: ignore[reportMissingImports,reportMissingModuleSource]

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")

STATUS_TONES: dict[str, str] = {
    "submitted": "info",
    "running": "warning",
    "completed": "success",
    "failed": "destructive",
    "unknown": "info",
}

DECISION_TONES: dict[str, str] = {
    "APPROVED": "success",
    "CONDITIONAL_APPROVAL": "warning",
    "REJECTED": "destructive",
    "REFERRED_TO_COMMITTEE": "info",
}

# ── API client ──────────────────────────────────────────────────

def api(method: str, endpoint: str, quiet: bool = False, **kwargs: Any) -> Any:
    timeout = kwargs.pop("timeout", 180)
    try:
        resp = requests.request(
            method=method.upper(),
            url=f"{API_BASE}{endpoint}",
            timeout=timeout,
            **kwargs,
        )
        resp.raise_for_status()
        if "application/json" in resp.headers.get("content-type", ""):
            return resp.json()
        return resp.text
    except requests.HTTPError as exc:
        if not quiet:
            detail = exc.response.text[:240] if exc.response is not None else str(exc)
            st.error(f"API error on {endpoint}: {detail}")
        return None
    except requests.RequestException as exc:
        if not quiet:
            st.error(
                "Cannot reach backend at "
                f"{API_BASE}. Start the API with `python run.py` or "
                "`uvicorn src.api.main:app --host 0.0.0.0 --port 8000`. "
                f"Details: {exc}"
            )
        return None


def api_bytes(endpoint: str, quiet: bool = False, **kwargs: Any) -> bytes | None:
    timeout = kwargs.pop("timeout", 180)
    try:
        resp = requests.get(f"{API_BASE}{endpoint}", timeout=timeout, **kwargs)
        resp.raise_for_status()
        return resp.content
    except requests.HTTPError as exc:
        if not quiet:
            detail = exc.response.text[:240] if exc.response is not None else str(exc)
            st.error(f"API error on {endpoint}: {detail}")
        return None
    except requests.RequestException as exc:
        if not quiet:
            st.error(f"Cannot reach backend at {API_BASE}. Details: {exc}")
        return None


# ── Session state helpers ───────────────────────────────────────

def push_log(headline: str, copy: str, tone: str = "info") -> None:
    stamp = datetime.utcnow().strftime("%H:%M:%S")
    st.session_state["terminal_log"] = (
        st.session_state["terminal_log"]
        + [{"stamp": stamp, "headline": headline, "copy": copy, "tone": tone}]
    )[-20:]


# ── Formatters ──────────────────────────────────────────────────

def fmt_inr_cr(value: Any) -> str:
    if value in (None, ""):
        return "—"
    try:
        return f"₹{float(value):,.2f} Cr"
    except (TypeError, ValueError):
        return str(value)


def fmt_pct(value: Any, digits: int = 1) -> str:
    if value in (None, ""):
        return "—"
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return str(value)


def fmt_ts(value: Any) -> str:
    if not value:
        return "—"
    try:
        cleaned = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned).strftime("%d %b %Y %H:%M")
    except ValueError:
        return str(value)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ── Tone mapping ────────────────────────────────────────────────

def tone_for_status(status: str | None) -> str:
    return STATUS_TONES.get((status or "unknown").lower(), "info")


def tone_for_decision(decision: str | None) -> str:
    return DECISION_TONES.get((decision or "").upper(), "info")


# ── Data loaders ────────────────────────────────────────────────

def load_portfolio() -> list[dict[str, Any]]:
    apps = api("get", "/api/applications", quiet=True) or []
    return sorted(apps, key=lambda a: a.get("started_at") or "", reverse=True)


def load_backend_info() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        api("get", "/health", quiet=True) or {},
        api("get", "/info", quiet=True) or {},
    )


def load_application_package(app_id: str) -> dict[str, Any]:
    return {
        "status": api("get", f"/api/applications/{app_id}/status", quiet=True),
        "decision": api("get", f"/api/applications/{app_id}/decision", quiet=True),
        "cam": api("get", f"/api/applications/{app_id}/cam", quiet=True),
        "fraud": api("get", f"/api/applications/{app_id}/fraud", quiet=True),
        "research": api("get", f"/api/applications/{app_id}/research", quiet=True),
        "xai": api("get", f"/api/applications/{app_id}/xai", quiet=True),
        "debate": api("get", f"/api/applications/{app_id}/debate", quiet=True),
        "audit": api("get", f"/api/applications/{app_id}/audit-trail", quiet=True) or [],
    }


# ── Selection helpers ───────────────────────────────────────────

def hydrate_selection(apps: list[dict[str, Any]]) -> None:
    ids = [a.get("application_id") for a in apps]
    if not ids:
        st.session_state["selected_application"] = None
        return
    if st.session_state["selected_application"] not in ids:
        st.session_state["selected_application"] = ids[0]


def application_label(app: dict[str, Any]) -> str:
    company = app.get("company", "Unknown")
    app_id = app.get("application_id", "")
    amount = fmt_inr_cr(app.get("requested_amount_cr"))
    status = (app.get("status") or "unknown").upper()
    return f"{company}  ·  {app_id}  ·  {status}  ·  {amount}"


def current_application(apps: list[dict[str, Any]]) -> dict[str, Any] | None:
    sel = st.session_state["selected_application"]
    for app in apps:
        if app.get("application_id") == sel:
            return app
    return apps[0] if apps else None


def dataframe_or_none(
    rows: list[dict[str, Any]], columns: list[str] | None = None
) -> pd.DataFrame | None:
    if not rows:
        return None
    frame = pd.DataFrame(rows)
    if isinstance(frame, pd.Series):
        frame = frame.to_frame().T
    if columns:
        keep = [c for c in columns if c in frame.columns]
        frame = frame[keep]
    return frame
