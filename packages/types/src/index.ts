/**
 * Shared type surface for the DocFetch Security Lab frontend.
 * Mirrors apps/api/app/schemas.py — keep in sync when the API schema changes.
 */

// ---------------------------------------------------------------------------
// Health & version
// ---------------------------------------------------------------------------

export type HealthStatus = "ok" | "degraded" | "error";

export interface HealthCheck {
  status: HealthStatus;
  version: string;
  uptime_seconds: number | null;
  database: Record<string, unknown>;
  storage: Record<string, unknown>;
  timestamp: string;
}

export interface VersionInfo {
  name: string;
  version: string;
  app_env: string;
  auth_configured: boolean;
  rate_limits: Record<string, number>;
}

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------

export type DocumentStatus = "ready" | "processing" | "failed" | "expired";
export type DocumentSource = "url" | "upload";

export interface DocumentOut {
  id: string;
  source_url: string | null;
  final_url: string | null;
  title: string | null;
  filename: string | null;
  mime_type: string;
  size_bytes: number;
  page_count: number | null;
  sha256: string;
  status: DocumentStatus;
  error_code: string | null;
  error_message: string | null;
  source: DocumentSource;
  created_at: string;
  expires_at: string | null;
}

export interface AnalyzeResult {
  document: DocumentOut;
  verdict: "document_found" | "not_a_document" | "blocked" | "failed";
}

export interface UploadResult {
  document: DocumentOut;
  verdict: string;
}

export interface PreviewPage {
  page: number;
  width: number;
  height: number;
  thumb_url: string;
  image_url: string;
}

export interface PreviewOut {
  document_id: string;
  page_count: number;
  pages: PreviewPage[];
}

export interface DownloadRecord {
  id: string;
  document_id: string;
  downloaded_at: string;
  bytes_transferred: number;
  user_agent: string | null;
}

export interface DeleteResult {
  deleted: boolean;
  id: string;
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export interface DashboardSummary {
  documents_total: number;
  uploads_total: number;
  downloads_total: number;
  tests_total: number;
  open_findings: number;
  all_findings: number;
  targets_total: number;
  targets_reachable: number;
  recent_activity: ActivityItem[];
}

export interface ActivityItem {
  id: string;
  kind: string;
  summary: string;
  created_at: string;
  meta?: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// Security Lab
// ---------------------------------------------------------------------------

export type LabEnvironment = "local" | "docker" | "network";
export type LabAuthStatus = "none" | "token" | "header";
export type TestStatus = "running" | "passed" | "failed" | "error";
export type FindingSeverity = "critical" | "high" | "medium" | "low" | "informational";
export type FindingStatus = "open" | "acknowledged" | "verified" | "fixed";

export interface LabTarget {
  id: string;
  name: string;
  base_url: string;
  environment_type: LabEnvironment;
  auth_status: LabAuthStatus;
  allowed_test_profiles: string[];
  authorized: boolean;
  enabled: boolean;
  description: string | null;
  reachable: boolean | null;
  last_checked_at: string | null;
  created_at: string;
}

export interface LabTargetCreate {
  name: string;
  base_url: string;
  environment_type: LabEnvironment;
  auth_status: LabAuthStatus;
  allowed_test_profiles?: string[];
  description?: string | null;
}

export interface TestProfile {
  name: string;
  title: string;
  description: string;
  apply_to: LabEnvironment[];
}

export interface SecurityTest {
  id: string;
  target_id: string;
  profile: string;
  title: string;
  status: TestStatus;
  started_at: string;
  finished_at: string | null;
  request_summary: Record<string, unknown> | null;
  response_summary: Record<string, unknown> | null;
  evidence: Record<string, unknown> | null;
  error_message: string | null;
}

export interface RequestEvidence {
  method: string;
  url: string;
  timestamp: string;
  headers: Record<string, string>;
  body_summary?: string | null;
}

export interface ResponseEvidence {
  status: number;
  content_type?: string | null;
  content_length?: number | null;
  security_headers?: Record<string, string>;
  body_sha256?: string | null;
  body_preview?: string | null;
}

export interface EvidenceBlock {
  label: string;
  request: RequestEvidence;
  response: ResponseEvidence;
}

export interface Finding {
  id: string;
  target_id: string;
  test_id: string;
  title: string;
  severity: FindingSeverity;
  status: FindingStatus;
  description: string;
  expected_behavior: string;
  observed_behavior: string;
  recommendation: string;
  evidence: Record<string, unknown> | null;
  created_at: string;
}

export interface FindingPatch {
  status: FindingStatus;
  recommendation?: string | null;
}

export interface SecurityReport {
  id: string;
  target_id: string | null;
  format: "json" | "html";
  path: string | null;
  summary: Record<string, unknown> | null;
  finding_count: number;
  created_at: string;
}

export interface ReportGenerate {
  target_id?: string | null;
  formats?: Array<"json" | "html">;
}

export interface TargetCheck {
  target_id: string;
  reachable: boolean;
  checked_at: string;
}

// ---------------------------------------------------------------------------
// API errors
// ---------------------------------------------------------------------------

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string | null;
    details?: Record<string, unknown> | null;
  };
}

// ---------------------------------------------------------------------------
// Rate limits (mirror apps/api/app/core/rate_limit.py default_rules)
// ---------------------------------------------------------------------------

export const RATE_LIMIT_GROUPS: Record<string, { limit: number; window_seconds: number }> = {
  analyze: { limit: 20, window_seconds: 60 },
  upload: { limit: 15, window_seconds: 60 },
  download: { limit: 60, window_seconds: 60 },
  lab: { limit: 40, window_seconds: 60 },
};