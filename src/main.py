"""
Main entry point for 공기업 주요 언론 보도 PDF generator.

Usage:
    python -m src.main --keyword "한국전력공사"
    python -m src.main --keyword "한국전력공사" --no-screenshot
    python -m src.main --keyword "한국전력공사" --output /path/to/out.pdf
"""

import argparse
import datetime
import os
import sys
import tempfile
import time
from pathlib import Path

from src.config import COMPANY_STOCK_MAP, NEWSPAPERS, NEWS_COUNT, OUTPUT_DIR
from src.scrapers.market_data import collect_market_data
from src.scrapers.news_scraper import search_naver_news, enrich_articles
from src.scrapers.newspaper_capture import capture_all_newspapers
from src.pdf_generator import generate_pdf


def run(keyword: str, capture_screenshots: bool = True, output_path: str = None) -> str:
    print(f"\n{'='*60}")
    print(f"  공기업 주요 언론 보도 생성 시작")
    print(f"  키워드: {keyword}")
    print(f"  일시: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    # ── 1. Market data ─────────────────────────────────────────────────────────
    print("[1/4] 시장 데이터 수집 중...")
    company_info = COMPANY_STOCK_MAP.get(keyword, {"krx": None, "nyse": None, "name": keyword})
    try:
        market_rows = collect_market_data(keyword, company_info)
        print(f"      → {len(market_rows)}개 항목 수집 완료")
    except Exception as e:
        print(f"      [경고] 시장 데이터 수집 오류: {e}")
        market_rows = []

    # ── 2. News articles ───────────────────────────────────────────────────────
    print(f"[2/4] 뉴스 기사 검색 중 (키워드: {keyword})...")
    try:
        articles = search_naver_news(keyword, count=NEWS_COUNT)
        print(f"      → {len(articles)}개 기사 발견")
        print("      → 기사 본문 수집 중...")
        articles = enrich_articles(articles)
        print(f"      → 본문 수집 완료")
    except Exception as e:
        print(f"      [경고] 뉴스 수집 오류: {e}")
        articles = []

    # ── 3. Newspaper screenshots ────────────────────────────────────────────────
    newspaper_results = []
    if capture_screenshots:
        print("[3/4] 신문사 헤드라인 캡처 중 (12개)...")
        tmp_dir = str(Path(OUTPUT_DIR) / "screenshots" / datetime.date.today().strftime("%Y%m%d"))
        try:
            newspaper_results = capture_all_newspapers(NEWSPAPERS, tmp_dir)
            success_count = sum(1 for r in newspaper_results if r["success"])
            print(f"      → {success_count}/{len(NEWSPAPERS)}개 캡처 완료")
        except Exception as e:
            print(f"      [경고] 신문 캡처 오류: {e}")
            newspaper_results = [{"name": p["name"], "url": p["url"], "success": False, "screenshot_path": None}
                                  for p in NEWSPAPERS]
    else:
        print("[3/4] 신문 캡처 건너뜀 (--no-screenshot 옵션)")
        newspaper_results = [{"name": p["name"], "url": p["url"], "success": False, "screenshot_path": None}
                              for p in NEWSPAPERS]

    # ── 4. PDF generation ──────────────────────────────────────────────────────
    print("[4/4] PDF 생성 중...")
    try:
        out_path = generate_pdf(
            keyword=keyword,
            market_rows=market_rows,
            articles=articles,
            newspaper_results=newspaper_results,
            output_path=output_path,
        )
        print(f"\n{'='*60}")
        print(f"  ✓ PDF 생성 완료!")
        print(f"  경로: {out_path}")
        print(f"{'='*60}\n")
        return out_path
    except Exception as e:
        print(f"  [오류] PDF 생성 실패: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="공기업 주요 언론 보도 PDF 조간지 생성기"
    )
    parser.add_argument(
        "--keyword", "-k",
        required=True,
        help="검색 키워드 (예: 한국전력공사)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="출력 PDF 파일 경로 (기본: output/ 디렉토리 자동 생성)",
    )
    parser.add_argument(
        "--no-screenshot",
        action="store_true",
        help="신문사 헤드라인 스크린샷 생략 (빠른 테스트용)",
    )
    args = parser.parse_args()

    out = run(
        keyword=args.keyword,
        capture_screenshots=not args.no_screenshot,
        output_path=args.output,
    )
    print(f"생성된 파일: {out}")


if __name__ == "__main__":
    main()
