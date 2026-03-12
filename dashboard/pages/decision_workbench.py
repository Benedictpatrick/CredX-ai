# pyright: reportMissingImports=false, reportMissingModuleSource=false
"""Decision Workbench — committee-grade underwriting review surface."""
from __future__ import annotations

import json
from html import escape
from typing import Any

import streamlit as st  # type: ignore[reportMissingImports,reportMissingModuleSource]

from dashboard.components.charts import (
    debate_chart,
    financials_chart,
    five_cs_radar,
    shap_chart,
    workflow_timeline_chart,
)
from dashboard.components.data import (
    api,
    api_bytes,
    dataframe_or_none,
    fmt_inr_cr,
    fmt_pct,
    fmt_ts,
    load_application_package,
    push_log,
    safe_float,
    tone_for_decision,
    tone_for_status,
)
from dashboard.components.markup import (
    divider,
    empty_state,
    feed_item,
    info_grid,
    kv_row,
    loading_state,
    metric_card,
    page_header,
    panel,
    pill,
    prose,
    section_title,
    signal_card,
    terminal,
)


def _extract_feature_metric(xai: dict[str, Any], feature_name: str) -> str:
    for item in xai.get("feature_importance") or []:
        if item.get("feature_name") == feature_name:
            value = item.get("value")
            if isinstance(value, float):
                return f"{value:.2f}"
            return str(value)
    return "—"


def _count(items: Any) -> int:
    return len(items) if isinstance(items, list) else 0


def render(
    selected_app: dict[str, Any] | None,
    info: dict[str, Any],
) -> None:
    if not selected_app:
        st.markdown(
            page_header(
                title="No Application Selected",
                description="Create a borrower case from Intake Studio or launch a synthetic company from Demo Lab to unlock the decision workbench.",
                eyebrow="DECISION WORKBENCH",
                stats=[("Status", "Awaiting"), ("Decision", "—"), ("Audit", "—")],
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            empty_state("Waiting for intake", "Select an application from the sidebar to review."),
            unsafe_allow_html=True,
        )
        return

    app_id = str(selected_app.get("application_id") or "")
    pkg = load_application_package(app_id)

    status = pkg.get("status") or {}
    cam = pkg.get("cam") or {}
    decision = pkg.get("decision") or cam.get("decision") or {}
    fraud = pkg.get("fraud") or cam.get("fraud_report") or {}
    research = pkg.get("research") or cam.get("research_report") or {}
    xai = pkg.get("xai") or cam.get("shap_explanation") or {}
    debate = pkg.get("debate") or cam.get("debate_result") or {}
    five_cs = cam.get("five_cs") or {}

    decision_name = decision.get("decision") or "PENDING"
    fraud_score = safe_float(fraud.get("overall_fraud_score"))
    sector_outlook = str(research.get("sector_outlook") or "Monitoring")
    alert_count = _count(research.get("regulatory_alerts"))
    news_count = _count(research.get("news_items"))
    audit_count = _count(pkg.get("audit"))
    primary_diligence = _extract_feature_metric(xai, "primary_diligence_score")
    leverage = _extract_feature_metric(xai, "leverage_score")
    cashflow = _extract_feature_metric(xai, "cashflow_score")
    condition_count = _count(decision.get("conditions"))
    blocker_count = _count(decision.get("rejection_reasons"))
    pipeline_running = str(status.get("status", "")).lower() == "running"

    # ── Header ──────────────────────────────────────────────
    st.markdown(
        page_header(
            title=selected_app.get("company", "Decision Workbench"),
            description="Committee-grade decision review — recommendation, risk posture, sector research, explainability, and full audit trace.",
            eyebrow="DECISION WORKBENCH",
            stats=[
                ("Application", selected_app.get("application_id", "—")),
                ("Phase", str(status.get("current_phase", "submitted")).upper()),
                ("Updated", fmt_ts(status.get("completed_at") or status.get("started_at"))),
                ("Audit events", str(audit_count)),
            ],
        ),
        unsafe_allow_html=True,
    )

    # ── Action bar ──────────────────────────────────────────
    a1, a2, a3 = st.columns([1.1, 1.1, 0.9])
    with a1:
        if st.button("Run full pipeline", type="primary", key="wb_run"):
            outcome = api("post", f"/api/applications/{app_id}/run", timeout=600)
            if outcome:
                push_log("pipeline_run", f'{app_id} → {outcome.get("decision", "UNKNOWN")}', "success")
                st.success(f'Pipeline completed — {outcome.get("decision", "UNKNOWN")}')
                st.rerun()
    with a2:
        if st.button("Refresh workbench", key="wb_refresh"):
            push_log("refresh", f"Refreshed intelligence for {app_id}", "info")
            st.rerun()
    with a3:
        st.download_button(
            "Download CAM",
            data=json.dumps(cam, indent=2, default=str) if cam else "{}",
            file_name=f"{app_id}_cam.json",
            mime="application/json",
        )

    if cam:
        docx_bytes = api_bytes(f"/api/applications/{app_id}/cam.docx", quiet=True)
        st.download_button(
            "Download CAM DOCX",
            data=docx_bytes or b"",
            file_name=f"{app_id}_credit_appraisal_memo.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            disabled=not bool(docx_bytes),
        )

    # ── Key metrics ─────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            metric_card(
                "Decision",
                decision_name.replace("_", " "),
                "Underwriting recommendation",
                tone_for_decision(decision_name),
            ),
            unsafe_allow_html=True,
        )
    with k2:
        grade = str(decision.get("risk_grade", "—"))
        st.markdown(
            metric_card(
                "Risk grade",
                grade,
                f"Cashflow {cashflow} · Leverage {leverage}",
                "warning" if grade in {"BB", "B", "C", "D"} else "accent",
            ),
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            metric_card(
                "Approved amount",
                fmt_inr_cr(decision.get("approved_amount_cr")),
                f"Conditions {condition_count} · Blockers {blocker_count}",
                "success",
            ),
            unsafe_allow_html=True,
        )
    with k4:
        fraud_tone = "destructive" if fraud_score > 0.6 else "warning" if fraud_score > 0.3 else "success"
        st.markdown(
            metric_card("Fraud score", f"{fraud_score:.2f}", f"{sector_outlook} · {alert_count} alerts", fraud_tone),
            unsafe_allow_html=True,
        )

    # ── Tabbed deep-dive ────────────────────────────────────
    overview_tab, cam_tab, risk_tab, xai_tab, audit_tab = st.tabs([
        "Overview",
        "CAM",
        "Risk & research",
        "Explainability",
        "Audit trail",
    ])

    # ─ Overview ─────────────────────────────────────────────
    with overview_tab:
        st.markdown(section_title("Workflow execution", "PIPELINE MAP"), unsafe_allow_html=True)
        st.plotly_chart(
            workflow_timeline_chart(
                audit_rows=pkg.get("audit") or [],
                current_phase=str(status.get("current_phase", "submitted")),
                status=str(status.get("status", "submitted")),
            ),
            use_container_width=True,
            config={"displayModeBar": False},
        )

        brief_l, brief_r = st.columns([1.2, 0.8])
        with brief_l:
            st.markdown(section_title("Committee brief", "READOUT"), unsafe_allow_html=True)
            st.markdown(
                panel(
                    f'<div class="cx-eyebrow">Decision posture</div>'
                    f'<div style="display:flex;justify-content:space-between;gap:var(--space-5);align-items:flex-start;">'
                    f'<div>'
                    f'<div style="font-family:var(--font-display);font-size:32px;font-weight:600;line-height:1.05;letter-spacing:-0.035em;">'
                    f'{escape(decision_name.replace("_", " "))}</div>'
                    f'{prose("Committee-ready output built from underwriting score, fraud surveillance, external research, and explainability traces.")}'
                    f'</div>'
                    f'{pill(str(status.get("status", "unknown")).upper(), tone_for_status(status.get("status")))}'
                    f'</div>'
                    f'{divider()}'
                    f'{kv_row("Recommendation", decision_name.replace("_", " "))}'
                    f'{kv_row("Risk grade", str(decision.get("risk_grade", "—")))}'
                    f'{kv_row("Policy amount", fmt_inr_cr(decision.get("approved_amount_cr")))}'
                    f'{kv_row("Primary diligence", primary_diligence)}'
                ),
                unsafe_allow_html=True,
            )
        with brief_r:
            st.markdown(section_title("Driver ledger", "WHAT MOVED THE CALL"), unsafe_allow_html=True)
            st.markdown(
                panel(
                    f'{kv_row("Fraud threat", f"{fraud_score:.2f}")}'
                    f'{kv_row("Sector outlook", sector_outlook)}'
                    f'{kv_row("Regulatory alerts", str(alert_count))}'
                    f'{kv_row("Research items", str(news_count))}'
                    f'{kv_row("Audit entries", str(audit_count))}'
                ),
                unsafe_allow_html=True,
            )

        left, right = st.columns([1.15, 1])
        with left:
            st.markdown(section_title("Committee snapshot", "DECISION CORE"), unsafe_allow_html=True)
            conditions = decision.get("conditions") or []
            rejections = decision.get("rejection_reasons") or []
            summary = cam.get("executive_summary") or "CAM not yet available. Run the pipeline to generate a recommendation."

            status_pill = pill(status.get("status", "unknown"), tone_for_status(status.get("status")))
            st.markdown(
                panel(
                    f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:var(--space-4);">'
                    f'<div>'
                    f'<div class="cx-eyebrow">Recommendation</div>'
                    f'<div style="font-family:var(--font-display);font-size:var(--text-2xl);font-weight:700;'
                    f'letter-spacing:-0.03em;margin-top:var(--space-1);">{escape(decision_name.replace("_", " "))}</div>'
                    f'<div style="font-size:var(--text-sm);color:var(--color-text-tertiary);margin-top:var(--space-2);'
                    f'font-variant-numeric:tabular-nums;">'
                    f'Risk premium: {fmt_pct(decision.get("risk_premium_pct"), 2)} · '
                    f'Interest: {fmt_pct(decision.get("interest_rate_pct"), 2)}</div>'
                    f'</div>{status_pill}</div>'
                    f'{divider()}'
                    f'<div style="font-size:var(--text-sm);color:var(--color-text-secondary);line-height:1.6;">'
                    f'{escape(summary)}</div>'
                ),
                unsafe_allow_html=True,
            )
            st.markdown(section_title("Interlocks", "COMMITTEE GATES"), unsafe_allow_html=True)
            if conditions:
                for item in conditions:
                    st.markdown(feed_item("Condition", item), unsafe_allow_html=True)
            if rejections:
                for item in rejections:
                    st.markdown(feed_item("Blocker", item), unsafe_allow_html=True)
            if not conditions and not rejections:
                st.markdown(
                    empty_state("No interlocks", "Run the pipeline to generate covenants or rejection blockers."),
                    unsafe_allow_html=True,
                )

        with right:
            st.markdown(section_title("Five Cs radar", "ANATOMY"), unsafe_allow_html=True)
            radar = five_cs_radar(five_cs)
            if radar:
                st.plotly_chart(radar, use_container_width=True, config={"displayModeBar": False})
            elif pipeline_running:
                st.markdown(
                    loading_state("Scoring Five Cs", "The underwriter and research nodes are still assembling the borrower profile."),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    empty_state("No Five Cs data", "Scores appear after a completed pipeline run."),
                    unsafe_allow_html=True,
                )

        lo_l, lo_r = st.columns(2)
        with lo_l:
            st.markdown(section_title("Financial trajectory", "HISTORICAL"), unsafe_allow_html=True)
            fin_fig = financials_chart(cam.get("financial_metrics") or [])
            if fin_fig:
                st.plotly_chart(fin_fig, use_container_width=True, config={"displayModeBar": False})
            elif pipeline_running:
                st.markdown(
                    loading_state("Building financial trajectory", "Historical financials will render once ingestion and memo generation complete."),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(empty_state("No financials", "Time-series data not yet available."), unsafe_allow_html=True)
        with lo_r:
            st.markdown(section_title("Bull vs Bear", "DEBATE"), unsafe_allow_html=True)
            deb_fig = debate_chart(debate)
            if deb_fig:
                st.plotly_chart(deb_fig, use_container_width=True, config={"displayModeBar": False})
            elif pipeline_running:
                st.markdown(
                    loading_state("Running committee simulation", "Bull and bear arguments appear after the debate stage finishes."),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(empty_state("No debate data", "Committee simulation runs after pipeline execution."), unsafe_allow_html=True)

    # ─ CAM ──────────────────────────────────────────────────
    with cam_tab:
        st.markdown(section_title("Memo narrative", "CREDIT APPRAISAL"), unsafe_allow_html=True)
        st.markdown(
            panel(
                f'<div class="cx-eyebrow">Executive summary</div>'
                f'{prose(cam.get("executive_summary", "No CAM generated yet."))}'
                f'{divider()}'
                f'<div class="cx-eyebrow">Risk narrative</div>'
                f'{prose(cam.get("risk_narrative", "Risk narrative not yet available."))}'
            ),
            unsafe_allow_html=True,
        )

        fin_df = dataframe_or_none(
            cam.get("financial_metrics") or [],
            ["fiscal_year", "revenue_cr", "ebitda_cr", "pat_cr", "net_worth_cr", "current_ratio", "debt_equity_ratio", "dscr"],
        )
        if fin_df is not None:
            st.markdown(section_title("Financial metrics", "REPORTED"), unsafe_allow_html=True)
            st.dataframe(fin_df, use_container_width=True, hide_index=True)
        elif pipeline_running:
            st.markdown(loading_state("Formatting financial tables", "The CAM tables appear once memo assembly finishes."), unsafe_allow_html=True)

        bank_df = dataframe_or_none(
            cam.get("bank_summaries") or [],
            ["bank_name", "avg_monthly_balance_cr", "total_credits_cr", "total_debits_cr", "peak_utilization_pct", "mandate_bounces", "inward_return_count"],
        )
        if bank_df is not None:
            st.markdown(section_title("Bank conduct", "STATEMENT DIGEST"), unsafe_allow_html=True)
            st.dataframe(bank_df, use_container_width=True, hide_index=True)
        elif pipeline_running:
            st.markdown(loading_state("Reconciling bank conduct", "Statement digest is being assembled from ingestion outputs."), unsafe_allow_html=True)

        gst_df = dataframe_or_none(
            cam.get("gst_summaries") or [],
            ["period", "gstr1_turnover_cr", "gstr3b_turnover_cr", "gstr2a_purchases_cr", "gstr2b_purchases_cr", "turnover_mismatch_pct"],
        )
        if gst_df is not None:
            st.markdown(section_title("GST triangulation", "FILING"), unsafe_allow_html=True)
            st.dataframe(gst_df, use_container_width=True, hide_index=True)
        elif pipeline_running:
            st.markdown(loading_state("Triangulating GST filings", "Tax consistency checks are still running."), unsafe_allow_html=True)

    # ─ Risk & research ──────────────────────────────────────
    with risk_tab:
        t_l, t_r = st.columns(2)
        with t_l:
            st.markdown(section_title("Fraud posture", "SHERLOCK"), unsafe_allow_html=True)
            severity_pill = pill(
                str(fraud.get("severity", "CLEAN")),
                "destructive" if fraud_score > 0.6 else "warning" if fraud_score > 0.3 else "success",
            )
            st.markdown(
                panel(
                    f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:var(--space-4);">'
                    f'<div>'
                    f'<div class="cx-eyebrow">Threat score</div>'
                    f'<div style="font-family:var(--font-display);font-size:var(--text-2xl);font-weight:700;'
                    f'letter-spacing:-0.03em;font-variant-numeric:tabular-nums;margin-top:var(--space-1);">'
                    f'{fraud_score:.2f}</div>'
                    f'<div style="font-size:var(--text-xs);color:var(--color-text-tertiary);margin-top:var(--space-2);'
                    f'font-variant-numeric:tabular-nums;">'
                    f'Severity: {escape(str(fraud.get("severity", "CLEAN")))} · '
                    f'GST-bank mismatch: {fmt_pct(fraud.get("gst_bank_mismatch_pct"))}</div>'
                    f'</div>{severity_pill}</div>'
                ),
                unsafe_allow_html=True,
            )
            for sig in fraud.get("signals", [])[:8]:
                sev = str(sig.get("severity", "LOW")).upper()
                evidence = "; ".join(sig.get("evidence", [])[:3])
                st.markdown(
                    signal_card(
                        sig.get("signal_type", "signal").replace("_", " ").title(),
                        sig.get("description", ""),
                        evidence,
                        sev,
                    ),
                    unsafe_allow_html=True,
                )

        with t_r:
            st.markdown(section_title("Research posture", "SCHOLAR"), unsafe_allow_html=True)
            st.markdown(
                panel(
                    f'<div class="cx-eyebrow">Sector outlook</div>'
                    f'<div style="font-family:var(--font-display);font-size:var(--text-xl);font-weight:700;'
                    f'letter-spacing:-0.03em;margin-top:var(--space-1);">'
                    f'{escape(research.get("sector_outlook", "No outlook yet"))}</div>'
                    f'{info_grid([('"'"'Litigation'"'"', f"{safe_float(research.get('litigation_score')):.2f}", None), ('"'"'News sentiment'"'"', f"{safe_float(research.get('news_sentiment')):.2f}", None), ('"'"'Research coverage'"'"', str(news_count), None)])}'
                    f'{divider()}'
                    f'{kv_row("Research coverage", str(news_count))}'
                    f'{kv_row("Regulatory alerts", str(alert_count))}'
                ),
                unsafe_allow_html=True,
            )
            for alert in (research.get("regulatory_alerts") or []):
                st.markdown(
                    feed_item("Regulatory", "Alert", alert),
                    unsafe_allow_html=True,
                )
            for item in (research.get("news_items") or [])[:4]:
                body = item.get("summary") or item.get("headline", "")
                st.markdown(
                    feed_item(
                        str(item.get("source", "news")),
                        item.get("headline", "Untitled"),
                        body,
                    ),
                    unsafe_allow_html=True,
                )

            lit_df = dataframe_or_none(
                research.get("litigation_records") or [],
                ["case_number", "case_type", "court", "status", "potential_liability_cr", "summary"],
            )
            if lit_df is not None:
                st.markdown(section_title("Litigation records", "CASE SHEET"), unsafe_allow_html=True)
                st.dataframe(lit_df, use_container_width=True, hide_index=True)

    # ─ Explainability ───────────────────────────────────────
    with xai_tab:
        st.markdown(section_title("SHAP attribution", "DECISION DECOMPOSITION"), unsafe_allow_html=True)
        shap_fig = shap_chart(xai)
        if shap_fig:
            st.plotly_chart(shap_fig, use_container_width=True, config={"displayModeBar": False})
        elif pipeline_running:
            st.markdown(
                loading_state("Computing attribution", "Feature contributions are generated after underwriting and XAI complete."),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                empty_state("No explainability data", "SHAP payload appears after the underwriter node runs."),
                unsafe_allow_html=True,
            )

        if xai:
            narrative = xai.get("narrative")
            if narrative:
                st.markdown(
                    panel(
                        f'<div class="cx-eyebrow">AI narrative</div>'
                        f'{prose(narrative)}'
                    ),
                    unsafe_allow_html=True,
                )
            feat_df = dataframe_or_none(
                xai.get("feature_importance") or [],
                ["display_name", "value", "shap_value", "direction", "impact_pct"],
            )
            if feat_df is not None:
                st.markdown(section_title("Feature ledger", "ATTRIBUTION"), unsafe_allow_html=True)
                st.dataframe(feat_df, use_container_width=True, hide_index=True)

    # ─ Audit trail ──────────────────────────────────────────
    with audit_tab:
        st.markdown(section_title("Execution trace", "GUARDIAN LOGS"), unsafe_allow_html=True)
        audit_rows = pkg.get("audit", [])
        if audit_rows:
            for row in audit_rows:
                st.markdown(
                    feed_item(
                        fmt_ts(row.get("timestamp")),
                        f'{row.get("agent", "agent")} → {row.get("action", "action")}',
                        row.get("output_summary") or row.get("reasoning_trace") or row.get("input_summary") or "No summary.",
                    ),
                    unsafe_allow_html=True,
                )
        elif pipeline_running:
            st.markdown(
                loading_state("Collecting audit trace", "Guardian logs will appear as each agent finishes its stage."),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                empty_state("No audit entries", "Execution trace populates after pipeline runs."),
                unsafe_allow_html=True,
            )

        st.markdown(section_title("Operator terminal", "SESSION"), unsafe_allow_html=True)
        st.markdown(terminal(st.session_state["terminal_log"]), unsafe_allow_html=True)
