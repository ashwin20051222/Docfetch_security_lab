import { useCallback, useEffect, useState } from "react";

import { client, ApiError } from "@docfetch/core";
import type { LabTarget, SecurityTest, TestProfile } from "@docfetch/types";
import { StatusDot, TEST_STATUS_META } from "@docfetch/ui";

import { usePoll } from "../hooks";

interface EvidenceState {
  request_url: string;
  blocks: Array<{ label: string; request: { method: string; url: string; headers: Record<string, string> }; response: Record<string, unknown> }>;
}

export function LabPage() {
  const [targets, setTargets] = useState<LabTarget[]>([]);
  const [profiles, setProfiles] = useState<TestProfile[]>([]);
  const [tests, setTests] = useState<SecurityTest[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<string>("");
  const [selectedProfile, setSelectedProfile] = useState<string>("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeEvidence, setActiveEvidence] = useState<EvidenceState | null>(null);

  const load = useCallback(async () => {
    const [t, p, ts] = await Promise.all([
      client.listTargets().catch(() => []),
      client.listProfiles().catch(() => []),
      client.listTests().catch(() => []),
    ]);
    setTargets(t);
    setProfiles(p);
    setTests(ts);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  usePoll(load, 12_000);

  const run = useCallback(async () => {
    if (!selectedTarget || !selectedProfile) return;
    setRunning(true);
    setError(null);
    setActiveEvidence(null);
    try {
      const test = await client.runTest(selectedTarget, selectedProfile);
      setTests((prev) => [test, ...prev]);
      if (test.evidence) {
        const ev = test.evidence as unknown as EvidenceState;
        setActiveEvidence(ev);
      }
      if (test.error_message) setError(test.error_message);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Test failed");
    } finally {
      setRunning(false);
    }
  }, [selectedTarget, selectedProfile]);

  const targetById = (id: string) => targets.find((t) => t.id === id);

  return (
    <>
      <div className="app-card">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex items-center justify-center rounded-xl w-10 h-10" style={{ background: "color-mix(in srgb, var(--primary-container) 15%, white)" }}>
            <span className="text-primary">◈</span>
          </div>
          <div>
            <h2 className="app-headline-md">Security Test Runner</h2>
            <p className="app-body-sm text-on-surface-variant">
              Probes execute against <b>authorized local targets</b> only. Findings derive from observed server responses — no simulation.
            </p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-2">
          <select className="app-input flex-1" value={selectedTarget} onChange={(e) => setSelectedTarget(e.target.value)}>
            <option value="">Select authorized target…</option>
            {targets.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} — {t.base_url}
              </option>
            ))}
          </select>
          <select className="app-input flex-1" value={selectedProfile} onChange={(e) => setSelectedProfile(e.target.value)}>
            <option value="">Select test profile…</option>
            {profiles.map((p) => (
              <option key={p.name} value={p.name}>
                {p.title}
              </option>
            ))}
          </select>
          <button type="button" className="app-btn app-btn-primary" disabled={running || !selectedTarget || !selectedProfile} onClick={run}>
            {running ? "Running…" : "Run Test ▶"}
          </button>
        </div>
      </div>

      {error && <div className="app-callout">{error}</div>}

      {activeEvidence && <EvidencePane evidence={activeEvidence} />}

      <div className="app-card">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="app-headline-md">Test History</h3>
            <p className="app-body-sm text-on-surface-variant">Most recent first — live from the backend.</p>
          </div>
          <span className="app-chip" style={{ background: "var(--surface-container-low)", color: "var(--on-surface-variant)" }}>
            {tests.length} executed
          </span>
        </div>
        {tests.length === 0 ? (
          <p className="app-body-sm text-on-surface-variant">
            No tests yet. Run your first verification probe above — findings will also appear in the Findings page.
          </p>
        ) : (
          <table className="app-table">
            <thead>
              <tr>
                <th>Profile</th>
                <th>Target</th>
                <th>Status</th>
                <th>Response</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {tests.slice(0, 25).map((test) => {
                const t = targetById(test.target_id);
                const rs = test.response_summary as Record<string, unknown> | null;
                const statusMeta = TEST_STATUS_META[test.status] ?? TEST_STATUS_META.error;
                return (
                  <tr key={test.id}>
                    <td className="font-semibold">{test.title}</td>
                    <td className="app-code-body text-secondary">{t?.name ?? test.target_id}</td>
                    <td>
                      <StatusDot color={statusMeta.dot} pulse={test.status === "running"} label={statusMeta.label} />
                    </td>
                    <td className="app-code-body tabular">
                      {rs
                        ? `${String(rs.unauthorized_status ?? "?")} vs ${String(rs.authorized_status ?? "?")}`
                        : test.status === "running"
                          ? "…"
                          : "—"}
                    </td>
                    <td className="app-code-body text-secondary tabular">
                      {new Date(test.started_at).toLocaleString()}
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

function EvidencePane({ evidence }: { evidence: EvidenceState }) {
  const blocks = evidence.blocks ?? [];
  return (
    <div className="app-card" style={{ borderColor: "var(--outline-variant)" }}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="app-headline-md">Requests / Response Evidence — {evidence.request_url}</h3>
        <span className="app-chip" style={{ background: "var(--surface-container-low)", color: "var(--on-surface-variant)" }}>
          Real HTTP
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {blocks.map((block) => (
          <div key={block.label} className="evidence-pane" style={{ maxHeight: 420 }}>
            <div className="app-label-body mb-2" style={{ color: "var(--primary)" }}>
              {block.label}
            </div>
            <div className="app-code-body">
              <span className="text-on-surface">{block.request.method} {block.request.url}</span>
            </div>
            <div className="mt-1 app-code-body text-secondary tabular">
              status: {String(block.response.status)} · type: {String(block.response.content_type ?? "–")} · bytes: {String(block.response.content_length ?? 0)}
            </div>
            <div className="mt-1 app-code-body text-secondary tabular">
              sha256: {block.response.body_sha256 ? String(block.response.body_sha256).slice(0, 32) + "…" : "–"}
            </div>
            <div className="mt-2 pl-3 border-l" style={{ borderColor: "var(--outline-variant)" }}>
              <div className="app-label-sm mb-1">HEADERS (REDACTED)</div>
              <div className="app-code-body text-secondary">
                {Object.entries(block.request.headers ?? {}).map(([k, v]) => (
                  <div key={k}>
                    {k}: <span className="del">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}