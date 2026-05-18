"""
PDF generator for 공기업 주요 언론 보도.
Sections:
  1. Cover page  — market data table
  2. TOC page    — 주요 언론 보도 목차 (20 articles)
  3. Body pages  — article details with links
  4. Headline pages — 12 newspaper screenshots (가나다 순)
"""

import os
import datetime
from pathlib import Path
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
    KeepTogether,
    HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from src.config import FONT_REGULAR, FONT_BOLD, OUTPUT_DIR

# ─── Font registration ────────────────────────────────────────────────────────
pdfmetrics.registerFont(TTFont("Nanum", FONT_REGULAR))
pdfmetrics.registerFont(TTFont("NanumBold", FONT_BOLD))

# ─── Color palette ────────────────────────────────────────────────────────────
C_NAVY      = colors.HexColor("#1B3A6B")
C_BLUE      = colors.HexColor("#2563EB")
C_LIGHT     = colors.HexColor("#EFF6FF")
C_HEADER_BG = colors.HexColor("#1E40AF")
C_ROW_ALT   = colors.HexColor("#F8FAFF")
C_BORDER    = colors.HexColor("#CBD5E1")
C_WHITE     = colors.white
C_GRAY      = colors.HexColor("#64748B")
C_DARK      = colors.HexColor("#1E293B")
C_RED       = colors.HexColor("#DC2626")
C_GREEN     = colors.HexColor("#16A34A")
C_GOLD      = colors.HexColor("#D97706")

W, H = A4
MARGIN = 18 * mm


def _style(name, **kwargs) -> ParagraphStyle:
    base = {
        "fontName": "Nanum",
        "fontSize": 9,
        "leading": 13,
        "textColor": C_DARK,
    }
    base.update(kwargs)
    return ParagraphStyle(name, **base)


# ─── Shared styles ────────────────────────────────────────────────────────────
S_TITLE     = _style("title",     fontName="NanumBold", fontSize=20, textColor=C_NAVY, leading=26, spaceAfter=4)
S_SUBTITLE  = _style("subtitle",  fontName="NanumBold", fontSize=13, textColor=C_BLUE, leading=17, spaceAfter=3)
S_BODY      = _style("body",      fontSize=9,  leading=14)
S_SMALL     = _style("small",     fontSize=8,  textColor=C_GRAY, leading=11)
S_CENTER    = _style("center",    fontSize=9,  alignment=TA_CENTER)
S_BOLD      = _style("bold",      fontName="NanumBold", fontSize=9)
S_LINK      = _style("link",      fontSize=8,  textColor=C_BLUE)
S_H1        = _style("h1",        fontName="NanumBold", fontSize=14, textColor=C_NAVY, leading=19, spaceBefore=6, spaceAfter=4)
S_H2        = _style("h2",        fontName="NanumBold", fontSize=11, textColor=C_BLUE, leading=15, spaceBefore=4, spaceAfter=3)
S_TOC_ITEM  = _style("toc_item",  fontSize=9,  leading=14, leftIndent=6)
S_TOC_SRC   = _style("toc_src",   fontName="NanumBold", fontSize=8, textColor=C_BLUE)
S_ART_SRC   = _style("art_src",   fontName="NanumBold", fontSize=8, textColor=C_WHITE)
S_ART_TITLE = _style("art_title", fontName="NanumBold", fontSize=11, textColor=C_NAVY, leading=16, spaceAfter=2)
S_ART_DATE  = _style("art_date",  fontSize=8,  textColor=C_GRAY)
S_ART_BODY  = _style("art_body",  fontSize=9,  leading=14, spaceAfter=3)

# ─── Page templates ───────────────────────────────────────────────────────────

def _make_doc(output_path: str) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN + 8 * mm,
        bottomMargin=MARGIN,
        title="공기업 주요 언론 보도",
    )
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="main",
    )
    doc.addPageTemplates([
        PageTemplate(id="main", frames=[frame], onPage=_draw_page_border),
    ])
    return doc


def _draw_page_border(canvas, doc):
    canvas.saveState()
    # Top decorative bar
    canvas.setFillColor(C_NAVY)
    canvas.rect(0, H - 12 * mm, W, 12 * mm, fill=1, stroke=0)
    # Bottom page number
    canvas.setFillColor(C_GRAY)
    canvas.setFont("Nanum", 7)
    canvas.drawCentredString(W / 2, 8 * mm, f"- {doc.page} -")
    # Footer text
    canvas.setFillColor(C_GRAY)
    canvas.setFont("Nanum", 7)
    canvas.drawString(MARGIN, 8 * mm, "공기업 주요 언론 보도")
    canvas.drawRightString(W - MARGIN, 8 * mm,
                           datetime.date.today().strftime("%Y년 %m월 %d일"))
    canvas.restoreState()


# ─── Helper builders ──────────────────────────────────────────────────────────

def _colored_cell(text: str, style: ParagraphStyle, bg: object) -> list:
    return [Paragraph(text, style)]


def _fmt_num(val, decimals=2, unit="") -> str:
    if val is None:
        return "N/A"
    try:
        if decimals == 0:
            return f"{val:,.0f}{unit}"
        return f"{val:,.{decimals}f}{unit}"
    except Exception:
        return str(val)


def _fmt_change(change, pct, decimals=2, unit="") -> tuple[str, object]:
    """Return (formatted string, color)."""
    if change is None:
        return "N/A", C_GRAY
    try:
        sign = "▲" if change >= 0 else "▼"
        color = C_RED if change >= 0 else C_BLUE
        s = f"{sign}{abs(change):,.{decimals}f}{unit} ({abs(pct):.2f}%)"
        return s, color
    except Exception:
        return "N/A", C_GRAY


def _fmt_yoy(yoy_change, yoy_pct, decimals=2, unit="") -> str:
    if yoy_change is None:
        return "N/A"
    try:
        sign = "▲" if yoy_change >= 0 else "▼"
        return f"{sign}{abs(yoy_change):,.{decimals}f}{unit} ({abs(yoy_pct):.2f}%)"
    except Exception:
        return "N/A"


# ─── Section builders ─────────────────────────────────────────────────────────

def build_cover_section(keyword: str, market_rows: list[dict], report_date: str) -> list:
    """Page 1: Header + market data table."""
    story = []

    # ── Main title ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("공기업 주요 언론 보도", S_TITLE))
    story.append(Paragraph(f"{keyword} | {report_date}", S_SUBTITLE))
    story.append(HRFlowable(width="100%", thickness=2, color=C_BLUE, spaceAfter=6))

    # ── Market data table ──────────────────────────────────────────────────────
    story.append(Paragraph("■ 주요 시장 지표", S_BOLD))
    story.append(Spacer(1, 2 * mm))

    col_widths = [45 * mm, 28 * mm, 38 * mm, 42 * mm, 42 * mm]
    headers = ["구분", "기준일", "현재가", "전일대비", "전년대비"]

    tbl_data = [headers]

    for row in market_rows:
        if not row:
            continue
        label = row.get("label", "")
        date  = row.get("date", "-") or "-"
        unit  = row.get("unit", "")
        price = row.get("price")

        # Format price
        if price is None:
            price_str = "N/A"
        elif "환율" in label or "SMP" in label or "유가" in label:
            price_str = _fmt_num(price, 2, f" {unit}" if unit else "")
        elif price > 1000:
            price_str = _fmt_num(price, 0, f" {unit}" if unit else "")
        else:
            price_str = _fmt_num(price, 2, f" {unit}" if unit else "")

        # Change
        change_str, _ = _fmt_change(
            row.get("change"), row.get("change_pct"),
            0 if price and price > 1000 else 2,
        )

        # YoY
        yoy_str = _fmt_yoy(
            row.get("yoy_change"), row.get("yoy_pct"),
            0 if price and price > 1000 else 2,
        )

        tbl_data.append([label, date, price_str, change_str, yoy_str])

    col_styles = [
        ("BACKGROUND",  (0, 0), (-1, 0),  C_HEADER_BG),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  C_WHITE),
        ("FONTNAME",    (0, 0), (-1, 0),  "NanumBold"),
        ("FONTNAME",    (0, 1), (-1, -1), "Nanum"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("ALIGN",       (0, 1), (0, -1),  "LEFT"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",        (0, 0), (-1, -1), 0.5, C_BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_ROW_ALT]),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]

    tbl = Table(tbl_data, colWidths=col_widths)
    tbl.setStyle(TableStyle(col_styles))
    story.append(tbl)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f"※ 기준 시각: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} | "
        "환율: 조회 시점 기준 | SMP: 한국전력거래소(KPX) | 유가: Dubai 원유 기준",
        S_SMALL
    ))
    story.append(PageBreak())
    return story


def build_toc_section(articles: list[dict], article_page_offset: int = 3) -> list:
    """Page 2: Table of contents with article list."""
    story = []

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("목  차", S_TITLE))
    story.append(HRFlowable(width="100%", thickness=2, color=C_BLUE, spaceAfter=4))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("■ 주요 언론 보도", S_H1))
    story.append(Spacer(1, 2 * mm))

    col_widths = [8 * mm, 28 * mm, 95 * mm, 18 * mm]
    tbl_data = [["번호", "언론사", "기사 제목", "페이지"]]

    for i, art in enumerate(articles, 1):
        page_no = article_page_offset + i - 1
        title = art.get("title", "")[:60]
        source = art.get("source", "")[:12]
        tbl_data.append([
            str(i),
            source,
            title,
            str(page_no),
        ])

    tbl_styles = [
        ("BACKGROUND",  (0, 0), (-1, 0),  C_HEADER_BG),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  C_WHITE),
        ("FONTNAME",    (0, 0), (-1, 0),  "NanumBold"),
        ("FONTNAME",    (0, 1), (-1, -1), "Nanum"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("ALIGN",       (0, 0), (0, -1),  "CENTER"),
        ("ALIGN",       (1, 0), (1, -1),  "CENTER"),
        ("ALIGN",       (3, 0), (3, -1),  "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",        (0, 0), (-1, -1), 0.4, C_BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_ROW_ALT]),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]

    tbl = Table(tbl_data, colWidths=col_widths)
    tbl.setStyle(TableStyle(tbl_styles))
    story.append(tbl)
    story.append(PageBreak())
    return story


def build_article_section(articles: list[dict]) -> list:
    """Pages 3+: Individual article pages with content and links."""
    story = []

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("주요 언론 보도 — 본문", S_TITLE))
    story.append(HRFlowable(width="100%", thickness=2, color=C_BLUE, spaceAfter=4))

    for i, art in enumerate(articles, 1):
        title   = art.get("title", "제목 없음")
        source  = art.get("source", "")
        date    = art.get("date", "")
        url     = art.get("url", "")
        summary = art.get("summary", "")
        content = art.get("content", "") or summary

        block = []
        block.append(Spacer(1, 4 * mm))

        # Source badge + number
        src_row_data = [[
            Paragraph(f"  {source}  ", _style(f"src_{i}", fontName="NanumBold", fontSize=8,
                                               textColor=C_WHITE, backColor=C_BLUE)),
            Paragraph(f"No. {i}", _style(f"no_{i}", fontSize=8, textColor=C_GRAY,
                                          alignment=TA_RIGHT)),
        ]]
        src_row = Table(src_row_data, colWidths=[40 * mm, 115 * mm])
        src_row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
        ]))
        block.append(src_row)

        # Title
        block.append(Paragraph(title, S_ART_TITLE))

        # Date
        if date:
            block.append(Paragraph(f"📅 {date}", S_ART_DATE))

        block.append(Spacer(1, 2 * mm))
        block.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER, spaceAfter=3))

        # Content
        if content:
            # Break into paragraphs
            paras = [p.strip() for p in content.split("\n") if p.strip()]
            for para in paras[:12]:
                block.append(Paragraph(para, S_ART_BODY))

        # Link
        if url:
            block.append(Spacer(1, 2 * mm))
            safe_url = url.replace("&", "&amp;")
            block.append(Paragraph(
                f'🔗 원문 링크: <link href="{safe_url}" color="#2563EB">{safe_url[:80]}...</link>',
                S_LINK,
            ))

        block.append(Spacer(1, 3 * mm))
        block.append(HRFlowable(width="100%", thickness=0.3, color=C_BORDER))

        story.extend(block)
        story.append(PageBreak())

    return story


def build_newspaper_headline_section(newspaper_results: list[dict]) -> list:
    """Last pages: Newspaper front page screenshots, 2-per-page grid."""
    story = []

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("주요 언론 헤드라인", S_TITLE))
    story.append(Paragraph("가나다 순 | 전국지 · 경제지 주요 신문 오늘의 헤드라인", S_SUBTITLE))
    story.append(HRFlowable(width="100%", thickness=2, color=C_BLUE, spaceAfter=6))

    # 2 columns layout
    available_w = W - 2 * MARGIN
    col_w = (available_w - 6 * mm) / 2

    # Group into pairs
    successful = [r for r in newspaper_results if r.get("success") and r.get("screenshot_path")]
    failed     = [r for r in newspaper_results if not r.get("success")]

    pairs = [successful[i:i+2] for i in range(0, len(successful), 2)]

    for pair in pairs:
        cells = []
        for r in pair:
            cell_content = []
            cell_content.append(Paragraph(
                r["name"],
                _style(f"paper_{r['name']}", fontName="NanumBold", fontSize=10,
                       textColor=C_NAVY, alignment=TA_CENTER)
            ))
            cell_content.append(Spacer(1, 1 * mm))
            try:
                img = Image(r["screenshot_path"], width=col_w, height=col_w * 0.65)
                cell_content.append(img)
            except Exception:
                cell_content.append(Paragraph("(이미지 로드 실패)", S_SMALL))
            cell_content.append(Spacer(1, 1 * mm))
            cell_content.append(Paragraph(
                f'<link href="{r["url"]}" color="#2563EB">{r["url"]}</link>',
                _style(f"url_{r['name']}", fontSize=7, textColor=C_BLUE, alignment=TA_CENTER)
            ))
            cells.append(cell_content)

        if len(cells) == 1:
            cells.append([""])

        row_table = Table(
            [cells],
            colWidths=[col_w, col_w],
        )
        row_table.setStyle(TableStyle([
            ("VALIGN",  (0, 0), (-1, -1), "TOP"),
            ("ALIGN",   (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING",   (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
            ("BOX",     (0, 0), (0, 0),  0.5, C_BORDER),
            ("BOX",     (1, 0), (1, 0),  0.5, C_BORDER),
        ]))
        story.append(row_table)
        story.append(Spacer(1, 4 * mm))

    if failed:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("※ 캡처 실패 신문사", S_BOLD))
        for r in failed:
            story.append(Paragraph(
                f"• {r['name']} ({r['url']}) — 캡처 실패 (사이트 접근 제한 또는 타임아웃)",
                S_SMALL
            ))

    return story


# ─── Main entry point ─────────────────────────────────────────────────────────

def generate_pdf(
    keyword: str,
    market_rows: list[dict],
    articles: list[dict],
    newspaper_results: list[dict],
    output_path: str | None = None,
) -> str:
    """Generate the full morning news PDF. Returns output file path."""
    today = datetime.date.today()
    if not output_path:
        fname = f"morning_news_{keyword}_{today.strftime('%Y%m%d')}.pdf"
        output_path = str(OUTPUT_DIR / fname)

    report_date = today.strftime("%Y년 %m월 %d일")

    # article pages start at page 3 (cover=1, toc=2, articles=3+)
    article_page_offset = 3

    doc = _make_doc(output_path)

    story = []
    story += build_cover_section(keyword, market_rows, report_date)
    story += build_toc_section(articles, article_page_offset)
    story += build_article_section(articles)
    story += build_newspaper_headline_section(newspaper_results)

    doc.build(story)
    return output_path
