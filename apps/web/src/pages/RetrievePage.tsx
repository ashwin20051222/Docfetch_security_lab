import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { client, ApiError } from "@docfetch/core";
import { peekHeader, validateUpload, formatBytes } from "@docfetch/document-engine";
import type { DocumentOut } from "@docfetch/types";

export function RetrievePage() {
  const [params] = useSearchParams();
  const urlInput = useRef<HTMLInputElement>(null);

  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<DocumentOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [uploading, setUploading] = useState(false);
  const [localHint, setLocalHint] = useState<string | null>(null);

  const wrap = <T,>(p: Promise<T>): Promise<T | null> =>
    p.catch((e) => {
      const msg = e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Unexpected failure";
      setError(msg);
      return null;
    });

  const runAnalyze = useCallback(
    (url: string) => {
      setAnalyzing(true);
      setError(null);
      setResult(null);
      void wrap(client.analyze(url)).then((res) => {
        setAnalyzing(false);
        if (res) setResult(res.document);
      });
    },
    [wrap],
  );

  useEffect(() => {
    const q = params.get("url");
    if (q) {
      if (urlInput.current) urlInput.current.value = q;
      runAnalyze(q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onUpload = useCallback(
    async (file: File) => {
      setError(null);
      const header = await peekHeader(file);
      const verdict = validateUpload(file.name, file.type, file.size, header);
      if (!verdict.ok) {
        setError(verdict.message);
        return;
      }
      setLocalHint(verdict.message);
      setUploading(true);
      const res = await wrap(client.upload(file));
      setUploading(false);
      setLocalHint(null);
      if (res) setResult(res.document);
    },
    [wrap],
  );

  return (
    <>
      <div className="app-card">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex items-center justify-center rounded-xl w-10 h-10" style={{ background: "color-mix(in srgb, var(--primary-container) 15%, white)" }}>
            <span className="text-primary">⌕</span>
          </div>
          <div>
            <h2 className="app-headline-md">Retrieve a Public Document</h2>
            <p className="app-body-sm text-on-surface-variant">
              URL must be public. Paywalled or restricted content is reported as such — it is never bypassed.
            </p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-2">
          <input
            ref={urlInput}
            className="app-input mono flex-1"
            placeholder="https://example.com/paper.pdf"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.target as HTMLInputElement).value.trim()) {
                runAnalyze((e.target as HTMLInputElement).value.trim());
              }
            }}
          />
          <button
            type="button"
            className="app-btn app-btn-primary"
            disabled={analyzing}
            onClick={() => runAnalyze(urlInput.current?.value.trim() ?? "")}
          >
            {analyzing ? "Fetching…" : "Fetch →"}
          </button>
        </div>
      </div>

      <div className="app-card">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex items-center justify-center rounded-xl w-10 h-10" style={{ background: "color-mix(in srgb, var(--primary-container) 15%, white)" }}>
            <span className="text-primary">⇪</span>
          </div>
          <div>
            <h2 className="app-headline-md">Upload a PDF You Already Hold</h2>
            <p className="app-body-sm text-on-surface-variant">
              The backend verifies magic bytes and PDF structure — extensions and browser MIME are never trusted.
            </p>
          </div>
        </div>

        <label className="app-btn" style={{ cursor: "pointer" }}>
          {uploading ? "Uploading…" : "Choose PDF file"}
          <input
            type="file"
            accept=".pdf"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void onUpload(file);
              e.target.value = "";
            }}
          />
        </label>
        {localHint && <p className="app-body-sm mt-2" style={{ color: "var(--primary)" }}>{localHint}</p>}
      </div>

      {error && (
        <div className="app-callout">
          <strong>{error}</strong>
        </div>
      )}

      {result && <DocumentPanel doc={result} onDelete={() => setResult(null)} />}
    </>
  );
}

function DocumentPanel({ doc, onDelete }: { doc: DocumentOut; onDelete: () => void }) {
  const [pages, setPages] = useState<number | null>(null);
  useEffect(() => {
    if (doc.page_count != null) setPages(doc.page_count);
  }, [doc]);
  void pages;

  return (
    <div className="app-card">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div className="min-w-0">
          <h3 className="app-headline-md truncate">{doc.title ?? doc.filename ?? doc.id}</h3>
          <p className="app-code-body text-secondary tabular truncate">{doc.source_url ?? doc.id}</p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="app-chip"
            style={
              doc.status === "failed"
                ? { background: "var(--error-container)", color: "var(--on-error-container)" }
                : { background: "#ecfdf5", color: "#047857", borderColor: "#a7f3d0" }
            }
          >
            {doc.status.toUpperCase()}
          </span>
          <a className="app-btn" href={client.downloadUrl(doc.id)}>
            Download PDF
          </a>
          <button type="button" className="app-btn app-btn-destructive" onClick={() => void client.deleteDocument(doc.id).then(onDelete)}>
            Delete
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 app-body-sm text-secondary">
        <span>Pages: <b className="text-on-surface tabular">{doc.page_count ?? "?"}</b></span>
        <span>Size: <b className="text-on-surface tabular">{formatBytes(doc.size_bytes)}</b></span>
        <span className="col-span-2 truncate">MIME: <b className="text-on-surface">{doc.mime_type}</b></span>
      </div>
      <div className="app-code-body text-secondary tabular mt-1 truncate">SHA-256: {doc.sha256}</div>

      <div className="mt-3">
        <a className="app-btn" href={client.pageImageUrl(`/api/v1/documents/${doc.id}/preview`)} target="_blank" rel="noreferrer">
          Open preview
        </a>
      </div>
    </div>
  );
}