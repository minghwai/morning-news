"""
공기업 주요 언론 보도 조간지 — 생성 및 발송.

Usage:
  python -m src.main --keyword "한국전력공사"
  python -m src.main --keyword "한국전력공사" --no-mail        # 파일만 생성
  python -m src.main --keyword "한국전력공사" --no-pdf         # 메일 본문만
  python -m src.main --keyword "한국전력공사" --hours-back 24  # 최근 24시간
  python -m src.main --keyword "한국전력공사" --no-archive     # 아카이브 저장 생략
  python -m src.main --keyword "한국전력공사" --dry-run        # 샘플 데이터로 레이아웃 확인
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from src import render_html
from src.collector import CollectorError

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"


def run(
    keyword: str,
    make_pdf: bool = True,
    send_mail: bool = True,
    archive_it: bool = True,
    hours_back: int = 0,
    max_articles: int = 30,
    allow_empty: bool = False,
    dry_run: bool = False,
    source: str = "naver",
) -> dict:
    print(f"\n{'=' * 60}")
    print(f"  공기업 주요 언론 보도 — {keyword}")
    print(f"{'=' * 60}\n")

    print("[1/5] 기사 수집 중...")
    if dry_run:
        from src.sample_data import make_sample

        data = make_sample(keyword)
        print(f"      → 샘플 데이터 {data['stats']['kept']}건")
    else:
        if source == "rss":
            from src.collector_rss import collect as collect_fn
            print("      → 수집원: 구글 뉴스 RSS (API 키 불필요)")
        else:
            from src.collector import collect as collect_fn
            print("      → 수집원: 네이버 검색 오픈API")
        data = collect_fn(keyword, max_articles=max_articles, hours_back=hours_back)
        st = data["stats"]
        print(
            f"      → 검색 {st['total_seen']}건 · 시각 미달 {st['dropped_old']}건 "
            f"· 중복 {st['dropped_dup']}건 제외 → 최종 {st['kept']}건 ({st['press_count']}개 매체)"
        )

    # 조용한 실패 방지: 기사가 0건이면 빈 메일을 보내는 대신 실패로 끝낸다.
    if not data["articles"] and not allow_empty:
        raise SystemExit(
            "\n[중단] 오늘 발행된 기사가 0건입니다. 빈 조간지를 발송하지 않고 종료합니다.\n"
            "       키워드가 맞는지, --hours-back 24 로 범위를 넓힐지 확인하세요.\n"
            "       빈 상태로도 발송하려면 --allow-empty 를 붙이세요."
        )

    print("\n[2/5] 아카이브 갱신 중...")
    if archive_it:
        from src import archive, site_builder

        archive.save_day(data)
        archive.build_index()
        site_builder.build()
    else:
        print("      → 건너뜀 (--no-archive)")

    print("\n[3/5] 메일 본문 생성 중...")
    html_body = render_html.render(data)
    text_body = render_html.render_text(data)
    OUTPUT_DIR.mkdir(exist_ok=True)
    preview = OUTPUT_DIR / f"preview_{data['collected_at']:%Y%m%d}.html"
    preview.write_text(html_body, encoding="utf-8")
    print(f"      → 미리보기: {preview}")

    print("\n[4/5] PDF 생성 중...")
    attachments: list[str] = []
    if make_pdf:
        from src import pdf_report

        pdf_path = pdf_report.generate(data)
        size_kb = Path(pdf_path).stat().st_size // 1024
        attachments.append(pdf_path)
        print(f"      → {pdf_path} ({size_kb} KB)")
    else:
        print("      → 건너뜀 (--no-pdf)")

    print("\n[5/5] 메일 발송 중...")
    if send_mail:
        from src import mailer

        subject = (
            f"[{keyword}] 주요 언론 보도 "
            f"{data['collected_at']:%Y년 %m월 %d일} ({data['stats']['kept']}건)"
        )
        mailer.send(subject, html_body, text_body, attachments)
    else:
        print("      → 건너뜀 (--no-mail)")

    print(f"\n{'=' * 60}")
    print("  완료")
    print(f"{'=' * 60}\n")
    return data


def main():
    ap = argparse.ArgumentParser(description="공기업 주요 언론 보도 조간지")
    ap.add_argument("--keyword", "-k", required=True, help="검색 키워드 (예: 한국전력공사)")
    ap.add_argument("--hours-back", type=int, default=0,
                    help="0이면 오늘 00:00 이후, N이면 최근 N시간")
    ap.add_argument("--max-articles", type=int, default=30, help="최대 기사 수")
    ap.add_argument("--no-pdf", action="store_true", help="PDF 첨부 생략")
    ap.add_argument("--no-mail", action="store_true", help="메일 발송 생략")
    ap.add_argument("--no-archive", action="store_true", help="아카이브/사이트 갱신 생략")
    ap.add_argument("--allow-empty", action="store_true", help="기사 0건이어도 발송")
    ap.add_argument("--source", choices=["naver", "rss"],
                    default=os.environ.get("NEWS_SOURCE", "naver"),
                    help="naver=네이버 오픈API(키 필요), rss=구글 뉴스 RSS(키 불필요)")
    ap.add_argument("--dry-run", action="store_true", help="샘플 데이터로 레이아웃만 확인")
    args = ap.parse_args()

    try:
        run(
            keyword=args.keyword,
            make_pdf=not args.no_pdf,
            send_mail=not args.no_mail,
            archive_it=not args.no_archive,
            hours_back=args.hours_back,
            max_articles=args.max_articles,
            allow_empty=args.allow_empty,
            dry_run=args.dry_run,
            source=args.source,
        )
    except CollectorError as exc:
        print(f"\n[오류] {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
