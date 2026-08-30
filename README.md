# 공기업 주요 언론 보도 조간지

키워드 관련 **오늘 발행된 기사만** 모아 매일 아침 메일로 보내고, 결과를 저장소에 누적해
검색 가능한 웹 아카이브로 만드는 자동 시스템.

GitHub Actions에서 실행되므로 **내 컴퓨터가 꺼져 있어도 동작한다.**

---

## 하는 일

```
매일 08:00 KST
  ↓
① 기사 수집      네이버 검색 API 또는 구글 뉴스 RSS
② 아카이브 갱신  data/YYYY-MM-DD.json 저장 → 저장소에 커밋
③ 메일 본문 생성 모바일 가독성 기준 HTML
④ PDF 생성       보관·회람용 (reportlab)
⑤ 메일 발송      HTML 본문 + PDF 첨부
```

결과물은 세 가지다.

| | 용도 |
|---|---|
| 메일 본문 (HTML) | 아침에 폰으로 훑어보기 |
| PDF 첨부 | 보관·전달 |
| 웹 아카이브 | 전 기간 검색·통계 |

---

## 기사 신뢰성

1. **출처 제한** — 네이버 뉴스에 색인된 등록 언론사 기사만 수집한다
2. **발행 시각 검증** — 언론사가 기록한 `pubDate` 기준 오늘 00시 이후만 통과. 시각을 못 읽으면 버린다
3. **원문 대조** — 기사마다 언론사 원문 URL을 실어 클릭 한 번으로 확인할 수 있다
4. **언론사 역추적** — 표시되는 매체명은 본문이 아니라 URL 도메인에서 추출한다
5. **집계 공개** — "검색 N건 중 시각 미달 N건, 중복 N건 제외"를 메일 상단에 명시한다
6. **빈 결과 차단** — 0건이면 발송하지 않고 워크플로를 실패시킨다

기사 전문은 저장하지 않는다. 제목·링크·요약 200자까지만 보관해 저작권 문제를 피한다.

---

## 수집원

두 가지 중 하나를 쓴다. `rss`로 시작해 나중에 `naver`로 바꿔도 된다.

| | `naver` (기본) | `rss` |
|---|---|---|
| API 키 | 필요 | **불필요** |
| 요약문 | 있음 | 없음 (제목만) |
| 링크 | 언론사 원문 직행 | 구글 경유 후 원문 |
| 매체명 | URL에서 역추적 | RSS가 직접 제공 |

`rss`로 쓰려면 Settings → Secrets and variables → Actions → **Variables** 탭 →
New repository variable → 이름 `NEWS_SOURCE`, 값 `rss`. (Secrets 탭이 아니다.)

수동 실행 시에는 Run workflow 화면에서 그때그때 고를 수 있다.

### 네이버 검색 API 키

네이버는 검색 API를 개발자센터에서 **네이버클라우드 NAVER API HUB**로 이관했다.
개발자센터 등록 화면의 '사용 API' 목록에 `검색`이 없다면 HUB에서 발급받아야 한다.

- ncloud.com → AI·NAVER API → Application 등록 → **'검색' 서비스 선택**
- 발급된 Client ID / Secret 을 `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` 에 넣는다
- 코드가 HUB 방식과 구 개발자센터 방식을 자동으로 구분하므로 별도 설정은 없다
- HUB는 종량제다. 이 시스템은 하루 5회 호출이라 미미하지만 콘솔에서 요금을 확인해 둘 것

콘솔 Application에서 '검색' 서비스를 선택하지 않으면 429 오류가 난다.

---

## 설정

### 1. 네이버 메일 SMTP 켜기

네이버 메일 → 환경설정 → POP3/IMAP 설정 → **IMAP/SMTP 사용: 사용함** → 저장

네이버는 외부 프로그램이 계정으로 메일 보내는 것을 기본 차단한다. 이걸 켜야 발송이 된다.
2단계 인증을 쓴다면 계정 비밀번호 대신 **애플리케이션 비밀번호**를 발급해 쓴다.

### 2. GitHub Secrets 등록

Settings → Secrets and variables → Actions → New repository secret

| 이름 | 값 | 필수 |
|---|---|---|
| `SMTP_HOST` | `smtp.naver.com` | ✅ |
| `SMTP_PORT` | `465` | 선택 (기본 465) |
| `SMTP_USER` | 보내는 네이버 메일 주소 | ✅ |
| `SMTP_PASS` | 네이버 비밀번호 또는 앱 비밀번호 | ✅ |
| `NOTIFY_EMAIL` | 받을 주소. 쉼표로 여러 명 가능 | ✅ |
| `NAVER_CLIENT_ID` | 검색 API Client ID | `naver` 사용 시 |
| `NAVER_CLIENT_SECRET` | 검색 API Client Secret | `naver` 사용 시 |

### 3. 쓰기 권한

Settings → Actions → General → Workflow permissions → **Read and write**

워크플로가 아카이브를 커밋하려면 필요하다.

### 4. 웹 아카이브 켜기

Settings → Pages → Source: **Deploy from a branch** → Branch: **main**, 폴더: **/docs**

`docs/` 폴더는 첫 실행 때 생성되므로 **한 번 실행한 뒤에** 설정한다.
1~2분 뒤 `https://minghwai.github.io/morning-news/` 에서 열린다.

도메인은 없어도 된다. 붙이려면 DNS에 CNAME(`news` → `minghwai.github.io`)을 추가하고
Settings → Pages → Custom domain 에 입력한 뒤 Enforce HTTPS를 켠다.

### 5. 테스트

Actions → `공기업 주요 언론 보도 조간지` → **Run workflow**

1분 안에 끝난다. 로그에 `→ 인증 방식: ...` 과 `→ 발송 완료: ...` 이 찍히면 정상이다.

---

## 사용법

### 자동 실행

매일 **08:00 KST**. 시각은 `.github/workflows/morning-news.yml` 의 cron을 UTC 기준으로 고친다.

```
'0 22 * * *'  →  07:00 KST
'0 23 * * *'  →  08:00 KST  (현재)
'30 23 * * *' →  08:30 KST
```

GitHub cron은 정시를 보장하지 않아 10~40분 늦을 수 있다.
60일간 커밋이 없으면 스케줄이 자동 정지되는데, 매일 아카이브를 커밋하므로 해당되지 않는다.

### 수동 실행

Actions → Run workflow. 키워드·수집 범위·수집원을 그때그때 바꿀 수 있다.

### 로컬 실행

```bash
pip install -r requirements.txt
export NAVER_CLIENT_ID=...
export NAVER_CLIENT_SECRET=...

python -m src.main --keyword "한국전력공사" --no-mail   # 파일만 생성
python -m src.main --keyword "한국전력공사" --dry-run   # 샘플 데이터로 레이아웃 확인
```

`output/preview_YYYYMMDD.html` 을 브라우저로 열면 메일 본문 모습 그대로 보인다.

### 옵션

| 옵션 | 설명 |
|---|---|
| `--keyword` | 검색 키워드 (필수) |
| `--source rss` | 구글 뉴스 RSS로 수집 (API 키 불필요) |
| `--hours-back 24` | 오늘 00시 대신 최근 24시간 |
| `--max-articles 50` | 최대 기사 수 (기본 30) |
| `--no-pdf` | PDF 첨부 없이 본문만 |
| `--no-mail` | 발송 없이 파일만 |
| `--no-archive` | 아카이브·사이트 갱신 생략 |
| `--allow-empty` | 기사 0건이어도 발송 |
| `--dry-run` | 샘플 데이터 (API 호출 없음) |

---

## 웹 아카이브

매일 결과가 `data/YYYY-MM-DD.json` 으로 저장소에 커밋된다.
저장소가 곧 데이터베이스이므로 서버도 DB도 필요 없고, git 히스토리가 변경 이력이 된다.

`docs/` 의 정적 페이지에서 전 기간 키워드 검색, 매체별 필터, 기간 필터를 쓸 수 있다.
상단의 일별 보도량 막대를 누르면 해당 날짜로 바로 이동한다.

기사 1건이 약 400바이트라 하루 30건 기준 연 4MB 남짓이다. 몇 년을 쌓아도 문제없다.

공개 저장소면 아카이브도 공개된다. 비공개로 두려면 저장소를 private으로 바꿔야 하고
그 경우 GitHub Pages는 유료 플랜이 필요하다. (대안: Cloudflare Pages·Netlify에 `docs/` 연결)

---

## 구조

```
src/collector.py     네이버 검색 API 수집 (HUB·구 방식 자동 판별)
src/collector_rss.py 구글 뉴스 RSS 수집 (키 불필요)
src/archive.py       일별 JSON 누적 저장 + 전체 색인 생성
src/site_builder.py  docs/index.html 정적 아카이브 사이트
src/render_html.py   메일 본문 HTML (인라인 스타일)
src/pdf_report.py    PDF 조간지 (reportlab)
src/mailer.py        SMTP 발송 (SSL/STARTTLS)
src/main.py          진입점
src/sample_data.py   --dry-run 용 샘플
data/                일별 아카이브 (Actions가 자동 커밋)
docs/                GitHub Pages로 서비스되는 정적 사이트
fonts/               나눔고딕 (PDF 한글용)
```

의존성은 `requests` 와 `reportlab` 둘뿐이다. 브라우저를 쓰지 않는다.

---

## 문제 해결

| 증상 | 원인 |
|---|---|
| 개발자센터에 `검색`이 없음 | NAVER API HUB로 이관됨. ncloud.com에서 발급 |
| 인증 실패 (401) | Client ID/Secret 오타, 또는 HUB 콘솔에서 '검색' 서비스 미선택 |
| 호출 한도 초과 (429) | HUB Application에서 '검색' 서비스를 선택했는지 확인 |
| `SMTP 로그인 실패` | 네이버 IMAP/SMTP 미사용 설정, 또는 앱 비밀번호 필요 |
| `기사가 0건입니다` | 해당 키워드의 오늘 기사가 없음. `--hours-back 24` 로 넓혀볼 것 |
| 메일이 안 옴 | Secrets 등록 확인. Actions 로그의 `HAS_MAIL` 값 확인 |
| `Permission denied` (커밋 단계) | Settings → Actions → General → Workflow permissions 를 Read and write 로 |
| 사이트가 404 | Settings → Pages 에서 Branch=main, 폴더=/docs 확인. 반영에 1~2분 |
