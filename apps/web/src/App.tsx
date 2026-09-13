import React, { useCallback, useEffect, useRef, useState } from 'react';
import './styles.css';

type Downloads = {
  pdf: { ready: boolean; size_bytes: number; filename: string | null; url: string };
  pptx: { ready: boolean; size_bytes: number; filename: string | null; url: string };
};

type ItemMeta = {
  id: string;
  title: string;
  description: string;
  author: string;
  page_count: number;
  url: string;
};

const STAGE_LABELS: Record<string, string> = {
  task_started: 'Starting download...',
  metadata_fetch_started: 'Fetching document info...',
  metadata_fetch_completed: 'Document info fetched',
  render_started: 'Rendering pages...',
  render_completed: 'Rendering pages...',
  pdf_generation_started: 'Building PDF...',
  finalizing: 'Finalizing...',
  completed: 'Ready',
};

// PWA install support
const isStandalone =
  window.matchMedia('(display-mode: standalone)').matches ||
  (window.navigator as any).standalone === true;

// Backend base. Defaults to same-origin `/api` (vite dev proxy or nginx);
// set VITE_API_BASE to a hosted API when deploying the static build elsewhere.
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/+$/, '') ?? '';

function formatBytes(bytes: number): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function apiError(data: any, fallback: string): Error {
  return new Error(data?.error?.message || data?.message || fallback);
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function App() {
  const [url, setUrl] = useState('');
  const [phase, setPhase] = useState<'idle' | 'processing' | 'ready' | 'error'>('idle');
  const [progress, setProgress] = useState(0);
  const [stageText, setStageText] = useState('');
  const [error, setError] = useState('');
  const [item, setItem] = useState<ItemMeta | null>(null);
  const [downloads, setDownloads] = useState<Downloads | null>(null);
  const [format, setFormat] = useState<'pdf' | 'pptx'>('pdf');
  const [preparingPptx, setPreparingPptx] = useState(false);
  const pollTimer = useRef<number | null>(null);
  const [installPrompt, setInstallPrompt] = useState<any>(null);
  const [isInstalled, setIsInstalled] = useState<boolean>(isStandalone);

  useEffect(() => {
    const onBeforeInstall = (e: Event) => {
      e.preventDefault();
      setInstallPrompt(e);
    };
    const onInstalled = () => {
      setIsInstalled(true);
      setInstallPrompt(null);
    };
    window.addEventListener('beforeinstallprompt', onBeforeInstall);
    window.addEventListener('appinstalled', onInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstall);
      window.removeEventListener('appinstalled', onInstalled);
    };
  }, []);

  const handleInstall = async () => {
    if (!installPrompt) {
      if ((window.navigator as any).standalone) {
        setIsInstalled(true);
      }
      return;
    }
    (installPrompt as any).prompt();
    try {
      const choice: any = await (installPrompt as any).userChoice;
      if (choice?.outcome === 'accepted') setIsInstalled(true);
    } finally {
      setInstallPrompt(null);
    }
  };

  const clearTimer = () => {
    if (pollTimer.current !== null) {
      window.clearTimeout(pollTimer.current);
      pollTimer.current = null;
    }
  };

  const fetchItemAndDownloads = useCallback(async (itemId: string) => {
    const [metaRes, dlRes] = await Promise.all([
      fetch(`${API_BASE}/api/item/${itemId}`),
      fetch(`${API_BASE}/api/item/${itemId}/downloads`),
    ]);
    const meta = await metaRes.json();
    const dl = await dlRes.json();
    setItem(meta);
    setDownloads(dl);
  }, []);

  const beginDownload = useCallback(async (taskId: string) => {
    const poll = async () => {
      const res = await fetch(`${API_BASE}/api/status/${taskId}`);
      const data = await res.json();
      if (!res.ok) {
        setError(apiError(data, 'Failed to read download status.').message);
        setPhase('error');
        return;
      }
      if (data.status === 'failed') {
        setError(data.error || 'The download failed. Please check the URL and try again.');
        setPhase('error');
        return;
      }
      setProgress(data.progress ?? 0);
      setStageText(STAGE_LABELS[data.stage] || data.stage || '');

      if (data.status === 'completed' && data.item_id) {
        await fetchItemAndDownloads(data.item_id);
        setPhase('ready');
        return;
      }
      pollTimer.current = window.setTimeout(poll, 1300);
    };
    poll();
  }, [fetchItemAndDownloads]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;
    clearTimer();
    setError('');
    setItem(null);
    setDownloads(null);
    setPhase('processing');
    setProgress(3);
    setStageText('Queuing download...');
    try {
      const res = await fetch('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (!res.ok) throw apiError(data, `Server error (${res.status}).`);
      setStageText('Starting download...');
      if (data.task_id) {
        await beginDownload(data.task_id);
      } else {
        setError('The server did not return a task.');
        setPhase('error');
      }
    } catch (err) {
      const msg = (err as Error).message;
      setError(
        msg.includes('Failed to fetch')
          ? 'Could not reach the download backend. Start it with: npm run dev:api'
          : msg,
      );
      setPhase('error');
    }
  };

  const ensurePptx = async () => {
    if (!item) return;
    setPreparingPptx(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/item/${item.id}/formats/pptx/generate`, { method: 'POST' });
      if (!res.ok) {
        const data = await res.json();
        throw apiError(data, 'Failed to start PPTX generation.');
      }
      for (let attempt = 0; attempt < 40; attempt++) {
        await delay(1500);
        const dlRes = await fetch(`${API_BASE}/api/item/${item.id}/downloads`);
        const dl = await dlRes.json();
        setDownloads(dl);
        if (dl.pptx?.ready) {
          setPreparingPptx(false);
          return;
        }
        setStageText('Preparing PPTX...');
      }
      setError('PPTX generation is taking longer than expected. Please try again.');
      setPreparingPptx(false);
    } catch (err) {
      setError((err as Error).message);
      setPreparingPptx(false);
    }
  };

  const pdfDownload = downloads?.pdf?.ready ? `${API_BASE}/api/download/pdf/${item?.id}` : null;
  const pptxDownload = downloads?.pptx?.ready ? `${API_BASE}/api/download/pptx/${item?.id}` : null;

  return (
    <div className="wrapper">
      <header>
        <div className="container flex aic jcsb" style={{ padding: '0', display: 'flex', justifyContent: 'space-between' }}>
          <a href="/" className="logo">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            ScribSave
          </a>
          <nav style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <a href="/" style={{ color: 'var(--text-main)', textDecoration: 'none', fontWeight: 600 }}>Scribd Downloader</a>
            {!isInstalled && (
              <button className="install-btn" onClick={handleInstall}>Install</button>
            )}
          </nav>
        </div>
      </header>

      <div className="container">
        <div className="top-title">
          <h1>Scribd Downloader</h1>
          <p>Download Scribd documents, books, and presentations as PDF files, or convert supported Scribd slides to editable PPTX presentations.</p>
        </div>

        <div className="input-form">
          <form onSubmit={handleSubmit}>
            <input
              type="url"
              placeholder="Paste the Scribd document, book, or presentation URL"
              required
              value={url}
              disabled={phase === 'processing'}
              onChange={(e) => setUrl(e.target.value)}
            />
            <button type="submit" disabled={phase === 'processing' || !url}>
              {phase === 'processing' ? <span className="spinner"></span> : 'Download'}
            </button>
          </form>

          {phase === 'processing' && (
            <div className="progress-area">
              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${Math.max(3, progress)}%` }}></div>
              </div>
              <div className="progress-row">
                <span className="progress-stage">{stageText}</span>
                <span className="progress-pct">{progress}%</span>
              </div>
            </div>
          )}
          {phase === 'error' && (
            <div className="app-callout" style={{ marginTop: '1.25rem' }}>{error}</div>
          )}

          <div className="search-trust-badges">
            <div className="search-trust-item">
              <span role="img" aria-label="free">✨</span>
              <span>Free to Use</span>
            </div>
            <div className="search-trust-item">
              <span role="img" aria-label="safe">🔒</span>
              <span>Secure Connections</span>
            </div>
            <div className="search-trust-item">
              <span role="img" aria-label="no-limit">⚡</span>
              <span>No Registration Required</span>
            </div>
          </div>
        </div>

        {phase === 'ready' && item && (
          <div className="presentation-info-wrap">
            <div className="presentation-info">
              <h2>{item.title || 'Document Ready'}</h2>
              <p style={{ color: 'var(--text-muted)' }}>
                {item.page_count} {item.page_count === 1 ? 'page' : 'pages'}
                {item.author ? ` · ${item.author}` : ''}
              </p>

              <div className="download-panel">
                <div className="format-switcher">
                  <label className="format-option">
                    <input
                      type="radio"
                      name="format"
                      value="pdf"
                      checked={format === 'pdf'}
                      onChange={() => setFormat('pdf')}
                    />
                    <span>PDF {downloads?.pdf?.ready ? `(${formatBytes(downloads.pdf.size_bytes)})` : ''}</span>
                  </label>
                  <label className="format-option">
                    <input
                      type="radio"
                      name="format"
                      value="pptx"
                      checked={format === 'pptx'}
                      onChange={() => setFormat('pptx')}
                    />
                    <span>PPT / PPTX {downloads?.pptx?.ready ? `(${formatBytes(downloads.pptx.size_bytes)})` : ''}</span>
                  </label>
                </div>

                {format === 'pdf' && pdfDownload && (
                  <a href={pdfDownload} className="download-btn" download>
                    <span className="btn-text">Download PDF</span>
                  </a>
                )}
                {format === 'pdf' && !pdfDownload && (
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>PDF is not ready yet.</p>
                )}

                {format === 'pptx' && pptxDownload && (
                  <a href={pptxDownload} className="download-btn" download>
                    <span className="btn-text">Download PPTX</span>
                  </a>
                )}
                {format === 'pptx' && !pptxDownload && (
                  <button className="download-btn" onClick={ensurePptx} disabled={preparingPptx}>
                    <span className="btn-text">
                      {preparingPptx ? <span className="spinner"></span> : 'Prepare PPTX'}
                    </span>
                  </button>
                )}
                {format === 'pptx' && preparingPptx && (
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginTop: '0.75rem' }}>
                    Preparing PPTX from {item.page_count} slides...
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      <footer>
        <div className="container">
          <p>Made with <span className="red-heart">❤</span> by Ashwin S</p>
          <p style={{ marginTop: '0.5rem', fontSize: '0.875rem' }}>
          © {new Date().getFullYear()} ScribSave Downloader Clone · Downloads are generated server-side with headless Chromium. Only download content you have the right to use.
          </p>
        </div>
      </footer>
    </div>
  );
}