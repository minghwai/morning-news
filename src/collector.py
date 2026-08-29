"""
네이버 검색 오픈API 기반 뉴스 수집기.

검증 원칙 (허위·과거 기사 차단):
  1. 네이버 뉴스 검색 API만 사용 — 네이버에 색인된 등록 언론사 기사만 들어옴
  2. pubDate(언론사 발행 시각) 기준으로 '오늘(KST)' 발행 기사만 통과
  3. 모든 기사에 originallink(언론사 원문 URL)를 보존 → 1클릭 대조 가능
  4. 언론사명은 URL 도메인에서 역추적 (본문에 적힌 이름을 믿지 않음)
"""

from __future__ import annotations

import html
import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests

KST = timezone(timedelta(hours=9))
API_URL = "https://openapi.naver.com/v1/search/news.json"

#: 도메인 → 언론사명. 없으면 도메인을 그대로 표시한다.
PRESS_BY_DOMAIN = {
    "khan.co.kr": "경향신문",
    "kmib.co.kr": "국민일보",
    "donga.com": "동아일보",
    "seoul.co.kr": "서울신문",
    "segye.com": "세계일보",
    "chosun.com": "조선일보",
    "joongang.co.kr": "중앙일보",
    "hani.co.kr": "한겨레",
    "hankookilbo.com": "한국일보",
    "mk.co.kr": "매일경제",
    "sedaily.com": "서울경제",
    "hankyung.com": "한국경제",
    "fnnews.com": "파이낸셜뉴스",
    "edaily.co.kr": "이데일리",
    "mt.co.kr": "머니투데이",
    "asiae.co.kr": "아시아경제",
    "heraldcorp.com": "헤럴드경제",
    "etnews.com": "전자신문",
    "yna.co.kr": "연합뉴스",
    "newsis.com": "뉴시스",
    "news1.kr": "뉴스1",
    "ytn.co.kr": "YTN",
    "kbs.co.kr": "KBS",
    "imnews.imbc.com": "MBC",
    "news.sbs.co.kr": "SBS",
    "electimes.com": "전기신문",
    "energy-news.co.kr": "에너지신문",
    "ekn.kr": "에너지경제",
    "todayenergy.kr": "투데이에너지",
    "e2news.com": "이투뉴스",
}

_TAG_RE = re.compile(r"<[^>]+>")


class CollectorError(RuntimeError):
    """수집 자체가 불가능한 상태 (키 누락, 인증 실패 등)."""


def _clean(text: str) -> str:
    """API가 돌려주는 <b> 태그와 HTML 엔티티를 제거한다."""
    return html.unescape(_TAG_RE.sub("", text or "")).strip()


def _press_name(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    for domain, name in PRESS_BY_DOMAIN.items():
        if host == domain or host.endswith("." + domain):
            return name
    return host or "출처 미상"


def _parse_pubdate(raw: str) -> datetime | None:
    """'Mon, 30 Aug 2026 07:12:00 +0900' → KST datetime."""
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KST)
        return dt.astimezone(KST)
    except Exception:
        return None


def _fetch_page(keyword: str, start: int, client_id: str, client_secret: str) -> list[dict]:
    resp = requests.get(
        API_URL,
        params={"query": keyword, "display": 100, "start": start, "sort": "date"},
        headers={
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        },
        timeout=15,
    )
    if resp.status_code == 401:
        raise CollectorError("네이버 API 인증 실패 (401) — Client ID/Secret을 확인하세요.")
    if resp.status_code == 429:
        raise CollectorError("네이버 API 일일 호출 한도(25,000회) 초과.")
    resp.raise_for_status()
    return resp.json().get("items", [])


def collect(keyword: str, max_articles: int = 30, hours_back: int = 0) -> dict:
    """
    keyword 관련 기사를 수집한다.

    hours_back=0 이면 오늘 00:00(KST) 이후 발행분만.
    hours_back=N 이면 지금으로부터 N시간 이내 발행분만.

    반환: {"keyword", "collected_at", "cutoff", "articles", "stats"}
    """
    client_id = os.environ.get("NAVER_CLIENT_ID", "").strip()
    client_secret = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise CollectorError(
            "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 비어 있습니다."
        )

    now = datetime.now(KST)
    if hours_back > 0:
        cutoff = now - timedelta(hours=hours_back)
    else:
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)

    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    articles: list[dict] = []

    total_seen = 0
    dropped_old = 0
    dropped_dup = 0

    for start in (1, 101, 201, 301, 401):
        try:
            items = _fetch_page(keyword, start, client_id, client_secret)
        except CollectorError:
            raise
        except Exception as exc:
            print(f"    [경고] {start}번째 페이지 조회 실패: {exc}")
            break

        if not items:
            break

        stop = False
        for item in items:
            total_seen += 1
            published = _parse_pubdate(item.get("pubDate", ""))

            # 발행 시각을 못 읽으면 신뢰할 수 없으므로 버린다.
            if published is None:
                dropped_old += 1
                continue

            if published < cutoff:
                # sort=date라 이후 항목은 전부 더 오래됨 → 조기 종료
                dropped_old += 1
                stop = True
                continue

            source_url = (item.get("originallink") or item.get("link") or "").strip()
            naver_url = (item.get("link") or "").strip()
            title = _clean(item.get("title", ""))

            if not title or not source_url:
                continue
            if source_url in seen_urls or title in seen_titles:
                dropped_dup += 1
                continue

            seen_urls.add(source_url)
            seen_titles.add(title)
            articles.append(
                {
                    "title": title,
                    "summary": _clean(item.get("description", "")),
                    "press": _press_name(source_url),
                    "source_url": source_url,
                    "naver_url": naver_url,
                    "published": published,
                    "published_str": published.strftime("%m/%d %H:%M"),
                }
            )

        if stop or len(items) < 100:
            break
        time.sleep(0.2)

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
