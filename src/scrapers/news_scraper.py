"""
News article scraper using Naver News search.
Returns structured article data including title, source, date, url, summary.
"""

import re
import time
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://search.naver.com/",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}


def search_naver_news(keyword: str, count: int = 20) -> list[dict]:
    """Search Naver News and return structured article list."""
    articles = []
    page = 1

    while len(articles) < count:
        start = (page - 1) * 10 + 1
        url = (
            f"https://search.naver.com/search.naver"
            f"?where=news&query={quote_plus(keyword)}"
            f"&sort=1&start={start}"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")

            items = soup.select("div.news_area")
            if not items:
                # Try alternative selector
                items = soup.select("li.bx")

            if not items:
                break

            for item in items:
                if len(articles) >= count:
                    break

                article = _parse_naver_news_item(item)
                if article:
                    articles.append(article)

            page += 1
            time.sleep(0.5)

        except Exception as e:
            print(f"[news_scraper] Error fetching page {page}: {e}")
            break

    return articles[:count]


def _parse_naver_news_item(item) -> dict | None:
    """Parse a single Naver News search result item."""
    try:
        # Title
        title_el = (
            item.select_one("a.news_tit")
            or item.select_one(".news_tit")
            or item.select_one("a[class*='tit']")
        )
        if not title_el:
            return None
        title = title_el.get_text(strip=True)
        url = title_el.get("href", "")

        # Source
        source_el = (
            item.select_one("a.info.press")
            or item.select_one(".info_group a")
            or item.select_one(".press")
        )
        source = source_el.get_text(strip=True) if source_el else "미확인"

        # Date
        date_el = (
            item.select_one("span.info")
            or item.select_one(".info_group span.info")
        )
        date_str = ""
        if date_el:
            texts = [s.get_text(strip=True) for s in item.select("span.info")]
            for t in texts:
                if re.search(r"\d+[시간분일]|어제|\d{4}\.", t):
                    date_str = t
                    break

        # Summary
        desc_el = (
            item.select_one("div.dsc_wrap")
            or item.select_one(".news_dsc")
            or item.select_one(".dsc")
        )
        summary = desc_el.get_text(strip=True) if desc_el else ""

        return {
            "title": title,
            "source": source,
            "date": date_str or _now_str(),
            "url": url,
            "summary": summary[:300],
            "content": "",
        }
    except Exception:
        return None


def fetch_article_content(url: str, max_chars: int = 1200) -> str:
    """
    Fetch and extract the main article body text from a news URL.
    Returns plain text truncated to max_chars.
    """
    if not url or not url.startswith("http"):
        return ""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(resp.text, "lxml")

        # Try common article body selectors across major Korean news sites
        selectors = [
            "article#dic_area",
            "div#articleBodyContents",
            "div.article_body",
            "div#article-view-content-div",
            "div.article_txt",
            "div#newsct_article",
            "div.news_end",
            "div#content-article",
            "div.article_content",
            "section.article-body",
            "div[class*='article'][class*='body']",
            "div[class*='article'][class*='content']",
            "div.article",
        ]

        content = ""
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                # Remove script, style, figure tags
                for tag in el.select("script, style, figure, .ad, .advertisement"):
                    tag.decompose()
                content = el.get_text(separator="\n", strip=True)
                if len(content) > 100:
                    break

        if not content:
            # Fallback: get all paragraph text
            paragraphs = soup.select("p")
            content = "\n".join(
                p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30
            )

        # Clean up excessive whitespace
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content[:max_chars].strip()

    except Exception:
        return ""


def enrich_articles(articles: list[dict]) -> list[dict]:
    """Fetch article content for each article (with rate limiting)."""
    for i, article in enumerate(articles):
        try:
            content = fetch_article_content(article["url"])
            article["content"] = content
        except Exception:
            article["content"] = article.get("summary", "")
        time.sleep(0.3)
    return articles


def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y.%m.%d")
