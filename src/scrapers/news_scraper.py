"""
Korean news scraper — Google News RSS (primary) + Playwright article body extractor.

Why Google News RSS instead of Naver search:
  - No bot detection / CAPTCHA
  - Returns real article URLs from actual newspapers
  - Clean structured XML (no fragile CSS selectors on search UI)
  - Playwright is reserved only for article full-text extraction,
    where it's proven to work on newspaper sites.
"""

import re
import os
import time
import datetime
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

# ── HTTP session for RSS + redirect resolution ────────────────────────────────
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

# ── Playwright config ─────────────────────────────────────────────────────────
_CHROME_ARGS = [
    "--no-sandbox", "--disable-setuid-sandbox",
    "--disable-dev-shm-usage", "--disable-gpu", "--no-zygote",
    "--ignore-certificate-errors",
    "--disable-blink-features=AutomationControlled",
    "--window-size=1440,900",
]
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Article body selectors — ordered by reliability
_ARTICLE_SELECTORS = [
    # Naver News (hosted)
    "#dic_area", "#articeBody", "#newsEndContents", "#articleBodyContents",
    # 주요 신문사
    "#article_txt",                     # 동아일보
    "#articleText",                     # 경향신문
    "#articleBody",                     # 국민일보
    "#article_content",                 # 서울신문
    ".article-body", ".article_body",   # 한국경제, 조선 등
    "#newsViewArea",                    # 매일경제
    ".news_cnt_detail_wrap",            # 매일경제 v2
    ".article_txt",                     # 세계일보
    ".view_text", ".article_view",      # 서울경제
    ".article-text", ".article_text",   # 한겨레
    ".article_body_content",            # 중앙일보
    "#article-view-content-div",        # 일부 지역지
    "div[itemprop='articleBody']",
    "article",
    "div[class*='article'][class*='body']",
    "div[class*='article'][class*='content']",
    ".view_content", ".news_view",
]

_NOISE = (
    "script, style, figure, figcaption, "
    ".ad, .advertisement, .reporter, .relate_news, "
    ".photo_area, .vod_area, .copyright, "
    ".article_relation, .ad_area, iframe, aside"
)


# ── Helper utilities ──────────────────────────────────────────────────────────

def _clean_html(html: str) -> str:
    """Strip HTML tags and unescape entities."""
    text = re.sub(r"<[^>]+>", "", html or "")
    for ent, ch in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                    ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")]:
        text = text.replace(ent, ch)
    return text.strip()


def _parse_rss_date(pub_date: str) -> str:
    """Convert RFC 2822 date (RSS pubDate) to Korean date string."""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(pub_date)
        # Convert to KST (+9)
        kst = dt.astimezone(datetime.timezone(datetime.timedelta(hours=9)))
        return kst.strftime("%Y.%m.%d. %H:%M")
    except Exception:
        return datetime.date.today().strftime("%Y.%m.%d.")


def _resolve_url(google_url: str) -> str:
    """
    Follow the Google News redirect to get the actual newspaper article URL.
    Google News RSS <link>s are 302 redirects to the real article.
    """
    if not google_url or not google_url.startswith("http"):
        return google_url or ""
    try:
        resp = _SESSION.get(google_url, allow_redirects=True, timeout=10)
        final = resp.url
        # If redirect brought us to a real newspaper (not google.com), use it
        if "google.com" not in final and "google.co" not in final:
            return final
    except Exception:
        pass
    return google_url  # Keep Google URL as fallback


def _browser_exe() -> str | None:
    custom = os.getenv("CHROME_EXECUTABLE")
    if custom and os.path.exists(custom):
        return custom
    return None


# ── Primary: Google News RSS ──────────────────────────────────────────────────

def search_google_news_rss(keyword: str, count: int = 20) -> list[dict]:
    """
    Fetch Google News RSS for `keyword` and return structured article list.
    Each dict: title, source, date, url (real newspaper URL), summary, content="".
    """
    rss_url = (
        f"https://news.google.com/rss/search"
        f"?q={quote_plus(keyword)}&hl=ko&gl=KR&ceid=KR:ko"
    )
    print(f"      → Google News RSS 요청: {rss_url[:80]}")

    try:
        resp = _SESSION.get(rss_url, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"      [오류] RSS 수집 실패: {e}")
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"      [오류] RSS XML 파싱 실패: {e}")
        return []

    items = root.findall(".//item")
    print(f"      → RSS 아이템 {len(items)}개 발견")

    articles = []
    for item in items[:count]:
        title    = _clean_html(item.findtext("title", ""))
        glink    = item.findtext("link", "").strip()
        pub_date = item.findtext("pubDate", "")
        desc_raw = item.findtext("description", "")
        desc     = _clean_html(desc_raw)[:500]

        # Source name from <source> element
        src_el = item.find("source")
        source = (src_el.text or "").strip() if src_el is not None else ""

        if not title or not glink:
            continue

        # Resolve actual article URL (follow Google redirect)
        real_url = _resolve_url(glink)

        articles.append({
            "title":   title,
            "source":  source,
            "date":    _parse_rss_date(pub_date),
            "url":     real_url,
            "summary": desc,
            "content": "",
        })

    print(f"      → URL 추적 완료: {len(articles)}개 기사")
    return articles


# ── Fallback: Naver News (Playwright) ────────────────────────────────────────

def _search_naver_playwright(keyword: str, count: int = 20) -> list[dict]:
    """Fallback: scrape Naver News search results via Playwright."""
    from playwright.sync_api import sync_playwright

    articles = []
    kwargs = {"args": _CHROME_ARGS}
    exe = _browser_exe()
    if exe:
        kwargs["executable_path"] = exe

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**kwargs)
            ctx = browser.new_context(
                viewport={"width": 1440, "height": 900}, user_agent=_UA,
                locale="ko-KR", ignore_https_errors=True,
                extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"},
            )
            page = ctx.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                "window.chrome={runtime:{}};"
            )

            url = (
                f"https://search.naver.com/search.naver"
                f"?where=news&query={quote_plus(keyword)}&sort=1"
            )
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(3000)

            print(f"      → Naver 검색 페이지 제목: {page.title()!r}")

            # Extract via JS (most reliable, bypasses selector fragility)
            raw = page.evaluate("""() => {
                const results = [];
                document.querySelectorAll('a.news_tit').forEach(a => {
                    const li   = a.closest('li') || a.closest('div.news_wrap');
                    const srcA = li ? li.querySelector('a.info.press, a[class*="press"]') : null;
                    const date = li ? li.querySelector('span.info') : null;
                    const desc = li ? li.querySelector('.dsc_wrap, .dsc_txt') : null;
                    results.push({
                        title:   a.innerText.trim(),
                        url:     a.href,
                        source:  srcA ? srcA.innerText.trim() : '',
                        date:    date ? date.innerText.trim() : '',
                        summary: desc ? desc.innerText.trim() : '',
                    });
                });
                return results;
            }""")

            print(f"      → Naver JS 추출: {len(raw)}개")
            for item in raw[:count]:
                if item.get("title") and item.get("url"):
                    articles.append({**item, "content": ""})

            browser.close()
    except Exception as e:
        print(f"      [오류] Naver Playwright 수집 실패: {e}")

    return articles


# ── Public search entry point ─────────────────────────────────────────────────

def search_naver_news(keyword: str, count: int = 20) -> list[dict]:
    """
    Main entry point: try Google News RSS first, fall back to Naver Playwright.
    """
    articles = search_google_news_rss(keyword, count)
    if not articles:
        print("      → RSS 실패, Naver News Playwright 방식 재시도...")
        articles = _search_naver_playwright(keyword, count)
    return articles[:count]


# ── Article full-text extractor (Playwright) ──────────────────────────────────

def enrich_articles(articles: list[dict]) -> list[dict]:
    """
    Visit each article URL and extract the full article body text.
    Uses a single Playwright browser session for all articles.
    """
    from playwright.sync_api import sync_playwright

    if not articles:
        return articles

    kwargs = {"args": _CHROME_ARGS}
    exe = _browser_exe()
    if exe:
        kwargs["executable_path"] = exe

    with sync_playwright() as pw:
        browser = pw.chromium.launch(**kwargs)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900}, user_agent=_UA,
            locale="ko-KR", ignore_https_errors=True,
        )
        page = ctx.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            "window.chrome={runtime:{}};"
        )

        # Block images / media to speed up page loads
        page.route(
            "**/*",
            lambda r: r.abort()
            if r.request.resource_type in ("image", "media", "font")
            else r.continue_(),
        )

        for i, art in enumerate(articles):
            url = art.get("url", "")
            print(f"    [{i+1:2d}/{len(articles)}] {art.get('source',''):12s} | {art.get('title','')[:45]}")

            if not url or not url.startswith("http"):
                art["content"] = art.get("summary", "")
                continue

            content = _extract_body(page, url)
            if content:
                art["content"] = content
                print(f"                 → {len(content)}자")
            else:
                art["content"] = art.get("summary", "")
                print(f"                 → 본문 없음, 요약 사용")

        browser.close()

    return articles


def _extract_body(page, url: str, max_chars: int = 2500) -> str:
    """Navigate to article URL and extract full body text."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1000)
    except Exception as e:
        print(f"                 → 접속 실패: {e}")
        return ""

    for sel in _ARTICLE_SELECTORS:
        try:
            el = page.query_selector(sel)
            if not el:
                continue
            # Remove noise nodes
            page.eval_on_selector(
                sel,
                f"el => el.querySelectorAll('{_NOISE}').forEach(n => n.remove())"
            )
            text = (el.inner_text() or "").strip()
            if len(text) > 150:
                text = re.sub(r"\n{3,}", "\n\n", text)
                text = re.sub(r"[ \t]{2,}", " ", text)
                return text[:max_chars]
        except Exception:
            continue

    # Fallback: collect all <p> with substantial text
    try:
        paras = page.query_selector_all("p")
        chunks = [(p.inner_text() or "").strip() for p in paras]
        body = "\n\n".join(c for c in chunks if len(c) > 40)
        if len(body) > 150:
            return body[:max_chars]
    except Exception:
        pass

    return ""
