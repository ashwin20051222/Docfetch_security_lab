/**
 * Client-side document validation and helper logic for the DocFetch Security
 * Lab. Mirrors the server-side rules in apps/api/app/services/pdf_validation.py
 * and document_engine.py so the UI gives accurate up-front feedback.
 *
 * IMPORTANT: these are UX accelerators for *uploads* the user already holds.
 * The authoritative verdict always comes from the backend, which re-validates
 * magic bytes and PDF structure server-side.
 */

export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

// Percent-encoded PDF header: "%PDF-" / "%\xE2\xE3\xCF\xD3"
const PDF_MAGIC = "%PDF-";
const PDF_MAGIC_ENC = [0x25, 0xe2, 0xe3, 0xcf, 0xd3];

export type UploadVerdict =
  | { ok: true; message: string }
  | { ok: false; code: string; message: string };

function hasPdfMagic(header: Uint8Array): boolean {
  const text = header.subarray(0, 5);
  if (String.fromCharCode(...text) === PDF_MAGIC) {
    return true;
  }
  return text.every((byte, i) => byte === PDF_MAGIC_ENC[i]);
}

/**
 * Validate an upload candidate before it reaches the network.
 * Mirrors the server: extension and browser MIME are never trusted.
 */
export function validateUpload(
  name: string,
  mime: string,
  sizeBytes: number,
  fileHeader: Uint8Array | null,
): UploadVerdict {
  if (!name) {
    return { ok: false, code: "MISSING_FILENAME", message: "A file is required." };
  }
  if (sizeBytes === 0) {
    return {
      ok: false,
      code: "EMPTY_FILE",
      message: "The file is empty; nothing to ingest.",
    };
  }
  if (sizeBytes > MAX_UPLOAD_BYTES) {
    return {
      ok: false,
      code: "FILE_TOO_LARGE",
      message: `Files are limited to ${Math.round(MAX_UPLOAD_BYTES / 1024 / 1024)} MB.`,
    };
  }
  const lowerName = name.toLowerCase();
  const plausiblePdfName = lowerName.endsWith(".pdf") || mime === "application/pdf";

  // Magic bytes are authoritative: a header proving PDF wins even when the
  // filename suggests something else. The backend re-verifies server-side.
  if (fileHeader) {
    if (hasPdfMagic(fileHeader)) {
      return { ok: true, message: "PDF magic bytes confirmed — the backend will verify it." };
    }
    return {
      ok: false,
      code: "UNSUPPORTED_FORMAT",
      message: "The file does not start with a PDF header (magic bytes mismatch).",
    };
  }

  if (!plausiblePdfName) {
    return {
      ok: false,
      code: "UNSUPPORTED_FORMAT",
      message: "Only PDF documents are accepted.",
    };
  }
  return {
    ok: true,
    message: "Looks like a valid PDF — the backend will verify it.",
  };
}

/** Read the first bytes of a File without loading the whole thing. */
export async function peekHeader(file: File, bytes = 64): Promise<Uint8Array | null> {
  try {
    const buf = await file.slice(0, bytes).arrayBuffer();
    return new Uint8Array(buf);
  } catch {
    return null;
  }
}

/** Human-readable byte size. */
export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

/** Truncate a long string at a middle/end boundary for compact display. */
export function truncateMiddle(value: string, max = 48): string {
  if (value.length <= max) return value;
  const head = value.slice(0, Math.ceil(max / 2));
  const tail = value.slice(value.length - Math.floor(max / 2) + 1);
  return `${head}…${tail}`;
}