"""Intake Studio — borrower setup, document upload, and field intelligence."""
from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

from dashboard.components.data import api, fmt_inr_cr, push_log
from dashboard.components.markup import (
    divider,
    empty_state,
    info_grid,
    kv_row,
    metric_card,
    page_header,
    panel,
    prose,
    section_title,
)


def render(selected_app: dict[str, Any] | None) -> None:
    selected_company = selected_app.get("company", "No active case") if selected_app else "No active case"
    selected_amount = fmt_inr_cr(selected_app.get("requested_amount_cr")) if selected_app else "—"
    st.markdown(
        page_header(
            title="Operational Intake",
            description="Borrower creation, source document upload, site visit notes, and management interview capture — the human inputs that feed the AI committee.",
            eyebrow="INTAKE STUDIO",
            stats=[
                ("Input style", "Structured + qualitative"),
                ("Documents", "Multi-file upload"),
                ("Field intel", "Visits & interviews"),
                ("Focus case", selected_company),
            ],
        ),
        unsafe_allow_html=True,
    )

    pre_l, pre_r, pre_x = st.columns(3)
    with pre_l:
        st.markdown(metric_card("Focus case", selected_company, selected_amount), unsafe_allow_html=True)
    with pre_r:
        st.markdown(metric_card("Intake quality", "Human-led", "Documents + field intelligence", "accent"), unsafe_allow_html=True)
    with pre_x:
        st.markdown(metric_card("Capture pattern", "Staged", "Create, upload, then diligence", "success"), unsafe_allow_html=True)

    intake_tab, docs_tab, field_tab = st.tabs([
        "New application",
        "Document vault",
        "Field diligence",
    ])

    # ── New application form ────────────────────────────────
    with intake_tab:
        st.markdown(
            panel(
                '<div class="cx-eyebrow">Intake operating model</div>'
                f'{prose("This page is the structured edge of the system. Use it to create the borrower shell first, then add source documents and field intelligence so downstream scoring reflects actual borrower context instead of synthetic placeholders.")}'
            ),
            unsafe_allow_html=True,
        )
        st.markdown(section_title("Borrower setup", "COMPANY & LOAN"), unsafe_allow_html=True)
        promoter_count = st.number_input(
            "Promoter count", min_value=0, max_value=4, value=1, step=1,
        )

        with st.form("new_application_form"):
            c1, c2 = st.columns(2)
            with c1:
                company_name = st.text_input("Company name", placeholder="Tata Steel Ltd")
                cin = st.text_input("CIN", placeholder="L27100MH1907PLC000260")
                sector = st.text_input("Sector", placeholder="Manufacturing")
                sub_sector = st.text_input("Sub-sector", placeholder="Flat steel")
                gstin = st.text_input("GSTIN")
                pan = st.text_input("PAN")
            with c2:
                annual_turnover = st.number_input("Annual turnover (₹ Cr)", min_value=0.0, step=10.0)
                net_worth = st.number_input("Net worth (₹ Cr)", min_value=0.0, step=10.0)
                requested_amount = st.number_input("Requested amount (₹ Cr)", min_value=0.1, step=5.0)
                purpose = st.text_input("Loan purpose", placeholder="Working capital expansion")
                tenure = st.slider("Loan tenure (months)", min_value=12, max_value=120, value=60, step=6)
                collateral_desc = st.text_input("Collateral description", placeholder="Current assets and plant")
                collateral_value = st.number_input("Collateral value (₹ Cr)", min_value=0.0, step=5.0)

            promoters: list[dict[str, Any]] = []
            if promoter_count:
                st.markdown(section_title("Promoter roster", "KEY MANAGEMENT"), unsafe_allow_html=True)
            for idx in range(int(promoter_count)):
                p1, p2, p3 = st.columns(3)
                with p1:
                    p_name = st.text_input(f"Name #{idx + 1}", key=f"pn_{idx}")
                    p_din = st.text_input(f"DIN #{idx + 1}", key=f"pd_{idx}")
                with p2:
                    p_desg = st.text_input(f"Designation #{idx + 1}", key=f"pde_{idx}")
                    p_share = st.number_input(
                        f"Shareholding #{idx + 1} (%)", 0.0, 100.0, step=1.0, key=f"ps_{idx}",
                    )
                with p3:
                    p_cibil = st.number_input(
                        f"CIBIL #{idx + 1}", 0, 900, value=750, step=10, key=f"pc_{idx}",
                    )
                    p_disq = st.checkbox(f"Disqualified #{idx + 1}", key=f"px_{idx}")
                if p_name:
                    promoters.append({
                        "name": p_name,
                        "din": p_din or "00000000",
                        "designation": p_desg or None,
                        "shareholding_pct": p_share or None,
                        "cibil_score": p_cibil or None,
                        "disqualified": p_disq,
                    })

            submitted = st.form_submit_button("Create borrower case", type="primary")
            if submitted:
                payload = {
                    "company_name": company_name,
                    "cin": cin,
                    "sector": sector or None,
                    "sub_sector": sub_sector or None,
                    "gstin": gstin or None,
                    "pan": pan or None,
                    "annual_turnover_cr": annual_turnover or None,
                    "net_worth_cr": net_worth or None,
                    "requested_amount_cr": requested_amount,
                    "loan_purpose": purpose,
                    "loan_tenure_months": tenure,
                    "collateral_description": collateral_desc or None,
                    "collateral_value_cr": collateral_value or None,
                    "promoters": promoters,
                }
                result = api("post", "/api/applications", json=payload)
                if result:
                    st.session_state["selected_application"] = result.get("application_id")
                    push_log(
                        "application_submitted",
                        f'{result.get("company")} → {result.get("application_id")}',
                        "success",
                    )
                    st.success(f'Application created — {result.get("company")} · {result.get("application_id")}')
                    st.rerun()

    # ── Document vault ──────────────────────────────────────
    with docs_tab:
        st.markdown(section_title("Document vault", "UPLOAD SOURCE MATERIAL"), unsafe_allow_html=True)
        if not selected_app:
            st.markdown(
                empty_state("No application selected", "Create or select a borrower case first."),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                panel(
                    f'<div class="cx-eyebrow">Selected borrower</div>'
                    f'<div style="font-family:var(--font-display);font-size:var(--text-2xl);font-weight:600;'
                    f'letter-spacing:-0.03em;margin-top:var(--space-1);">{escape(selected_app.get("company", "Unknown"))}</div>'
                    f'<div style="font-family:var(--font-mono);font-size:var(--text-xs);color:var(--color-text-tertiary);'
                    f'margin-top:var(--space-2);font-variant-numeric:tabular-nums;">'
                    f'{escape(selected_app.get("application_id", ""))}</div>'
                    f'{divider()}'
                    f'{info_grid([("Requested amount", fmt_inr_cr(selected_app.get("requested_amount_cr")), None), ("Status", str(selected_app.get("status", "submitted")).upper(), None)])}'
                ),
                unsafe_allow_html=True,
            )

            uploads = st.file_uploader(
                "Source documents",
                accept_multiple_files=True,
                type=["pdf", "png", "jpg", "jpeg", "xlsx", "xls", "csv"],
            )
            if st.button("Upload documents", type="primary", key="upload_docs"):
                if not uploads:
                    st.warning("Select one or more files to upload.")
                else:
                    ok = 0
                    for f in uploads:
                        result = api(
                            "post",
                            f'/api/applications/{selected_app.get("application_id")}/upload',
                            files={"file": (f.name, f.getvalue(), f.type or "application/octet-stream")},
                        )
                        if result:
                            ok += 1
                    if ok:
                        push_log("documents_uploaded", f'{selected_app.get("application_id")} — {ok} file(s)', "info")
                        st.success(f"Uploaded {ok} document(s).")

    # ── Field diligence ─────────────────────────────────────
    with field_tab:
        st.markdown(section_title("Field intelligence", "SITE VISITS & INTERVIEWS"), unsafe_allow_html=True)
        if not selected_app:
            st.markdown(
                empty_state("No application selected", "Create or select a borrower case first."),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                panel(
                    '<div class="cx-eyebrow">Primary diligence</div>'
                    f'{prose("Site visits and management interviews directly affect the downstream recommendation. Capture operational reality here: utilization, management credibility, and anything that changes the confidence level behind the numbers.")}'
                ),
                unsafe_allow_html=True,
            )
            site_col, int_col = st.columns(2)

            with site_col:
                st.markdown(
                    '<div style="font-size:var(--text-sm);font-weight:600;color:var(--color-text-secondary);'
                    'margin-bottom:var(--space-3);">Site visit observation</div>',
                    unsafe_allow_html=True,
                )
                with st.form("site_visit_form"):
                    observer = st.text_input("Observer name")
                    location = st.text_input("Location")
                    notes = st.text_area("Observations", height=160)
                    capacity = st.slider("Capacity utilization (%)", 0, 100, 60)
                    if st.form_submit_button("Add site visit"):
                        result = api(
                            "post",
                            f'/api/applications/{selected_app.get("application_id")}/site-visit',
                            json={
                                "application_id": selected_app.get("application_id"),
                                "observer_name": observer,
                                "location": location,
                                "notes": notes,
                                "capacity_utilization_pct": capacity,
                            },
                        )
                        if result:
                            push_log("site_visit", f'{selected_app.get("application_id")} — {location or "field note"}', "warning")
                            st.success("Site visit saved.")

            with int_col:
                st.markdown(
                    '<div style="font-size:var(--text-sm);font-weight:600;color:var(--color-text-secondary);'
                    'margin-bottom:var(--space-3);">Management interview</div>',
                    unsafe_allow_html=True,
                )
                with st.form("interview_form"):
                    interviewee = st.text_input("Interviewee")
                    designation = st.text_input("Designation")
                    key_points = st.text_area("Key points (one per line)", height=160)
                    integrity = st.slider("Integrity score", 0.0, 1.0, 0.7, 0.05)
                    if st.form_submit_button("Add interview"):
                        result = api(
                            "post",
                            f'/api/applications/{selected_app.get("application_id")}/interview',
                            json={
                                "application_id": selected_app.get("application_id"),
                                "interviewee": interviewee,
                                "designation": designation,
                                "key_points": [l.strip() for l in key_points.splitlines() if l.strip()],
                                "integrity_score": integrity,
                            },
                        )
                        if result:
                            push_log("interview", f'{selected_app.get("application_id")} — {interviewee or "management"}', "info")
                            st.success("Interview saved.")
