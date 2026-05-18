"""
Korean news scraper — Playwright-only multi-source approach.

Sources attempted in order:
  A. Google News search page (Playwright)
  B. Naver News search page (Playwright)
  C. Bing News search page (Playwright)

Playwright is used exclusively for all web fetching (no requests library).
"""

import re
import os
import datetime
from urllib.parse import quote_plus

# ── Playwright / Chrome config ────────────────────────────────────────────────

_CHROME_ARGS = [
    "--no-sandbox", "--disable-setuid-sandbox",
    "--disable-dev-shm-usage", "--disable-gpu", "--no-zygote",
    "--ignore-certificate-errors",
    "--disable-blink-features=AutomationControlled",
]

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_STEALTH_SCRIPT = (
    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
    "window.chrome={runtime:{}};"
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
    ".article-body", ".article_body",
    "#newsViewArea", ".news_cnt_detail_wrap",  # 매일경제
    ".article_txt",                     # 세계일보
    ".view_text", ".article_view",      # 서울경제
    ".article-text", ".article_text",   # 한겨레
    ".article_body_content",            # 중앙일보
    "article",
    "div[itemprop='articleBody']",
    "div[class*='article'][class*='body']",
    "div[class*='article'][class*='content']",
]

_NOISE = (
    "script, style, figure, figcaption, "
    ".ad, .advertisement, .reporter, .relate_news, "
    ".photo_area, .vod_area, .copyright, "
    ".article_relation, .ad_area, iframe, aside"
)

# ── JS snippets for article extraction ───────────────────────────────────────

_JS_GOOGLE_NEWS = """() => {
  const results = [];
  document.querySelectorAll('article').forEach(art => {
    const a = art.querySelector('h3 a, h4 a, a[href*="article"]');
    if (!a || !a.innerText.trim()) return;
    const src = art.querySelector('time')?.closest('div')?.querySelector('a')?.innerText?.trim()
             || art.querySelector('[data-n-tid]')?.innerText?.trim() || '';
    const t = art.querySelector('time');
    results.push({
      title: a.innerText.trim(),
      href: a.href,
      source: src,
      date: t ? (t.getAttribute('datetime') || t.innerText.trim()) : '',
    });
  });
  return results;
}"""

_JS_NAVER_NEWS = """() => {
  return Array.from(document.querySelectorAll('a.news_tit')).map(a => {
    const li = a.closest('li') || a.closest('div');
    return {
      title: a.innerText.trim(),
      url: a.href,
      source: li?.querySelector('a.info.press, a[class*="press"]')?.innerText?.trim() || '',
      date: li?.querySelector('span.info')?.innerText?.trim() || '',
      summary: li?.querySelector('.dsc_wrap, .dsc_txt')?.innerText?.trim() || '',
    };
  }).filter(a => a.title && a.url);
}"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _browser_exe():
    """Return custom Chrome executable path if set and exists, else None."""
    custom = os.getenv("CHROME_EXECUTABLE")
    if custom and os.path.exists(custom):
        return custom
    return None


def _launch_kwargs():
    """Build kwargs for pw.chromium.launch()."""
    kwargs = {"args": _CHROME_ARGS, "headless": True}
    exe = _browser_exe()
    if exe:
        kwargs["executable_path"] = exe
    return kwargs


def _new_context(browser):
    """Create a new browser context with standard settings."""
    return browser.new_context(
        viewport={"width": 1440, "height": 900},
        user_agent=_UA,
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        ignore_https_errors=True,
    )


def _new_page(ctx):
    """Create a new page with stealth init script applied."""
    page = ctx.new_page()
    page.add_init_script(_STEALTH_SCRIPT)
    return page


def _clean_text(text: str) -> str:
    """Normalise whitespace in extracted text."""
    text = re.sub(r"\n{3,}", "\n\n", text or "")
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# ── Source A: Google News search page (Playwright) ────────────────────────────

def _source_google_news(keyword: str, count: int) -> list:
    """Scrape Google News search page via Playwright."""
    from playwright.sync_api import sync_playwright

    url = f"https://news.google.com/search?q={quote_plus(keyword)}&hl=ko&gl=KR&ceid=KR:ko"
    print(f"      [Source A] Google News: {url[:90]}")

    articles = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**_launch_kwargs())
            ctx = _new_context(browser)
            page = _new_page(ctx)

            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            print(f"      [Source A] 페이지 제목: {page.title()!r}")

            raw = page.evaluate(_JS_GOOGLE_NEWS)
            print(f"      [Source A] article 요소 {len(raw)}개 추출")

            for item in raw[:count]:
                title = item.get("title", "").strip()
                href = item.get("href", "").strip()
                if not title or not href:
                    continue
                articles.append({
                    "title":   title,
                    "url":     href,
                    "source":  item.get("source", ""),
                    "date":    item.get("date", ""),
                    "summary": "",
                    "content": "",
                })

            browser.close()
    except Exception as e:
        print(f"      [Source A] 오류: {e}")

    print(f"      [Source A] 수집 완료: {len(articles)}개")
    return articles


# ── Source B: Naver News search page (Playwright) ────────────────────────────

def _source_naver_news(keyword: str, count: int) -> list:
    """Scrape Naver News search via Playwright."""
    from playwright.sync_api import sync_playwright

    url = (
        f"https://search.naver.com/search.naver"
        f"?where=news&query={quote_plus(keyword)}&sort=1"
    )
    print(f"      [Source B] Naver News: {url[:90]}")

    articles = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**_launch_kwargs())
            ctx = _new_context(browser)
            page = _new_page(ctx)

            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            print(f"      [Source B] 페이지 제목: {page.title()!r}")

            raw = page.evaluate(_JS_NAVER_NEWS)
            print(f"      [Source B] news_tit 요소 {len(raw)}개 추출")

            for item in raw[:count]:
                title = item.get("title", "").strip()
                url_item = item.get("url", "").strip()
                if not title or not url_item:
                    continue
                articles.append({
                    "title":   title,
                    "url":     url_item,
                    "source":  item.get("source", ""),
                    "date":    item.get("date", ""),
                    "summary": item.get("summary", ""),
                    "content": "",
                })

            browser.close()
    except Exception as e:
        print(f"      [Source B] 오류: {e}")

    print(f"      [Source B] 수집 완료: {len(articles)}개")
    return articles


# ── Source C: Bing News search page (Playwright) ─────────────────────────────

def _source_bing_news(keyword: str, count: int) -> list:
    """Scrape Bing News search via Playwright."""
    from playwright.sync_api import sync_playwright

    url = f"https://www.bing.com/news/search?q={quote_plus(keyword)}&mkt=ko-KR"
    print(f"      [Source C] Bing News: {url[:90]}")

    articles = []
    _JS_BING = """() => {
      return Array.from(document.querySelectorAll('a.title, .news-card a[href]')).map(a => {
        const card = a.closest('.news-card, article, li');
        return {
          title: (a.innerText || a.textContent || '').trim(),
          url: a.href,
          source: card?.querySelector('.source, .provider')?.innerText?.trim() || '',
          date: card?.querySelector('time, .datetime')?.innerText?.trim() || '',
          summary: card?.querySelector('.snippet, .description')?.innerText?.trim() || '',
        };
      }).filter(a => a.title && a.url && !a.url.includes('bing.com'));
    }"""

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**_launch_kwargs())
            ctx = _new_context(browser)
            page = _new_page(ctx)

            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            print(f"      [Source C] 페이지 제목: {page.title()!r}")

            raw = page.evaluate(_JS_BING)
            print(f"      [Source C] 뉴스 카드 {len(raw)}개 추출")

            seen_titles = set()
            for item in raw:
                title = item.get("title", "").strip()
                url_item = item.get("url", "").strip()
                if not title or not url_item or title in seen_titles:
                    continue
                seen_titles.add(title)
                articles.append({
                    "title":   title,
                    "url":     url_item,
                    "source":  item.get("source", ""),
                    "date":    item.get("date", ""),
                    "summary": item.get("summary", ""),
                    "content": "",
                })
                if len(articles) >= count:
                    break

            browser.close()
    except Exception as e:
        print(f"      [Source C] 오류: {e}")

    print(f"      [Source C] 수집 완료: {len(articles)}개")
    return articles


# ── Public search entry point ─────────────────────────────────────────────────

def search_naver_news(keyword: str, count: int = 20) -> list:
    """
    Main entry point: try Google News, Naver News, Bing News in order.
    Returns up to `count` articles from the first source that succeeds.
    """
    print(f"      키워드: {keyword!r}, 목표 기사 수: {count}")

    # Source A: Google News
    articles = _source_google_news(keyword, count)
    if articles:
        print(f"      → Source A 성공: {len(articles)}개 기사")
        return articles[:count]

    # Source B: Naver News
    print("      → Source A 실패 또는 결과 없음, Source B 시도...")
    articles = _source_naver_news(keyword, count)
    if articles:
        print(f"      → Source B 성공: {len(articles)}개 기사")
        return articles[:count]

    # Source C: Bing News
    print("      → Source B 실패 또는 결과 없음, Source C 시도...")
    articles = _source_bing_news(keyword, count)
    if articles:
        print(f"      → Source C 성공: {len(articles)}개 기사")
        return articles[:count]

    print("      → 모든 Source 실패: 기사를 찾지 못했습니다.")
    return []


# ── Article full-text extractor (Playwright) ──────────────────────────────────

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
            try:
                page.eval_on_selector(
                    sel,
                    f"el => el.querySelectorAll('{_NOISE}').forEach(n => n.remove())"
                )
            except Exception:
                pass
            text = (el.inner_text() or "").strip()
            if len(text) > 150:
                return _clean_text(text)[:max_chars]
        except Exception:
            continue

    # Fallback: collect all <p> with substantial text
    try:
        paras = page.query_selector_all("p")
        chunks = [(p.inner_text() or "").strip() for p in paras]
        body = "\n\n".join(c for c in chunks if len(c) > 40)
        if len(body) > 150:
            return _clean_text(body)[:max_chars]
    except Exception:
        pass

    return ""


def enrich_articles(articles: list) -> list:
    """
    Visit each article URL and extract the full article body text.
    Uses a SINGLE Playwright browser session for all articles.
    After navigation, updates art['url'] to the real URL (after redirects).
    """
    from playwright.sync_api import sync_playwright

    if not articles:
        return articles

    with sync_playwright() as pw:
        browser = pw.chromium.launch(**_launch_kwargs())
        ctx = _new_context(browser)
        page = _new_page(ctx)

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

            # Update URL to real URL after any redirects (e.g. Google News)
            art["url"] = page.url

            if content:
                art["content"] = content
                print(f"                 → {len(content)}자")
            else:
                art["content"] = art.get("summary", "")
                print(f"                 → 본문 없음, 요약 사용")

        browser.close()

    with_content = sum(1 for a in articles if len(a.get("content", "")) > 100)
    summary_only = len(articles) - with_content
    print(f"      → 전문 수집 요약: {with_content}개 본문 있음, {summary_only}개 요약만 있음")

    return articles
