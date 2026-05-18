"""
Capture full-page screenshots of Korean newspaper front pages using Playwright.
"""

import os
import time
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

CHROME_EXECUTABLE = os.getenv(
    "CHROME_EXECUTABLE",
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
)

VIEWPORT = {"width": 1440, "height": 900}
SCREENSHOT_TIMEOUT = 25000  # ms


def capture_newspaper(name: str, url: str, output_path: str) -> bool:
    """
    Capture a screenshot of a newspaper's front page.
    Returns True on success, False on failure.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=CHROME_EXECUTABLE,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-zygote",
                ],
            )
            context = browser.new_context(
                viewport=VIEWPORT,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="ko-KR",
                extra_http_headers={
                    "Accept-Language": "ko-KR,ko;q=0.9",
                },
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=SCREENSHOT_TIMEOUT)
            except Exception:
                try:
                    page.goto(url, wait_until="load", timeout=SCREENSHOT_TIMEOUT)
                except Exception:
                    pass

            # Wait for content to settle
            try:
                page.wait_for_timeout(3000)
            except Exception:
                pass

            # Dismiss popups/overlays
            _dismiss_popups(page)

            # Scroll to top
            try:
                page.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass

            page.screenshot(path=output_path, full_page=False, type="png")
            browser.close()
            return True

    except Exception as e:
        print(f"[newspaper_capture] Failed to capture {name}: {e}")
        return False


def _dismiss_popups(page):
    """Try to close common popup overlays on Korean news sites."""
    popup_selectors = [
        "button[class*='close']",
        "button[class*='Close']",
        "a[class*='close']",
        "div[class*='popup'] button",
        "div[class*='layer'] button.btn_close",
        ".modal button.close",
        "[id*='layer'] .close",
        "button[aria-label='닫기']",
        "button:has-text('닫기')",
        "button:has-text('확인')",
        "button:has-text('X')",
    ]
    for sel in popup_selectors:
        try:
            elements = page.query_selector_all(sel)
            for el in elements[:3]:
                if el.is_visible():
                    el.click()
                    page.wait_for_timeout(300)
        except Exception:
            pass


def capture_all_newspapers(newspapers: list[dict], output_dir: str) -> list[dict]:
    """
    Capture screenshots for all newspapers.
    Returns list of dicts with name, url, screenshot_path, success.
    """
    results = []
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    for paper in newspapers:
        name = paper["name"]
        url = paper["url"]
        safe_name = name.replace("/", "_")
        output_path = str(Path(output_dir) / f"{safe_name}.png")

        print(f"[newspaper_capture] Capturing {name}...")
        success = capture_newspaper(name, url, output_path)

        results.append({
            "name": name,
            "url": url,
            "screenshot_path": output_path if success else None,
            "success": success,
        })

        time.sleep(1.0)

    return results
