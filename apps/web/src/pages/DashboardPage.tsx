import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { client } from "@docfetch/core";
import type { DashboardSummary } from "@docfetch/types";
import { StatusDot } from "@docfetch/ui";

import { usePoll } from "../hooks";

export function DashboardPage() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    () =>
      client
        .dashboard()
        .then(setSummary)
        .catch((e: Error) => setError(e.message)),
    [],
  );

  useEffect(() => {
    void load();
  }, [load]);

  usePoll(load, 10_000);

  const docs = summary?.documents_total ?? 0;
  const tests = summary?.tests_total ?? 0;
  const reachable = summary?.targets_reachable ?? 0;
  const targets = summary?.targets_total ?? 0;
  const findings = summary?.open_findings ?? 0;

  return (
    <>
      {/* Quick actions */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="app-card flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center rounded-xl w-10 h-10" style={{ background: "color-mix(in srgb, var(--primary-container) 15%, white)" }}>
                <span className="text-primary">⌕</span>
              </div>
              <div>
                <h2 className="app-headline-md">Retrieve Public Document</h2>
                <p className="app-body-sm text-on-surface-variant">Fetch open-access PDFs by URL.</p>
              </div>
            </div>
            <div className="flex flex-col sm:flex-row gap-2 pt-2">
              <input
                className="app-input flex-1"
                placeholder="Enter a public PDF URL…"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.target as HTMLInputElement).value.trim()) {
                    navigate(`/retrieve?url=${encodeURIComponent((e.target as HTMLInputElement).value.trim())}`);
                  }
                }}
              />
              <button
                type="button"
                className="app-btn app-btn-primary"
                onClick={() => {
                  const input = document.querySelector<HTMLInputElement>("main input.app-input");
                  if (input?.value.trim()) navigate(`/retrieve?url=${encodeURIComponent(input.value.trim())}`);
                }}
              >
                Fetch →
              </button>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t flex items-center justify-between app-label-sm text-secondary" style={{ borderColor: "var(--surface-container-low)" }}>
            <span>Open Access & Public URLs Only</span>
            <span className="text-on-surface-variant">{error ? "API offline" : "Ready"}</span>
          </div>
        </div>

        <div className="app-card flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center rounded-xl w-10 h-10" style={{ background: "color-mix(in srgb, var(--primary-container) 15%, white)" }}>
                <span className="text-primary">◈</span>
              </div>
              <div>
                <h2 className="app-headline-md">Security Test Runner</h2>
                <p className="app-body-sm text-on-surface-variant">Run verification probes against authorized local targets.</p>
              </div>
            </div>
            <div className="pt-2">
              <button type="button" className="app-btn app-btn-primary" onClick={() => navigate("/lab")}>
                Open Security Lab →
              </button>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t flex items-center justify-between app-label-sm text-secondary" style={{ borderColor: "var(--surface-container-low)" }}>
            <span className="flex items-center gap-1.5">
              <span className="status-dot" style={{ background: reachable > 0 ? "var(--primary)" : "var(--outline-variant)" }} />
              Isolated Local Environment
            </span>
            <span className="text-on-surface-variant">
              {reachable}/{targets} Reachable
            </span>
          </div>
        </div>
      </section>

      {/* Metrics */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="app-card">
          <div className="flex items-center justify-between text-secondary app-body-sm">Verified Documents</div>
          <div className="mt-3">
            <span className="app-headline-xl font-bold tabular">{docs}</span>
          </div>
          <div className="mt-1 app-label-sm" style={{ color: "var(--primary)" }}>
            ingested & verified
          </div>
        </div>
        <div className="app-card">
          <div className="flex items-center justify-between text-secondary app-body-sm">Tests Executed</div>
          <div className="mt-3">
            <span className="app-headline-xl font-bold tabular">{tests}</span>
          </div>
          <div className="mt-1 app-label-sm text-secondary">across {targets} targets</div>
        </div>
        <div className="app-card">
          <div className="flex items-center justify-between text-secondary app-body-sm">Lab Uptime</div>
          <div className="mt-3">
            <span className="app-headline-lg font-bold app-code-body tabular">
              {reachable}/{targets}
            </span>
          </div>
          <div className="mt-1 app-label-sm" style={{ color: "var(--primary)" }}>
            {reachable > 0 ? <StatusDot color="#059669" pulse label="Online & Isolated" /> : "None reachable"}
          </div>
        </div>
        <div className="app-card">
          <div className="flex items-center justify-between text-secondary app-body-sm">Open Findings</div>
          <div className="mt-3">
            <span className="app-headline-xl font-bold tabular" style={{ color: findings > 0 ? "var(--error)" : undefined }}>
              {findings}
            </span>
          </div>
          <div className="mt-1 app-label-sm" style={{ color: findings > 0 ? "var(--error)" : "var(--secondary)" }}>
            {summary?.all_findings ?? 0} total reported
          </div>
        </div>
      </section>

      {/* Recent activity */}
      <section className="app-card">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="app-headline-md">Recent Activity</h3>
            <p className="app-body-sm text-on-surface-variant">Live audit trail — every entry is a recorded backend event.</p>
          </div>
          <span className="app-chip" style={{ background: "var(--surface-container-low)", color: "var(--on-surface-variant)" }}>
            {summary?.recent_activity.length ?? 0} shown
          </span>
        </div>
        {error ? (
          <div className="app-callout">Backend unreachable: {error}</div>
        ) : summary && summary.recent_activity.length > 0 ? (
          <table className="app-table">
            <thead>
              <tr>
                <th>Event</th>
                <th>Detail</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {summary.recent_activity.slice(0, 8).map((a) => (
                <tr key={a.id}>
                  <td className="app-code-body tabular">{a.kind}</td>
                  <td className="text-on-surface-variant">{a.summary}</td>
                  <td className="app-code-body text-secondary tabular">
                    {new Date(a.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="app-body-sm text-on-surface-variant">
            No events yet — run an analysis or a lab test and they will appear here.
          </p>
        )}
      </section>
    </>
  );
}