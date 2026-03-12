"""Plotly chart builders with consistent Credx design tokens.

Every chart uses:
- Transparent paper/plot background
- Plus Jakarta Sans font
- Token-aligned grid colors
- Consistent color palette
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go

from .data import safe_float, fmt_inr_cr

# ── Palette ─────────────────────────────────────────────────────

ACCENT = "#20d2a0"
SUCCESS = "#4ade80"
WARNING = "#fbbf24"
DESTRUCTIVE = "#f87171"
INFO = "#60a5fa"
TEXT = "#ededef"
TEXT_MUTED = "rgba(237,237,239,0.55)"
TEXT_TERTIARY = "rgba(237,237,239,0.32)"
GRID = "rgba(255,255,255,0.04)"
SURFACE = "#16161b"
SURFACE_RAISED = "#24242d"
FONT = "Plus Jakarta Sans"
MONO = "DM Mono"

STATUS_COLORS = {
    "completed": SUCCESS,
    "running": WARNING,
    "submitted": INFO,
    "failed": DESTRUCTIVE,
}

_LAYOUT_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family=FONT, color=TEXT, size=12),
    margin=dict(l=16, r=16, t=12, b=16),
)


def _base_layout(**overrides: Any) -> dict[str, Any]:
    layout = {**_LAYOUT_BASE}
    layout.update(overrides)
    return layout


def _apply_axis_style(fig: go.Figure, *, x_dtick: int | None = None, y_range: list[float] | None = None) -> None:
    xaxis_args: dict[str, Any] = {
        "gridcolor": GRID,
        "zerolinecolor": GRID,
        "showline": False,
        "tickfont": {"family": MONO, "size": 11, "color": TEXT_TERTIARY},
        "title": {"font": {"family": FONT, "size": 11, "color": TEXT_TERTIARY}},
    }
    if x_dtick is not None:
        xaxis_args["dtick"] = x_dtick

    yaxis_args: dict[str, Any] = {
        "gridcolor": GRID,
        "zerolinecolor": GRID,
        "showline": False,
        "tickfont": {"family": MONO, "size": 11, "color": TEXT_TERTIARY},
        "title": {"font": {"family": FONT, "size": 11, "color": TEXT_TERTIARY}},
    }
    if y_range is not None:
        yaxis_args["range"] = y_range

    fig.update_xaxes(**xaxis_args)
    fig.update_yaxes(**yaxis_args)


# ── Portfolio bar chart ─────────────────────────────────────────

def portfolio_bar(apps: list[dict[str, Any]]) -> go.Figure | None:
    if not apps:
        return None
    df = pd.DataFrame(apps)
    df["amount"] = df["requested_amount_cr"].apply(safe_float)
    fig = go.Figure(
        go.Bar(
            x=df["amount"],
            y=df["company"],
            orientation="h",
            marker_color=[
                STATUS_COLORS.get(s, TEXT_MUTED) for s in df["status"]
            ],
            text=[fmt_inr_cr(v) for v in df["amount"]],
            textposition="outside",
            textfont=dict(family=FONT, size=11, color=TEXT_MUTED),
        )
    )
    fig.update_layout(
        **_base_layout(height=max(280, 56 * len(df.index))),
        xaxis_title="",
        yaxis_title="",
        bargap=0.35,
    )
    _apply_axis_style(fig)
    fig.update_yaxes(autorange="reversed", tickfont=dict(family=FONT, size=12, color=TEXT))
    fig.update_traces(
        marker=dict(
            color="rgba(96,165,250,0.10)",
            line=dict(
                color=[STATUS_COLORS.get(s, TEXT_TERTIARY) for s in df["status"]],
                width=1,
            ),
        ),
        hovertemplate="%{y}<br>%{text}<extra></extra>",
    )
    return fig


# ── Portfolio donut ─────────────────────────────────────────────

def portfolio_donut(apps: list[dict[str, Any]]) -> go.Figure | None:
    if not apps:
        return None
    counts = pd.Series([a.get("status", "unknown") for a in apps]).value_counts()
    colors = [STATUS_COLORS.get(s, TEXT_MUTED) for s in counts.index]
    fig = go.Figure(
        go.Pie(
            labels=counts.index.tolist(),
            values=counts.values.tolist(),
            hole=0.76,
            marker=dict(colors=colors, line=dict(width=0)),
            textinfo="label+value",
            textfont=dict(family=FONT, size=11, color=TEXT),
            sort=False,
        )
    )
    fig.update_layout(
        **_base_layout(height=280),
        showlegend=True,
        legend=dict(
            orientation="h", y=-0.05, x=0.5, xanchor="center",
            font=dict(size=11, color=TEXT_MUTED),
        ),
        annotations=[
            dict(
                text=str(int(counts.sum())),
                x=0.5,
                y=0.53,
                showarrow=False,
                font=dict(family=FONT, size=24, color=TEXT),
            ),
            dict(
                text="Applications",
                x=0.5,
                y=0.43,
                showarrow=False,
                font=dict(family=MONO, size=11, color=TEXT_TERTIARY),
            ),
        ],
    )
    return fig


# ── Five Cs radar ───────────────────────────────────────────────

def five_cs_radar(five_cs: dict[str, Any] | None) -> go.Figure | None:
    if not five_cs:
        return None
    labels = ["Character", "Capacity", "Capital", "Collateral", "Conditions"]
    values = [
        safe_float(five_cs.get("character_score")),
        safe_float(five_cs.get("capacity_score")),
        safe_float(five_cs.get("capital_score")),
        safe_float(five_cs.get("collateral_score")),
        safe_float(five_cs.get("conditions_score")),
    ]
    fig = go.Figure(
        go.Scatterpolar(
            r=values + [values[0]],
            theta=labels + [labels[0]],
            fill="toself",
            line=dict(color=ACCENT, width=1.5),
            fillcolor="rgba(32, 210, 160, 0.10)",
        )
    )
    fig.update_layout(
        **_base_layout(height=340),
        polar=dict(
            radialaxis=dict(
                range=[0, 1],
                gridcolor=GRID,
                tickfont=dict(color=TEXT_TERTIARY, size=10, family=MONO),
                showline=False,
            ),
            angularaxis=dict(
                tickfont=dict(color=TEXT, size=11, family=FONT),
                gridcolor=GRID,
            ),
            bgcolor="rgba(0,0,0,0)",
        ),
    )
    return fig


# ── Bull vs Bear debate ────────────────────────────────────────

def debate_chart(debate: dict[str, Any] | None) -> go.Figure | None:
    rounds = (debate or {}).get("rounds", [])
    if not rounds:
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[r.get("round_number") for r in rounds],
        y=[safe_float(r.get("bull_score")) for r in rounds],
        mode="lines+markers",
        name="Bull",
        line=dict(color=SUCCESS, width=2.5),
        marker=dict(size=6),
    ))
    fig.add_trace(go.Scatter(
        x=[r.get("round_number") for r in rounds],
        y=[safe_float(r.get("bear_score")) for r in rounds],
        mode="lines+markers",
        name="Bear",
        line=dict(color=DESTRUCTIVE, width=2.5),
        marker=dict(size=6),
    ))
    fig.update_layout(
        **_base_layout(height=300),
        xaxis_title="Round",
        yaxis_title="Conviction",
        legend=dict(orientation="h", y=1.08, x=0, font=dict(size=11)),
    )
    _apply_axis_style(fig, x_dtick=1, y_range=[0, 1])
    return fig


# ── SHAP attribution ───────────────────────────────────────────

def shap_chart(xai: dict[str, Any] | None) -> go.Figure | None:
    if not xai:
        return None
    features = xai.get("feature_importance")
    if features:
        df = pd.DataFrame(features).sort_values(
            by="shap_value", key=lambda s: s.abs()
        )
        labels = df["display_name"].tolist()
        values = df["shap_value"].astype(float).tolist()
    else:
        shap_values = xai.get("shap_values") or {}
        if not shap_values:
            return None
        ordered = sorted(shap_values.items(), key=lambda kv: abs(kv[1]))
        labels = [kv[0] for kv in ordered]
        values = [float(kv[1]) for kv in ordered]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=["rgba(74,222,128,0.10)" if v >= 0 else "rgba(248,113,113,0.10)" for v in values],
            marker_line_color=[SUCCESS if v >= 0 else DESTRUCTIVE for v in values],
            marker_line_width=1,
            text=[f"{v:+.3f}" for v in values],
            textposition="outside",
            textfont=dict(family=MONO, size=11, color=TEXT_MUTED),
        )
    )
    fig.update_layout(
        **_base_layout(height=max(280, 40 * len(labels))),
        xaxis_title="",
        yaxis_title="",
        bargap=0.3,
    )
    _apply_axis_style(fig)
    return fig


# ── Financial trajectory ───────────────────────────────────────

def financials_chart(financials: list[dict[str, Any]]) -> go.Figure | None:
    if not financials:
        return None
    df = pd.DataFrame(financials)
    if "fiscal_year" not in df:
        return None
    fig = go.Figure()
    for col, color, name in [
        ("revenue_cr", INFO, "Revenue"),
        ("ebitda_cr", ACCENT, "EBITDA"),
        ("net_worth_cr", WARNING, "Net worth"),
    ]:
        if col in df:
            fig.add_trace(go.Scatter(
                x=df["fiscal_year"],
                y=df[col],
                mode="lines+markers",
                name=name,
                line=dict(color=color, width=2.5),
                marker=dict(size=6),
            ))
    fig.update_layout(
        **_base_layout(height=300),
        xaxis_title="",
        yaxis_title="₹ Cr",
        legend=dict(orientation="h", y=1.08, x=0, font=dict(size=11)),
        hoverlabel=dict(
            bgcolor=SURFACE_RAISED,
            bordercolor="rgba(255,255,255,0.14)",
            font=dict(family=FONT, size=12, color=TEXT),
        ),
    )
    _apply_axis_style(fig)
    return fig


def workflow_timeline_chart(
    audit_rows: list[dict[str, Any]],
    current_phase: str,
    status: str,
) -> go.Figure:
    stages: list[tuple[str, str]] = [
        ("initialize", "Initialize"),
        ("ingest", "Ingest"),
        ("fraud", "Fraud"),
        ("research", "Research"),
        ("underwriter", "Underwriter"),
        ("debate", "Debate"),
        ("reflexion", "Reflexion"),
        ("cam", "CAM"),
        ("guardian", "Guardian"),
    ]
    phase_index = {key: idx for idx, (key, _) in enumerate(stages)}

    completed_from_audit: set[str] = set()
    for row in audit_rows:
        token = f"{str(row.get('agent', ''))} {str(row.get('action', ''))}".lower()
        if "ingest" in token:
            completed_from_audit.add("ingest")
        if "fraud" in token or "sherlock" in token:
            completed_from_audit.add("fraud")
        if "research" in token or "scholar" in token:
            completed_from_audit.add("research")
        if "underwriter" in token:
            completed_from_audit.add("underwriter")
        if "debate" in token:
            completed_from_audit.add("debate")
        if "reflex" in token:
            completed_from_audit.add("reflexion")
        if "cam" in token:
            completed_from_audit.add("cam")
        if "guardian" in token or "safety" in token:
            completed_from_audit.add("guardian")

    phase_key = str(current_phase or "initialize").lower()
    active_idx = phase_index.get(phase_key, 0)
    if str(status).lower() == "completed":
        active_idx = len(stages) - 1

    marker_colors: list[str] = []
    marker_labels: list[str] = []
    for idx, (key, _) in enumerate(stages):
        if key in completed_from_audit or idx < active_idx:
            marker_colors.append(SUCCESS)
            marker_labels.append("done")
        elif idx == active_idx and str(status).lower() == "running":
            marker_colors.append(WARNING)
            marker_labels.append("running")
        elif idx == active_idx and str(status).lower() == "submitted":
            marker_colors.append(INFO)
            marker_labels.append("queued")
        else:
            marker_colors.append(TEXT_TERTIARY)
            marker_labels.append("pending")

    x = list(range(len(stages)))
    y = [0] * len(stages)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="lines",
            line=dict(color=GRID, width=2),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="markers+text",
            marker=dict(size=16, color=marker_colors, line=dict(color="rgba(255,255,255,0.14)", width=1)),
            text=[label for _, label in stages],
            textposition="top center",
            textfont=dict(family=FONT, size=11, color=TEXT),
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        )
    )
    fig.update_layout(
        **_base_layout(height=180, margin=dict(l=10, r=10, t=20, b=12)),
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False, fixedrange=True),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False, fixedrange=True),
        annotations=[
            dict(
                text=f"Current phase: {str(current_phase or 'submitted').upper()} · Status: {str(status).upper()}",
                x=0,
                y=-0.35,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(family=MONO, size=11, color=TEXT_TERTIARY),
                xanchor="left",
            )
        ],
    )
    return fig
