"""HTML markup builders for Credx UI components.

Every function returns raw HTML strings consumed via st.markdown(…, unsafe_allow_html=True).
All user-supplied text is escaped to prevent injection.
"""
from __future__ import annotations

from html import escape
from typing import Any


# ── Pill / badge ────────────────────────────────────────────────

def pill(label: str, tone: str = "info") -> str:
    css_mod = f"cx-pill--{tone}" if tone else ""
    return f'<span class="cx-pill {css_mod}">{escape(label)}</span>'


# ── Page header ─────────────────────────────────────────────────

def page_header(
    title: str,
    description: str,
    eyebrow: str = "CREDX",
    stats: list[tuple[str, str]] | None = None,
) -> str:
    stats_html = ""
    if stats:
        items = "".join(
            f'<div class="cx-stat"><div class="cx-stat-label">{escape(label)}</div>'
            f'<div class="cx-stat-value">{escape(value)}</div></div>'
            for label, value in stats
        )
        stats_html = f'<div class="cx-stats-strip">{items}</div>'

    return f"""
    <div class="cx-page-header">
        <div class="cx-eyebrow">{escape(eyebrow)}</div>
        <h1 class="cx-page-title">{escape(title)}</h1>
        <div class="cx-page-desc">{escape(description)}</div>
        {stats_html}
    </div>
    """


# ── Section title ───────────────────────────────────────────────

def section_title(title: str, kicker: str = "") -> str:
    kicker_html = f'<div class="cx-section-kicker">{escape(kicker)}</div>' if kicker else ""
    return f"""
    <div class="cx-section">
        {kicker_html}
        <h2 class="cx-section-title">{escape(title)}</h2>
    </div>
    """


def topbar(crumb: str, focus_label: str, status_label: str, mode_label: str = "Credit committee mode") -> str:
    return f"""
    <div class="cx-topbar">
        <div>
            <div class="cx-topbar-crumb">{escape(crumb)}</div>
            <div class="cx-topbar-focus">{escape(focus_label)}</div>
        </div>
        <div class="cx-topbar-actions">
            <div class="cx-topbar-chip">{escape(mode_label)}</div>
            <div class="cx-topbar-chip cx-topbar-chip--accent">{escape(status_label)}</div>
        </div>
    </div>
    """


def prose(text: str) -> str:
    return f'<div class="cx-prose">{escape(text)}</div>'


def info_grid(items: list[tuple[str, str, str | None]]) -> str:
    cells = []
    for label, value, meta in items:
        meta_html = f'<div class="cx-info-meta">{escape(meta)}</div>' if meta else ""
        cells.append(
            '<div class="cx-info-cell">'
            f'<div class="cx-info-label">{escape(label)}</div>'
            f'<div class="cx-info-value">{escape(value)}</div>'
            f'{meta_html}'
            '</div>'
        )
    return '<div class="cx-info-grid">' + ''.join(cells) + '</div>'


def loading_state(title: str, body: str = "") -> str:
    body_html = f'<div class="cx-loading-copy">{escape(body)}</div>' if body else ""
    return (
        '<div class="cx-loading">'
        '<div class="cx-loading-bars">'
        '<span class="cx-loading-bar"></span>'
        '<span class="cx-loading-bar cx-loading-bar--mid"></span>'
        '<span class="cx-loading-bar cx-loading-bar--short"></span>'
        '</div>'
        f'<div class="cx-loading-title">{escape(title)}</div>'
        f'{body_html}'
        '</div>'
    )


# ── Metric card ─────────────────────────────────────────────────

def metric_card(
    label: str,
    value: str,
    caption: str = "",
    tone: str = "",
) -> str:
    mod = f"cx-metric--{tone}" if tone else ""
    caption_html = f'<div class="cx-metric-caption">{escape(caption)}</div>' if caption else ""
    return f"""
    <div class="cx-metric cx-enter {mod}">
        <div class="cx-metric-label">{escape(label)}</div>
        <div class="cx-metric-value">{escape(value)}</div>
        {caption_html}
    </div>
    """


# ── List item (queue row) ──────────────────────────────────────

def list_card(title: str, meta: str, status: str, tone: str = "info") -> str:
    return f"""
    <div class="cx-list-item cx-enter">
        <div>
            <div class="cx-list-item-title">{escape(title)}</div>
            <div class="cx-list-item-meta">{escape(meta)}</div>
        </div>
        {pill(status or "unknown", tone)}
    </div>
    """


# ── Terminal ────────────────────────────────────────────────────

def terminal(lines: list[dict[str, str]]) -> str:
    rows = []
    for line in lines[-12:]:
        rows.append(
            '<div class="cx-terminal-line">'
            f'<strong>{escape(line.get("stamp", "--:--:--"))}</strong> '
            f'{escape(line.get("headline", ""))} — '
            f'{escape(line.get("copy", ""))}'
            "</div>"
        )
    if not rows:
        rows.append(
            '<div class="cx-terminal-line">'
            "<strong>idle</strong> No operator events yet."
            "</div>"
        )
    return (
        '<div class="cx-terminal">'
        '<div class="cx-terminal-chrome">'
        '<span class="cx-terminal-dot" style="background:var(--color-destructive);"></span>'
        '<span class="cx-terminal-dot" style="background:var(--color-warning);"></span>'
        '<span class="cx-terminal-dot" style="background:var(--color-success);"></span>'
        "</div>"
        + "".join(rows)
        + "</div>"
    )


# ── Panel ───────────────────────────────────────────────────────

def panel(content: str) -> str:
    return f'<div class="cx-panel">{content}</div>'


# ── Signal card ─────────────────────────────────────────────────

def signal_card(
    title: str,
    body: str,
    evidence: str = "",
    severity: str = "LOW",
) -> str:
    tone_map = {
        "HIGH": "destructive",
        "CRITICAL": "destructive",
        "MEDIUM": "warning",
        "LOW": "success",
        "CLEAN": "success",
    }
    tone = tone_map.get(severity.upper(), "info")
    evidence_html = (
        f'<div class="cx-signal-body" style="opacity:0.7">Evidence: {escape(evidence)}</div>'
        if evidence else ""
    )
    return f"""
    <div class="cx-signal cx-signal--{tone} cx-enter">
        <div class="cx-signal-header">
            <div class="cx-signal-title">{escape(title)}</div>
            {pill(severity, tone)}
        </div>
        <div class="cx-signal-body">{escape(body)}</div>
        {evidence_html}
    </div>
    """


# ── Feed item ───────────────────────────────────────────────────

def feed_item(
    stamp: str,
    headline: str,
    body: str = "",
) -> str:
    body_html = f'<div class="cx-feed-body">{escape(body)}</div>' if body else ""
    return f"""
    <div class="cx-feed-item cx-enter">
        <div class="cx-feed-stamp">{escape(stamp)}</div>
        <div class="cx-feed-headline">{escape(headline)}</div>
        {body_html}
    </div>
    """


# ── Empty state ─────────────────────────────────────────────────

def empty_state(title: str, body: str, icon: str = "○") -> str:
    return f"""
    <div class="cx-empty">
        <div class="cx-empty-icon">{escape(icon)}</div>
        <div class="cx-empty-title">{escape(title)}</div>
        <div class="cx-empty-body">{escape(body)}</div>
    </div>
    """


# ── Divider ─────────────────────────────────────────────────────

def divider() -> str:
    return '<div class="cx-divider"></div>'


# ── Key-value detail row ───────────────────────────────────────

def kv_row(label: str, value: str) -> str:
    return (
        '<div class="cx-kv-row">'
        f'<span class="cx-kv-label">{escape(label)}</span>'
        f'<span class="cx-kv-value">{escape(value)}</span>'
        '</div>'
    )
