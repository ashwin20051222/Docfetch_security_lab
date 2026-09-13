"""Scribd document downloader.

Renders a Scribd embed in headless Chromium (which is the only way modern
Scribd serves content — plain HTTP is answered with a JavaScript challenge),
scrolls every page into the DOM, exports a faithful PDF through the Chromium
print pipeline, and keeps the per-page render for optional PPTX conversion.
"""
from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import fitz  # PyMuPDF
from playwright.async_api import Browser, Playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.config import get_settings
from app.core.errors import (
    ApiError,
    DocumentNotFoundError,
    FetchFailedError,
    InvalidURLError,
)

log = logging.getLogger("docfetch.scribd")
settings = get_settings()

DOC_TEMPLATE = "https://www.scribd.com/document/{doc_id}"
EMBED_TEMPLATE = "https://www.scribd.com/embeds/{doc_id}/content?view_mode=scroll"

# Navigation errors that indicate transient transport/DNS failures worth
# retrying. DNS64/NAT64 networks (some homes, mobile/CG-NAT) intermittently
# answer queries through a NAT64 tunnel whose path wobbles; Chromium then
# raises e.g. net::ERR_NAME_NOT_RESOLVED even though `getent`/`curl` work.
_NETWORK_RETRYABLE = (
    "net::ERR_NAME_NOT_RESOLVED",
    "net::ERR_ADDRESS_UNREACHABLE",
    "net::ERR_CONNECTION_",
    "net::ERR_INTERNET_DISCONNECTED",
    "net::ERR_NETWORK_CHANGED",
    "net::ERR_NETWORK_ACCESS_DENIED",
    "net::ERR_PROXY_CONNECTION_FAILED",
    "net::ERR_TIMED_OUT",
    "net::ERR_SOCKET_NOT_CONNECTED",
    "ERR_EMPTY_RESPONSE",
    "navigation failed",
    "connection is refused",
    "socket hang up",
)

MAX_NAV_ATTEMPTS = 3
NAV_BACKOFF_SECONDS = (1.5, 4.0)

_CHROME_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--mute-audio",
    "--window-size=1365,900",
]

_SCRIBD_HOST_RE = re.compile(r"(^|\.)scribd\.com$", re.I)
_DOC_ID_PATTERNS = [
    re.compile(r"/embeds/(\d+)/", re.I),
    re.compile(r"/(?:document|doc|presentation)/(\d+)(?:[/?#\-]|$)", re.I),
    re.compile(r"[?&](?:document_id|doc_id|fbclid_only)=(\d+)", re.I),
]

_META_JS = """() => {
  const g = name => {
    const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
    return el ? (el.content || null) : null;
  };
  return {
    title: document.title,
    ogTitle: g('og:title'),
    ogDescription: g('og:description') || g('description'),
    author: g('author') || g('author_name'),
    ogUrl: g('og:url'),
  };
}"""

_SCROLL_JS = """() => {
  const sc = document.querySelector('.document_scroller') || document.scrollingElement;
  if (sc) sc.scrollTop = sc.scrollHeight;
}"""

_FLATTEN_JS = """() => {
  document.querySelectorAll('.document_scroller').forEach(s => {
    s.style.position='static'; s.style.overflow='visible'; s.style.height='auto';
    s.style.maxHeight='none'; s.style.top='auto'; s.style.bottom='auto';
    s.style.left='auto'; s.style.right='auto';
  });
  document.querySelectorAll('[class*="auto__embeds_new_show"], [class*="book_container"]').forEach(s => {
    s.style.position='static'; s.style.overflow='visible'; s.style.height='auto';
    s.style.maxHeight='none';
  });
  document.querySelectorAll('.outer_page').forEach(p => {
    p.style.breakAfter='page'; p.style.breakInside='avoid';
  });
  document.querySelectorAll('.toolbar_top, .toolbar_bottom, .pagebar, .page-controls, .cookie-banner, [class*="cookie"]').forEach(el => el.remove());
}"""

_MEASURE_JS = """() => {
  const el = document.querySelector('.outer_page');
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { w: r.width / 96, h: r.height / 96 };
}"""


# ---------------------------------------------------------------------------
#  URL parsing
# ---------------------------------------------------------------------------


def parse_scribd_url(raw_url: str) -> str:
    """Return the numeric Scribd document ID, or raise InvalidURLError."""
    url = (raw_url or "").strip()
    if not url:
        raise InvalidURLError("The URL field is empty.")
    parsed = urlparse(url if "://" in url else f"https://{url}")
    if parsed.scheme not in ("http", "https"):
        raise InvalidURLError("Only http:// and https:// URLs are supported.")
    host = (parsed.hostname or "").lower()
    if not _SCRIBD_HOST_RE.search(host):
        raise InvalidURLError(
            "Only scribd.com document links are supported. "
            "Paste a URL like https://www.scribd.com/document/123XYZ/..."
        )
    for pattern in _DOC_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    raise InvalidURLError(
        "Could not find a Scribd document ID in that URL. "
        "Use a URL of the form https://www.scribd.com/document/<id>/..."
    )


def _clean_title(title: str, fallback_slug: str | None = None) -> str:
    text = (title or "").strip()
    if not text:
        text = fallback_slug or ""
    # Scribd auto-suffixes og:title with " | PDF | <category> | <publisher>".
    text = re.sub(
        r"\s*\|\s*(pdf|pptx?|pages?|slides?|ebooks?|presentation|reports?)\b.*$",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"\s*\|\s*[^|]*$", "", text).strip()
    return text[:200] or "Scribd document"


def _slug_fallback(url: str) -> str | None:
    path = urlparse(url).path.rstrip("/")
    last = path.rsplit("/", 1)[-1] if path else ""
    if last.isdigit() or not last:
        return None
    return last.replace("-", " ").strip() or None


async def _goto_retry(page, url: str, *, timeout: int = 60000) -> None:
    """Navigate to ``url``, retrying transient network/DNS failures."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_NAV_ATTEMPTS + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            return
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            retryable = isinstance(exc, PlaywrightTimeoutError) or any(
                token.lower() in msg.lower() for token in _NETWORK_RETRYABLE
            )
            if not retryable:
                raise
            last_error = exc
            log.warning(
                "scribd_goto_retry attempt=%s/%s msg=%s",
                attempt,
                MAX_NAV_ATTEMPTS,
                msg.splitlines()[0],
            )
            if attempt < MAX_NAV_ATTEMPTS:
                await asyncio.sleep(NAV_BACKOFF_SECONDS[attempt - 1])
    raise FetchFailedError(
        "Scribd.com could not be reached (the network/DNS connection dropped "
        "while loading the document). Check your internet connection and try "
        "again — this error is usually temporary."
        + (f" [{str(last_error).splitlines()[0]}]" if last_error else ""),
        "SCRIBD_NETWORK_ERROR",
    ) from last_error


# ---------------------------------------------------------------------------
#  Headless Chromium pool
# ---------------------------------------------------------------------------


class _BrowserPool:
    def __init__(self) -> None:
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()

    async def get_browser(self) -> Browser:
        async with self._lock:
            if self._browser is not None and self._browser.is_connected():
                return self._browser
            if self._pw is None:
                self._pw = await async_playwright_start()
            self._browser = await self._launch(self._pw)
            log.info("chromium_launched channel=* is_connected=%s", self._browser.is_connected())
            return self._browser

    async def _launch(self, pw: Playwright) -> Browser:
        executable = settings.scribd_chrome_executable.strip()
        errors: list[str] = []
        attempts: list[dict] = []
        if settings.scribd_chrome_channel:
            attempts.append({"channel": settings.scribd_chrome_channel})
        if executable:
            attempts.append({"executable_path": executable})
        attempts.append({})  # bundled Playwright Chromium (playwright install)

        for kwargs in attempts:
            try:
                return await pw.chromium.launch(
                    headless=settings.scribd_headless,
                    args=_CHROME_ARGS,
                    **kwargs,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{kwargs or 'bundled'}: {exc}")
                log.debug("chromium_launch_failed %s", kwargs)
        raise FetchFailedError(
            "Could not launch a Chromium browser for Scribd retrieval. "
            "Install Google Chrome or run `playwright install chromium`."
            f" Tried: {'; '.join(errors)}",
            "SCRIBD_BROWSER_UNAVAILABLE",
        )


_pools: dict[int, _BrowserPool] = {}
_pools_lock = threading.Lock()


def _pool_for_loop() -> _BrowserPool:
    loop_id = id(asyncio.get_running_loop())
    with _pools_lock:
        pool = _pools.get(loop_id)
        if pool is None:
            pool = _BrowserPool()
            _pools[loop_id] = pool
        return pool


async def async_playwright_start() -> Playwright:
    from playwright.async_api import async_playwright

    return await async_playwright().start()


# ---------------------------------------------------------------------------
#  Task / item store (in-memory, single-process)
# ---------------------------------------------------------------------------


@dataclass
class ScribdTask:
    id: str
    url: str
    status: str = "pending"  # pending | running | completed | failed
    progress: int = 0
    stage: str = "task_started"
    error: str | None = None
    item_id: str | None = None
    created: float = field(default_factory=time.time)


@dataclass
class ScribdItem:
    id: str
    doc_id: str
    url: str
    title: str = ""
    description: str = ""
    author: str = ""
    page_count: int = 0
    pdf_path: Path | None = None
    pptx_path: Path | None = None
    pngs: list[Path] = field(default_factory=list)
    pdf_busy: bool = False
    pptx_busy: bool = False
    error: str | None = None
    created: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created


_TASKS: dict[str, ScribdTask] = {}
_ITEMS: dict[str, ScribdItem] = {}
_ITEMS_BY_DOC: dict[str, ScribdItem] = {}
_store_lock = threading.Lock()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _item_dir(item: ScribdItem) -> Path:
    p = settings.scribd_dir / item.id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _gc_old_items() -> None:
    import shutil

    cutoff = settings.scribd_item_ttl_minutes * 60
    now = time.time()
    with _store_lock:
        stale = [i for i in _ITEMS.values() if now - i.last_access > cutoff]
        for item in stale:
            _ITEMS.pop(item.id, None)
            _ITEMS_BY_DOC.pop(item.doc_id, None)
            item_dir = settings.scribd_dir / item.id
            try:
                if item_dir.exists():
                    shutil.rmtree(item_dir, ignore_errors=True)
            except OSError:
                pass
        if stale:
            log.info("scribd_gc removed=%s", len(stale))


def get_task(task_id: str) -> ScribdTask | None:
    with _store_lock:
        return _TASKS.get(task_id)


def get_item(item_id: str) -> ScribdItem | None:
    with _store_lock:
        item = _ITEMS.get(item_id)
        if item is not None:
            item.last_access = time.time()
        return item


def _find_existing(doc_id: str) -> ScribdItem | None:
    _gc_old_items()
    with _store_lock:
        item = _ITEMS_BY_DOC.get(doc_id)
        if item is not None and item.pdf_path and item.pdf_path.exists():
            item.last_access = time.time()
            return item
        return None


def _update_task(task: ScribdTask, progress: int, stage: str) -> None:
    task.progress = min(100, max(0, progress))
    task.stage = stage
    log.debug("scribd_task progress=%s stage=%s task=%s", task.progress, stage, task.id)


def _set_item(item: ScribdItem) -> None:
    with _store_lock:
        _ITEMS[item.id] = item
        _ITEMS_BY_DOC[item.doc_id] = item


# ---------------------------------------------------------------------------
#  Document processing
# ---------------------------------------------------------------------------


def submit(url: str) -> ScribdTask:
    _gc_old_items()
    task = ScribdTask(id=_new_id(), url=url.strip(), status="pending", progress=0)
    with _store_lock:
        _TASKS[task.id] = task
    return task


async def run_job(task_id: str) -> None:
    task = get_task(task_id)
    if task is None:
        return
    started = time.time()
    try:
        doc_id = parse_scribd_url(task.url)
        existing = _find_existing(doc_id)
        if existing is not None:
            task.status = "completed"
            task.progress = 100
            task.stage = "completed"
            task.item_id = existing.id
            with _store_lock:
                _TASKS[task_id] = task
            log.info("scribd_cached item=%s doc=%s", existing.id, doc_id)
            return

        item = ScribdItem(id=_new_id(), doc_id=doc_id, url=task.url)
        _set_item(item)
        task.item_id = item.id
        _update_task(task, 5, "task_started")

        await asyncio.wait_for(
            _process(item, task), timeout=settings.scribd_download_timeout
        )

        task.status = "completed"
        task.progress = 100
        task.stage = "completed"
        log.info("scribd_completed item=%s doc=%s elapsed=%.1fs", item.id, doc_id, time.time() - started)
    except asyncio.TimeoutError:
        task.status = "failed"
        task.error = "The document timed out while being processed. Try again later."
        log.warning("scribd_timeout task=%s", task_id)
    except Exception as exc:  # noqa: BLE001
        task.status = "failed"
        raw = str(exc) or ""
        if isinstance(exc, ApiError):
            task.error = str(exc)
        elif "Call log:" in raw or raw.startswith(("Page.", "Timeout", "Target ", "ProtocolError")):
            task.error = "The document could not be processed (browser error). Please try again."
        else:
            task.error = raw
        log.exception("scribd_failed task=%s", task_id)
        item = get_item(task.item_id) if task.item_id else None
        if item is not None:
            item.error = task.error


async def _process(item: ScribdItem, task: ScribdTask) -> None:
    browser = await _pool_for_loop().get_browser()
    context = await browser.new_context(
        user_agent=settings.scribd_user_agent,
        viewport={"width": 1365, "height": 900},
        locale="en-US",
        color_scheme="light",
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    try:
        await _fetch_metadata(item, task, context)
        await _render_document(item, task, context)
        await _build_pdf(item, task)
        _update_task(task, 95, "finalizing")
    finally:
        await context.close()


async def _fetch_metadata(item: ScribdItem, task: ScribdTask, context) -> None:
    _update_task(task, 12, "metadata_fetch_started")
    page = await context.new_page()
    try:
        await _goto_retry(page, DOC_TEMPLATE.format(doc_id=item.doc_id))
        # Let the anti-bot challenge / render settle.
        await page.wait_for_timeout(2600)
        meta = await page.evaluate(_META_JS)
        title = _clean_title(meta.get("ogTitle"), _slug_fallback(item.url))
        item.title = title
        item.description = (meta.get("ogDescription") or "")[:400]
        item.author = (meta.get("author") or "").strip()
        log.info("scribd_metadata title=%r doc=%s", title, item.doc_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("scribd_metadata_failed doc=%s err=%s", item.doc_id, exc)
        item.title = _clean_title(None, _slug_fallback(item.url))
        item.description = ""
    finally:
        await page.close()
    _update_task(task, 18, "metadata_fetch_completed")


async def _render_document(item: ScribdItem, task: ScribdTask, context) -> None:
    _update_task(task, 22, "render_started")
    page = await context.new_page()
    try:
        await _goto_retry(page, EMBED_TEMPLATE.format(doc_id=item.doc_id))
        try:
            await page.wait_for_selector(".outer_page", timeout=35000)
        except Exception as exc:  # noqa: BLE001
            raise FetchFailedError(
                "Scribd did not expose this document. It may be private, "
                "removed, or restricted.",
                "SCRIBD_EMBED_FAILED",
            ) from exc
        await page.wait_for_timeout(1600)

        # Force every lazy-loaded page into the DOM.
        prev_count = 0
        stable = 0
        for _ in range(180):
            await page.evaluate(_SCROLL_JS)
            await page.wait_for_timeout(120)
            count = await page.locator(".outer_page").count()
            if count == prev_count:
                stable += 1
                if stable >= 3:
                    break
            else:
                stable = 0
            prev_count = count

        await page.wait_for_timeout(1500)
        total = await page.locator(".outer_page").count()
        if total == 0:
            raise FetchFailedError("Scribd returned no printable pages.", "SCRIBD_EMPTY_DOCUMENT")
        item.page_count = total

        # Per-page renders (used for PPTX + thumbnail previews).
        pages_dir = _item_dir(item) / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        for i in range(total):
            png_path = pages_dir / f"{i + 1:03d}.png"
            if not png_path.exists():
                await page.locator(".outer_page").nth(i).screenshot(path=str(png_path))
            item.pngs.append(png_path)
            progress = 30 + int(35 * (i + 1) / total)
            _update_task(task, progress, "render_completed")

        # Flatten the inner scroll container so print covers every page.
        dims = await page.evaluate(_MEASURE_JS) or {"w": 8.5, "h": 11.0}
        await page.evaluate(_FLATTEN_JS)
        await page.wait_for_timeout(700)

        raw_pdf = _item_dir(item) / "raw.pdf"
        await page.pdf(
            path=str(raw_pdf),
            width=f"{dims['w']:.4f}in",
            height=f"{dims['h']:.4f}in",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        _update_task(task, 78, "pdf_generation_started")
    finally:
        await page.close()


def _strip_blank_pages(src: Path, dst: Path, title: str, author: str) -> int:
    """Remove blank filler pages introduced by the print pipeline."""
    src_doc = fitz.open(src)
    out = fitz.open()
    kept = 0
    for i in range(src_doc.page_count):
        pg = src_doc[i]
        if not pg.get_text().strip() and not pg.get_images():
            continue
        out.insert_pdf(src_doc, from_page=i, to_page=i)
        kept += 1
    out.set_metadata(
        {
            "title": title or "Scribd document",
            "author": author or "",
            "producer": "ScribSave (Chromium print) ",
            "creator": "ScribSave",
        }
    )
    out.save(dst, garbage=3, deflate=True)
    out.close()
    src_doc.close()
    return kept


async def _build_pdf(item: ScribdItem, task: ScribdTask) -> None:
    raw = _item_dir(item) / "raw.pdf"
    if not raw.exists():
        raise FetchFailedError(
            "The document render produced no output.", "SCRIBD_RENDER_FAILED"
        )
    final = _item_dir(item) / "document.pdf"
    kept = await asyncio.to_thread(
        _strip_blank_pages, raw, final, item.title, item.author
    )
    item.page_count = kept or item.page_count
    item.pdf_path = final
    raw.unlink(missing_ok=True)
    log.info("scribd_pdf item=%s pages=%s bytes=%s", item.id, kept, final.stat().st_size)


def _build_pptx_sync(item: ScribdItem) -> Path:
    from pptx import Presentation
    from pptx.util import Emu
    from PIL import Image

    if not item.pngs:
        raise FetchFailedError("No page renders are available for PPTX.", "SCRIBD_NO_PAGES")

    first = Image.open(item.pngs[0])
    aspect = first.width / first.height
    first.close()

    prs = Presentation()
    EMU_INCH = 914400
    slide_w = 10 * EMU_INCH
    slide_h = int(slide_w / aspect)
    prs.slide_width = slide_w
    prs.slide_height = slide_h
    blank = prs.slide_layouts[6]

    for png in item.pngs:
        slide = prs.slides.add_slide(blank)
        slide.shapes.add_picture(str(png), 0, 0, width=slide_w, height=slide_h)

    out = _item_dir(item) / f"{_safe_file_stem(item.title)}.pptx"
    prs.save(out)
    return out


def _safe_file_stem(title: str) -> str:
    stem = re.sub(r"[^\w\- ]+", "", title).strip().replace(" ", "_") or "document"
    return stem[:90]


async def generate_pptx(item_id: str) -> str:
    """Generate (or return) the PPTX for an item. Returns the item id."""
    item = get_item(item_id)
    if item is None:
        raise DocumentNotFoundError("Item not found.", code="ITEM_NOT_FOUND")
    if item.pptx_path is not None and item.pptx_path.exists():
        return item.id
    if item.pptx_busy:
        raise FetchFailedError("PPTX generation is already running.", "BUSY")
    item.pptx_busy = True
    try:
        out = await asyncio.to_thread(_build_pptx_sync, item)
        item.pptx_path = out
        log.info("scribd_pptx item=%s bytes=%s", item.id, out.stat().st_size)
    finally:
        item.pptx_busy = False
    return item.id