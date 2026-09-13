import type { FindingSeverity, FindingStatus, TestStatus } from "@docfetch/types";

export const SEVERITY_META: Record<FindingSeverity, { label: string; text: string; fill: string; border: string }> = {
  critical: {
    label: "CRITICAL",
    text: "#b91c1c",
    fill: "#fef2f2",
    border: "#fca5a5",
  },
  high: {
    label: "HIGH",
    text: "#c2410c",
    fill: "#fff7ed",
    border: "#fdba74",
  },
  medium: {
    label: "MEDIUM",
    text: "#b45309",
    fill: "#fffbeb",
    border: "#fcd34d",
  },
  low: {
    label: "LOW",
    text: "#475569",
    fill: "#f1f5f9",
    border: "#cbd5e1",
  },
  informational: {
    label: "INFO",
    text: "#0f766e",
    fill: "#f0fdfa",
    border: "#99f6e4",
  },
};

export const STATUS_META: Record<FindingStatus, { label: string; text: string; fill: string; border: string }> = {
  open: { label: "OPEN", text: "#b91c1c", fill: "#fef2f2", border: "#fecaca" },
  acknowledged: { label: "ACKNOWLEDGED", text: "#b45309", fill: "#fffbeb", border: "#fde68a" },
  verified: { label: "VERIFIED", text: "#0f766e", fill: "#f0fdfa", border: "#5eead4" },
  fixed: { label: "FIXED", text: "#047857", fill: "#ecfdf5", border: "#6ee7b7" },
};

export const TEST_STATUS_META: Record<TestStatus, { label: string; dot: string; text?: string }> = {
  running: { label: "RUNNING", dot: "#059669" },
  passed: { label: "PASSED", dot: "#059669" },
  failed: { label: "FAILED", dot: "#b91c1c" },
  error: { label: "ERROR", dot: "#b91c1c" },
};

/** Map a backend document verdict to a readable, honest status phrase. */
export function verdictLabel(verdict: string, status: string): string {
  if (status === "failed" || status === "expired") return "FAILED";
  switch (verdict) {
    case "document_found":
      return "DOCUMENT RETRIEVED";
    case "not_a_document":
      return "NOT A DOCUMENT";
    case "blocked":
      return "BLOCKED";
    case "failed":
      return "FAILED";
    default:
      return status.toUpperCase();
  }
}