"""Demo Lab — synthetic scenario testing and rapid pipeline execution."""
from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.components.data import (
    api,
    current_application,
    fmt_inr_cr,
    push_log,
)
from dashboard.components.markup import (
    empty_state,
    info_grid,
    metric_card,
    page_header,
    panel,
    prose,
    section_title,
    terminal,
)


def render(apps: list[dict[str, Any]]) -> None:
    active_cases = len(apps)
    st.markdown(
        page_header(
            title="Synthetic Deal Lab",
            description="Spawn benchmark borrowers, push them through the full orchestration graph, and compare AI behaviour under clean, risky, and fraudulent conditions.",
            eyebrow="DEMO LAB",
            stats=[
                ("Profiles", "3 archetypes"),
                ("Objective", "Model range testing"),
                ("Execution", "One-click pipeline"),
                ("Active cases", str(active_cases)),
            ],
        ),
        unsafe_allow_html=True,
    )

    brief_l, brief_r = st.columns([1.1, 0.9])
    with brief_l:
        st.markdown(section_title("Simulation brief", "LAB CONTROL"), unsafe_allow_html=True)
        st.markdown(
            panel(
                '<div class="cx-eyebrow">Why this page exists</div>'
                f'{prose("Use synthetic borrowers to demonstrate range: clean approvals, stressed credits, and explicit fraud pressure. The goal is not fake demo gloss; it is deterministic evidence that the pipeline reacts differently under materially different borrower conditions.")}'
                f'{terminal(st.session_state["terminal_log"])}'
            ),
            unsafe_allow_html=True,
        )
    with brief_r:
        st.markdown(section_title("Scenario mix", "TEST MATRIX"), unsafe_allow_html=True)
        st.markdown(
            panel(
                f'{info_grid([("Clean", "Low noise", "Approval baseline"), ("Risky", "Margin stress", "Committee boundary"), ("Fraud", "Red flags", "Control failure")])}'
            ),
            unsafe_allow_html=True,
        )

    judge_enabled = bool(st.session_state.get("judge_mode", False))
    st.markdown(section_title("Judge demo mode", "ONE-CLICK STORY"), unsafe_allow_html=True)
    st.markdown(
        panel(
            '<div class="cx-eyebrow">Problem statement proof path</div>'
            f'{prose("This guided mode demonstrates end-to-end compliance with the challenge: synthetic intake, full AI underwriting pipeline, explainable decisioning, CAM generation, and audit traceability.")}'
            f'{info_grid([("Step 1", "Spawn benchmark borrowers", "Clean, risky, fraud"), ("Step 2", "Execute full pipeline", "Fraud + research + committee"), ("Step 3", "Show evidence artifacts", "Decision, CAM, XAI, audit")])}'
            + ("" if judge_enabled else prose("Enable Judge Demo Mode from the sidebar to activate one-click sequence controls."))
        ),
        unsafe_allow_html=True,
    )

    j1, j2 = st.columns(2)
    with j1:
        if st.button("Generate judge pack", key="judge_pack", type="secondary", disabled=not judge_enabled):
            pack_results: list[dict[str, str]] = []
            for name, endpoint in [
                ("CLEAN", "/api/demo/clean"),
                ("RISKY", "/api/demo/risky"),
                ("FRAUD", "/api/demo/fraudulent"),
            ]:
                created = api("post", endpoint)
                if created:
                    pack_results.append(
                        {
                            "Profile": name,
                            "Application": str(created.get("application_id", "—")),
                            "Company": str(created.get("company", "—")),
                            "Status": "CREATED",
                        }
                    )
                    push_log("judge_pack", f"{name} case staged: {created.get('application_id', '—')}", "info")
            st.session_state["judge_pack_results"] = pack_results
            st.success("Judge pack staged. You can now run the full sequence.")

    with j2:
        if st.button("Run full judge sequence", key="judge_run", type="primary", disabled=not judge_enabled):
            sequence_results: list[dict[str, str]] = []
            progress = st.progress(0)
            steps = [
                ("CLEAN", "/api/demo/clean"),
                ("RISKY", "/api/demo/risky"),
                ("FRAUD", "/api/demo/fraudulent"),
            ]
            total = len(steps)
            for idx, (name, endpoint) in enumerate(steps, start=1):
                created = api("post", endpoint)
                if not created:
                    sequence_results.append(
                        {"Profile": name, "Application": "—", "Decision": "FAILED", "Status": "CREATE_ERROR"}
                    )
                    progress.progress(int((idx / total) * 100))
                    continue

                app_id = str(created.get("application_id", ""))
                outcome = api("post", f"/api/applications/{app_id}/run", timeout=600)
                if outcome:
                    decision = str(outcome.get("decision", "UNKNOWN"))
                    sequence_results.append(
                        {
                            "Profile": name,
                            "Application": app_id,
                            "Decision": decision,
                            "Status": "COMPLETED",
                        }
                    )
                    push_log("judge_run", f"{name} → {decision} ({app_id})", "success")
                else:
                    sequence_results.append(
                        {
                            "Profile": name,
                            "Application": app_id,
                            "Decision": "FAILED",
                            "Status": "RUN_ERROR",
                        }
                    )
                progress.progress(int((idx / total) * 100))

            st.session_state["judge_run_results"] = sequence_results
            st.success("Judge sequence complete. Results are ready below.")
            st.rerun()

    run_results = st.session_state.get("judge_run_results")
    if run_results:
        st.markdown(section_title("Judge sequence results", "SCORECARD"), unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(run_results), use_container_width=True, hide_index=True)

    # ── Scenario launchers ──────────────────────────────────
    st.markdown(section_title("Scenario launchers", "SYNTHETIC BORROWERS"), unsafe_allow_html=True)

    scenarios = [
        (
            "Clean profile",
            "CLEAN",
            "Confident financials, low noise, clean promoter footprint.",
            "success",
            "/api/demo/clean",
        ),
        (
            "Risky profile",
            "RISKY",
            "Margin compression, litigation pressure, weaker operating resilience.",
            "warning",
            "/api/demo/risky",
        ),
        (
            "Fraudulent profile",
            "FRAUD",
            "Transaction anomalies, red-flag entities, amplified compliance risk.",
            "destructive",
            "/api/demo/fraudulent",
        ),
    ]

    cols = st.columns(3)
    for col, (label, tag, desc, tone, endpoint) in zip(cols, scenarios):
        with col:
            st.markdown(metric_card(label, tag, desc, tone), unsafe_allow_html=True)
            btn_type = "primary" if tone == "success" else "secondary"
            if st.button(f"Spawn {label.split()[0]}", key=f"spawn_{tone}", type=btn_type):
                created = api("post", endpoint)
                if created:
                    st.session_state["selected_application"] = created.get("application_id")
                    push_log(
                        "demo_created",
                        f'{created.get("company", "Synthetic borrower")} → {created.get("application_id")}',
                        tone,
                    )
                    st.success(f'Created {created.get("company")} — {created.get("application_id")}')
                    st.rerun()

    # ── Rapid execution ─────────────────────────────────────
    st.markdown(section_title("Rapid execution", "RUN PIPELINE"), unsafe_allow_html=True)

    if not apps:
        st.markdown(
            empty_state("No demo cases yet", "Launch a synthetic scenario above to get started."),
            unsafe_allow_html=True,
        )
        return

    target = current_application(apps)
    if not target:
        return

    left, right = st.columns([1.2, 1])
    with left:
        st.markdown(
            panel(
                f'<div class="cx-eyebrow">Selected deal</div>'
                f'<div style="font-family:var(--font-display);font-size:var(--text-2xl);font-weight:600;'
                f'letter-spacing:-0.03em;margin-top:var(--space-1);">{escape(target.get("company", "Unknown"))}</div>'
                f'<div style="font-family:var(--font-mono);font-size:var(--text-xs);color:var(--color-text-tertiary);'
                f'margin-top:var(--space-2);font-variant-numeric:tabular-nums;">'
                f'{escape(target.get("application_id", ""))}</div>'
                f'<div style="font-size:var(--text-sm);color:var(--color-text-secondary);margin-top:var(--space-3);">'
                f'Requested: {fmt_inr_cr(target.get("requested_amount_cr"))}</div>'
                f'{section_title("Execution posture", "RUN READY")}'
                f'{info_grid([("Mode", "Full orchestration", None), ("Artifacts", "Decision, CAM, audit", None)])}'
            ),
            unsafe_allow_html=True,
        )
    with right:
        if st.button("Run full pipeline", type="primary", key="demo_run"):
            outcome = api(
                "post",
                f'/api/applications/{target.get("application_id")}/run',
                timeout=600,
            )
            if outcome:
                push_log(
                    "pipeline_run",
                    f'{target.get("application_id")} → {outcome.get("decision", "UNKNOWN")}',
                    "success",
                )
                st.success(f'Pipeline completed — decision: {outcome.get("decision", "UNKNOWN")}')
                st.rerun()
