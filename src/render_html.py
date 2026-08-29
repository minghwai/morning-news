"""
메일 본문용 HTML 렌더러.

메일 클라이언트(네이버메일/Gmail/아웃룩)는 <style> 태그와 외부 CSS를 자주 무시하므로
모든 스타일을 인라인으로 넣는다. 폰트 크기는 모바일 가독성 기준(16px 본문).
"""

from __future__ import annotations

import html

ACCENT = "#1b3a6b"
MUTED = "#6b7280"
LINE = "#e5e7eb"
BG = "#f6f7f9"

_WRAP = (
    "max-width:640px;margin:0 auto;padding:0 16px;"
    "font-family:-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo',"
    "'Malgun Gothic','맑은 고딕',sans-serif;color:#111827;"
)


def _esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def _header(data: dict) -> str:
    collected = data["collected_at"]
    stats = data["stats"]
    cutoff_label = data["cutoff"].strftime("%m월 %d일 %H:%M")

    return f"""
<div style="padding:28px 0 20px;border-bottom:3px solid {ACCENT};">
  <div style="font-size:13px;letter-spacing:2px;color:{MUTED};margin-bottom:6px;">
    주요 언론 보도
  </div>
  <div style="font-size:28px;font-weight:800;line-height:1.25;color:{ACCENT};">
    {_esc(data['keyword'])}
  </div>
  <div style="font-size:14px;color:{MUTED};margin-top:8px;">
    {collected.strftime('%Y년 %m월 %d일 (%a) %H:%M')} 기준 · 총 {stats['kept']}건 · {stats['press_count']}개 매체
  </div>
</div>

<div style="background:{BG};border-radius:8px;padding:14px 16px;margin-top:16px;
            font-size:13px;line-height:1.7;color:#374151;">
  <strong style="color:{ACCENT};">수집 조건</strong><br>
  {cutoff_label} 이후 발행된 기사만 포함했습니다.
  검색 결과 {stats['total_seen']}건 중 발행 시각 미달·판독 불가 {stats['dropped_old']}건,
  중복 {stats['dropped_dup']}건을 제외했습니다.<br>
  각 제목을 누르면 언론사 원문으로 바로 이동합니다.
</div>
"""


def _article_block(idx: int, art: dict) -> str:
    summary = _esc(art["summary"])
    if len(summary) > 220:
        summary = summary[:220] + "…"

    return f"""
<div style="padding:20px 0;border-bottom:1px solid {LINE};">
  <div style="font-size:12px;color:{MUTED};margin-bottom:6px;">
    <span style="display:inline-block;background:{BG};border-radius:4px;
                 padding:2px 8px;font-weight:700;color:{ACCENT};">
      {_esc(art['press'])}
    </span>
    <span style="margin-left:8px;">{_esc(art['published_str'])}</span>
  </div>
  <a href="{_esc(art['source_url'])}"
     style="font-size:17px;font-weight:700;line-height:1.45;color:#111827;
            text-decoration:none;display:block;">
    {idx}. {_esc(art['title'])}
  </a>
  <div style="font-size:14px;line-height:1.65;color:#4b5563;margin-top:8px;">
    {summary}
  </div>
  <div style="font-size:12px;margin-top:10px;">
    <a href="{_esc(art['source_url'])}" style="color:{ACCENT};text-decoration:none;">원문 보기 ↗</a>
    <span style="color:{LINE};margin:0 6px;">|</span>
    <a href="{_esc(art['naver_url'])}" style="color:{MUTED};text-decoration:none;">네이버뉴스 ↗</a>
  </div>
</div>
"""


def _press_summary(data: dict) -> str:
    rows = "".join(
        f"<tr><td style='padding:5px 0;font-size:14px;'>{_esc(name)}</td>"
        f"<td style='padding:5px 0;font-size:14px;text-align:right;color:{MUTED};'>{cnt}건</td></tr>"
        for name, cnt in data["stats"]["by_press"].items()
    )
    return f"""
<div style="margin-top:28px;padding:18px 16px;background:{BG};border-radius:8px;">
  <div style="font-size:14px;font-weight:700;color:{ACCENT};margin-bottom:10px;">매체별 보도량</div>
  <table style="width:100%;border-collapse:collapse;">{rows}</table>
</div>
"""


def render(data: dict) -> str:
    articles = data["articles"]

    if not articles:
        body = f"""
<div style="padding:40px 0;text-align:center;color:{MUTED};font-size:15px;">
  오늘 발행된 관련 기사가 없습니다.
</div>
"""
    else:
        body = "".join(_article_block(i, a) for i, a in enumerate(articles, 1))
        body += _press_summary(data)

    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#ffffff;">
<div style="{_WRAP}">
{_header(data)}
{body}
<div style="padding:22px 0 40px;font-size:11px;color:{MUTED};line-height:1.7;">
  본 메일은 네이버 검색 오픈API로 자동 수집·생성되었습니다.
  기사 원문의 저작권은 각 언론사에 있으며, 제목·요약은 API 제공 범위 내에서 인용했습니다.
</div>
</div>
</body></html>"""


def render_text(data: dict) -> str:
    """HTML을 못 읽는 클라이언트를 위한 대체 본문."""
    lines = [
        f"[{data['keyword']}] 주요 언론 보도",
        data["collected_at"].strftime("%Y년 %m월 %d일 %H:%M 기준"),
        f"총 {data['stats']['kept']}건 / {data['stats']['press_count']}개 매체",
        "",
    ]
    for i, art in enumerate(data["articles"], 1):
        lines += [
            f"{i}. [{art['press']}] {art['title']}",
            f"   {art['published_str']} | {art['source_url']}",
            "",
        ]
    return "\n".join(lines)
