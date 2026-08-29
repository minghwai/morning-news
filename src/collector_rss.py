"""
구글 뉴스 RSS 기반 수집기 — API 키가 필요 없는 대안.

네이버 오픈API 키 발급이 막히거나 어려울 때 이쪽을 쓴다.
NEWS_SOURCE=rss 환경변수 또는 --source rss 로 전환한다.

네이버 방식과 비교
  장점: 키 발급 불필요, 즉시 사용, 매체 이름을 RSS가 직접 알려줌
  단점: 요약문이 제공되지 않아 제목만 실린다.
        링크가 구글 경유 주소라 클릭해야 언론사로 이동한다.

검증 원칙은 동일하다. pubDate 기준 오늘 발행분만 통과시키고,
매체명은 RSS의 <source> 값을 그대로 쓴다.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import quote_plus, urlparse

import requests

from src.collector import KST, CollectorError, PRESS_BY_DOMAIN

RSS_URL = (
    "https://news.google.com/rss/search"
    "?q={q}+when:2d&hl=ko&gl=KR&ceid=KR:ko"
)
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"


def _parse_pubdate(raw: str) -> datetime | None:
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KST)
        return dt.astimezone(KST)
    except Exception:
        return None


def _press_from(item: ET.Element) -> str:
    node = item.find("source")
    if node is not None:
        name = (node.text or "").strip()
        if name:
            return name
        host = (urlparse(node.get("url", "")).hostname or "").replace("www.", "")
        for domain, label in PRESS_BY_DOMAIN.items():
            if host.endswith(domain):
                return label
        if host:
            return host
    return "출처 미상"


def _clean_title(title: str, press: str) -> str:
    """구글 RSS 제목은 '기사 제목 - 언론사' 형태라 접미사를 떼어낸다."""
    text = html.unescape(title or "").strip()
    if press and text.endswith(" - " + press):
        text = text[: -(len(press) + 3)].strip()
    else:
        text = re.sub(r"\s+-\s+[^-]{2,20}$", "", text).strip()
    return text


def collect(keyword: str, max_articles: int = 30, hours_back: int = 0) -> dict:
    """collector.collect() 와 같은 형태의 결과를 돌려준다."""
    now = datetime.now(KST)
    cutoff = (
        now - timedelta(hours=hours_back)
        if hours_back > 0
        else now.replace(hour=0, minute=0, second=0, microsecond=0)
    )

    url = RSS_URL.format(q=quote_plus(keyword))
    try:
        resp = requests.get(url, headers={"User-Agent": _UA}, timeout=20)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as exc:
        raise CollectorError(f"구글 뉴스 RSS 조회 실패: {exc}") from exc

    items = root.findall(".//item")
    total_seen = len(items)
    dropped_old = 0
    dropped_dup = 0

    seen_titles: set[str] = set()
    articles: list[dict] = []

    for item in items:
        published = _parse_pubdate((item.findtext("pubDate") or ""))
        if published is None or published < cutoff:
            dropped_old += 1
            continue

        press = _press_from(item)
        title = _clean_title(item.findtext("title") or "", press)
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        if title in seen_titles:
            dropped_dup += 1
            continue

        seen_titles.add(title)
        articles.append(
            {
                "title": title,
                "summary": "",
                "press": press,
                "source_url": link,
                "naver_url": link,
                "published": published,
                "published_str": published.strftime("%m/%d %H:%M"),
            }
        )

    articles.sort(key=lambda a: a["published"], reverse=True)
    articles = articles[:max_articles]

    by_press: dict[str, int] = {}
    for art in articles:
        by_press[art["press"]] = by_press.get(art["press"], 0) + 1

    return {
        "keyword": keyword,
        "collected_at": now,
        "cutoff": cutoff,
        "articles": articles,
        "stats": {
            "total_seen": total_seen,
            "dropped_old": dropped_old,
            "dropped_dup": dropped_dup,
            "kept": len(articles),
            "press_count": len(by_press),
            "by_press": dict(sorted(by_press.items(), key=lambda kv: -kv[1])),
        },
    }
