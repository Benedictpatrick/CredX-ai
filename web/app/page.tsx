"use client";

import { useEffect, useMemo, useRef } from "react";
import {
  Activity,
  BarChart3,
  Briefcase,
  ChevronDown,
  Command,
  Database,
  Gauge,
  Shield,
} from "lucide-react";
import {
  AreaSeries,
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";

interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  active?: boolean;
}

interface TopMetric {
  id: string;
  label: string;
  value: string;
  subtext: string;
}

interface PostureRow {
  id: string;
  metric: string;
  status: string;
  detail: string;
  tone: "emerald" | "amber";
}

const NAV_ITEMS: NavItem[] = [
  { id: "deck", label: "Command Deck", icon: Command, active: true },
  { id: "tower", label: "Control Tower", icon: Gauge },
  { id: "portfolio", label: "Portfolio", icon: Briefcase },
  { id: "risk", label: "Risk Engine", icon: Shield },
  { id: "telemetry", label: "Telemetry", icon: Activity },
  { id: "data", label: "Data Fabric", icon: Database },
];

const TOP_METRICS: TopMetric[] = [
  {
    id: "capital",
    label: "Capital Under Review",
    value: "INR 89.55 Cr",
    subtext: "+2.4% vs prior session",
  },
  {
    id: "active",
    label: "Active Pipelines",
    value: "12",
    subtext: "3 elevated watch signals",
  },
  {
    id: "velocity",
    label: "Decision Velocity",
    value: "4.8h",
    subtext: "Median underwriting cycle",
  },
  {
    id: "approvals",
    label: "Approval Confidence",
    value: "97.2%",
    subtext: "Model certainty envelope",
  },
];

const POSTURE_ROWS: PostureRow[] = [
  {
    id: "engine",
    metric: "Inference Engine",
    status: "Healthy",
    detail: "P99 latency 118ms",
    tone: "emerald",
  },
  {
    id: "fraud",
    metric: "Fraud Sentinel",
    status: "Watch",
    detail: "2 anomalous hops detected",
    tone: "amber",
  },
  {
    id: "stream",
    metric: "Event Stream",
    status: "Healthy",
    detail: "0 dropped packets / 24h",
    tone: "emerald",
  },
  {
    id: "ledger",
    metric: "Ledger Sync",
    status: "Healthy",
    detail: "Replication lag 430ms",
    tone: "emerald",
  },
];

type TelemetryPoint = { time: UTCTimestamp; value: number };

function buildTelemetrySeries(points: number): TelemetryPoint[] {
  const nowSec = Math.floor(Date.now() / 1000);
  const start = nowSec - points * 60;
  let price = 74_800;
  const result: TelemetryPoint[] = [];

  for (let i = 0; i < points; i += 1) {
    const volatility = (Math.random() - 0.5) * 360;
    const impulse = Math.sin(i / 4) * 55 + Math.cos(i / 9) * 28;
    price = Math.max(72_000, price + volatility + impulse);
    result.push({
      time: (start + i * 60) as UTCTimestamp,
      value: Number(price.toFixed(2)),
    });
  }

  return result;
}

function TelemetryChart() {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const telemetryData = useMemo(() => buildTelemetrySeries(50), []);

  useEffect(() => {
    if (!hostRef.current) return;

    const chart = createChart(hostRef.current, {
      width: hostRef.current.clientWidth,
      height: 320,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#A1A1AA",
      },
      grid: {
        vertLines: { color: "rgba(255, 255, 255, 0.03)" },
        horzLines: { color: "rgba(255, 255, 255, 0.03)" },
      },
      crosshair: {
        mode: CrosshairMode.Magnet,
        vertLine: {
          color: "#3F3F46",
          style: LineStyle.Dashed,
          width: 1,
        },
        horzLine: {
          color: "#3F3F46",
          style: LineStyle.Dashed,
          width: 1,
        },
      },
      timeScale: {
        borderVisible: false,
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderVisible: false,
        scaleMargins: {
          top: 0.2,
          bottom: 0.2,
        },
      },
    });

    const area = chart.addSeries(AreaSeries, {
      lineColor: "#10B981",
      lineWidth: 2,
      topColor: "rgba(16, 185, 129, 0.2)",
      bottomColor: "rgba(16, 185, 129, 0.0)",
    });

    area.setData(telemetryData);
    chart.timeScale().fitContent();
    chartRef.current = chart;

    const observer = new ResizeObserver((entries) => {
      const [entry] = entries;
      if (!entry || !chartRef.current) return;
      const { width, height } = entry.contentRect;
      chartRef.current.applyOptions({
        width: Math.floor(width),
        height: Math.max(280, Math.floor(height)),
      });
    });

    observer.observe(hostRef.current);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [telemetryData]);

  return (
    <section className="rounded-xl border border-white/10 bg-[#141417] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
      <header className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-zinc-400">
          Capital Flow Telemetry
        </h3>
        <span className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-400">
          <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.9)]" />
          Live
        </span>
      </header>
      <div ref={hostRef} className="h-[320px] w-full" />
    </section>
  );
}

export default function EnterpriseDashboardPage() {
  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-100">
      <aside className="fixed left-0 top-0 z-20 flex h-screen w-64 flex-col border-r border-white/5 bg-[#141417] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
        <div className="mb-8 flex items-center gap-3">
          <svg
            className="h-9 w-9"
            viewBox="0 0 40 40"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path d="M5 30L14 8L22 19L15 32L5 30Z" fill="#10B981" fillOpacity="0.85" />
            <path d="M15 32L22 19L34 12L28 34L15 32Z" fill="#059669" fillOpacity="0.9" />
            <path
              d="M9 25L24 14"
              stroke="#34D399"
              strokeWidth="2"
              strokeLinecap="round"
              className="drop-shadow-[0_0_8px_rgba(16,185,129,0.8)]"
            />
            <path
              d="M14 8L34 12"
              stroke="#6EE7B7"
              strokeWidth="1.5"
              strokeOpacity="0.65"
              strokeLinecap="round"
            />
          </svg>
          <div className="text-xl font-bold tracking-tighter text-zinc-50">Credx</div>
        </div>

        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={[
                  "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition",
                  item.active
                    ? "bg-white/10 text-zinc-100"
                    : "text-zinc-400 hover:bg-white/5 hover:text-zinc-100",
                ].join(" ")}
                type="button"
              >
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="mt-auto rounded-xl border border-white/10 bg-[#111114] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
          <button
            type="button"
            className="flex w-full items-center justify-between rounded-lg px-2 py-2 text-sm text-zinc-300 transition hover:bg-white/5"
          >
            <span className="font-medium">Production Grid</span>
            <ChevronDown className="h-4 w-4 text-zinc-500" />
          </button>
          <p className="px-2 pb-1 pt-0.5 text-[11px] tracking-wide text-zinc-500">
            ap-south-1 / low-latency cluster
          </p>
        </div>
      </aside>

      <main className="ml-64 min-h-screen">
        <header className="sticky top-0 z-30 border-b border-white/5 bg-[#09090b]/80 backdrop-blur-md">
          <div className="flex items-center justify-between px-8 py-4">
            <div className="text-xs text-zinc-400">Home / Command Deck / Trading Telemetry</div>
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold text-emerald-400">
              <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.9)]" />
              System Healthy
            </div>
          </div>
        </header>

        <div className="space-y-6 px-8 py-7">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-zinc-50">Portfolio Command Surface</h1>
          </div>

          <section className="rounded-xl border border-white/10 bg-[#141417] shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
            <div className="grid grid-cols-1 divide-y divide-white/5 md:grid-cols-4 md:divide-x md:divide-y-0">
              {TOP_METRICS.map((metric) => (
                <div key={metric.id} className="p-5">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">{metric.label}</p>
                  <p className="mt-2 text-2xl font-medium tracking-tight text-zinc-100">{metric.value}</p>
                  <p className="mt-1 text-xs text-zinc-500">{metric.subtext}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="grid grid-cols-1 gap-6 xl:grid-cols-12">
            <div className="xl:col-span-8">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Control Tower</h2>
                <div className="inline-flex items-center gap-2 text-xs text-zinc-400">
                  <BarChart3 className="h-3.5 w-3.5" />
                  real-time risk exposure
                </div>
              </div>
              <TelemetryChart />
            </div>

            <div className="xl:col-span-4">
              <div className="mb-3">
                <h2 className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">System Posture</h2>
              </div>
              <section className="rounded-xl border border-white/10 bg-[#141417] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]">
                <div className="space-y-3">
                  {POSTURE_ROWS.map((row) => (
                    <div
                      key={row.id}
                      className="rounded-lg border border-white/10 bg-[#111114] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-zinc-200">{row.metric}</p>
                        <span
                          className={[
                            "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.12em]",
                            row.tone === "emerald"
                              ? "border border-emerald-500/20 bg-emerald-500/10 text-emerald-400"
                              : "border border-amber-500/20 bg-amber-500/10 text-amber-400",
                          ].join(" ")}
                        >
                          <span
                            className={[
                              "h-1.5 w-1.5 rounded-full",
                              row.tone === "emerald" ? "bg-emerald-400" : "bg-amber-400",
                            ].join(" ")}
                          />
                          {row.status}
                        </span>
                      </div>
                      <p className="mt-1.5 text-xs text-zinc-500">{row.detail}</p>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}