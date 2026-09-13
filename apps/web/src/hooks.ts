import { useCallback, useEffect, useState } from "react";

import { client } from "@docfetch/core";
import type { HealthCheck, VersionInfo } from "@docfetch/types";

export interface AppMeta {
  health: HealthCheck | null;
  version: VersionInfo | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/** Fetch application health + version once on mount; manual refresh available. */
export function useAppMeta(): AppMeta {
  const [health, setHealth] = useState<HealthCheck | null>(null);
  const [version, setVersion] = useState<VersionInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([client.health(), client.version()])
      .then(([h, v]) => {
        setHealth(h);
        setVersion(v);
      })
      .catch((e: unknown) => {
        setHealth(null);
        setVersion(null);
        setError(e instanceof Error ? e.message : "API unreachable");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(refresh, [refresh]);

  return { health, version, loading, error, refresh };
}

/** Kick off a poll loop that re-runs `fn` every `ms` while `active`. */
export function usePoll<T>(fn: () => Promise<T>, ms: number, active = true) {
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => {
      void fn().catch(() => undefined);
    }, ms);
    return () => clearInterval(id);
  }, [fn, ms, active]);
}