"""
보관·전달용 PDF 조간지 생성 (reportlab).

메일 본문 HTML이 주(主)이고, PDF는 사내 회람·보관용 사본이다.
브라우저를 쓰지 않으므로 Playwright/Xvfb 의존성이 전혀 없다.
"""

from __future__ import annotations

import html
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageTemplate,
    Paragraph,
    Spacer,
)

BASE_DIR = Path(__file__).resolve().parent.parent
FONTS_DIR = BASE_DIR / "fonts"
OUTPUT_DIR = BASE_DIR / "output"

ACCENT = colors.HexColor("#1b3a6b")
MUTED = colors.HexColor("#6b7280")
LINE = colors.HexColor("#e5e7eb")

pdfmetrics.registerFont(TTFont("Nanum", str(FONTS_DIR / "NanumGothic.ttf")))
pdfmetrics.registerFont(TTFont("NanumBd", str(FONTS_DIR / "NanumGothicBold.ttf")))


def _style(name: str, **kw) -> ParagraphStyle:
    base = dict(fontName="Nanum", fontSize=10, leading=15, alignment=TA_LEFT)
    base.update(kw)
    return ParagraphStyle(name, **base)


S_TITLE = _style("t", fontName="NanumBd", fontSize=24, leading=30, textColor=ACCENT)
S_SUB = _style("s", fontSize=10, leading=15, textColor=MUTED)
S_HEAD = _style("h", fontName="NanumBd", fontSize=12, leading=18, spaceAfter=3)
S_META = _style("m", fontSize=8.5, leading=13, textColor=MUTED)
S_BODY = _style("b", fontSize=9.5, leading=15, textColor=colors.HexColor("#374151"))


def _esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def _decorate(canvas, doc, keyword: str, stamp: str):
    canvas.saveState()
    canvas.setFont("Nanum", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 12 * mm, f"{keyword} 주요 언론 보도 · {stamp}")
    canvas.drawRightString(190 * mm, 12 * mm, f"{doc.page}")
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(20 * mm, 15 * mm, 190 * mm, 15 * mm)
    canvas.restoreState()


def generate(data: dict, output_path: str | None = None) -> str:
    OUTPUT_DIR.mkdir(exist_ok=True)
    collected = data["collected_at"]
    stamp = collected.strftime("%Y-%m-%d %H:%M")

    if not output_path:
        fname = f"{data['keyword']}_언론보도_{collected.strftime('%Y%m%d')}.pdf"
        output_path = str(OUTPUT_DIR / fname)

    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"{data['keyword']} 주요 언론 보도 {collected:%Y-%m-%d}",
        author="morning-news",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates(
        [
            PageTemplate(
                id="pg",
                frames=[frame],
                onPage=lambda c, d: _decorate(c, d, data["keyword"], stamp),
            )
        ]
    )

    stats = data["stats"]
    story: list = [
        Paragraph(_esc(data["keyword"]), S_TITLE),
        Spacer(1, 4),
        Paragraph(
            f"{collected:%Y년 %m월 %d일} 주요 언론 보도 &nbsp;|&nbsp; "
            f"총 {stats['kept']}건 · {stats['press_count']}개 매체",
            S_SUB,
        ),
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=2, color=ACCENT, spaceAfter=10),
        Paragraph(
            f"수집 기준: {data['cutoff']:%m월 %d일 %H:%M} 이후 발행분 · "
            f"검색 {stats['total_seen']}건 중 시각 미달 {stats['dropped_old']}건, "
            f"중복 {stats['dropped_dup']}건 제외 · 출처: 네이버 검색 오픈API",
            S_META,
        ),
        Spacer(1, 14),
    ]

    if not data["articles"]:
        story.append(Paragraph("오늘 발행된 관련 기사가 없습니다.", S_BODY))
    else:
        for i, art in enumerate(data["articles"], 1):
            summary = _esc(art["summary"])
            if len(summary) > 260:
                summary = summary[:260] + "…"
            story += [
                Paragraph(
                    f'<a href="{_esc(art["source_url"])}" color="#111827">'
                    f"{i}. {_esc(art['title'])}</a>",
                    S_HEAD,
                ),
                Paragraph(
                    f"{_esc(art['press'])} &nbsp;·&nbsp; {_esc(art['published_str'])} "
                    f'&nbsp;·&nbsp; <a href="{_esc(art["source_url"])}" color="#1b3a6b">원문</a>',
                    S_META,
                ),
                Spacer(1, 3),
                Paragraph(summary, S_BODY),
                Spacer(1, 6),
                HRFlowable(width="100%", thickness=0.5, color=LINE, spaceAfter=10),
            ]

    doc.build(story)
    return output_path
