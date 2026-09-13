import { useCallback, useEffect, useState } from "react";

import { client, ApiError } from "@docfetch/core";
import type { LabTarget, SecurityReport } from "@docfetch/types";

export function SettingsPage() {
  const [targets, setTargets] = useState<LabTarget[]>([]);
  const [reports, setReports] = useState<SecurityReport[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [targetId, setTargetId] = useState<string>("");
  const [format, setFormat] = useState<"json" | "html">("json");
  const [generating, setGenerating] = useState(false);

  const load = useCallback(async () => {
    const [t, r] = await Promise.all([
      client.listTargets().catch(() => [] as LabTarget[]),
      client.listReports().catch(() => [] as SecurityReport[]),
    ]);
    setTargets(t);
    setReports(r);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const first = targets.find(() => true);
    if (!targetId && first) {
      setTargetId(first.id);
    }
  }, [targets, targetId]);

  const generate = useCallback(async () => {
    if (!targetId) return;
    setGenerating(true);
    setError(null);
    try {
      await client.generateReport(targetId, [format]);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Report generation failed");
    } finally {
      setGenerating(false);
    }
  }, [targetId, format, load]);

  return (
    <>
      <div className="app-card">
        <h2 className="app-headline-md mb-1">Settings & Report Export</h2>
        <p className="app-body-sm text-on-surface-variant">
          Reports are written server-side from executed tests and open findings — they never invent data.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4">
          <select className="app-input" value={targetId} onChange={(e) => setTargetId(e.target.value)}>
            <option value="" disabled>
              Select a target
            </option>
            {targets.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
          <select className="app-input" value={format} onChange={(e) => setFormat(e.target.value as "json" | "html")}>
            <option value="json">JSON</option>
            <option value="html">HTML</option>
          </select>
          <button type="button" className="app-btn app-btn-primary" disabled={generating} onClick={() => void generate()}>
            {generating ? "Generating…" : "Generate Report"}
          </button>
        </div>
        {error && <div className="app-callout mt-3">{error}</div>}
      </div>

      <div className="app-card">
        <h3 className="app-headline-md mb-3">Generated Reports</h3>
        {reports.length === 0 ? (
          <p className="app-body-sm text-on-surface-variant">No reports yet.</p>
        ) : (
          <table className="app-table">
            <thead>
              <tr>
                <th>Format</th>
                <th>Target</th>
                <th>Findings</th>
                <th>Generated</th>
                <th className="text-right">Download</th>
              </tr>
            </thead>
            <tbody>
              {reports.slice(0, 50).map((r) => (
                <tr key={r.id}>
                  <td className="app-code-body text-secondary">{r.format.toUpperCase()}</td>
                  <td className="app-code-body text-secondary">{targets.find((t) => t.id === r.target_id)?.name ?? "All targets"}</td>
                  <td className="tabular">{r.finding_count}</td>
                  <td className="app-code-body text-secondary tabular">{new Date(r.created_at).toLocaleString()}</td>
                  <td className="text-right">
                    <a className="app-btn" href={client.reportDownloadUrl(r.id)}>
                      Download
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}