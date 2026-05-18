"""
공기업 주요 언론 보도 PDF 생성기

Usage:
  python -m src.main --keyword "한국전력공사"
  python -m src.main --keyword "한국전력공사" --no-screenshot
  python -m src.main --keyword "한국전력공사" --output /path/to/out.pdf
  python -m src.main --keyword "한국전력공사" --demo   # 레이아웃 테스트용 (가짜 데이터)
"""

import argparse
import datetime
import sys
from pathlib import Path

from src.config import COMPANY_STOCK_MAP, NEWSPAPERS, NEWS_COUNT, OUTPUT_DIR
from src.scrapers.market_data import collect_market_data
from src.scrapers.news_scraper import search_naver_news, enrich_articles
from src.scrapers.newspaper_capture import capture_all_newspapers
from src.pdf_generator import generate_pdf


def run(
    keyword: str,
    capture_screenshots: bool = True,
    output_path: str = None,
    demo: bool = False,
) -> str:
    today = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*62}")
    print(f"  공기업 주요 언론 보도 생성 {'[DEMO 모드]' if demo else ''}")
    print(f"  키워드: {keyword}  |  일시: {today}")
    print(f"{'='*62}\n")

    company_info = COMPANY_STOCK_MAP.get(keyword, {"krx": None, "nyse": None, "name": keyword})

    # ── 1. Market data ──────────────────────────────────────────────────────
    print("[1/4] 시장 데이터 수집 중...")
    if demo:
        from src.demo_data import DEMO_MARKET_ROWS
        market_rows = DEMO_MARKET_ROWS
        print(f"      → DEMO 데이터 사용 ({len(market_rows)}개)")
    else:
        try:
            market_rows = collect_market_data(keyword, company_info)
            ok = sum(1 for r in market_rows if r.get("price") is not None)
            print(f"      → {ok}/{len(market_rows)}개 항목 수집 완료")
        except Exception as e:
            print(f"      [경고] 시장 데이터 수집 실패: {e}")
            market_rows = []

    # ── 2. News articles ────────────────────────────────────────────────────
    print(f"\n[2/4] 뉴스 기사 수집 중 (키워드: {keyword})...")
    if demo:
        from src.demo_data import DEMO_ARTICLES
        articles = DEMO_ARTICLES
        print(f"      → DEMO 데이터 사용 ({len(articles)}개 기사)")
    else:
        try:
            articles = search_naver_news(keyword, count=NEWS_COUNT)
            if not articles:
                print("      [경고] 기사를 찾지 못했습니다. 인터넷 연결을 확인하세요.")
                articles = []
            else:
                print(f"      → {len(articles)}개 기사 발견, 전문 수집 중...")
                articles = enrich_articles(articles)
        except Exception as e:
            print(f"      [경고] 뉴스 수집 실패: {e}")
            articles = []

    # ── 3. Newspaper screenshots ─────────────────────────────────────────────
    print(f"\n[3/4] 신문사 헤드라인 캡처 중...")
    if not capture_screenshots:
        print("      → 건너뜀 (--no-screenshot)")
        newspaper_results = [
            {"name": p["name"], "url": p["url"], "success": False, "screenshot_path": None}
            for p in NEWSPAPERS
        ]
    elif demo:
        from src.demo_data import get_demo_newspaper_results
        newspaper_results = get_demo_newspaper_results()
        print("      → DEMO 모드: 스크린샷 생략")
    else:
        import os
        screenshot_dir = str(
            Path(OUTPUT_DIR) / "screenshots" / datetime.date.today().strftime("%Y%m%d")
        )
        try:
            newspaper_results = capture_all_newspapers(NEWSPAPERS, screenshot_dir)
        except Exception as e:
            print(f"      [경고] 신문 캡처 실패: {e}")
            newspaper_results = [
                {"name": p["name"], "url": p["url"], "success": False, "screenshot_path": None}
                for p in NEWSPAPERS
            ]

    # ── 4. Generate PDF ──────────────────────────────────────────────────────
    print(f"\n[4/4] PDF 생성 중...")
    try:
        out = generate_pdf(
            keyword=keyword,
            market_rows=market_rows,
            articles=articles,
            newspaper_results=newspaper_results,
            output_path=output_path,
        )
        size_kb = Path(out).stat().st_size // 1024
        print(f"\n{'='*62}")
        print(f"  ✓ 완료!  {out}  ({size_kb} KB)")
        print(f"{'='*62}\n")
        return out
    except Exception as e:
        print(f"  [오류] PDF 생성 실패: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="공기업 주요 언론 보도 PDF 생성기")
    parser.add_argument("--keyword", "-k", required=True, help="검색 키워드 (예: 한국전력공사)")
    parser.add_argument("--output", "-o", default=None, help="출력 PDF 경로")
    parser.add_argument("--no-screenshot", action="store_true", help="신문 스크린샷 생략")
    parser.add_argument("--demo", action="store_true",
                        help="레이아웃 테스트용 DEMO 모드 (실제 데이터 수집 안 함)")
    args = parser.parse_args()

    run(
        keyword=args.keyword,
        capture_screenshots=not args.no_screenshot,
        output_path=args.output,
        demo=args.demo,
    )


if __name__ == "__main__":
    main()
