"""
일별 아카이브 저장소.

저장소(repo) 자체를 데이터베이스로 쓴다.
  data/2026-08-30.json   ← 하루치 원본 (Actions가 매일 커밋)
  docs/archive.json      ← 전체 병합본 (정적 사이트가 읽는 파일)

DB도 서버도 필요 없고, git 히스토리가 곧 변경 이력이 된다.

저작권 유의: 기사 전문은 저장하지 않는다. 제목·링크·API가 제공하는
짧은 요약(200자 이내)만 보관한다.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"

SUMMARY_LIMIT = 200


def _slim(art: dict) -> dict:
    """저장용으로 필드를 줄인다."""
    summary = (art.get("summary") or "")[:SUMMARY_LIMIT]
    return {
        "title": art["title"],
        "press": art["press"],
        "url": art["source_url"],
        "naver": art.get("naver_url", ""),
        "at": art["published"].isoformat(timespec="minutes"),
        "summary": summary,
    }


def save_day(data: dict) -> Path:
    """하루치 결과를 data/YYYY-MM-DD.json 으로 저장한다. 같은 날 재실행 시 병합."""
    DATA_DIR.mkdir(exist_ok=True)
    day = data["collected_at"].strftime("%Y-%m-%d")
    path = DATA_DIR / f"{day}.json"

    articles = [_slim(a) for a in data["articles"]]

    if path.exists():
        try:
            prev = json.loads(path.read_text(encoding="utf-8"))
            seen = {a["url"] for a in articles}
            for old in prev.get("articles", []):
                if old.get("url") not in seen:
                    articles.append(old)
        except Exception as exc:
            print(f"    [경고] 기존 아카이브 병합 실패, 덮어씁니다: {exc}")

    articles.sort(key=lambda a: a["at"], reverse=True)

    payload = {
        "date": day,
        "keyword": data["keyword"],
        "updated_at": data["collected_at"].isoformat(timespec="seconds"),
        "count": len(articles),
        "articles": articles,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"      → 아카이브 저장: {path.name} ({len(articles)}건)")
    return path


def build_index() -> dict:
    """data/ 전체를 읽어 docs/archive.json 으로 병합한다."""
    DOCS_DIR.mkdir(exist_ok=True)
    days: list[dict] = []

    for path in sorted(DATA_DIR.glob("*.json"), reverse=True):
        try:
            days.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            print(f"    [경고] {path.name} 읽기 실패: {exc}")

    total = sum(d.get("count", 0) for d in days)
    presses: dict[str, int] = {}
    for d in days:
        for a in d.get("articles", []):
            presses[a["press"]] = presses.get(a["press"], 0) + 1

    index = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "day_count": len(days),
        "article_count": total,
        "keywords": sorted({d.get("keyword", "") for d in days if d.get("keyword")}),
        "presses": dict(sorted(presses.items(), key=lambda kv: -kv[1])),
        "days": days,
    }

    out = DOCS_DIR / "archive.json"
    out.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    size_kb = out.stat().st_size // 1024
    print(f"      → 색인 생성: {len(days)}일 · {total}건 · {size_kb} KB")
    return index
