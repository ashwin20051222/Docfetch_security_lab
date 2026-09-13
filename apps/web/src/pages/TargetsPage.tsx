import { useCallback, useEffect, useState } from "react";

import { client, ApiError } from "@docfetch/core";
import type { LabTarget, LabTargetCreate, TestProfile } from "@docfetch/types";
import { StatusDot } from "@docfetch/ui";

import { usePoll } from "../hooks";

export function TargetsPage() {
  const [targets, setTargets] = useState<LabTarget[]>([]);
  const [apiProfiles, setProfiles] = useState<TestProfile[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [environment, setEnvironment] = useState<LabTargetCreate["environment_type"]>("local");
  const [auth, setAuth] = useState<LabTargetCreate["auth_status"]>("none");
  const [formProfiles, setFormProfiles] = useState<string[]>([]);

  const toggleProfile = (p: string) =>
    setFormProfiles((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]));

  const load = useCallback(async () => {
    const [t, p] = await Promise.all([
      client.listTargets().catch(() => [] as LabTarget[]),
      client.listProfiles().catch(() => [] as TestProfile[]),
    ]);
    setTargets(t);
    setProfiles(p);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  usePoll(load, 15_000);

  const checkTarget = useCallback(async (id: string) => {
    setChecking(id);
    setError(null);
    try {
      await client.checkTarget(id);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Check failed");
    } finally {
      setChecking(null);
    }
  }, [load]);

  const create = useCallback(async () => {
    setError(null);
    try {
      await client.createTarget({
        name,
        base_url: baseUrl,
        environment_type: environment,
        auth_status: auth,
        allowed_test_profiles: formProfiles,
      });
      setName("");
      setBaseUrl("");
      setEnvironment("local");
      setAuth("none");
      setFormProfiles([]);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not register target");
    }
  }, [load, name, baseUrl, environment, auth, formProfiles]);

  const del = useCallback(
    async (id: string) => {
      setError(null);
      try {
        await client.deleteTarget(id);
        await load();
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Could not delete target");
      }
    },
    [load],
  );

  return (
    <>
      <div className="app-card">
        <h2 className="app-headline-md mb-1">Authorized Test Targets</h2>
        <p className="app-body-sm text-on-surface-variant mb-4">
          Only targets in this allowlist can be probed. External hosts require explicit authorization. Loopback targets are auto-authorized because you own them.
        </p>
        {error && <div className="app-callout mb-3">{error}</div>}
        {targets.length === 0 ? (
          <p className="app-body-sm text-on-surface-variant">No targets registered.</p>
        ) : (
          <table className="app-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Base URL</th>
                <th>Env</th>
                <th>Status</th>
                <th>Profiles</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {targets.map((t) => (
                <tr key={t.id}>
                  <td className="font-semibold">{t.name}</td>
                  <td className="app-code-body text-secondary">{t.base_url}</td>
                  <td className="app-code-body text-secondary">{t.environment_type}</td>
                  <td>
                    <StatusDot
                      color={t.reachable === false ? "#b91c1c" : t.reachable ? "#059669" : "#94a3b8"}
                      pulse={t.reachable === true}
                      label={t.reachable == null ? "UNCHECKED" : t.reachable ? "ONLINE" : "OFFLINE"}
                    />
                  </td>
                  <td className="app-code-body text-secondary">{t.allowed_test_profiles.join(", ") || "—"}</td>
                  <td className="text-right">
                    <button type="button" className="app-btn" disabled={checking === t.id} onClick={() => void checkTarget(t.id)}>
                      {checking === t.id ? "Checking…" : "Check"}
                    </button>{" "}
                    <button type="button" className="app-btn app-btn-destructive" onClick={() => void del(t.id)}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="app-card">
        <h3 className="app-headline-md mb-3">Register a New Target</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <input className="app-input" placeholder="Name (e.g. Local Lab A)" value={name} onChange={(e) => setName(e.target.value)} />
          <input className="app-input mono" placeholder="http://127.0.0.1:9444" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          <select className="app-input" value={environment} onChange={(e) => setEnvironment(e.target.value as LabTargetCreate["environment_type"])}>
            <option value="local">local</option>
            <option value="docker">docker</option>
            <option value="network">network</option>
          </select>
          <select
            className="app-input"
            value={auth}
            onChange={(e) => setAuth(e.target.value as LabTargetCreate["auth_status"])}
          >
            <option value="none">auth: none</option>
            <option value="token">auth: token</option>
            <option value="header">auth: header</option>
          </select>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {apiProfiles.map((p) => (
            <button
              key={p.name}
              type="button"
              className={`app-pill ${formProfiles.includes(p.name) ? "app-pill-active" : ""}`}
              onClick={() => toggleProfile(p.name)}
            >
              {p.title}
            </button>
          ))}
        </div>
        <div className="mt-4">
          <button type="button" className="app-btn app-btn-primary" onClick={() => void create()}>
            Register Target
          </button>
        </div>
      </div>
    </>
  );
}

