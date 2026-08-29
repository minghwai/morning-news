# 공기업 주요 언론 보도 조간지

키워드 관련 **오늘 발행된 기사만** 모아 매일 아침 메일로 보내는 자동 시스템.
GitHub Actions에서 실행되므로 **내 컴퓨터가 꺼져 있어도 동작한다.**

---

## 무엇이 달라졌나 (v1 → v2)

| | v1 | v2 |
|---|---|---|
| 뉴스 수집 | Playwright 크롤링 (마크업 바뀌면 0건) | 네이버 검색 오픈API 또는 구글 뉴스 RSS |
| 날짜 검증 | 없음 (과거 기사 섞임) | `pubDate` 기준 오늘 발행분만 |
| 출처 확인 | 신문 1면 스크린샷 (기사와 무관) | 기사별 언론사 원문 링크 |
| 브라우저 | Chromium + Xvfb 필요 | 불필요 |
| 실행 시간 | 20분+ | 약 1분 |
| 기사 0건일 때 | 빈 PDF를 그냥 발송 | 발송 중단 + 실패 처리 |
| 결과물 보관 | Artifact 90일 (용량 초과로 실패) | 저장소에 커밋 (용량 제한 없음) |
| 결과물 | PDF 첨부만 | 메일 본문 HTML + PDF 첨부 |
| 누적 | 없음 (메일함에만 남음) | `data/` 에 영구 누적 + 검색 가능한 웹 아카이브 |

---

## 설치 (최초 1회, 약 10분)

### 0단계 — 수집원 고르기

두 가지 중 하나를 쓴다. **rss로 시작해서 나중에 naver로 바꿔도 된다.**

| | `naver` (기본) | `rss` |
|---|---|---|
| API 키 | 필요 | **불필요** |
| 요약문 | 있음 | 없음 (제목만) |
| 링크 | 언론사 원문 직행 | 구글 경유 후 원문 |
| 설정 | 1단계부터 진행 | **1단계를 건너뛰고 2단계로** |

`rss`로 쓰려면 저장소 → Settings → Secrets and variables → Actions →
**Variables** 탭 → New repository variable → 이름 `NEWS_SOURCE`, 값 `rss`.
(Secret이 아니라 Variable 탭이다.)

수동 실행 시에는 Run workflow 화면에서 그때그때 고를 수도 있다.

### 1단계 — 네이버 오픈API 키 발급 (`naver` 를 쓸 때만)

1. https://developers.naver.com/apps/#/register 접속 (네이버 로그인)
2. 애플리케이션 이름: 아무거나 (예: `morning-news`)
3. **사용 API: "검색"** 선택
4. 환경 추가: **WEB 설정** → 서비스 URL에 `http://localhost` 입력

> 드롭다운은 가나다순이라 `검색`은 목록 맨 위에 있다. 안 보이면 목록 안에서 위로 스크롤할 것.
> 그래도 없으면 0단계의 `rss` 방식으로 진행하면 된다.
5. 등록하면 **Client ID**와 **Client Secret**이 나온다 → 복사

무료이며 하루 25,000회까지 호출할 수 있다. 이 시스템은 하루 최대 5회 쓴다.

### 2단계 — 네이버 메일 SMTP 켜기

네이버 메일 → 우측 상단 **환경설정** → **POP3/IMAP 설정** → **IMAP/SMTP 사용: 사용함** → 저장

2단계 인증을 쓰고 있다면 네이버 계정 비밀번호 대신 **애플리케이션 비밀번호**를 발급해서 써야 한다.

### 3단계 — GitHub Secrets 등록

저장소 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| 이름 | 값 | 필수 |
|---|---|---|
| `NAVER_CLIENT_ID` | 1단계에서 받은 Client ID | ✅ |
| `NAVER_CLIENT_SECRET` | 1단계에서 받은 Client Secret | ✅ |
| `SMTP_HOST` | `smtp.naver.com` | ✅ |
| `SMTP_PORT` | `465` | 선택 (기본 465) |
| `SMTP_USER` | 보내는 네이버 메일 주소 | ✅ |
| `SMTP_PASS` | 네이버 비밀번호 또는 앱 비밀번호 | ✅ |
| `NOTIFY_EMAIL` | 받을 주소. 쉼표로 여러 명 가능 | ✅ |

### 4단계 — 테스트

**Actions** 탭 → 좌측 `공기업 주요 언론 보도 조간지` → **Run workflow** →
키워드 입력 후 실행. 1분 안에 끝나고 메일이 도착하면 완료.

---

## 사용법

### 자동 실행
매일 **08:00 KST**. 시각을 바꾸려면 `.github/workflows/morning-news.yml`의 cron을 UTC 기준으로 수정한다.

```
'0 22 * * *'  →  07:00 KST
'0 23 * * *'  →  08:00 KST  (현재)
'30 23 * * *' →  08:30 KST
```

> GitHub cron은 정시를 보장하지 않아 10~40분 늦을 수 있다.
> 또한 **60일간 커밋이 없으면 스케줄이 자동 정지**되므로, 두 달에 한 번은 아무 커밋이나 남기는 게 좋다.

### 수동 실행
Actions 탭 → Run workflow. 키워드와 수집 범위를 그때그때 바꿀 수 있다.

### 로컬 실행

```bash
pip install -r requirements.txt
export NAVER_CLIENT_ID=...
export NAVER_CLIENT_SECRET=...

python -m src.main --keyword "한국전력공사" --no-mail   # 파일만 생성
python -m src.main --keyword "한국전력공사" --dry-run   # 샘플 데이터로 레이아웃 확인
```

`output/preview_YYYYMMDD.html`을 브라우저로 열면 메일 본문 모습 그대로 보인다.

### 옵션

| 옵션 | 설명 |
|---|---|
| `--hours-back 24` | 오늘 00시 대신 최근 24시간 |
| `--max-articles 50` | 최대 기사 수 (기본 30) |
| `--no-pdf` | PDF 첨부 없이 본문만 |
| `--no-mail` | 발송 없이 파일만 |
| `--allow-empty` | 기사 0건이어도 발송 |
| `--source rss` | 구글 뉴스 RSS로 수집 (API 키 불필요) |
| `--no-archive` | 아카이브·사이트 갱신 생략 |
| `--dry-run` | 샘플 데이터 (API 호출 없음) |

---

## 기사 신뢰성은 어떻게 확보하나

1. **출처 제한** — 네이버 뉴스에 색인된 등록 언론사 기사만 들어온다
2. **발행 시각 검증** — 언론사가 기록한 `pubDate`로 필터링. 발행 시각을 못 읽으면 버린다
3. **원문 대조** — 기사마다 언론사 원문 URL을 실어 클릭 한 번으로 확인 가능
4. **언론사 역추적** — 표시되는 언론사명은 본문이 아니라 URL 도메인에서 추출
5. **집계 공개** — "검색 N건 중 시각 미달 N건, 중복 N건 제외" 를 메일 상단에 명시
6. **빈 결과 차단** — 0건이면 발송하지 않고 워크플로를 실패시킨다

---

## 누적 아카이브 사이트

매일 실행될 때마다 결과가 `data/YYYY-MM-DD.json` 으로 **저장소에 커밋**된다.
저장소가 곧 데이터베이스이므로 별도 서버도 DB도 필요 없고, git 히스토리가 변경 이력이 된다.

`docs/` 에는 전체 기간을 검색할 수 있는 정적 페이지가 함께 생성된다.
전체 기간 키워드 검색, 매체별 필터, 일별 보도량 막대에서 날짜로 바로 이동할 수 있다.

### GitHub Pages 켜기 (무료, 도메인 불필요)

1. 저장소 → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: **main**, 폴더: **/docs** → Save
4. 1~2분 뒤 `https://minghwai.github.io/morning-news/` 에서 열린다

### 내 도메인 붙이기 (선택)

도메인은 있으면 주소가 짧아질 뿐 기능 차이는 없다. 나중에 언제든 붙일 수 있다.

1. 도메인 구입 (가비아·후이즈 등, `.com` 기준 연 1~2만원)
2. DNS에 CNAME 레코드 추가: `news` → `minghwai.github.io`
3. Settings → Pages → Custom domain 에 `news.내도메인.com` 입력
4. **Enforce HTTPS** 체크

### 데이터 규모

기사 1건이 약 400바이트다. 하루 30건이면 연 4MB 남짓이라 몇 년을 쌓아도 문제없다.
아카이브가 아주 커지면 `docs/archive.json` 을 연도별로 쪼개면 된다.

### 알아두실 점

- **공개 저장소면 아카이브도 공개된다.** 뉴스 링크 모음이라 대개 문제없지만,
  비공개로 두려면 저장소를 private으로 바꿔야 하고 그 경우 GitHub Pages는 유료 플랜이 필요하다.
  (대안: Cloudflare Pages·Netlify에 `docs/` 만 연결)
- **기사 전문은 저장하지 않는다.** 제목·링크·API 제공 요약 200자까지만 보관해 저작권 문제를 피한다.
- 아카이브 커밋이 매일 쌓이므로 **"60일 무커밋 시 스케줄 자동 정지" 문제도 자동으로 해결**된다.

---

## 구조

```
src/collector.py     네이버 오픈API 수집 + 날짜/중복 필터
src/collector_rss.py 구글 뉴스 RSS 수집 (키 불필요 대안)
src/archive.py       일별 JSON 누적 저장 + 전체 색인 생성
src/site_builder.py  docs/index.html 정적 아카이브 사이트
src/render_html.py   메일 본문 HTML (인라인 스타일)
src/pdf_report.py    PDF 조간지 (reportlab)
src/mailer.py        SMTP 발송 (SSL/STARTTLS)
src/main.py          진입점
src/sample_data.py   --dry-run 용 샘플
data/                일별 아카이브 (Actions가 자동 커밋)
docs/                GitHub Pages로 서비스되는 정적 사이트
fonts/               나눔고딕 (PDF 한글용, apt 설치 불필요)
```

## 문제 해결

| 증상 | 원인 |
|---|---|
| `네이버 API 인증 실패 (401)` | Client ID/Secret 오타, 또는 앱에 "검색" API 미추가 |
| 등록 화면에 `검색`이 안 보임 | 드롭다운을 위로 스크롤. 그래도 없으면 `NEWS_SOURCE=rss` 로 우회 |
| `SMTP 로그인 실패` | 네이버 IMAP/SMTP 미사용 설정, 또는 앱 비밀번호 필요 |
| `기사가 0건입니다` | 키워드에 해당하는 오늘 기사가 없음. `--hours-back 24` 로 넓혀볼 것 |
| 메일이 안 옴 | Secrets 5개가 다 등록됐는지 확인. Actions 로그의 `HAS_MAIL` 값 확인 |
| 스케줄이 멈춤 | 60일 무커밋으로 자동 비활성화. v2는 매일 커밋하므로 발생하지 않음 |
| `Permission denied` (커밋 단계) | Settings → Actions → General → Workflow permissions 를 **Read and write** 로 |
| `Artifact storage quota has been hit` | v2는 Artifact를 쓰지 않으므로 발생하지 않음. 기존에 쌓인 Artifact는 Actions 탭에서 삭제 |
| 사이트가 404 | Settings → Pages 에서 Branch=main, 폴더=/docs 인지 확인. 반영에 1~2분 걸림 |
