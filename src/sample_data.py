"""--dry-run 전용 샘플 데이터 (레이아웃 확인용, 실제 기사 아님)."""

from datetime import datetime, timedelta

from src.collector import KST

_ROWS = [
    ("한전, 3분기 영업이익 흑자 전환… 연료비 하락 영향", "연합뉴스", "https://www.yna.co.kr/view/AKR00000000", 1),
    ("전력망 특별법 후속 조치 논의 본격화", "전기신문", "https://www.electimes.com/news/000000", 2),
    ("한국전력, 해외 신재생 사업 지분 추가 확보", "매일경제", "https://www.mk.co.kr/news/000000", 3),
    ("정부, 4분기 전기요금 동결 가닥", "한국경제", "https://www.hankyung.com/article/000000", 5),
    ("한전 채권 발행 한도 상향안 국회 계류", "이데일리", "https://www.edaily.co.kr/news/000000", 7),
]


def make_sample(keyword: str) -> dict:
    now = datetime.now(KST)
    cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    articles = []
    for title, press, url, hours in _ROWS:
        pub = now - timedelta(hours=hours)
        articles.append({
            "title": title,
            "summary": "샘플 요약문입니다. 실제 실행 시에는 네이버 검색 오픈API가 돌려주는 "
                       "기사 요약이 이 자리에 들어갑니다. 레이아웃 확인용 더미 텍스트입니다.",
            "press": press,
            "source_url": url,
            "naver_url": url,
            "published": pub,
            "published_str": pub.strftime("%m/%d %H:%M"),
        })
    by_press = {}
    for a in articles:
        by_press[a["press"]] = by_press.get(a["press"], 0) + 1
    return {
        "keyword": keyword,
        "collected_at": now,
        "cutoff": cutoff,
        "articles": articles,
        "stats": {"total_seen": 48, "dropped_old": 31, "dropped_dup": 12,
                  "kept": len(articles), "press_count": len(by_press), "by_press": by_press},
    }
