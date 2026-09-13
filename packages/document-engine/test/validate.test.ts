import { describe, expect, it } from "vitest";

import { formatBytes, truncateMiddle, validateUpload } from "../src/index";

const enc = (s: string) => new TextEncoder().encode(s);

describe("validateUpload", () => {
  it("accepts a PDF by magic bytes even with a nonstandard extension", () => {
    const r = validateUpload("report.bin", "application/octet-stream", 100, enc("%PDF-1.7"));
    expect(r.ok).toBe(true);
  });

  it("accepts the percent-encoded PDF header", () => {
    const r = validateUpload("doc.pdf", "", 100, new Uint8Array([0x25, 0xe2, 0xe3, 0xcf, 0xd3]));
    expect(r.ok).toBe(true);
  });

  it("rejects HTML renamed as a PDF (magic mismatch)", () => {
    const r = validateUpload("fake.pdf", "application/pdf", 100, enc("<html>"));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.code).toBe("UNSUPPORTED_FORMAT");
  });

  it("rejects empty files", () => {
    const r = validateUpload("empty.pdf", "application/pdf", 0, enc("%PDF-1.7"));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.code).toBe("EMPTY_FILE");
  });

  it("rejects non-PDF names regardless of content", () => {
    const r = validateUpload("notes.txt", "text/plain", 10, enc("hello world"));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.code).toBe("UNSUPPORTED_FORMAT");
  });
});

describe("formatBytes", () => {
  it("formats bytes, KB and MB", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});

describe("truncateMiddle", () => {
  it("keeps short strings intact", () => {
    expect(truncateMiddle("abc", 48)).toBe("abc");
  });
  it("truncates long strings in the middle", () => {
    const long = "a".repeat(100);
    const t = truncateMiddle(long, 48);
    expect(t).toContain("…");
    expect(t.length).toBeLessThan(long.length);
  });
});