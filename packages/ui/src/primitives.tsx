import type { ReactNode } from "react";

export function Spinner({ label = "working…" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-secondary text-[13px]">
      <span className="spinner" aria-hidden="true" />
      <span className="font-body-md text-[13px]">{label}</span>
    </span>
  );
}

export interface CardProps {
  children: ReactNode;
  className?: string;
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function Card({ children, className, title, subtitle, actions }: CardProps) {
  return (
    <section className={`app-card ${className ?? ""}`}>
      {(title || actions) && (
        <div className="flex items-center justify-between gap-3 mb-3">
          <div>
            {title && <h3 className="app-headline-md">{title}</h3>}
            {subtitle && <p className="app-body-sm text-on-surface-variant mt-0.5">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export interface MetricCardProps {
  label: string;
  value: string | number;
  hint: string;
  icon: ReactNode;
  tone?: "primary" | "tertiary" | "error";
}

export function MetricCard({ label, value, hint, icon, tone = "primary" }: MetricCardProps) {
  const color = tone === "error" ? "#ba1a1a" : tone === "tertiary" ? "#00685f" : "#006948";
  return (
    <div className="app-card">
      <div className="flex items-center justify-between text-secondary">
        <span className="font-body-sm text-body-sm">{label}</span>
        <span style={{ color }}>{icon}</span>
      </div>
      <div className="mt-3">
        <span className="app-headline-xl font-bold" style={tone === "error" ? { color } : undefined}>
          {value}
        </span>
      </div>
      <div className="mt-1 app-label-sm" style={{ color: tone === "error" ? color : "#006948" }}>
        {hint}
      </div>
    </div>
  );
}

export interface ButtonProps {
  variant?: "primary" | "secondary" | "destructive";
  disabled?: boolean;
  onClick?: () => void;
  children: ReactNode;
  type?: "button" | "submit";
  className?: string;
}

export function Button({ variant = "secondary", disabled, onClick, children, type = "button", className }: ButtonProps) {
  const cls =
    variant === "primary"
      ? "app-btn app-btn-primary"
      : variant === "destructive"
        ? "app-btn app-btn-destructive"
        : "app-btn";
  return (
    <button type={type} className={`${cls} ${className ?? ""}`} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}