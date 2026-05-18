"""
APScheduler-based daily scheduler.
Runs the PDF generator every day at 08:00 (KST/local time).

Usage:
    python -m src.scheduler --keyword "한국전력공사"
    python -m src.scheduler --keyword "한국전력공사" --hour 8 --minute 0
"""

import argparse
import logging
import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from src.config import SCHEDULE_HOUR, SCHEDULE_MINUTE
from src.main import run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

KST = pytz.timezone("Asia/Seoul")


def scheduled_job(keyword: str, capture_screenshots: bool = True):
    logger.info(f"스케줄 작업 시작: {keyword}")
    try:
        out = run(keyword=keyword, capture_screenshots=capture_screenshots)
        logger.info(f"완료: {out}")
    except Exception as e:
        logger.error(f"작업 실패: {e}", exc_info=True)


def start_scheduler(keyword: str, hour: int = SCHEDULE_HOUR, minute: int = SCHEDULE_MINUTE,
                    capture_screenshots: bool = True):
    scheduler = BlockingScheduler(timezone=KST)

    trigger = CronTrigger(hour=hour, minute=minute, timezone=KST)
    scheduler.add_job(
        scheduled_job,
        trigger=trigger,
        args=[keyword, capture_screenshots],
        id="morning_news",
        name=f"Morning News PDF — {keyword}",
        misfire_grace_time=600,
        replace_existing=True,
    )

    next_run = scheduler.get_jobs()[0].next_run_time
    logger.info(f"스케줄러 시작: 매일 {hour:02d}:{minute:02d} (KST)")
    logger.info(f"다음 실행 예정: {next_run}")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")
        scheduler.shutdown()


def main():
    parser = argparse.ArgumentParser(description="공기업 주요 언론 보도 자동 스케줄러")
    parser.add_argument("--keyword", "-k", required=True, help="검색 키워드")
    parser.add_argument("--hour",   type=int, default=SCHEDULE_HOUR,   help="실행 시각 (시)")
    parser.add_argument("--minute", type=int, default=SCHEDULE_MINUTE, help="실행 시각 (분)")
    parser.add_argument("--no-screenshot", action="store_true", help="스크린샷 생략")
    parser.add_argument("--run-now", action="store_true", help="스케줄 없이 즉시 실행")
    args = parser.parse_args()

    if args.run_now:
        scheduled_job(args.keyword, not args.no_screenshot)
        return

    start_scheduler(
        keyword=args.keyword,
        hour=args.hour,
        minute=args.minute,
        capture_screenshots=not args.no_screenshot,
    )


if __name__ == "__main__":
    main()
