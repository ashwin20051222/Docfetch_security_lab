import type { CSSProperties, ReactNode } from "react";

export interface ChipProps {
  label?: string;
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
}

/** Fixed-height status chip in JetBrains Mono, 11px uppercase, 0.03em tracking. */
export function Chip({ label, className, style, children }: ChipProps) {
  return (
    <span
      className={`app-chip ${className ?? ""}`}
      style={style}
    >
      {children ?? label}
    </span>
  );
}

export interface StatusDotProps {
  color: string;
  pulse?: boolean;
  label: string;
}

export function StatusDot({ color, pulse, label }: StatusDotProps) {
  return (
    <span className="inline-flex items-center gap-1.5 align-middle">
      <span
        className={`status-dot ${pulse ? "pulse" : ""}`}
        style={{ backgroundColor: color, boxShadow: pulse ? `0 0 0 0 ${color}` : undefined }}
        aria-hidden="true"
      />
      <span className="app-mon-label">{label}</span>
    </span>
  );
}

export interface PillProps {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}

export function Pill({ active, onClick, children }: PillProps) {
  return (
    <button
      type="button"
      className={`app-pill ${active ? "app-pill-active" : ""}`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}