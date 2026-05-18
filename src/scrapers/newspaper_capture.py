"""
Capture full-page screenshots of Korean newspaper front pages using Playwright.
"""

import os
import time
from pathlib import Path


_PLAYWRIGHT_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--no-zygote",
    "--ignore-certificate-errors",
    "--allow-running-insecure-content",
]

VIEWPORT = {"width": 1440, "height": 900}
SCREENSHOT_TIMEOUT = 30000


def _get_browser_executable():
    custom = os.getenv("CHROME_EXECUTABLE")
    if custom and os.path.exists(custom):
        return custom
    return None


def capture_newspaper(name: str, url: str, output_path: str) -> bool:
    """
    Capture a screenshot of a newspaper's front page.
    Returns True on success, False on failure.
    """
    from playwright.sync_api import sync_playwright

    exe = _get_browser_executable()
    launch_kwargs = {
        "args": _PLAYWRIGHT_ARGS,
    }
    if exe:
        launch_kwargs["executable_path"] = exe

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(
                viewport=VIEWPORT,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="ko-KR",
                extra_http_headers={
                    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                ignore_https_errors=True,
            )
            page = context.new_page()

            # Navigate with fallback wait strategies
            loaded = False
            for wait_until in ["domcontentloaded", "load"]:
                try:
                    page.goto(url, wait_until=wait_until, timeout=SCREENSHOT_TIMEOUT)
                    loaded = True
                    break
                except Exception:
                    continue

            if not loaded:
                browser.close()
                return False

            # Let JS render
            page.wait_for_timeout(3500)

            # Dismiss common popups/overlays
            _dismiss_popups(page)

            # Hide cookie banners, subscription walls, etc.
            _hide_overlays(page)

            # Scroll back to top
            try:
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(500)
            except Exception:
                pass

            page.screenshot(
                path=output_path,
                full_page=False,
                type="png",
                clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": VIEWPORT["height"]},
            )
            browser.close()
            return True

    except Exception as e:
        print(f"[newspaper_capture] Failed to capture {name}: {e}")
        return False


def _dismiss_popups(page):
    """Close common popup overlays on Korean news sites."""
    popup_selectors = [
        "button[class*='close']",
        "button[class*='Close']",
        "a[class*='close']",
        "button[aria-label='닫기']",
        "button[aria-label='close']",
        ".modal button",
        ".popup button",
        ".layer button.close",
        "[class*='popup'] [class*='close']",
        "[class*='modal'] [class*='close']",
        "button[class*='btn_close']",
        ".btn_close",
        "#toast .close",
    ]
    for sel in popup_selectors:
        try:
            elements = page.query_selector_all(sel)
            for el in elements[:2]:
                if el.is_visible():
                    el.click()
                    page.wait_for_timeout(200)
        except Exception:
            pass


def _hide_overlays(page):
    """Hide cookie banners, paywalls, and subscription overlays via CSS injection."""
    try:
        page.add_style_tag(content="""
            /* Hide overlays, cookie banners, modals, subscriptions */
            .cookie-banner, .cookie_banner, #cookie-banner,
            .paywall, .subscription-wall, .login-wall,
            .popup, .modal, .layer, .overlay,
            .newsletter-popup, .push-notification-bar,
            [class*='cookie'], [class*='Cookie'],
            [class*='gdpr'], [class*='GDPR'],
            [class*='subscribe'][class*='popup'],
            [class*='subscribe'][class*='layer'],
            .floating-banner, .fixed-banner,
            #floating-layer, .float_layer,
            .gnb_notice, .alert_wrap {
                display: none !important;
                visibility: hidden !important;
            }
            /* Remove scroll lock from body */
            body, html {
                overflow: auto !important;
            }
        """)
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

        print(f"      [{len(results)+1}/{len(newspapers)}] {name} 캡처 중...")
        success = capture_newspaper(name, url, output_path)

        # Validate screenshot (not blank/error)
        if success:
            success = _validate_screenshot(output_path)

        results.append({
            "name": name,
            "url": url,
            "screenshot_path": output_path if success else None,
            "success": success,
        })

        time.sleep(0.5)

    ok = sum(1 for r in results if r["success"])
    print(f"      → {ok}/{len(newspapers)}개 캡처 완료")
    return results


def _validate_screenshot(path: str) -> bool:
    """Check if screenshot contains actual content (not blank/error page)."""
    try:
        from PIL import Image
        import statistics
        img = Image.open(path).convert("RGB")
        # Sample pixels across the image
        w, h = img.size
        samples = []
        for x in range(0, w, w // 10):
            for y in range(0, h, h // 10):
                r, g, b = img.getpixel((x, y))
                samples.append((r, g, b))
        r_vals = [s[0] for s in samples]
        g_vals = [s[1] for s in samples]
        b_vals = [s[2] for s in samples]
        r_mean = statistics.mean(r_vals)
        r_stdev = statistics.stdev(r_vals) if len(r_vals) > 1 else 0
        # Blank/error page: near-white with very low variance
        if r_mean > 248 and r_stdev < 5:
            return False
        return True
    except Exception:
        return True  # If we can't check, assume OK
