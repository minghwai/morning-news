"""
Newspaper front-page screenshot capturer.

Strategy per site:
  1. Launch stealth Chromium (no headless signals)
  2. Block ads/trackers to speed up rendering
  3. Wait for the main headline area to appear
  4. Dismiss cookie/subscription overlays
  5. Scroll to top → capture viewport screenshot
  6. Validate: reject near-white / near-grey blank pages
"""

import os
import time
import re
from pathlib import Path

_CHROME_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--no-zygote",
    "--ignore-certificate-errors",
    "--allow-running-insecure-content",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--window-size=1440,900",
]

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

VIEWPORT = {"width": 1440, "height": 900}

# Ad/tracker domains to block
_BLOCK_PATTERNS = [
    "*googlesyndication*", "*doubleclick*", "*googletagmanager*",
    "*facebook.net*", "*kakao.com/sdk*", "*adservice*",
    "*.googletag*", "*ad.naver*", "*adfit*",
]

# Per-site: which CSS selector signals that real content has loaded
_SITE_READY_SELECTORS: dict[str, str] = {
    "khan.co.kr":         "article, .headline, h2.title",
    "kmib.co.kr":         ".headline, h2, .tit",
    "donga.com":          "h2.title, .title_a, .news_headline",
    "seoul.co.kr":        "h2, .title, .headline",
    "segye.com":          "h2.title, .headline",
    "chosun.com":         "h2, .story-card__headline, .article-title",
    "joongang.co.kr":     "h2, .headline, .card__title",
    "hani.co.kr":         "h2, .title, .article-title",
    "hankookilbo.com":    "h2, .headline, .article-title",
    "mk.co.kr":           "h2, .title, .headline",
    "sedaily.com":        "h2, .title, .article-title",
    "hankyung.com":       "h2.titles-heading, h2, .article-title",
}


def _browser_exe():
    custom = os.getenv("CHROME_EXECUTABLE")
    if custom and os.path.exists(custom):
        return custom
    return None


def _make_context(browser):
    return browser.new_context(
        viewport=VIEWPORT,
        user_agent=_UA,
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        ignore_https_errors=True,
        extra_http_headers={
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        },
    )


def _apply_stealth(page):
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR','ko','en-US']});
        window.chrome = {runtime: {}, app: {}, loadTimes: () => {}};
    """)


def _site_key(url: str) -> str:
    for key in _SITE_READY_SELECTORS:
        if key in url:
            return key
    return ""


def _hide_overlays(page):
    """Inject CSS to hide cookie banners, modals, subscription walls."""
    try:
        page.add_style_tag(content="""
            /* Popups, cookie banners, modals, subscription walls */
            [class*="cookie"], [class*="Cookie"],
            [class*="gdpr"], [class*="GDPR"],
            [id*="cookie"], [id*="Cookie"],
            [class*="popup"], [class*="Popup"],
            [class*="modal"], [class*="Modal"],
            [id*="popup"], [id*="modal"],
            [class*="layer"][class*="ad"],
            [class*="subscribe"][class*="wall"],
            [class*="paywall"], [class*="pay-wall"],
            [class*="newsletter"], [class*="push-noti"],
            .floating-bar, .float-bar, .sticky-bar,
            #floating-layer, .float_layer, .gnb_notice,
            [class*="dim"], [class*="overlay"],
            .toast_message, #toast-message,
            .ad-layer, .ad_layer, .floating_ad {
                display: none !important;
                visibility: hidden !important;
                opacity: 0 !important;
                pointer-events: none !important;
            }
            /* Allow scrolling */
            body, html { overflow: auto !important; }
        """)
    except Exception:
        pass


def _dismiss_popups(page):
    """Click close buttons on visible popups."""
    selectors = [
        "button[aria-label='닫기']", "button[aria-label='close']",
        ".btn_close", ".close_btn", ".btn-close",
        "button[class*='close']", "a[class*='close']",
        ".modal__close", ".popup__close", ".layer_close",
        "[class*='popup'] [class*='close']",
        "[class*='modal'] [class*='close']",
        "button:has-text('닫기')", "button:has-text('확인')",
        "button:has-text('동의')", "button:has-text('이후에 보기')",
    ]
    for sel in selectors:
        try:
            els = page.query_selector_all(sel)
            for el in els[:3]:
                if el.is_visible():
                    el.click(timeout=1000)
                    page.wait_for_timeout(300)
        except Exception:
            pass


def capture_newspaper(name: str, url: str, output_path: str) -> bool:
    """
    Capture a viewport screenshot of `url` as `output_path`.
    Returns True on success (non-blank image), False otherwise.
    """
    from playwright.sync_api import sync_playwright

    kwargs = {"args": _CHROME_ARGS}
    exe = _browser_exe()
    if exe:
        kwargs["executable_path"] = exe

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**kwargs)
            ctx = _make_context(browser)
            page = ctx.new_page()
            _apply_stealth(page)

            # Block ad/tracker requests
            def _route(route):
                req = route.request
                if req.resource_type in ("media",):
                    route.abort()
                elif any(re.search(pat.replace("*", ".*"), req.url)
                         for pat in _BLOCK_PATTERNS):
                    route.abort()
                else:
                    route.continue_()
            page.route("**/*", _route)

            # Navigate
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=35000)
            except Exception:
                try:
                    page.goto(url, wait_until="load", timeout=35000)
                except Exception as e:
                    print(f"      [{name}] 탐색 실패: {e}")
                    browser.close()
                    return False

            # Wait for meaningful content
            site_key = _site_key(url)
            ready_sel = _SITE_READY_SELECTORS.get(site_key, "h2, h1, article")
            try:
                page.wait_for_selector(ready_sel, timeout=10000, state="visible")
            except Exception:
                # Fallback: just wait a bit
                page.wait_for_timeout(4000)

            # Extra settle time for JS rendering
            page.wait_for_timeout(2000)

            # Dismiss overlays
            _hide_overlays(page)
            _dismiss_popups(page)
            page.wait_for_timeout(500)

            # Scroll to top
            try:
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(300)
            except Exception:
                pass

            # Take screenshot
            page.screenshot(
                path=output_path,
                full_page=False,
                type="png",
                clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": VIEWPORT["height"]},
            )
            browser.close()

        # Validate: reject blank/near-white pages
        return _is_valid_screenshot(output_path)

    except Exception as e:
        print(f"      [{name}] 캡처 오류: {e}")
        return False


def _is_valid_screenshot(path: str) -> bool:
    """Return False if the screenshot is a blank/error page."""
    try:
        from PIL import Image
        import statistics

        img = Image.open(path).convert("RGB")
        w, h = img.size
        if w < 100 or h < 100:
            return False

        # Sample grid of pixels
        samples = []
        for xi in range(5, w, w // 12):
            for yi in range(5, h, h // 10):
                r, g, b = img.getpixel((xi, yi))
                samples.append((r, g, b))

        if not samples:
            return False

        r_vals = [s[0] for s in samples]
        r_mean = sum(r_vals) / len(r_vals)
        r_std  = statistics.stdev(r_vals) if len(r_vals) > 1 else 0

        # Blank white page: mean ≈ 255, std ≈ 0
        # Browser error page: mean ≈ 240+, std < 15
        if r_mean > 245 and r_std < 12:
            print(f"        → 빈 화면 감지 (평균 {r_mean:.0f}, σ {r_std:.1f}) — 캡처 실패 처리")
            return False
        return True
    except Exception:
        return True  # Can't check → assume OK


def capture_all_newspapers(newspapers: list[dict], output_dir: str) -> list[dict]:
    """
    Capture all newspaper screenshots. Each newspaper gets its own browser session
    to avoid state leakage.

    Returns list of result dicts: name, url, screenshot_path, success.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    results = []

    for idx, paper in enumerate(newspapers):
        name = paper["name"]
        url  = paper["url"]
        safe = name.replace("/", "_")
        out  = str(Path(output_dir) / f"{safe}.png")

        print(f"      [{idx+1:2d}/{len(newspapers)}] {name} — {url}")
        ok = capture_newspaper(name, url, out)
        results.append({
            "name": name,
            "url": url,
            "screenshot_path": out if ok else None,
            "success": ok,
        })
        time.sleep(0.8)

    good = sum(1 for r in results if r["success"])
    print(f"\n      스크린샷: {good}/{len(newspapers)}개 성공")
    return results
