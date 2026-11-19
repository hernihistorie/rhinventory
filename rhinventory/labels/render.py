"""Render label HTML to PNG with headless Chromium.

Playwright's sync API only works from the thread that started it, while requests are
served from any thread (the dev server starts one per request), so each process has one
thread that owns the browser and renders on behalf of the others.
"""
import concurrent.futures
import io
import math
import os
import threading

from PIL import Image
from playwright.sync_api import Browser, Playwright, Route, sync_playwright

CSS_PX_PER_MM = 96 / 25.4

# Below gunicorn's 60s worker timeout, so a stuck browser gives an error rather than a killed worker
RENDER_TIMEOUT_S = 30

_lock = threading.Lock()
_executor: concurrent.futures.ThreadPoolExecutor | None = None
_executor_pid: int | None = None

# Only touched from the executor's thread
_playwright: Playwright | None = None
_browser: Browser | None = None


def _get_executor() -> concurrent.futures.ThreadPoolExecutor:
    global _executor, _executor_pid, _playwright, _browser
    with _lock:
        if _executor_pid is not None and _executor_pid != os.getpid():
            # A forked process gets a copy of the parent's browser connection but not its thread,
            # so it can't use it. Forget it rather than closing it, as it's still the parent's.
            _playwright = None
            _browser = None
            _executor = None
        if _executor is None:
            _executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="label-render")
            _executor_pid = os.getpid()
        return _executor


def _get_browser() -> Browser:
    global _playwright, _browser
    if _browser is None or not _browser.is_connected():
        if _playwright is None:
            _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch()
    return _browser


def _block_request(route: Route) -> None:
    route.abort()


def _render(html: str, width_mm: float, height_mm: float, width_px: int) -> bytes:
    width_css = width_mm * CSS_PX_PER_MM
    height_css = height_mm * CSS_PX_PER_MM
    scale = width_px / width_css
    # Chromium only takes screenshots of whole CSS pixels, so take a bit more and crop it
    viewport = {"width": math.ceil(width_css), "height": math.ceil(height_css)}
    context = _get_browser().new_context(
        viewport=viewport,
        device_scale_factor=scale,
        # Labels are static, and their text comes from users
        java_script_enabled=False,
    )
    try:
        context.set_default_timeout(RENDER_TIMEOUT_S * 1000 / 2)
        # Assets are inlined as data: URIs, which aren't routed, so anything else is a mistake or an injection
        context.route("**/*", _block_request)
        page = context.new_page()
        page.set_content(html, wait_until="load")
        # The load event doesn't wait for web fonts (evaluate still works with page scripts disabled)
        page.evaluate("document.fonts.ready.then(() => null)")
        screenshot = page.screenshot(type="png", clip={"x": 0, "y": 0, **viewport})
    finally:
        context.close()

    image = Image.open(io.BytesIO(screenshot))
    image = image.crop((0, 0, width_px, round(height_css * scale)))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def render_png(html: str, width_mm: float, height_mm: float, width_px: int) -> bytes:
    """Render a self-contained HTML page as a `width_mm` × `height_mm` label, `width_px` pixels wide.

    The page can't load anything over the network or run scripts, so images and fonts
    have to be inlined as data: URIs.
    """
    future = _get_executor().submit(_render, html, width_mm, height_mm, width_px)
    return future.result(timeout=RENDER_TIMEOUT_S)


def _close() -> None:
    global _playwright, _browser
    if _browser is not None:
        _browser.close()
        _browser = None
    if _playwright is not None:
        _playwright.stop()
        _playwright = None


def close() -> None:
    """Shut down this process's browser, e.g. at the end of a test session. The next render starts a new one."""
    global _executor
    with _lock:
        if _executor is None or _executor_pid != os.getpid():
            return
        _executor.submit(_close).result(timeout=RENDER_TIMEOUT_S)
        _executor.shutdown()
        _executor = None
