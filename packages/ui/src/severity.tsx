import type { CSSProperties, ReactNode } from "react";

import { STATUS_META } from "./verdict";

export interface SeverityChipProps {
  severity: keyof typeof STATUS_META | string;
}

/** Strict severity chip — crisp 4px corners, mono uppercase. */
export function SeverityChip({ severity }: SeverityChipProps): ReactNode {
  const meta = STATUS_META[severity as keyof typeof STATUS_META] ?? {
    label: severity.toUpperCase(),
    text: "#475569",
    fill: "#f1f5f9",
    border: "#cbd5e1",
  };
  return (
    <span
      className="app-severity-chip"
      style={
        {
          color: meta.text,
          backgroundColor: meta.fill,
          borderColor: meta.border,
        } as CSSProperties
      }
    >
      {meta.label}
    </span>
  );
}

export function severityStyle(severity: string): { text: string; fill: string; border: string } {
  const meta = STATUS_META[severity as keyof typeof STATUS_META];
  if (!meta) return { text: "#475569", fill: "#f1f5f9", border: "#cbd5e1" };
  return meta;
}