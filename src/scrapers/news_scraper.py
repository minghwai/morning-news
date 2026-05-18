"""
Naver News real-data scraper using Playwright + stealth mode.

Flow:
  1. Search Naver News for keyword (sort=1 = latest)
  2. Collect real article URLs, sources, dates, summaries
  3. Visit each article URL → extract full article body text
"""

import re
import os
import time
import datetime
from urllib.parse import quote_plus

_CHROME_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--no-zygote",
    "--ignore-certificate-errors",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--window-size=1440,900",
]

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _browser_exe():
    custom = os.getenv("CHROME_EXECUTABLE")
    if custom and os.path.exists(custom):
        return custom
    return None


def _stealth_context(browser):
    """Create a stealth browser context."""
    ctx = browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent=_UA,
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        ignore_https_errors=True,
        extra_http_headers={
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        },
    )
    return ctx


def _apply_stealth(page):
    """Inject JS to hide headless browser signals."""
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3]});
        Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR','ko','en-US','en']});
        window.chrome = {runtime: {}};
    """)


def search_naver_news(keyword: str, count: int = 20) -> list[dict]:
    """
    Search Naver News for `keyword` and return up to `count` articles.
    Each article dict has: title, source, date, url, summary, content (empty until enriched).
    """
    from playwright.sync_api import sync_playwright

    articles: list[dict] = []
    page_no = 1

    kwargs = {"args": _CHROME_ARGS}
    exe = _browser_exe()
    if exe:
        kwargs["executable_path"] = exe

    with sync_playwright() as pw:
        browser = pw.chromium.launch(**kwargs)
        ctx = _stealth_context(browser)
        page = ctx.new_page()
        _apply_stealth(page)

        while len(articles) < count:
            start = (page_no - 1) * 10 + 1
            url = (
                f"https://search.naver.com/search.naver"
                f"?where=news&query={quote_plus(keyword)}&sort=1&start={start}"
            )
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(1800)
            except Exception as e:
                print(f"[news] 네이버 뉴스 검색 페이지 로드 실패 (page {page_no}): {e}")
                break

            batch = _parse_search_page(page)
            if not batch:
                break

            articles.extend(batch)
            if len(batch) < 10:
                break
            page_no += 1

        browser.close()

    return articles[:count]


def _parse_search_page(page) -> list[dict]:
    """Parse all article entries from a loaded Naver News search result page."""
    results = []

    # Naver News uses <li class="bx"> or <div class="news_area"> depending on skin
    items = (
        page.query_selector_all("li.bx")
        or page.query_selector_all("div.news_wrap")
        or page.query_selector_all("div.news_area")
    )

    for item in items:
        art = _extract_one(item)
        if art:
            results.append(art)

    return results


def _extract_one(el) -> dict | None:
    """Extract article data from a single search result element."""
    # ── Title + URL ──────────────────────────────────────────────────────────
    title_el = (
        el.query_selector("a.news_tit")
        or el.query_selector("a[class*='news_tit']")
        or el.query_selector("div.news_area a[href*='naver']")
        or el.query_selector("div.news_info a")
    )
    if not title_el:
        return None

    title = (title_el.inner_text() or "").strip()
    url = (title_el.get_attribute("href") or "").strip()

    if not title or not url.startswith("http"):
        return None

    # ── Source (언론사) ──────────────────────────────────────────────────────
    src_el = (
        el.query_selector("a.info.press")
        or el.query_selector("a[class*='press']")
        or el.query_selector("span.info_group a")
    )
    source = (src_el.inner_text() or "미확인").strip() if src_el else "미확인"

    # ── Date ────────────────────────────────────────────────────────────────
    date_str = ""
    for span in (el.query_selector_all("span.info") + el.query_selector_all("span[class*='date']")):
        t = (span.inner_text() or "").strip()
        if re.search(r'\d+[시간분일]|어제|전|\d{4}\.\d{2}', t):
            date_str = t
            break
    if not date_str:
        date_str = datetime.date.today().strftime("%Y.%m.%d.")

    # ── Summary ──────────────────────────────────────────────────────────────
    desc_el = (
        el.query_selector("div.dsc_wrap")
        or el.query_selector("a.dsc_txt")
        or el.query_selector("div[class*='dsc']")
    )
    summary = ""
    if desc_el:
        summary = (desc_el.inner_text() or "").strip()[:500]

    return {
        "title": title,
        "source": source,
        "date": date_str,
        "url": url,
        "summary": summary,
        "content": "",
    }


# ── Full article content extraction ──────────────────────────────────────────

#: Newspaper-specific CSS selectors for article body
_ARTICLE_SELECTORS = [
    # Naver News (mobile / PC)
    "#dic_area",
    "#articeBody",
    "#newsEndContents",
    "#articleBodyContents",
    # 한국경제
    ".article-body",
    ".article_body",
    "#article-view-content-div",
    # 매일경제
    ".news_cnt_detail_wrap",
    "#newsViewArea",
    # 조선일보
    ".article-body",
    "div[class*='article_body']",
    # 동아일보
    "#article_txt",
    # 한겨레
    ".article-text",
    ".article_text",
    # 중앙일보
    ".article_body_content",
    # 서울경제
    ".article_view",
    ".view_text",
    # 한국일보
    ".article-body",
    # 경향신문
    "#articleText",
    # 세계일보
    ".article_txt",
    # 국민일보
    "#articleBody",
    # 서울신문
    "#article_content",
    # 일반 패턴
    "article",
    "div[itemprop='articleBody']",
    "div[class*='article'][class*='content']",
    "div[class*='article'][class*='body']",
    "div[class*='news'][class*='content']",
    "div[class*='news'][class*='body']",
    ".news_view",
    ".view_content",
    "#content article",
]

_NOISE_SELECTORS = (
    "script, style, figure, figcaption, .ad, .advertisement, "
    ".reporter, .relate_news, .photo_area, .vod_area, "
    ".copyright, .article_relation, .ad_area, iframe"
)


def enrich_articles(articles: list[dict]) -> list[dict]:
    """
    Visit each article URL and extract the full article body.
    Reuses a single browser session for all articles.
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
        ctx = _stealth_context(browser)
        page = ctx.new_page()
        _apply_stealth(page)

        # Block heavy resources that aren't needed for text extraction
        page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in ("image", "media", "font", "stylesheet")
            else route.continue_(),
        )

        for i, art in enumerate(articles):
            url = art.get("url", "")
            print(f"    [{i+1:2d}/{len(articles)}] {art['source']:10s} | {art['title'][:40]}")

            if not url or not url.startswith("http"):
                art["content"] = art.get("summary", "")
                continue

            content = _fetch_article_body(page, url)
            art["content"] = content if content else art.get("summary", "")
            print(f"            → {len(art['content'])}자 수집")

        browser.close()

    return articles


def _fetch_article_body(page, url: str, max_chars: int = 2000) -> str:
    """Navigate to article URL and extract full body text."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1200)
    except Exception as e:
        print(f"            → 접속 실패: {e}")
        return ""

    # Try each selector in priority order
    for sel in _ARTICLE_SELECTORS:
        try:
            el = page.query_selector(sel)
            if not el:
                continue
            # Remove noise elements
            page.eval_on_selector(
                sel,
                f"""el => el.querySelectorAll('{_NOISE_SELECTORS}').forEach(n => n.remove())"""
            )
            text = (el.inner_text() or "").strip()
            # Must be substantial text
            if len(text) > 150:
                # Clean up: remove excessive blank lines
                text = re.sub(r'\n{3,}', '\n\n', text)
                text = re.sub(r'[ \t]{2,}', ' ', text)
                return text[:max_chars]
        except Exception:
            continue

    # Fallback: collect <p> tags
    try:
        paras = page.query_selector_all("p")
        texts = []
        for p in paras:
            t = (p.inner_text() or "").strip()
            if len(t) > 40:
                texts.append(t)
        combined = "\n\n".join(texts)
        if len(combined) > 150:
            return combined[:max_chars]
    except Exception:
        pass

    return ""
