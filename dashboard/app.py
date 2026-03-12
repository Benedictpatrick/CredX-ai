"""Credx — Credit Intelligence Deck.

Award-winning Streamlit dashboard for AI-driven corporate credit underwriting.
Modular architecture with component library, design token system, and page routing.

Archetype: Linear/Raycast (dense productivity) + Google/Meta (data dashboard).
"""
# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

from html import escape

import streamlit as st

st.set_page_config(
    page_title="Credx · Credit Intelligence",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dashboard.components.data import (  # noqa: E402
    application_label,
    current_application,
    hydrate_selection,
    load_backend_info,
    load_portfolio,
)
from dashboard.components.markup import divider, topbar  # noqa: E402
from dashboard.components.theme import THEME_CSS  # noqa: E402

# ── Inject design system ───────────────────────────────────────
st.markdown(THEME_CSS, unsafe_allow_html=True)

# ── Session state init ─────────────────────────────────────────
for key, default in {
    "selected_application": None,
    "terminal_log": [],
    "nav": "Command Deck",
    "judge_mode": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── Data bootstrap ─────────────────────────────────────────────
apps = load_portfolio()
health, info = load_backend_info()
hydrate_selection(apps)
selected_app = current_application(apps)

focus_label = "No application selected"
if selected_app:
    focus_label = f"{selected_app.get('company', 'Unknown')} · {selected_app.get('application_id', '')}"

st.markdown(
    topbar(
        crumb=st.session_state["nav"],
        focus_label=focus_label,
        status_label="JUDGE MODE" if st.session_state.get("judge_mode") else str(health.get("status", "offline")).upper(),
        mode_label="Judge demo mode" if st.session_state.get("judge_mode") else "Credit committee mode",
    ),
    unsafe_allow_html=True,
)


# ── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div class="cx-brand">'
        '<div class="cx-brand-mark" aria-hidden="true">'
        '<svg class="cx-brand-icon" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<rect x="1" y="1" width="38" height="38" rx="10" class="cx-brand-icon-frame"/>'
        '<path d="M27 13.5C25.4 11.8 23.2 10.8 20.8 10.8C16 10.8 12.2 14.6 12.2 19.4C12.2 24.2 16 28 20.8 28C23.2 28 25.4 27 27 25.3" class="cx-brand-icon-c"/>'
        '<path d="M20.2 15.2L27.8 22.8M27.8 15.2L20.2 22.8" class="cx-brand-icon-x"/>'
        '</svg>'
        '</div>'
        '<div class="cx-brand-wordmark">Credx</div>'
        '<div class="cx-brand-tag">Credit Intelligence OS</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    nav_options = ["Command Deck", "Demo Lab", "Intake Studio", "Decision Workbench", "Judge Narrative"]
    current_idx = nav_options.index(st.session_state["nav"])
    st.session_state["nav"] = st.radio(
        "Navigation",
        nav_options,
        index=current_idx,
        label_visibility="collapsed",
    )

    st.markdown(divider(), unsafe_allow_html=True)

    backend_state = str(health.get("status", "offline"))
    status_dot_class = "cx-sidebar-status-dot"
    if backend_state != "healthy":
        status_dot_class += " cx-sidebar-status-dot--destructive"
    st.markdown(
        '<div class="cx-sidebar-status">'
        f'<span class="{status_dot_class}"></span>'
        '<span class="cx-sidebar-status-label">Engine</span>'
        f'<span class="cx-sidebar-status-value">{escape(backend_state.title())}</span>'
        f'<span class="cx-sidebar-status-meta">v{escape(str(health.get("version", "—")))}</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    if apps:
        label_map = {application_label(a): a.get("application_id") for a in apps}
        current_label = next(
            (
                lbl
                for lbl, aid in label_map.items()
                if aid == st.session_state["selected_application"]
            ),
            list(label_map.keys())[0],
        )
        chosen = st.selectbox(
            "Focus application",
            list(label_map.keys()),
            index=list(label_map.keys()).index(current_label),
        )
        st.session_state["selected_application"] = label_map[chosen]

    st.markdown(divider(), unsafe_allow_html=True)

    st.toggle(
        "Judge demo mode",
        key="judge_mode",
        help="Turns on guided demo surfaces and one-click showcase flows for judges.",
    )

    st.markdown(divider(), unsafe_allow_html=True)

    modules = info.get("modules", [])
    if modules:
        st.markdown(
            '<div style="font-size:var(--text-xs);text-transform:uppercase;'
            'letter-spacing:0.08em;color:var(--color-text-tertiary);font-weight:600;'
            'margin-bottom:var(--space-2);">Active modules</div>',
            unsafe_allow_html=True,
        )
        module_rows: list[str] = []
        for mod in modules:
            module_rows.append(
                '<div class="cx-module-item">'
                '<span class="cx-module-dot"></span>'
                f'{escape(str(mod))}'
                '</div>'
            )
        st.markdown('<div class="cx-module-list">' + ''.join(module_rows) + '</div>', unsafe_allow_html=True)


# ── Page routing ───────────────────────────────────────────────
if st.session_state["nav"] == "Command Deck":
    from dashboard.pages.command_deck import render as render_page
    render_page(apps, selected_app, health, info)

elif st.session_state["nav"] == "Demo Lab":
    from dashboard.pages.demo_lab import render as render_page  # type: ignore[assignment]
    render_page(apps)

elif st.session_state["nav"] == "Intake Studio":
    from dashboard.pages.intake_studio import render as render_page  # type: ignore[assignment]
    render_page(selected_app)

elif st.session_state["nav"] == "Decision Workbench":
    from dashboard.pages.decision_workbench import render as render_page  # type: ignore[assignment]
    render_page(selected_app, info)

else:
    from dashboard.pages.judge_narrative import render as render_page  # type: ignore[assignment]
    render_page(apps, selected_app, info)

