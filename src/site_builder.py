"""
정적 아카이브 사이트 생성기.

docs/index.html 을 만든다. 이 페이지는 같은 폴더의 archive.json 을 읽어
전체 기간 검색·매체 필터·일별 보도량 탐색을 브라우저에서 처리한다.
서버가 없으므로 GitHub Pages에 그대로 올라간다.
"""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"

PAGE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>조간지 아카이브</title>
<meta name="description" content="공기업 주요 언론 보도 누적 아카이브">
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<link rel="stylesheet"
      href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<style>
:root{
  --ink:#16202b;
  --paper:#f8f8f6;
  --rule:#d9d9d2;
  --masthead:#a81f27;
  --muted:#78828e;
  --sub:#4a5561;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0;background:var(--paper);color:var(--ink);
  font-family:Pretendard,-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;
  font-size:15px;line-height:1.6;
}
.wrap{max-width:920px;margin:0 auto;padding:0 20px}
a{color:inherit}

/* ── 제호 ───────────────────────────────────────── */
.masthead{padding:34px 0 14px}
.masthead h1{
  margin:0;font-size:15px;font-weight:800;letter-spacing:.34em;
  text-transform:none;color:var(--masthead);
}
.masthead .kw{
  margin:10px 0 0;font-size:38px;font-weight:800;letter-spacing:-.02em;line-height:1.1;
}
.masthead .meta{margin-top:10px;font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}
.rule{height:3px;background:var(--masthead);margin:14px 0 0}
.rule.thin{height:1px;background:var(--rule);margin:0}

/* ── 보도량 스트립 (시그니처) ────────────────────── */
.strip-sec{padding:20px 0 14px}
.strip-label{
  display:flex;justify-content:space-between;align-items:baseline;
  font-size:11px;color:var(--muted);letter-spacing:.08em;margin-bottom:7px;
}
.strip{
  display:flex;align-items:flex-end;gap:1px;height:56px;
  overflow-x:auto;overflow-y:hidden;padding-bottom:2px;
}
.strip::-webkit-scrollbar{height:4px}
.strip::-webkit-scrollbar-thumb{background:var(--rule);border-radius:2px}
.bar{
  flex:0 0 5px;min-height:2px;background:var(--sub);cursor:pointer;
  border:0;padding:0;border-radius:1px 1px 0 0;
  transition:background .12s ease;
}
.bar:hover,.bar:focus-visible{background:var(--masthead);outline:none}
.bar.peak{background:var(--masthead);opacity:.55}
.bar.on{background:var(--masthead);opacity:1}

/* ── 검색 ───────────────────────────────────────── */
.tools{display:flex;gap:8px;flex-wrap:wrap;padding:16px 0}
.tools input,.tools select{
  font:inherit;font-size:14px;padding:9px 12px;
  border:1px solid var(--rule);border-radius:2px;background:#fff;color:var(--ink);
}
.tools input{flex:1 1 240px;min-width:0}
.tools input:focus,.tools select:focus{outline:2px solid var(--masthead);outline-offset:-1px}
.count{font-size:13px;color:var(--muted);padding-bottom:14px;font-variant-numeric:tabular-nums}

/* ── 일자 그룹 ──────────────────────────────────── */
.day{border-top:1px solid var(--rule);padding:22px 0 4px}
.day:first-of-type{border-top:0}
.day-head{
  display:flex;align-items:baseline;gap:10px;margin-bottom:12px;
  position:sticky;top:0;background:var(--paper);padding:6px 0;z-index:2;
}
.day-date{font-size:17px;font-weight:800;letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.day-n{font-size:12px;color:var(--muted)}

.item{display:flex;gap:14px;padding:9px 0;align-items:baseline}
.item .t{
  flex:0 0 44px;font-size:12px;color:var(--muted);
  font-variant-numeric:tabular-nums;padding-top:2px;
}
.item .b{flex:1 1 auto;min-width:0}
.item .p{
  font-size:11px;font-weight:700;color:var(--masthead);
  letter-spacing:.02em;margin-bottom:2px;
}
.item a.h{
  font-size:15.5px;font-weight:600;line-height:1.45;text-decoration:none;
  display:block;
}
.item a.h:hover{text-decoration:underline;text-underline-offset:3px}
.item .s{font-size:13px;color:var(--sub);line-height:1.55;margin-top:3px}
mark{background:#ffe9a8;color:inherit;padding:0 1px}

.empty{padding:56px 0;text-align:center;color:var(--muted);font-size:14px}
footer{
  border-top:1px solid var(--rule);margin-top:40px;padding:20px 0 48px;
  font-size:11.5px;color:var(--muted);line-height:1.8;
}
@media (max-width:600px){
  .masthead .kw{font-size:28px}
  .item{gap:10px}
  .item .t{flex-basis:38px;font-size:11px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>
<div class="wrap">

  <header class="masthead">
    <h1>조간지 아카이브</h1>
    <p class="kw" id="kw">—</p>
    <p class="meta" id="meta">불러오는 중…</p>
    <div class="rule"></div>
  </header>

  <section class="strip-sec">
    <div class="strip-label">
      <span>일별 보도량</span>
      <span id="strip-hint">막대를 누르면 해당 일자로 이동합니다</span>
    </div>
    <div class="strip" id="strip"></div>
    <div class="rule thin"></div>
  </section>

  <div class="tools">
    <input id="q" type="search" placeholder="제목·요약에서 검색" autocomplete="off">
    <select id="press"><option value="">전체 매체</option></select>
    <select id="span">
      <option value="0">전체 기간</option>
      <option value="7">최근 7일</option>
      <option value="30">최근 30일</option>
      <option value="90">최근 90일</option>
    </select>
  </div>
  <div class="count" id="count"></div>

  <main id="list"></main>

  <footer>
    네이버 검색 오픈API로 매일 자동 수집·누적됩니다. 제목과 요약은 API 제공 범위 내에서 인용했으며,
    기사 원문의 저작권은 각 언론사에 있습니다. 제목을 누르면 언론사 원문으로 이동합니다.
    <span id="gen"></span>
  </footer>
</div>

<script>
const DAYS_KO = ['일','월','화','수','목','금','토'];
let DB = null;

const el = id => document.getElementById(id);
const esc = s => (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function highlight(text, term){
  const safe = esc(text);
  if(!term) return safe;
  const re = new RegExp('(' + term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&') + ')','gi');
  return safe.replace(re, '<mark>$1</mark>');
}

async function load(){
  if(window.__ARCHIVE__){            // 자체 포함 미리보기용
    DB = window.__ARCHIVE__;
  }else{
    try{
      const res = await fetch('archive.json', {cache:'no-cache'});
      if(!res.ok) throw new Error(res.status);
      DB = await res.json();
    }catch(e){
      el('meta').textContent = 'archive.json을 불러오지 못했습니다. 아직 첫 수집이 실행되지 않았을 수 있습니다.';
      return;
    }
  }
  if(!DB.days || !DB.days.length){
    el('meta').textContent = '아직 누적된 자료가 없습니다.';
    return;
  }

  const first = DB.days[DB.days.length-1].date, last = DB.days[0].date;
  el('kw').textContent = (DB.keywords||[]).join(' · ') || '주요 언론 보도';
  el('meta').textContent =
    `${first.replace(/-/g,'.')} – ${last.replace(/-/g,'.')} · ${DB.day_count}일 · ${DB.article_count.toLocaleString()}건`;
  el('gen').textContent = '최종 갱신 ' + (DB.generated_at||'').slice(0,16).replace('T',' ');

  const sel = el('press');
  Object.entries(DB.presses||{}).forEach(([name,n])=>{
    const o = document.createElement('option');
    o.value = name; o.textContent = `${name} (${n})`;
    sel.appendChild(o);
  });

  buildStrip();
  render();
  ['q','press','span'].forEach(id => el(id).addEventListener('input', render));
}

function buildStrip(){
  const strip = el('strip');
  const asc = [...DB.days].reverse();
  const max = Math.max(...asc.map(d=>d.count), 1);
  strip.innerHTML = '';
  asc.forEach(d=>{
    const b = document.createElement('button');
    b.className = 'bar' + (d.count >= max*0.8 ? ' peak' : '');
    b.style.height = Math.max(2, Math.round(d.count/max*54)) + 'px';
    b.title = `${d.date} · ${d.count}건`;
    b.setAttribute('aria-label', `${d.date} ${d.count}건`);
    b.dataset.date = d.date;
    b.onclick = ()=>{
      const target = document.getElementById('d-'+d.date);
      if(target) target.scrollIntoView({behavior:'smooth', block:'start'});
      document.querySelectorAll('.bar.on').forEach(x=>x.classList.remove('on'));
      b.classList.add('on');
    };
    strip.appendChild(b);
  });
  strip.scrollLeft = strip.scrollWidth;
}

function render(){
  const term = el('q').value.trim();
  const press = el('press').value;
  const span = parseInt(el('span').value, 10);

  let days = DB.days;
  if(span > 0){
    const cut = new Date(Date.now() - span*86400000).toISOString().slice(0,10);
    days = days.filter(d => d.date >= cut);
  }

  const lower = term.toLowerCase();
  let shown = 0;
  const out = [];

  for(const d of days){
    const arts = d.articles.filter(a=>{
      if(press && a.press !== press) return false;
      if(!term) return true;
      return (a.title + ' ' + (a.summary||'')).toLowerCase().includes(lower);
    });
    if(!arts.length) continue;
    shown += arts.length;

    const dt = new Date(d.date + 'T00:00:00');
    const label = `${d.date.replace(/-/g,'.')} (${DAYS_KO[dt.getDay()]})`;

    out.push(`<section class="day" id="d-${d.date}">
      <div class="day-head"><span class="day-date">${label}</span><span class="day-n">${arts.length}건</span></div>
      ${arts.map(a=>`<article class="item">
        <div class="t">${esc((a.at||'').slice(11,16))}</div>
        <div class="b">
          <div class="p">${esc(a.press)}</div>
          <a class="h" href="${esc(a.url)}" target="_blank" rel="noopener">${highlight(a.title, term)}</a>
          ${a.summary ? `<div class="s">${highlight(a.summary, term)}</div>` : ''}
        </div>
      </article>`).join('')}
    </section>`);
  }

  el('count').textContent = shown
    ? `${shown.toLocaleString()}건${term ? ` · "${term}"` : ''}${press ? ` · ${press}` : ''}`
    : '';
  el('list').innerHTML = out.length
    ? out.join('')
    : '<div class="empty">조건에 맞는 기사가 없습니다. 검색어나 기간을 바꿔보세요.</div>';
}

load();
</script>
</body>
</html>
"""


def build() -> Path:
    DOCS_DIR.mkdir(exist_ok=True)
    path = DOCS_DIR / "index.html"
    path.write_text(PAGE, encoding="utf-8")
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"      → 사이트 생성: {path}")
    return path
