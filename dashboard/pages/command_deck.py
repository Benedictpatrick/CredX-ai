"""Command Deck — portfolio surveillance and live telemetry."""
from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

from dashboard.components.charts import portfolio_bar, portfolio_donut
from dashboard.components.data import (
    api,
    fmt_inr_cr,
    fmt_ts,
    push_log,
    safe_float,
    tone_for_status,
)
from dashboard.components.markup import (
    divider,
    empty_state,
    info_grid,
    list_card,
    metric_card,
    page_header,
    panel,
    pill,
    prose,
    section_title,
    terminal,
)


def render(
    apps: list[dict[str, Any]],
    selected_app: dict[str, Any] | None,
    health: dict[str, Any],
    info: dict[str, Any],
) -> None:
    total_requested = sum(safe_float(a.get("requested_amount_cr")) for a in apps)
    running = sum(1 for a in apps if a.get("status") == "running")
    completed = sum(1 for a in apps if a.get("status") == "completed")
    submitted = sum(1 for a in apps if a.get("status") == "submitted")
    backend = health.get("status", "offline")

    st.markdown(
        page_header(
            title="Portfolio Surveillance",
            description="Live telemetry across all corporate credit cases — exposure, pipeline state, and operator events in a single surface.",
            eyebrow="COMMAND DECK",
            stats=[
                ("Total cases", str(len(apps))),
                ("Running", str(running)),
                ("Capital under review", fmt_inr_cr(total_requested)),
                ("Pending review", str(submitted)),
            ],
        ),
        unsafe_allow_html=True,
    )

    spotlight_l, spotlight_r = st.columns([1.15, 0.85])
    with spotlight_l:
        if selected_app:
            status_tone = tone_for_status(selected_app.get("status"))
            st.markdown(
                section_title("Portfolio spotlight", "CONTROL TOWER"),
                unsafe_allow_html=True,
            )
            st.markdown(
                panel(
                    f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:var(--space-4);">'
                    f'<div>'
                    f'<div class="cx-eyebrow">Focused application</div>'
                    f'<div style="font-family:var(--font-display);font-size:var(--text-2xl);font-weight:600;letter-spacing:-0.03em;margin-top:var(--space-1);">{escape(selected_app.get("company", "Unknown"))}</div>'
                    f'<div style="font-family:var(--font-mono);font-size:var(--text-xs);color:var(--color-text-tertiary);margin-top:var(--space-2);font-variant-numeric:tabular-nums;">'
                    f'{escape(selected_app.get("application_id", ""))} · {fmt_inr_cr(selected_app.get("requested_amount_cr"))}'
                    f'</div>'
                    f'</div>{pill(selected_app.get("status", "unknown"), status_tone)}</div>'
                    f'{divider()}'
                    f'{info_grid([("Requested", fmt_inr_cr(selected_app.get("requested_amount_cr")), None), ("Started", fmt_ts(selected_app.get("started_at")), None), ("Model", str(info.get("llm_model", "n/a")), None)])}'
                ),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                empty_state("No case selected", "Select an application from the sidebar to open the live portfolio spotlight."),
                unsafe_allow_html=True,
            )
    with spotlight_r:
        st.markdown(section_title("System posture", "LIVE OPS"), unsafe_allow_html=True)
        st.markdown(
            panel(
                f'{info_grid([("Engine", str(backend).upper(), None), ("Vision", str(info.get("vision_model", "n/a")), None), ("Completed", str(completed), None), ("Running", str(running), None)])}'
            ),
            unsafe_allow_html=True,
        )

        if selected_app and str(selected_app.get("status", "submitted")).lower() != "completed":
            if st.button("Run selected pipeline", type="primary", key="cmd_run_selected"):
                app_id = str(selected_app.get("application_id") or "")
                outcome = api("post", f"/api/applications/{app_id}/run", timeout=600)
                if outcome:
                    push_log("pipeline_run", f"{app_id} → {outcome.get('decision', 'UNKNOWN')}", "success")
                    st.success(f"Pipeline completed for {app_id} — {outcome.get('decision', 'UNKNOWN')}")
                    st.rerun()

    # ── Key metrics row ─────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            metric_card("Applications", str(len(apps)), "Total submitted cases"),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            metric_card("Completed", str(completed), "Full CAM generated", "success"),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            metric_card("Running", str(running), "Active orchestration", "warning"),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            metric_card(
                "Backend",
                backend.upper(),
                "Engine health",
                "success" if backend == "healthy" else "destructive",
            ),
            unsafe_allow_html=True,
        )

    # ── Charts row ──────────────────────────────────────────
    left, right = st.columns([1.4, 1])
    with left:
        st.markdown(section_title("Exposure map", "BY COMPANY"), unsafe_allow_html=True)
        chart = portfolio_bar(apps)
        if chart:
            st.plotly_chart(chart, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown(empty_state("No exposure data", "Submit an application to see capital distribution."), unsafe_allow_html=True)

    with right:
        st.markdown(section_title("Status mix", "PIPELINE"), unsafe_allow_html=True)
        donut = portfolio_donut(apps)
        if donut:
            st.plotly_chart(donut, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown(empty_state("No status data", "Cases appear after submission."), unsafe_allow_html=True)

    # ── Queue + Feed row ────────────────────────────────────
    q_col, f_col = st.columns([1, 1.1])
    with q_col:
        st.markdown(section_title("Active queue", "NEWEST FIRST"), unsafe_allow_html=True)
        if apps:
            for a in apps[:6]:
                meta = f"{a.get('application_id', '')}  ·  {fmt_inr_cr(a.get('requested_amount_cr'))}  ·  {fmt_ts(a.get('started_at'))}"
                st.markdown(
                    list_card(
                        a.get("company", "Unknown"),
                        meta,
                        a.get("status", "unknown"),
                        tone_for_status(a.get("status")),
                    ),
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                empty_state("Queue empty", "Launch a case from Intake Studio or Demo Lab."),
                unsafe_allow_html=True,
            )

    with f_col:
        st.markdown(section_title("Operator feed", "SESSION"), unsafe_allow_html=True)
        st.markdown(terminal(st.session_state["terminal_log"]), unsafe_allow_html=True)
