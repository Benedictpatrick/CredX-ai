"""Credx design system — CSS tokens and component styles.

Archetype: Hybrid Linear/Raycast (dense productivity) + Google/Meta (data dashboard).
Font: Plus Jakarta Sans (display/body) + DM Mono (data/code).
Palette: Near-black base, single teal accent, semantic status colors.
"""

THEME_CSS = """<style>
@import url('https://fonts.bunny.net/css?family=plus-jakarta-sans:400,500,600,700&family=dm-mono:400,500&display=swap');

/* ────────────────────────────────────────────────
   DESIGN TOKENS
   ──────────────────────────────────────────────── */
:root {
  /* Spacing — 4px base unit */
  --space-1: 4px;  --space-2: 8px;  --space-3: 12px;
  --space-4: 16px; --space-5: 20px; --space-6: 24px;
  --space-8: 32px; --space-10: 40px; --space-12: 48px;
  --space-16: 64px;

  /* Type scale — strict 8-size system */
  --text-xs: 11px; --text-sm: 13px; --text-base: 14px;
  --text-lg: 16px; --text-xl: 18px; --text-2xl: 22px;
  --text-3xl: 32px; --text-display: 44px;

  /* Font families */
  --font-display: 'Plus Jakarta Sans', sans-serif;
  --font-body: 'Plus Jakarta Sans', sans-serif;
  --font-mono: 'DM Mono', 'IBM Plex Mono', monospace;

  /* Colors — semantic only, never raw hex in components */
  --color-bg: #0a0a0c;
  --color-surface: #111114;
  --color-surface-raised: #18181c;
  --color-surface-overlay: #222226;
  --color-border: rgba(255, 255, 255, 0.06);
  --color-border-strong: rgba(255, 255, 255, 0.10);
  --color-text-primary: #ededef;
  --color-text-secondary: rgba(237, 237, 239, 0.55);
  --color-text-tertiary: rgba(237, 237, 239, 0.32);
  --color-accent: #00d4aa;
  --color-accent-hover: #1aebbd;
  --color-accent-muted: rgba(0, 212, 170, 0.12);
  --color-accent-subtle: rgba(0, 212, 170, 0.06);
  --color-success: #22c55e;
  --color-warning: #f59e0b;
  --color-destructive: #ef4444;
  --color-info: #38bdf8;

  /* Radii — 3 core values + pill */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-pill: 9999px;

  /* Shadows — multi-layer, color-tinted */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.5);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.55), 0 1px 3px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 12px 32px rgba(0, 0, 0, 0.6), 0 4px 12px rgba(0, 0, 0, 0.4);
  --shadow-focus: 0 0 0 3px rgba(0, 212, 170, 0.25);
  --shadow-accent-glow: 0 8px 24px rgba(0, 212, 170, 0.12);

  /* Motion — named easings, never 'ease' */
  --ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-out-quart: cubic-bezier(0.25, 1, 0.5, 1);
  --ease-in-out-quart: cubic-bezier(0.76, 0, 0.24, 1);
  --duration-instant: 60ms;
  --duration-fast: 100ms;
  --duration-base: 150ms;
  --duration-slow: 300ms;
  --duration-enter: 400ms;

  /* Z-index layers */
  --z-base: 0;
  --z-raised: 10;
  --z-overlay: 20;
  --z-modal: 30;
  --z-toast: 40;
}

/* ────────────────────────────────────────────────
   GLOBAL RESETS
   ──────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"] {
  background: var(--color-bg) !important;
  color: var(--color-text-primary);
  font-family: var(--font-body);
  font-size: var(--text-base);
  line-height: 1.5;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

[data-testid="stMain"] {
  background: var(--color-bg) !important;
}

/* Custom scrollbar — thin, unobtrusive */
* {
  scrollbar-width: thin;
  scrollbar-color: rgba(255,255,255,0.08) transparent;
}
*::-webkit-scrollbar { width: 5px; height: 5px; }
*::-webkit-scrollbar-track { background: transparent; }
*::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.08);
  border-radius: var(--radius-pill);
}
*::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.14); }

/* ────────────────────────────────────────────────
   STREAMLIT CHROME OVERRIDES
   ──────────────────────────────────────────────── */
[data-testid="stHeader"] {
  background: transparent !important;
}

[data-testid="stToolbar"],
[data-testid="stAppDeployButton"],
[data-testid="stMainMenu"] {
  display: none !important;
}

.block-container {
  padding: var(--space-6) var(--space-8) var(--space-12) !important;
  max-width: 1400px;
}

[data-testid="stMainBlockContainer"] {
  padding-top: 0 !important;
}

/* Sidebar — 220px labeled, Linear-style */
[data-testid="stSidebar"] {
  background: var(--color-surface) !important;
  border-right: 1px solid var(--color-border) !important;
  width: 220px !important;
  min-width: 220px !important;
}

[data-testid="stSidebarNav"] { display: none; }

section[data-testid="stSidebar"] > div {
  padding: var(--space-5) var(--space-4) var(--space-4) !important;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
  font-size: var(--text-sm);
}

/* Tabs — pill-style segmented control */
.stTabs [data-baseweb="tab-list"] {
  gap: var(--space-1);
  background: var(--color-surface);
  padding: var(--space-1);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
}

.stTabs [data-baseweb="tab"] {
  border-radius: calc(var(--radius-md) - 2px);
  height: 36px;
  color: var(--color-text-secondary);
  font-family: var(--font-body);
  font-weight: 500;
  font-size: var(--text-sm);
  padding: 0 var(--space-4);
  transition: color var(--duration-fast) var(--ease-out-quart),
              background var(--duration-fast) var(--ease-out-quart);
}

.stTabs [data-baseweb="tab"]:hover {
  color: var(--color-text-primary);
  background: var(--color-surface-raised);
}

.stTabs [aria-selected="true"] {
  background: var(--color-surface-raised) !important;
  color: var(--color-text-primary) !important;
  box-shadow: var(--shadow-sm);
}

.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] {
  display: none !important;
}

/* Buttons — pill shape, compact */
.stButton > button,
.stDownloadButton > button {
  width: 100%;
  border-radius: var(--radius-sm) !important;
  border: 1px solid var(--color-border-strong) !important;
  background: var(--color-surface-raised) !important;
  color: var(--color-text-primary) !important;
  font-family: var(--font-body);
  font-weight: 500;
  font-size: var(--text-sm);
  height: 36px;
  padding: 0 var(--space-4);
  box-shadow: var(--shadow-sm);
  transition: transform var(--duration-instant) var(--ease-out-expo),
              background var(--duration-fast) var(--ease-out-quart),
              box-shadow var(--duration-fast) var(--ease-out-quart);
}

.stButton > button:hover,
.stDownloadButton > button:hover {
  background: var(--color-surface-overlay) !important;
  box-shadow: var(--shadow-md);
}

.stButton > button:active,
.stDownloadButton > button:active {
  transform: scale(0.97);
  transition-duration: var(--duration-instant);
}

.stButton > button:focus-visible,
.stDownloadButton > button:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
  box-shadow: var(--shadow-focus);
}

.stButton > button[kind="primary"] {
  background: var(--color-accent) !important;
  color: #050505 !important;
  border-color: transparent !important;
  font-weight: 600;
  box-shadow: var(--shadow-accent-glow);
}

.stButton > button[kind="primary"]:hover {
  background: var(--color-accent-hover) !important;
  box-shadow: var(--shadow-accent-glow), var(--shadow-md);
}

/* Form inputs — clean dark fields */
.stTextInput input,
.stNumberInput input,
.stTextArea textarea {
  border-radius: var(--radius-md) !important;
  background: var(--color-surface) !important;
  border: 1px solid var(--color-border-strong) !important;
  color: var(--color-text-primary) !important;
  font-family: var(--font-body);
  font-size: var(--text-sm);
  padding: var(--space-2) var(--space-3) !important;
  transition: border-color var(--duration-fast) var(--ease-out-quart),
              box-shadow var(--duration-fast) var(--ease-out-quart);
}

.stTextInput input:focus,
.stNumberInput input:focus,
.stTextArea textarea:focus {
  border-color: var(--color-accent) !important;
  box-shadow: var(--shadow-focus) !important;
}

.stSelectbox [data-baseweb="select"] > div,
.stMultiSelect [data-baseweb="select"] > div {
  border-radius: var(--radius-md) !important;
  background: var(--color-surface) !important;
  border: 1px solid var(--color-border-strong) !important;
  color: var(--color-text-primary) !important;
  font-size: var(--text-sm);
}

.stSlider [data-baseweb="slider"] div[role="slider"] {
  background: var(--color-accent) !important;
}

/* DataFrames — styled tables */
.stDataFrame, .stTable {
  border-radius: var(--radius-lg) !important;
  overflow: hidden;
  border: 1px solid var(--color-border) !important;
}

[data-testid="stDataFrame"] th {
  background: var(--color-surface-raised) !important;
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 600;
}

/* Hide Streamlit's default footer and menu */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
.stDeployButton { display: none; }

/* Radio buttons in sidebar — nav items */
[data-testid="stSidebar"] .stRadio > div {
  gap: var(--space-1) !important;
}

[data-testid="stSidebar"] .stRadio > div > label {
  background: transparent;
  border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3) !important;
  margin: 0;
  transition: background var(--duration-fast) var(--ease-out-quart);
  cursor: pointer;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
  min-height: 33px;
  position: relative;
}

[data-testid="stSidebar"] .stRadio > div > label:hover {
  background: var(--color-surface-raised);
  color: var(--color-text-primary);
}

[data-testid="stSidebar"] .stRadio > div > label[data-checked="true"],
[data-testid="stSidebar"] .stRadio > div > label:has(input:checked) {
  background: var(--color-surface-raised);
  color: var(--color-text-primary);
  font-weight: 600;
}

[data-testid="stSidebar"] .stRadio > div > label[data-checked="true"]::before,
[data-testid="stSidebar"] .stRadio > div > label:has(input:checked)::before {
  content: "";
  position: absolute;
  left: -12px;
  top: 50%;
  transform: translateY(-50%);
  width: 2px;
  height: 15px;
  background: var(--color-accent);
  border-radius: 0 2px 2px 0;
  box-shadow: var(--shadow-accent-glow);
}

/* ────────────────────────────────────────────────
   CUSTOM COMPONENTS
   ──────────────────────────────────────────────── */

/* Brand lockup */
.cx-brand {
  padding: 0 0 var(--space-4);
  border-bottom: 1px solid var(--color-border);
  margin-bottom: var(--space-4);
}

.cx-brand-mark {
  width: 40px;
  height: 40px;
  border-radius: 11px;
  margin-bottom: var(--space-2);
  background: linear-gradient(145deg, var(--color-surface-raised), rgba(0, 0, 0, 0));
  box-shadow: inset 0 0 0 1px var(--color-border), var(--shadow-accent-glow);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.cx-brand-icon {
  width: 34px;
  height: 34px;
  display: block;
}

.cx-brand-icon-frame {
  fill: var(--color-surface-overlay);
  stroke: var(--color-border-strong);
  stroke-width: 1;
}

.cx-brand-icon-c {
  stroke: var(--color-accent);
  stroke-width: 2.2;
  stroke-linecap: round;
}

.cx-brand-icon-x {
  stroke: var(--color-text-primary);
  stroke-width: 2;
  stroke-linecap: round;
  opacity: 0.9;
}

.cx-brand-wordmark {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 650;
  letter-spacing: -0.035em;
  color: var(--color-text-primary);
  line-height: 1.1;
}

.cx-brand-tag {
  margin-top: var(--space-1);
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-tertiary);
  font-weight: 500;
}

.cx-topbar {
  position: sticky;
  top: 0;
  z-index: var(--z-overlay);
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: 0 0 var(--space-1);
  margin-bottom: var(--space-6);
  background: rgba(10, 10, 12, 0.82);
  backdrop-filter: blur(14px) saturate(180%);
  -webkit-backdrop-filter: blur(14px) saturate(180%);
  border-bottom: 1px solid var(--color-border);
}

.cx-topbar-crumb {
  font-size: var(--text-xs);
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--color-accent);
  font-weight: 600;
}

.cx-topbar-focus {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 1px;
}

.cx-topbar-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.cx-topbar-chip {
  height: 24px;
  padding: 0 8px;
  border-radius: var(--radius-sm);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  font-size: var(--text-xs);
  display: inline-flex;
  align-items: center;
  font-weight: 500;
}

.cx-topbar-chip--accent {
  color: var(--color-text-primary);
  border-color: rgba(0,212,170,0.18);
  background: rgba(0,212,170,0.08);
}

/* Page header */
.cx-page-header {
  margin-bottom: var(--space-6);
}

.cx-eyebrow {
  font-size: var(--text-xs);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-accent);
  font-weight: 600;
  margin-bottom: var(--space-2);
}

.cx-page-title {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  font-weight: 600;
  letter-spacing: -0.03em;
  line-height: 1.15;
  color: var(--color-text-primary);
  margin: 0;
}

.cx-page-desc {
  margin-top: var(--space-2);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  line-height: 1.55;
  max-width: 70ch;
}

/* Stats strip */
.cx-stats-strip {
  display: flex;
  gap: var(--space-6);
  margin-top: var(--space-5);
  padding-top: var(--space-5);
  border-top: 1px solid var(--color-border);
}

.cx-stat {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.cx-stat-label {
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-tertiary);
  font-weight: 500;
}

.cx-stat-value {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--color-text-primary);
  font-variant-numeric: tabular-nums;
}

/* Section title */
.cx-section {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  margin: var(--space-6) 0 var(--space-4);
  gap: 3px;
}

.cx-section-title {
  font-family: var(--font-display);
  font-size: var(--text-sm);
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--color-text-primary);
  margin: 0;
}

.cx-section-kicker {
  font-size: var(--text-xs);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-tertiary);
  font-weight: 600;
}

.cx-sidebar-status {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 10px;
  border-radius: 6px;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  margin-bottom: var(--space-2);
}

.cx-sidebar-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-success);
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.45);
}

.cx-sidebar-status-dot--destructive {
  background: var(--color-destructive);
  box-shadow: 0 0 6px rgba(239, 68, 68, 0.4);
}

.cx-sidebar-status-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.cx-sidebar-status-value {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.cx-sidebar-status-meta {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

.cx-module-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cx-module-item {
  display: flex;
  align-items: center;
  gap: 7px;
  min-height: 27px;
  padding: 0 8px;
  border-radius: 6px;
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

.cx-module-item:hover {
  background: var(--color-surface-raised);
  color: var(--color-text-secondary);
}

.cx-module-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--color-accent);
  flex-shrink: 0;
}

/* Metric card */
.cx-metric {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-5) var(--space-5) var(--space-4);
  min-height: 120px;
  display: flex;
  flex-direction: column;
  transition: transform var(--duration-base) var(--ease-out-expo),
              box-shadow var(--duration-base) var(--ease-out-expo);
}

.cx-metric:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.cx-metric-label {
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-tertiary);
  font-weight: 600;
  margin-bottom: var(--space-3);
}

.cx-metric-value {
  font-family: var(--font-display);
  font-size: var(--text-3xl);
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.1;
  color: var(--color-text-primary);
  font-variant-numeric: tabular-nums;
}

.cx-metric-caption {
  margin-top: auto;
  padding-top: var(--space-3);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  line-height: 1.5;
}

/* Status-tinted metric borders */
.cx-metric--accent { border-color: rgba(0, 212, 170, 0.15); }
.cx-metric--success { border-color: rgba(34, 197, 94, 0.15); }
.cx-metric--warning { border-color: rgba(245, 158, 11, 0.15); }
.cx-metric--destructive { border-color: rgba(239, 68, 68, 0.15); }

.cx-metric--accent .cx-metric-value { color: var(--color-accent); }
.cx-metric--success .cx-metric-value { color: var(--color-success); }
.cx-metric--warning .cx-metric-value { color: var(--color-warning); }
.cx-metric--destructive .cx-metric-value { color: var(--color-destructive); }

/* Panel */
.cx-panel {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  box-shadow: var(--shadow-sm);
}

.cx-prose {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.cx-info-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}

.cx-info-cell {
  min-width: 0;
}

.cx-info-label {
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-tertiary);
  font-weight: 600;
  margin-bottom: var(--space-1);
}

.cx-info-value {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: 600;
  letter-spacing: -0.02em;
  color: var(--color-text-primary);
  font-variant-numeric: tabular-nums;
}

.cx-info-meta {
  margin-top: var(--space-1);
  color: var(--color-text-secondary);
  font-size: var(--text-xs);
  line-height: 1.5;
}

.cx-kv-row {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--color-border);
}

.cx-kv-label {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.cx-kv-value {
  font-size: var(--text-sm);
  color: var(--color-text-primary);
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.cx-loading {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  text-align: center;
  background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
}

.cx-loading-bars {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  height: 42px;
}

.cx-loading-bar {
  width: 10px;
  height: 100%;
  border-radius: 3px 3px 0 0;
  background: linear-gradient(180deg, rgba(32,210,160,0.18), rgba(32,210,160,0.05));
  border: 1px solid rgba(32,210,160,0.18);
  animation: cxPulse 1.4s var(--ease-out-quart) infinite;
}

.cx-loading-bar--mid {
  height: 70%;
  animation-delay: 120ms;
}

.cx-loading-bar--short {
  height: 46%;
  animation-delay: 240ms;
}

.cx-loading-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-text-primary);
}

.cx-loading-copy {
  max-width: 34ch;
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  line-height: 1.6;
}

@keyframes cxPulse {
  0%, 100% { opacity: 0.5; transform: translateY(0); }
  50% { opacity: 1; transform: translateY(-2px); }
}

div[data-testid="stPlotlyChart"],
div[data-testid="stDataFrame"] {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  box-shadow: var(--shadow-sm);
}

div[data-testid="stPlotlyChart"] > div {
  min-height: 280px;
}

@media (max-width: 1100px) {
  .block-container {
    padding: var(--space-5) var(--space-5) var(--space-10) !important;
  }

  .cx-topbar {
    height: auto;
    align-items: flex-start;
    flex-direction: column;
    padding-bottom: var(--space-3);
  }

  .cx-stats-strip,
  .cx-info-grid {
    flex-wrap: wrap;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .cx-stats-strip,
  .cx-info-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--space-3);
  }

  .cx-topbar-actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .cx-kv-row {
    flex-direction: column;
    gap: var(--space-1);
  }

  .cx-kv-value {
    text-align: left;
  }
}

/* List card — queue items */
.cx-list-item {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
  margin-bottom: var(--space-2);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-4);
  transition: background var(--duration-fast) var(--ease-out-quart);
}

.cx-list-item:hover {
  background: var(--color-surface-raised);
}

.cx-list-item-title {
  font-weight: 600;
  font-size: var(--text-base);
  color: var(--color-text-primary);
  letter-spacing: -0.01em;
}

.cx-list-item-meta {
  margin-top: var(--space-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  font-variant-numeric: tabular-nums;
}

/* Pill / badge */
.cx-pill {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  border-radius: var(--radius-pill);
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  white-space: nowrap;
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
  background: var(--color-surface-raised);
}

.cx-pill::before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}

.cx-pill--accent { color: var(--color-accent); border-color: rgba(0,212,170,0.15); background: rgba(0,212,170,0.06); }
.cx-pill--success { color: var(--color-success); border-color: rgba(34,197,94,0.15); background: rgba(34,197,94,0.06); }
.cx-pill--warning { color: var(--color-warning); border-color: rgba(245,158,11,0.15); background: rgba(245,158,11,0.06); }
.cx-pill--destructive { color: var(--color-destructive); border-color: rgba(239,68,68,0.15); background: rgba(239,68,68,0.06); }
.cx-pill--info { color: var(--color-info); border-color: rgba(56,189,248,0.15); background: rgba(56,189,248,0.06); }

/* Terminal */
.cx-terminal {
  background: #08080a;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  min-height: 200px;
  contain: layout style;
}

.cx-terminal-chrome {
  display: flex;
  gap: 6px;
  margin-bottom: var(--space-3);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--color-border);
}

.cx-terminal-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.cx-terminal-line {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  padding: var(--space-1) 0;
  line-height: 1.7;
  font-variant-numeric: tabular-nums;
}

.cx-terminal-line strong {
  color: var(--color-accent);
  font-weight: 500;
}

/* Feed card — events, news */
.cx-feed-item {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
  margin-bottom: var(--space-2);
  transition: background var(--duration-fast) var(--ease-out-quart);
}

.cx-feed-item:hover {
  background: var(--color-surface-raised);
}

.cx-feed-stamp {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  font-variant-numeric: tabular-nums;
}

.cx-feed-headline {
  font-weight: 600;
  font-size: var(--text-sm);
  color: var(--color-text-primary);
  margin-top: var(--space-1);
}

.cx-feed-body {
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  line-height: 1.55;
  margin-top: var(--space-1);
}

/* Signal card — fraud/risk signals */
.cx-signal {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
  margin-bottom: var(--space-2);
  border-left: 3px solid var(--color-border-strong);
}

.cx-signal--success { border-left-color: var(--color-success); }
.cx-signal--warning { border-left-color: var(--color-warning); }
.cx-signal--destructive { border-left-color: var(--color-destructive); }

.cx-signal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-4);
}

.cx-signal-title {
  font-weight: 600;
  font-size: var(--text-sm);
  color: var(--color-text-primary);
}

.cx-signal-body {
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  line-height: 1.55;
  margin-top: var(--space-2);
}

/* Empty state */
.cx-empty {
  text-align: center;
  padding: var(--space-12) var(--space-8);
  color: var(--color-text-tertiary);
}

.cx-empty-icon {
  font-size: var(--text-3xl);
  margin-bottom: var(--space-4);
  opacity: 0.4;
}

.cx-empty-title {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
}

.cx-empty-body {
  font-size: var(--text-sm);
  color: var(--color-text-tertiary);
  max-width: 40ch;
  margin: 0 auto;
  line-height: 1.55;
}

/* Divider */
.cx-divider {
  height: 1px;
  background: var(--color-border);
  margin: var(--space-4) 0;
  border: none;
}

/* Focus ring for interactive elements */
:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-focus);
}

/* Staggered entrance animations */
.cx-enter {
  opacity: 0;
  transform: translateY(6px);
  animation: cxEnter var(--duration-enter) var(--ease-out-expo) forwards;
}
.cx-enter:nth-child(1) { animation-delay: 0ms; }
.cx-enter:nth-child(2) { animation-delay: 40ms; }
.cx-enter:nth-child(3) { animation-delay: 80ms; }
.cx-enter:nth-child(4) { animation-delay: 120ms; }
.cx-enter:nth-child(5) { animation-delay: 160ms; }
.cx-enter:nth-child(6) { animation-delay: 200ms; }

@keyframes cxEnter {
  to { opacity: 1; transform: translateY(0); }
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}

/* Responsive */
@media (max-width: 900px) {
  .cx-stats-strip { flex-direction: column; gap: var(--space-3); }
  .cx-page-title { font-size: var(--text-2xl); }
}
</style>"""
