"""
PDF generator — 공기업 주요 언론 보도 조간지
Structure:
  1. Cover   — branding header + market data table
  2. TOC     — 주요 언론 보도 목차 (20 articles, page numbers)
  3. Body    — per-article pages with content + live URL
  4. Headlines — 12 newspaper front-page screenshots (2-column grid)
"""

import datetime
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from src.config import FONT_REGULAR, FONT_BOLD, OUTPUT_DIR

# ── Font registration ─────────────────────────────────────────────────────────
pdfmetrics.registerFont(TTFont("Nanum", FONT_REGULAR))
pdfmetrics.registerFont(TTFont("NanumBd", FONT_BOLD))

# ── Page geometry ─────────────────────────────────────────────────────────────
W, H = A4
MARGIN_LR = 16 * mm
MARGIN_TOP = 24 * mm
MARGIN_BOT = 16 * mm
HEADER_H = 14 * mm    # top blue bar height
FOOTER_H = 10 * mm

# ── Color palette ─────────────────────────────────────────────────────────────
NAVY    = colors.HexColor("#0D2B55")
BLUE    = colors.HexColor("#1D4ED8")
SKY     = colors.HexColor("#DBEAFE")
TEAL    = colors.HexColor("#0F766E")
RED     = colors.HexColor("#DC2626")
GREEN   = colors.HexColor("#15803D")
GRAY    = colors.HexColor("#64748B")
LGRAY   = colors.HexColor("#F1F5F9")
BORDER  = colors.HexColor("#CBD5E1")
WHITE   = colors.white
DARK    = colors.HexColor("#1E293B")
GOLD    = colors.HexColor("#B45309")


def _s(name, **kw) -> ParagraphStyle:
    defaults = {"fontName": "Nanum", "fontSize": 9, "leading": 14, "textColor": DARK}
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


# ── Style definitions ─────────────────────────────────────────────────────────
S = {
    "title":    _s("title",   fontName="NanumBd", fontSize=22, textColor=NAVY, leading=28, spaceAfter=2),
    "subtitle": _s("sub",     fontName="NanumBd", fontSize=11, textColor=BLUE, leading=15),
    "h1":       _s("h1",      fontName="NanumBd", fontSize=14, textColor=NAVY, leading=19),
    "h2":       _s("h2",      fontName="NanumBd", fontSize=10, textColor=BLUE, leading=14),
    "body":     _s("body",    fontSize=9,  leading=15),
    "small":    _s("small",   fontSize=7.5, textColor=GRAY, leading=11),
    "bold":     _s("bold",    fontName="NanumBd", fontSize=9),
    "art_title":_s("at",      fontName="NanumBd", fontSize=12, textColor=NAVY, leading=17, spaceAfter=3),
    "art_date": _s("ad",      fontSize=8,  textColor=GRAY, leading=11),
    "art_body": _s("ab",      fontSize=9,  leading=15, spaceAfter=2),
    "toc_src":  _s("ts",      fontName="NanumBd", fontSize=8, textColor=BLUE),
    "toc_title":_s("tt",      fontSize=9,  leading=13),
    "link":     _s("lnk",     fontSize=8,  textColor=BLUE, leading=11),
    "center":   _s("ctr",     fontSize=9,  alignment=TA_CENTER),
    "c_white":  _s("cw",      fontName="NanumBd", fontSize=9, textColor=WHITE, alignment=TA_CENTER),
    "paper_name":_s("pn",     fontName="NanumBd", fontSize=11, textColor=NAVY, alignment=TA_CENTER, leading=14),
    "paper_url":_s("pu",      fontSize=7,  textColor=BLUE, alignment=TA_CENTER, leading=10),
}


# ── Page decorators ───────────────────────────────────────────────────────────

def _draw_header_footer(canvas, doc, keyword: str, report_date: str, section: str = ""):
    canvas.saveState()

    # ── Header bar
    canvas.setFillColor(NAVY)
    canvas.rect(0, H - HEADER_H, W, HEADER_H, fill=1, stroke=0)

    # Left: report title
    canvas.setFillColor(WHITE)
    canvas.setFont("NanumBd", 10)
    canvas.drawString(MARGIN_LR, H - HEADER_H + 4.5 * mm, "공기업 주요 언론 보도")

    # Center: section name
    if section:
        canvas.setFont("Nanum", 8.5)
        canvas.setFillColor(colors.HexColor("#93C5FD"))
        canvas.drawCentredString(W / 2, H - HEADER_H + 4.5 * mm, section)

    # Right: keyword + date
    canvas.setFont("Nanum", 8.5)
    canvas.setFillColor(colors.HexColor("#BAE6FD"))
    canvas.drawRightString(W - MARGIN_LR, H - HEADER_H + 4.5 * mm, f"{keyword} | {report_date}")

    # ── Thin accent line below header
    canvas.setStrokeColor(BLUE)
    canvas.setLineWidth(0.8)
    canvas.line(0, H - HEADER_H, W, H - HEADER_H)

    # ── Footer
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.4)
    canvas.line(MARGIN_LR, FOOTER_H, W - MARGIN_LR, FOOTER_H)

    canvas.setFillColor(GRAY)
    canvas.setFont("Nanum", 7.5)
    canvas.drawString(MARGIN_LR, FOOTER_H - 4 * mm, "본 자료는 자동 수집된 공개 정보로 투자 참고자료가 아닙니다.")
    canvas.drawRightString(W - MARGIN_LR, FOOTER_H - 4 * mm, f"— {doc.page} —")

    canvas.restoreState()


def _make_page_decorator(keyword, report_date, section=""):
    def decorator(canvas, doc):
        _draw_header_footer(canvas, doc, keyword, report_date, section)
    return decorator


def _make_doc(output_path: str, keyword: str, report_date: str) -> BaseDocTemplate:
    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN_LR,
        rightMargin=MARGIN_LR,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOT + FOOTER_H,
        title="공기업 주요 언론 보도",
        author=keyword,
    )
    cover_frame = Frame(
        MARGIN_LR, MARGIN_BOT + FOOTER_H, W - 2 * MARGIN_LR,
        H - MARGIN_TOP - MARGIN_BOT - FOOTER_H, id="cover"
    )
    body_frame = Frame(
        MARGIN_LR, MARGIN_BOT + FOOTER_H, W - 2 * MARGIN_LR,
        H - MARGIN_TOP - MARGIN_BOT - FOOTER_H, id="body"
    )
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[cover_frame],
                     onPage=_make_page_decorator(keyword, report_date, "")),
        PageTemplate(id="toc",   frames=[body_frame],
                     onPage=_make_page_decorator(keyword, report_date, "목차")),
        PageTemplate(id="art",   frames=[body_frame],
                     onPage=_make_page_decorator(keyword, report_date, "주요 언론 보도")),
        PageTemplate(id="news",  frames=[body_frame],
                     onPage=_make_page_decorator(keyword, report_date, "주요 언론 헤드라인")),
    ])
    return doc


# ── Formatting helpers ────────────────────────────────────────────────────────

def _fmt_price(val, unit="", decimals=None) -> str:
    if val is None:
        return "–"
    if decimals is None:
        decimals = 0 if val >= 100 else 2
    return f"{val:,.{decimals}f}" + (f" {unit}" if unit else "")


def _fmt_change(change, pct, unit="", decimals=None) -> tuple[str, object]:
    if change is None:
        return "–", GRAY
    if decimals is None:
        decimals = 0 if abs(change) >= 100 else 2
    arrow = "▲" if change >= 0 else "▼"
    color = RED if change >= 0 else BLUE
    pct_str = f"({abs(pct):.2f}%)" if pct is not None else ""
    s = f"{arrow} {abs(change):,.{decimals}f}{' '+unit if unit else ''} {pct_str}".strip()
    return s, color


def _fmt_yoy(yoy_change, yoy_pct, unit="", decimals=None) -> tuple[str, object]:
    if yoy_change is None:
        return "–", GRAY
    if decimals is None:
        decimals = 0 if abs(yoy_change) >= 100 else 2
    arrow = "▲" if yoy_change >= 0 else "▼"
    color = RED if yoy_change >= 0 else BLUE
    pct_str = f"({abs(yoy_pct):.2f}%)" if yoy_pct is not None else ""
    s = f"{arrow} {abs(yoy_change):,.{decimals}f}{' '+unit if unit else ''} {pct_str}".strip()
    return s, color


def _colored_para(text: str, color: object, bold=False) -> Paragraph:
    font = "NanumBd" if bold else "Nanum"
    style = ParagraphStyle("inline", fontName=font, fontSize=8.5, leading=12,
                           textColor=color, alignment=TA_CENTER)
    return Paragraph(text, style)


# ── Section 1: Cover ──────────────────────────────────────────────────────────

def build_cover(keyword: str, market_rows: list[dict], report_date: str) -> list:
    story = []
    story.append(Spacer(1, 4 * mm))

    # Title block
    story.append(Paragraph("공기업 주요 언론 보도", S["title"]))
    story.append(Paragraph(keyword, _s("kw", fontName="NanumBd", fontSize=16,
                                        textColor=BLUE, leading=20)))
    story.append(Spacer(1, 1 * mm))
    story.append(Paragraph(
        f"보고 기준일: {report_date} 오전 08:00",
        _s("dt", fontSize=9, textColor=GRAY, leading=12)
    ))
    story.append(Spacer(1, 5 * mm))
    story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=5))

    # Section label
    story.append(Paragraph("▮ 주요 시장 지표", S["h1"]))
    story.append(Spacer(1, 3 * mm))

    # Market data table
    col_w = [42 * mm, 26 * mm, 36 * mm, 50 * mm, 42 * mm]
    headers = ["구분", "기준일", "현재가", "전일 대비", "전년 대비"]

    header_row = [
        Paragraph(h, _s(f"th{i}", fontName="NanumBd", fontSize=8.5, textColor=WHITE,
                         alignment=TA_CENTER, leading=12))
        for i, h in enumerate(headers)
    ]
    data = [header_row]

    for row in market_rows:
        if not row:
            continue
        label = row.get("label", "")
        date_ = row.get("date") or "–"
        unit  = row.get("unit", "")
        price = row.get("price")

        price_str = _fmt_price(price, unit)
        change_str, chg_color = _fmt_change(row.get("change"), row.get("change_pct"))
        yoy_str,   yoy_color  = _fmt_yoy(row.get("yoy_change"), row.get("yoy_pct"))

        data.append([
            Paragraph(label, _s(f"l{label}", fontName="NanumBd", fontSize=8.5, leading=12)),
            Paragraph(date_, _s(f"d{label}", fontSize=8, textColor=GRAY, alignment=TA_CENTER, leading=12)),
            Paragraph(price_str, _s(f"p{label}", fontName="NanumBd", fontSize=9,
                                     alignment=TA_RIGHT, leading=12)),
            _colored_para(change_str, chg_color, bold=True),
            _colored_para(yoy_str, yoy_color),
        ])

    tbl_style = [
        # Header
        ("BACKGROUND",    (0, 0), (-1, 0),  NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),  "NanumBd"),
        # Body font
        ("FONTNAME",      (0, 1), (-1, -1), "Nanum"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        # Alignment
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (-1, 0),  "CENTER"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        # Grid
        ("GRID",          (0, 0), (-1, -1), 0.4, BORDER),
        ("LINEBELOW",     (0, 0), (-1, 0),  1.2, BLUE),
        # Alternating rows
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGRAY]),
        # Left column accent
        ("BACKGROUND",    (0, 1), (0, -1),  colors.HexColor("#EFF6FF")),
    ]

    tbl = Table(data, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle(tbl_style))
    story.append(tbl)

    story.append(Spacer(1, 3 * mm))
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    story.append(Paragraph(
        f"※ 조회 시각: {now_str} KST  |  환율 · 유가: 네이버 금융  |  SMP: 한국전력거래소(KPX)  |  주가: KRX · NYSE",
        S["small"]
    ))
    story.append(PageBreak())
    return story


# ── Section 2: TOC ───────────────────────────────────────────────────────────

def build_toc(articles: list[dict], first_article_page: int = 3) -> list:
    story = []
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("목  차", S["title"]))
    story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=4))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("▮ 주요 언론 보도", S["h1"]))
    story.append(Spacer(1, 3 * mm))

    col_w = [9 * mm, 26 * mm, 112 * mm, 16 * mm]
    hdr_style = _s("toc_hdr", fontName="NanumBd", fontSize=8.5, textColor=WHITE,
                    alignment=TA_CENTER, leading=12)
    data = [[
        Paragraph("No.", hdr_style),
        Paragraph("언론사", hdr_style),
        Paragraph("기사 제목", hdr_style),
        Paragraph("p.", hdr_style),
    ]]

    for i, art in enumerate(articles, 1):
        page_no = first_article_page + i - 1
        title = art.get("title", "")
        if len(title) > 65:
            title = title[:63] + "…"
        source = art.get("source", "")

        # Source colored badge
        src_badge = Paragraph(
            source,
            _s(f"sb{i}", fontName="NanumBd", fontSize=8, textColor=BLUE,
                alignment=TA_CENTER, leading=12)
        )

        data.append([
            Paragraph(str(i), _s(f"n{i}", fontSize=8.5, textColor=GRAY, alignment=TA_CENTER, leading=12)),
            src_badge,
            Paragraph(title, S["toc_title"]),
            Paragraph(str(page_no), _s(f"pg{i}", fontSize=8.5, textColor=NAVY,
                                        alignment=TA_CENTER, leading=12, fontName="NanumBd")),
        ])

    tbl = Table(data, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  NAVY),
        ("FONTNAME",      (0, 0), (-1, 0),  "NanumBd"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (0, -1),  "CENTER"),
        ("ALIGN",         (3, 0), (3, -1),  "CENTER"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID",          (0, 0), (-1, -1), 0.35, BORDER),
        ("LINEBELOW",     (0, 0), (-1, 0),  1.2,  BLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGRAY]),
        ("BACKGROUND",    (1, 1), (1, -1),  colors.HexColor("#EFF6FF")),
    ]))
    story.append(tbl)
    story.append(PageBreak())
    return story


# ── Section 3: Article body pages ────────────────────────────────────────────

def _source_color(source: str) -> object:
    """Return a background color based on newspaper name."""
    palette = {
        "한국경제": colors.HexColor("#B45309"),
        "매일경제": colors.HexColor("#7C3AED"),
        "서울경제": colors.HexColor("#0369A1"),
        "한겨레":   colors.HexColor("#15803D"),
        "경향신문": colors.HexColor("#0F766E"),
        "조선일보": colors.HexColor("#B91C1C"),
        "동아일보": colors.HexColor("#1D4ED8"),
        "중앙일보": colors.HexColor("#D97706"),
        "서울신문": colors.HexColor("#7E22CE"),
        "국민일보": colors.HexColor("#0F766E"),
        "세계일보": colors.HexColor("#BE185D"),
        "한국일보": colors.HexColor("#0C4A6E"),
        "에너지신문": colors.HexColor("#166534"),
    }
    for k, v in palette.items():
        if k in source:
            return v
    return NAVY


def build_articles(articles: list[dict]) -> list:
    story = []

    for i, art in enumerate(articles, 1):
        title   = art.get("title", "(제목 없음)")
        source  = art.get("source", "")
        date_   = art.get("date", "")
        url     = art.get("url", "")
        summary = art.get("summary", "")
        content = art.get("content") or summary

        src_color = _source_color(source)
        block = []
        block.append(Spacer(1, 3 * mm))

        # ── Source tag + article number row ──────────────────────────────────
        src_cell = Paragraph(
            f"  {source}  ",
            _s(f"sc{i}", fontName="NanumBd", fontSize=8.5, textColor=WHITE,
                backColor=src_color, leading=13, alignment=TA_CENTER)
        )
        num_cell = Paragraph(
            f"기사 {i}",
            _s(f"nc{i}", fontSize=8, textColor=GRAY, leading=12, alignment=TA_RIGHT)
        )
        badge_row = Table([[src_cell, num_cell]], colWidths=[35 * mm, W - 2 * MARGIN_LR - 35 * mm])
        badge_row.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        block.append(badge_row)

        # ── Article title ─────────────────────────────────────────────────────
        block.append(Paragraph(title, S["art_title"]))

        # ── Date ─────────────────────────────────────────────────────────────
        if date_:
            block.append(Paragraph(f"▸ {date_}", S["art_date"]))
        block.append(Spacer(1, 2 * mm))
        block.append(HRFlowable(width="100%", thickness=0.6, color=BORDER, spaceAfter=4))

        # ── Content ──────────────────────────────────────────────────────────
        if content:
            paras = [p.strip() for p in content.replace("\r", "").split("\n") if p.strip()]
            for j, para in enumerate(paras[:15]):
                # Escape XML-special characters
                para_safe = (para.replace("&", "&amp;")
                                  .replace("<", "&lt;")
                                  .replace(">", "&gt;"))
                block.append(Paragraph(para_safe, S["art_body"]))
        elif summary:
            safe = (summary.replace("&", "&amp;")
                           .replace("<", "&lt;")
                           .replace(">", "&gt;"))
            block.append(Paragraph(safe, S["art_body"]))

        # ── Source URL ────────────────────────────────────────────────────────
        if url:
            block.append(Spacer(1, 2 * mm))
            display_url = url if len(url) <= 90 else url[:88] + "…"
            safe_url = url.replace("&", "&amp;")
            block.append(Paragraph(
                f'▸ 원문 링크: <link href="{safe_url}" color="#1D4ED8">{display_url}</link>',
                S["link"],
            ))

        block.append(Spacer(1, 3 * mm))
        block.append(HRFlowable(width="100%", thickness=0.3, color=LGRAY))

        story.extend(block)
        story.append(PageBreak())

    return story


# ── Section 4: Newspaper headlines ───────────────────────────────────────────

def build_headlines(newspaper_results: list[dict]) -> list:
    story = []

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("주요 언론 헤드라인", S["title"]))
    story.append(Paragraph("가나다 순 | 경향 · 국민 · 동아 · 서울 · 세계 · 조선 · 중앙 · 한겨레 · 한국일보 · 매일경제 · 서울경제 · 한국경제", S["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=6))

    avail_w = W - 2 * MARGIN_LR
    cell_w  = (avail_w - 6 * mm) / 2
    img_h   = cell_w * 0.65

    successful = [r for r in newspaper_results if r.get("success") and r.get("screenshot_path")]
    failed     = [r for r in newspaper_results if not r.get("success")]

    if not successful:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(
            "신문사 헤드라인 캡처에 실패했습니다. 네트워크 연결을 확인하거나 --no-screenshot 옵션을 사용하세요.",
            _s("warn", textColor=RED, fontSize=9)
        ))
    else:
        pairs = [successful[j:j+2] for j in range(0, len(successful), 2)]
        for pair in pairs:
            cells = []
            for r in pair:
                cell = _build_paper_cell(r, cell_w, img_h)
                cells.append(cell)
            # Pad to 2 columns
            while len(cells) < 2:
                cells.append([Spacer(1, 1)])

            row_tbl = Table([cells], colWidths=[cell_w + 2 * mm, cell_w + 2 * mm])
            row_tbl.setStyle(TableStyle([
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING",   (0, 0), (-1, -1), 2),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
                ("TOPPADDING",    (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("BOX",           (0, 0), (0, 0),   0.5, BORDER),
                ("BOX",           (1, 0), (1, 0),   0.5, BORDER),
            ]))
            story.append(row_tbl)
            story.append(Spacer(1, 4 * mm))

    # Failed list
    if failed:
        story.append(Spacer(1, 4 * mm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph("※ 캡처 실패 또는 미지원 신문사", S["bold"]))
        for r in failed:
            safe_url = r["url"].replace("&", "&amp;")
            story.append(Paragraph(
                f"• {r['name']} — "
                f'<link href="{safe_url}" color="#1D4ED8">{r["url"]}</link>',
                S["link"]
            ))

    return story


def _build_paper_cell(r: dict, cell_w: float, img_h: float) -> list:
    """Build a single newspaper cell (name + screenshot + url)."""
    cell = []

    # Paper name bar
    bar_style = _s(
        f"bar_{r['name']}",
        fontName="NanumBd", fontSize=10, textColor=WHITE,
        backColor=NAVY, alignment=TA_CENTER, leading=14,
    )
    cell.append(Paragraph(f" {r['name']} ", bar_style))
    cell.append(Spacer(1, 1.5 * mm))

    # Screenshot
    try:
        img = Image(r["screenshot_path"], width=cell_w - 2, height=img_h)
        img.hAlign = "CENTER"
        cell.append(img)
    except Exception:
        cell.append(Paragraph("(이미지 없음)", _s("noimg", fontSize=8, textColor=GRAY, alignment=TA_CENTER)))

    cell.append(Spacer(1, 1 * mm))

    # URL
    safe_url = r["url"].replace("&", "&amp;")
    cell.append(Paragraph(
        f'<link href="{safe_url}" color="#1D4ED8">{r["url"]}</link>',
        S["paper_url"]
    ))
    return cell


# ── Main generator ────────────────────────────────────────────────────────────

def generate_pdf(
    keyword: str,
    market_rows: list[dict],
    articles: list[dict],
    newspaper_results: list[dict],
    output_path: str | None = None,
) -> str:
    """Generate the full morning news PDF. Returns the output file path."""
    today = datetime.date.today()
    _day_kr = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목",
                "Fri": "금", "Sat": "토", "Sun": "일"}
    _day_en = today.strftime("%a")
    report_date = today.strftime("%Y년 %m월 %d일") + f" ({_day_kr.get(_day_en, _day_en)})"

    if not output_path:
        fname = f"morning_news_{keyword}_{today.strftime('%Y%m%d')}.pdf"
        output_path = str(OUTPUT_DIR / fname)

    # Page 1 = cover, page 2 = TOC, page 3+ = articles, then headlines
    first_article_page = 3

    doc = _make_doc(output_path, keyword, report_date)

    story = []
    story += build_cover(keyword, market_rows, report_date)

    from reportlab.platypus import NextPageTemplate
    story.append(NextPageTemplate("toc"))
    story += build_toc(articles, first_article_page)

    story.append(NextPageTemplate("art"))
    story += build_articles(articles)

    story.append(NextPageTemplate("news"))
    story += build_headlines(newspaper_results)

    doc.build(story)
    return output_path
