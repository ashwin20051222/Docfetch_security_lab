import { useCallback, useEffect, useState } from "react";

import { client, ApiError } from "@docfetch/core";
import type { Finding, FindingStatus, LabTarget } from "@docfetch/types";
import { Chip, SEVERITY_META, STATUS_META } from "@docfetch/ui";

import { usePoll } from "../hooks";

const STATUS_ORDER: FindingStatus[] = ["open", "acknowledged", "verified", "fixed"];

export function FindingsPage() {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [targets, setTargets] = useState<LabTarget[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FindingStatus | "all">("all");

  const load = useCallback(async () => {
    const [f, t] = await Promise.all([
      client.listFindings().catch(() => [] as Finding[]),
      client.listTargets().catch(() => [] as LabTarget[]),
    ]);
    setFindings(f);
    setTargets(t);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  usePoll(load, 20_000);

  const patch = useCallback(
    async (id: string, status: FindingStatus) => {
      setError(null);
      try {
        await client.updateFinding(id, { status });
        await load();
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Update failed");
      }
    },
    [load],
  );

  const targetName = (id: string) => targets.find((t) => t.id === id)?.name ?? "unknown target";
  const visible = filter === "all" ? findings : findings.filter((f) => f.status === filter);

  return (
    <>
      <div className="app-card">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="app-headline-md">Security Findings</h2>
            <p className="app-body-sm text-on-surface-variant">
              Every finding is derived from a real, recorded probe response — never from fabricated data.
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {(["all", ...STATUS_ORDER] as const).map((s) => (
              <button
                key={s}
                type="button"
                className={`app-pill ${filter === s ? "app-pill-active" : ""}`}
                onClick={() => setFilter(s)}
              >
                {s === "all" ? `All (${findings.length})` : STATUS_META[s].label}
              </button>
            ))}
          </div>
        </div>

        {error && <div className="app-callout mb-3">{error}</div>}

        {visible.length === 0 ? (
          <p className="app-body-sm text-on-surface-variant">
            {findings.length === 0
              ? "No findings yet — run tests from the Security Lab page. All targets pass here means clean behavior."
              : "Nothing matches this status filter."}
          </p>
        ) : (
          <table className="app-table">
            <thead>
              <tr>
                <th style={{ width: 80 }}>Severity</th>
                <th>Finding</th>
                <th>Target</th>
                <th>Status</th>
                <th>Detected</th>
                <th className="text-right">Triage</th>
              </tr>
            </thead>
            <tbody>
              {visible.slice(0, 100).map((f) => {
                const sev = SEVERITY_META[f.severity] ?? SEVERITY_META.low;
                const st = STATUS_META[f.status];
                return (
                  <tr key={f.id}>
                    <td>
                      <Chip style={{ color: sev.text, background: sev.fill, borderColor: sev.border }}>
                        {sev.label}
                      </Chip>
                    </td>
                    <td>
                      <div className="font-semibold text-on-surface">{f.title}</div>
                      <div className="app-body-sm text-on-surface-variant line-clamp-2">{f.observed_behavior}</div>
                    </td>
                    <td className="app-code-body text-secondary">{targetName(f.target_id)}</td>
                    <td>
                      <Chip style={{ color: st.text, background: st.fill, borderColor: st.border }}>
                        {st.label}
                      </Chip>
                    </td>
                    <td className="app-code-body text-secondary tabular">{new Date(f.created_at).toLocaleDateString()}</td>
                    <td className="text-right whitespace-nowrap">
                      <select
                        className="app-input"
                        style={{ width: "auto", display: "inline-flex", padding: "4px 8px", fontSize: 12 }}
                        value={f.status}
                        onChange={(e) => void patch(f.id, e.target.value as FindingStatus)}
                      >
                        {STATUS_ORDER.map((s) => (
                          <option key={s} value={s}>
                            {STATUS_META[s].label}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}