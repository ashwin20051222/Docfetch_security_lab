/**
 * Typed API client for the DocFetch Security Lab backend.
 *
 * All requests go through {@link apiFetch} which:
 *  - resolves a relative base URL for web/desktop builds
 *  - surfaces 4xx/5xx as {@link ApiError} with the backend error contract
 *  - opts into credentials for CORS-aware local development
 */
import type {
  AnalyzeResult,
  ApiErrorBody,
  DashboardSummary,
  DeleteResult,
  DocumentOut,
  DownloadRecord,
  Finding,
  FindingPatch,
  HealthCheck,
  LabTarget,
  LabTargetCreate,
  PreviewOut,
  SecurityReport,
  SecurityTest,
  TargetCheck,
  TestProfile,
  UploadResult,
  VersionInfo,
} from "@docfetch/types";

export interface ApiErrorDetails extends Error {
  code: string;
  requestId: string | null;
  status: number;
  details: Record<string, unknown> | null;
}

export class ApiError extends Error implements ApiErrorDetails {
  readonly code: string;
  readonly requestId: string | null;
  readonly status: number;
  readonly details: Record<string, unknown> | null;

  constructor(
    message: string,
    code: string,
    status: number,
    requestId: string | null,
    details: Record<string, unknown> | null,
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
    this.details = details;
  }
}

export interface ClientOptions {
  /** Absolute base URL of the API. Resolved from the environment otherwise. */
  baseUrl?: string;
  /** Throw on HTTP error statuses. Default true. */
  throwOnError?: boolean;
}

const DEFAULT_BASE = (import.meta as unknown)
  ? (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"
  : "http://127.0.0.1:8000";

export class DocFetchClient {
  readonly baseUrl: string;
  private readonly throwOnError: boolean;

  constructor(options: ClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? DEFAULT_BASE).replace(/\/+$/, "");
    this.throwOnError = options.throwOnError ?? true;
  }

  async request<T>(
    method: string,
    path: string,
    body?: unknown,
    init: RequestInit = {},
  ): Promise<T> {
    const headers: Record<string, string> = {
      ...(init.headers as Record<string, string> | undefined),
    };
    let payload: BodyInit | undefined;
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      method,
      headers,
      body: payload,
    });

    if (!response.ok && this.throwOnError) {
      let errBody: ApiErrorBody | null = null;
      try {
        errBody = (await response.json()) as ApiErrorBody;
      } catch {
        // Non-JSON error body; fall through to generic.
      }
      const error = errBody?.error;
      throw new ApiError(
        error?.message ?? `HTTP ${response.status} ${response.statusText}`,
        error?.code ?? "HTTP_ERROR",
        response.status,
        error?.request_id ?? null,
        error?.details ?? null,
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }
    const text = await response.text();
    return (text ? (JSON.parse(text) as T) : undefined) as T;
  }

  // -- Health & version ------------------------------------------------------

  health = (): Promise<HealthCheck> => this.request("GET", "/api/v1/health");
  version = (): Promise<VersionInfo> => this.request("GET", "/api/v1/version");

  // -- Dashboard -------------------------------------------------------------

  dashboard = (): Promise<DashboardSummary> =>
    this.request("GET", "/api/v1/dashboard/summary");

  // -- Documents -------------------------------------------------------------

  analyze = (url: string, titleHint?: string): Promise<AnalyzeResult> =>
    this.request("POST", "/api/v1/analyze", { url, title_hint: titleHint });

  async upload(
    file: File,
    onProgress?: (percent: number) => void,
  ): Promise<UploadResult> {
    const form = new FormData();
    form.append("file", file, file.name);

    const response = await fetch(`${this.baseUrl}/api/v1/uploads`, {
      method: "POST",
      body: form,
    });

    if (this.throwOnError && !response.ok) {
      let errBody: ApiErrorBody | null = null;
      try {
        errBody = (await response.json()) as ApiErrorBody;
      } catch {
        // ignore
      }
      const error = errBody?.error;
      throw new ApiError(
        error?.message ?? `HTTP ${response.status}`,
        error?.code ?? "HTTP_ERROR",
        response.status,
        error?.request_id ?? null,
        error?.details ?? null,
      );
    }
    void onProgress;
    return (await response.json()) as UploadResult;
  }

  listDocuments = (): Promise<DocumentOut[]> =>
    this.request("GET", "/api/v1/documents");

  getDocument = (id: string): Promise<DocumentOut> =>
    this.request("GET", `/api/v1/documents/${id}`);

  deleteDocument = (id: string): Promise<DeleteResult> =>
    this.request("DELETE", `/api/v1/documents/${id}`);

  preview = (id: string): Promise<PreviewOut> =>
    this.request("GET", `/api/v1/documents/${id}/preview`);

  downloadUrl = (id: string): string =>
    `${this.baseUrl}/api/v1/documents/${id}/download`;

  pageImageUrl = (pageUrl: string): string =>
    pageUrl.startsWith("http") ? pageUrl : `${this.baseUrl}${pageUrl}`;

  listDownloads = (): Promise<DownloadRecord[]> =>
    this.request("GET", "/api/v1/downloads");

  // -- Security Lab ----------------------------------------------------------

  listTargets = (): Promise<LabTarget[]> =>
    this.request("GET", "/api/v1/lab/targets");

  createTarget = (body: LabTargetCreate): Promise<LabTarget> =>
    this.request("POST", "/api/v1/lab/targets", body);

  deleteTarget = (id: string): Promise<DeleteResult> =>
    this.request("DELETE", `/api/v1/lab/targets/${id}`);

  checkTarget = (id: string): Promise<TargetCheck> =>
    this.request("POST", `/api/v1/lab/targets/${id}/check`);

  listProfiles = (): Promise<TestProfile[]> =>
    this.request("GET", "/api/v1/lab/profiles");

  runTest = (targetId: string, profile: string): Promise<SecurityTest> =>
    this.request("POST", "/api/v1/lab/tests", { target_id: targetId, profile });

  listTests = (): Promise<SecurityTest[]> =>
    this.request("GET", "/api/v1/lab/tests");

  getTest = (id: string): Promise<SecurityTest> =>
    this.request("GET", `/api/v1/lab/tests/${id}`);

  listFindings = (): Promise<Finding[]> =>
    this.request("GET", "/api/v1/lab/findings");

  updateFinding = (id: string, patch: FindingPatch): Promise<Finding> =>
    this.request("PATCH", `/api/v1/lab/findings/${id}`, patch);

  generateReport = (
    targetId: string | null,
    formats: Array<"json" | "html"> = ["json"],
  ): Promise<SecurityReport> =>
    this.request("POST", "/api/v1/lab/reports", {
      target_id: targetId,
      formats,
    });

  listReports = (): Promise<SecurityReport[]> =>
    this.request("GET", "/api/v1/lab/reports");

  getReport = (id: string): Promise<SecurityReport> =>
    this.request("GET", `/api/v1/lab/reports/${id}`);

  reportDownloadUrl = (id: string): string =>
    `${this.baseUrl}/api/v1/lab/reports/${id}/download`;
}

export const client = new DocFetchClient();