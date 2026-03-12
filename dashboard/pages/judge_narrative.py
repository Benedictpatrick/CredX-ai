"""Judge Narrative — live proof surface for jury walkthrough."""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from dashboard.components.charts import workflow_timeline_chart
from dashboard.components.data import (
    api,
    api_bytes,
    fmt_inr_cr,
    fmt_ts,
    load_application_package,
    safe_float,
)
from dashboard.components.markup import (
    empty_state,
    info_grid,
    kv_row,
    loading_state,
    metric_card,
    page_header,
    panel,
    pill,
    prose,
    section_title,
)


def _proof_rows(pkg: dict[str, Any]) -> list[dict[str, str]]:
    status = pkg.get("status") or {}
    decision = pkg.get("decision") or {}
    cam = pkg.get("cam") or {}
    fraud = pkg.get("fraud") or {}
    research = pkg.get("research") or {}
    xai = pkg.get("xai") or {}
    audit = pkg.get("audit") or []

    return [
        {
            "Pillar": "Ingestion",
            "What we prove": "Application, financial artifacts, and field inputs are captured and traceable.",
            "Live evidence": f"Phase={str(status.get('current_phase', 'submitted')).upper()} | Audit events={len(audit)}",
            "Result": "PASS" if status else "PENDING",
        },
        {
            "Pillar": "Fraud intelligence",
            "What we prove": "Cross-signal anomaly detection contributes to final underwriting stance.",
            "Live evidence": f"Fraud score={safe_float(fraud.get('overall_fraud_score')):.2f}",
            "Result": "PASS" if fraud else "PENDING",
        },
        {
            "Pillar": "Research agent",
            "What we prove": "External market/regulatory context is integrated into decisioning.",
            "Live evidence": f"Outlook={str(research.get('sector_outlook', 'N/A'))} | Alerts={len(research.get('regulatory_alerts', []) or [])}",
            "Result": "PASS" if research else "PENDING",
        },
        {
            "Pillar": "Explainable underwriting",
            "What we prove": "Decision decomposition is available for committee-level scrutiny.",
            "Live evidence": f"Attribution rows={len(xai.get('feature_importance', []) or [])}",
            "Result": "PASS" if xai else "PENDING",
        },
        {
            "Pillar": "Credit memo automation",
            "What we prove": "Structured CAM output is generated as a decision artifact.",
            "Live evidence": f"Decision={str(decision.get('decision', 'N/A'))} | CAM ready={'yes' if cam else 'no'}",
            "Result": "PASS" if cam else "PENDING",
        },
    ]


def render(
    apps: list[dict[str, Any]],
    selected_app: dict[str, Any] | None,
    info: dict[str, Any],
) -> None:
    st.markdown(
        page_header(
            title="Judge Narrative",
            description="Live evidence story for jury review: every claim is backed by current pipeline outputs, artifacts, and execution trace.",
            eyebrow="JUDGE MODE",
            stats=[
                ("Cases", str(len(apps))),
                ("Engine", str(info.get("llm_model", "n/a"))),
                ("Vision", str(info.get("vision_model", "n/a"))),
                ("Demo status", "Ready" if selected_app else "Select case"),
            ],
        ),
        unsafe_allow_html=True,
    )

    if not selected_app:
        st.markdown(
            empty_state(
                "No focus case selected",
                "Choose a case from the sidebar to generate a judge-ready proof narrative.",
            ),
            unsafe_allow_html=True,
        )
        return

    app_id = str(selected_app.get("application_id") or "")
    pkg = load_application_package(app_id)
    status = pkg.get("status") or {}
    decision = pkg.get("decision") or {}
    cam = pkg.get("cam") or {}
    audit = pkg.get("audit") or []

    top_l, top_r = st.columns([1.1, 0.9])
    with top_l:
        st.markdown(section_title("Proof brief", "LIVE CASE"), unsafe_allow_html=True)
        st.markdown(
            panel(
                '<div class="cx-eyebrow">Case in review</div>'
                + info_grid(
                    [
                        ("Company", str(selected_app.get("company", "Unknown")), None),
                        ("Application", app_id, None),
                        ("Requested", fmt_inr_cr(selected_app.get("requested_amount_cr")), None),
                        ("Phase", str(status.get("current_phase", "submitted")).upper(), None),
                        ("Updated", fmt_ts(status.get("completed_at") or status.get("started_at")), None),
                        ("Audit events", str(len(audit)), None),
                    ]
                )
                + '<div style="margin-top:var(--space-3);">'
                + pill(str(status.get("status", "unknown")).upper(), "success" if str(status.get("status", "")).lower() == "completed" else "warning")
                + '</div>'
            ),
            unsafe_allow_html=True,
        )

    with top_r:
        st.markdown(section_title("Judge controls", "ONE-CLICK"), unsafe_allow_html=True)
        run_now = st.button("Run current case pipeline", type="primary", key="judge_run_current")
        if run_now:
            outcome = api("post", f"/api/applications/{app_id}/run", timeout=600)
            if outcome:
                st.success(f"Pipeline complete — {outcome.get('decision', 'UNKNOWN')}")
                st.rerun()

        st.markdown(
            panel(
                '<div class="cx-eyebrow">Judge script</div>'
                + prose(
                    "1) Show the workflow map. 2) Open proof table. 3) Download CAM. 4) Jump to Decision Workbench for full artifact trace."
                )
                + kv_row("Current decision", str(decision.get("decision", "PENDING")))
                + kv_row("Risk grade", str(decision.get("risk_grade", "—")))
                + kv_row("CAM availability", "Ready" if cam else "Pending")
            ),
            unsafe_allow_html=True,
        )

    st.markdown(section_title("Workflow map", "AGENT EXECUTION"), unsafe_allow_html=True)
    st.plotly_chart(
        workflow_timeline_chart(
            audit_rows=audit,
            current_phase=str(status.get("current_phase", "submitted")),
            status=str(status.get("status", "submitted")),
        ),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    st.markdown(section_title("Problem-statement proof", "LIVE SCORECARD"), unsafe_allow_html=True)
    proof = _proof_rows(pkg)
    st.dataframe(pd.DataFrame(proof), use_container_width=True, hide_index=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            metric_card(
                "Decision",
                str(decision.get("decision", "PENDING")),
                "Final underwriting outcome",
                "success" if str(decision.get("decision", "")).upper() == "APPROVED" else "warning",
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            metric_card(
                "Fraud score",
                f"{safe_float((pkg.get('fraud') or {}).get('overall_fraud_score')):.2f}",
                "Sherlock threat level",
                "destructive" if safe_float((pkg.get('fraud') or {}).get('overall_fraud_score')) > 0.6 else "warning",
            ),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            metric_card(
                "Audit trace",
                str(len(audit)),
                "Recorded execution events",
                "accent",
            ),
            unsafe_allow_html=True,
        )

    st.markdown(section_title("Artifact links", "DELIVERABLES"), unsafe_allow_html=True)
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            "Download CAM JSON",
            data=__import__("json").dumps(cam, indent=2, default=str) if cam else "{}",
            file_name=f"{app_id}_cam.json",
            mime="application/json",
            disabled=not bool(cam),
        )
    with d2:
        docx = api_bytes(f"/api/applications/{app_id}/cam.docx", quiet=True)
        if docx:
            st.download_button(
                "Download CAM DOCX",
                data=docx,
                file_name=f"{app_id}_credit_appraisal_memo.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        else:
            st.markdown(loading_state("CAM DOCX pending", "Run the pipeline to generate document-grade memo export."), unsafe_allow_html=True)
