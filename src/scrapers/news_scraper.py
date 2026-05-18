"""
Naver News scraper using Playwright.
Works in environments with actual internet access (e.g., GitHub Actions, local machine).
"""

import re
import time
import datetime
from urllib.parse import quote_plus, urljoin

CHROME_EXECUTABLE = None  # None = Playwright auto-detect

_PLAYWRIGHT_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--no-zygote",
    "--ignore-certificate-errors",
]


def _get_browser_executable():
    import os
    custom = os.getenv("CHROME_EXECUTABLE")
    if custom and os.path.exists(custom):
        return custom
    return None


def search_naver_news(keyword: str, count: int = 20) -> list[dict]:
    """
    Search Naver News and return structured article list.
    Uses Playwright to bypass bot detection.
    """
    from playwright.sync_api import sync_playwright

    articles = []
    url = (
        f"https://search.naver.com/search.naver"
        f"?where=news&query={quote_plus(keyword)}&sort=1"
    )

    exe = _get_browser_executable()
    launch_kwargs = {"args": _PLAYWRIGHT_ARGS}
    if exe:
        launch_kwargs["executable_path"] = exe

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kwargs)
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="ko-KR",
                ignore_https_errors=True,
            )
            page = ctx.new_page()

            fetched = 0
            page_num = 1

            while fetched < count:
                start = (page_num - 1) * 10 + 1
                paged_url = url + f"&start={start}"
                try:
                    page.goto(paged_url, wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(1500)
                except Exception:
                    break

                # Parse article items
                batch = _parse_news_page(page, keyword)
                if not batch:
                    break

                articles.extend(batch)
                fetched += len(batch)
                page_num += 1

                if len(batch) < 10:
                    break

            browser.close()

    except Exception as e:
        print(f"[news_scraper] search error: {e}")

    return articles[:count]


def _parse_news_page(page, keyword: str) -> list[dict]:
    """Extract article data from a loaded Naver News search result page."""
    articles = []

    # Try multiple container selectors (Naver changes HTML frequently)
    containers = page.query_selector_all("div.news_wrap article") or \
                 page.query_selector_all("div.bx") or \
                 page.query_selector_all("li.bx")

    for item in containers:
        try:
            art = _extract_article(item)
            if art and art.get("title") and art.get("url"):
                articles.append(art)
        except Exception:
            continue

    return articles


def _extract_article(item) -> dict | None:
    """Extract a single article from a search result item element."""
    # Title + URL
    title_el = (
        item.query_selector("a.news_tit") or
        item.query_selector("a[class*='news_tit']") or
        item.query_selector("div.news_info a") or
        item.query_selector("a[href*='news']")
    )
    if not title_el:
        return None

    title = (title_el.inner_text() or "").strip()
    url = title_el.get_attribute("href") or ""
    if not title or not url.startswith("http"):
        return None

    # Source
    src_el = (
        item.query_selector("a.info.press") or
        item.query_selector("span.info_group a.press") or
        item.query_selector("a[class*='press']") or
        item.query_selector("div.news_info div.info_group a")
    )
    source = (src_el.inner_text() or "미확인").strip() if src_el else "미확인"

    # Date - look for time-like text
    date_str = ""
    info_spans = item.query_selector_all("span.info") + item.query_selector_all("span[class*='date']")
    for span in info_spans:
        t = (span.inner_text() or "").strip()
        if re.search(r'\d+[시간분일]|어제|전|\d{4}\.\d{2}\.\d{2}', t):
            date_str = t
            break

    if not date_str:
        date_str = datetime.date.today().strftime("%Y.%m.%d.")

    # Summary
    desc_el = (
        item.query_selector("div.dsc_wrap") or
        item.query_selector("a.dsc_txt") or
        item.query_selector("div[class*='dsc']")
    )
    summary = (desc_el.inner_text() or "").strip()[:400] if desc_el else ""

    return {
        "title": title,
        "source": source,
        "date": date_str,
        "url": url,
        "summary": summary,
        "content": "",
    }


def fetch_article_content(url: str, max_chars: int = 1500) -> str:
    """
    Fetch the main article body from a news URL using Playwright.
    """
    if not url or not url.startswith("http"):
        return ""

    from playwright.sync_api import sync_playwright

    exe = _get_browser_executable()
    launch_kwargs = {"args": _PLAYWRIGHT_ARGS}
    if exe:
        launch_kwargs["executable_path"] = exe

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kwargs)
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="ko-KR",
                ignore_https_errors=True,
            )
            page = ctx.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_timeout(1000)
            except Exception:
                browser.close()
                return ""

            content = _extract_article_content(page)
            browser.close()
            return content[:max_chars].strip()

    except Exception as e:
        print(f"[news_scraper] fetch_article_content error: {e}")
        return ""


def _extract_article_content(page) -> str:
    """Extract main text from an article page."""
    # Common article body selectors for major Korean news sites
    selectors = [
        # Naver News (most common target)
        "#dic_area",
        "#newsEndContents",
        "#articleBodyContents",
        # General patterns
        "article",
        "div.article_body",
        "div#article-view-content-div",
        "div.article_txt",
        "div#newsct_article",
        "div.news_end",
        "div.article_content",
        "div[class*='article'][class*='body']",
        "div[class*='article'][class*='content']",
        "section.article-body",
        ".article_body_content",
        ".view_text",
        ".article_view",
    ]

    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                # Remove noise elements
                page.eval_on_selector(sel,
                    """el => {
                        el.querySelectorAll('script,style,figure,.ad,.advertisement,.reporter,.relate_news').forEach(e=>e.remove());
                    }"""
                )
                text = (el.inner_text() or "").strip()
                if len(text) > 100:
                    # Clean up whitespace
                    text = re.sub(r'\n{3,}', '\n\n', text)
                    return text
        except Exception:
            continue

    # Fallback: collect all paragraphs
    try:
        paras = page.query_selector_all("p")
        texts = [(p.inner_text() or "").strip() for p in paras if len((p.inner_text() or "").strip()) > 30]
        return "\n\n".join(texts)
    except Exception:
        return ""


def enrich_articles(articles: list[dict]) -> list[dict]:
    """
    Fetch full article content for each article.
    Uses a single browser session for efficiency.
    """
    from playwright.sync_api import sync_playwright

    if not articles:
        return articles

    exe = _get_browser_executable()
    launch_kwargs = {"args": _PLAYWRIGHT_ARGS}
    if exe:
        launch_kwargs["executable_path"] = exe

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kwargs)
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="ko-KR",
                ignore_https_errors=True,
            )
            page = ctx.new_page()

            for i, art in enumerate(articles):
                url = art.get("url", "")
                if not url or not url.startswith("http"):
                    art["content"] = art.get("summary", "")
                    continue
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_timeout(800)
                    content = _extract_article_content(page)
                    art["content"] = content[:1500] if content else art.get("summary", "")
                    print(f"    [{i+1}/{len(articles)}] {art['source']} — {len(art['content'])}자")
                except Exception as e:
                    art["content"] = art.get("summary", "")
                    print(f"    [{i+1}/{len(articles)}] 본문 수집 실패: {e}")

            browser.close()

    except Exception as e:
        print(f"[news_scraper] enrich_articles error: {e}")
        for art in articles:
            if not art.get("content"):
                art["content"] = art.get("summary", "")

    return articles
