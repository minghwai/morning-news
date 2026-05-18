"""
Market data scraper for KOSPI, KOSDAQ, NYSE, 주가, 환율, SMP(육지), 유가(Dubai).
Primary: Naver Finance (via Playwright) + KPX for SMP.
Fallback: yfinance, pykrx.
"""

import re
import os
import datetime
from typing import Optional

_PLAYWRIGHT_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--no-zygote",
    "--ignore-certificate-errors",
]


def _get_browser_executable():
    custom = os.getenv("CHROME_EXECUTABLE")
    if custom and os.path.exists(custom):
        return custom
    return None


def _launch_browser():
    from playwright.sync_api import sync_playwright
    exe = _get_browser_executable()
    launch_kwargs = {"args": _PLAYWRIGHT_ARGS}
    if exe:
        launch_kwargs["executable_path"] = exe
    p = sync_playwright().start()
    browser = p.chromium.launch(**launch_kwargs)
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="ko-KR",
        ignore_https_errors=True,
    )
    page = ctx.new_page()
    return p, browser, page


def _cleanup(p, browser):
    try:
        browser.close()
    except Exception:
        pass
    try:
        p.stop()
    except Exception:
        pass


def _clean_num(text: str) -> Optional[float]:
    """Remove commas and parse float."""
    if not text:
        return None
    t = re.sub(r"[,\s원kWh달러배럴%/]", "", text.strip())
    try:
        return float(t)
    except ValueError:
        return None


def _parse_sign_change(text: str) -> Optional[float]:
    """Parse change text like +18.32 or -3.45 or ▲18.32 or ▼3.45."""
    if not text:
        return None
    t = text.strip().replace(",", "").replace("▲", "+").replace("▼", "-")
    t = re.sub(r"[^0-9.\-+]", "", t)
    try:
        return float(t)
    except ValueError:
        return None


# ─── NAVER FINANCE SCRAPERS ──────────────────────────────────────────────────

def _scrape_naver_index(page, code: str) -> dict:
    """Scrape KOSPI or KOSDAQ index from Naver Finance."""
    try:
        url = f"https://finance.naver.com/sise/sise_index.naver?code={code}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1000)

        # Current value
        val_el = page.query_selector("#now_value") or page.query_selector(".no_today .no_data em")
        price = _clean_num(val_el.inner_text()) if val_el else None

        # Change
        change_el = page.query_selector("#change_value") or page.query_selector(".no_today .no_change em")
        change_raw = (change_el.inner_text() or "").strip() if change_el else ""
        change = _parse_sign_change(change_raw)

        # Direction: check if it's up or down
        up_el = page.query_selector(".no_today .up") or page.query_selector(".no_today .dn")
        if up_el:
            class_name = up_el.get_attribute("class") or ""
            if "dn" in class_name and change and change > 0:
                change = -change

        # Percent change
        pct_el = page.query_selector("#rate_value") or page.query_selector(".no_today .no_percent em")
        pct_raw = (pct_el.inner_text() or "").strip() if pct_el else ""
        pct = _clean_num(pct_raw)
        if pct and change and change < 0 and pct > 0:
            pct = -pct

        today = datetime.date.today().strftime("%Y-%m-%d")
        result = {
            "label": code,
            "date": today,
            "price": price,
            "change": change,
            "change_pct": pct,
            "yoy_change": None,
            "yoy_pct": None,
        }

        # Try to get year-ago data from chart/history
        try:
            hist_url = f"https://finance.naver.com/sise/sise_index_day.naver?code={code}&page=253"
            page.goto(hist_url, wait_until="domcontentloaded", timeout=10000)
            rows = page.query_selector_all("table.type_1 tbody tr")
            for row in rows:
                tds = row.query_selector_all("td")
                if len(tds) >= 2:
                    date_text = (tds[0].inner_text() or "").strip()
                    close_text = (tds[1].inner_text() or "").strip()
                    if re.match(r"\d{4}\.\d{2}\.\d{2}", date_text) and close_text:
                        year_ago = _clean_num(close_text)
                        if year_ago and price:
                            yoy_change = price - year_ago
                            yoy_pct = yoy_change / year_ago * 100
                            result["yoy_change"] = round(yoy_change, 2)
                            result["yoy_pct"] = round(yoy_pct, 2)
                        break
        except Exception:
            pass

        return result

    except Exception as e:
        print(f"[market_data] _scrape_naver_index({code}) error: {e}")
        return {"label": code, "date": None, "price": None, "change": None, "change_pct": None}


def _scrape_naver_stock(page, krx_code: str, label: str) -> dict:
    """Scrape individual stock from Naver Finance using KRX code."""
    try:
        url = f"https://finance.naver.com/item/main.naver?code={krx_code}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1000)

        # Current price
        price_el = page.query_selector("#chart_area .rate_info .blind") or \
                   page.query_selector("p.no_today em") or \
                   page.query_selector(".today .no_today em")
        price = None
        if price_el:
            price = _clean_num(price_el.inner_text())

        if price is None:
            # Try alternative selector
            em_els = page.query_selector_all("#chart_area em")
            for em in em_els[:3]:
                v = _clean_num(em.inner_text())
                if v and v > 100:
                    price = v
                    break

        # Change
        change_el = page.query_selector(".today_new span.blind") or \
                    page.query_selector(".no_exday em")
        change_raw = (change_el.inner_text() or "").strip() if change_el else ""
        change = _parse_sign_change(change_raw)

        # Check direction
        down_el = page.query_selector(".today .dn")
        if down_el and change and change > 0:
            change = -change

        pct_el = page.query_selector(".today_rate em") or page.query_selector(".no_exday_rate em")
        pct_raw = (pct_el.inner_text() or "").strip() if pct_el else ""
        pct = _clean_num(pct_raw)
        if pct and change and change < 0 and pct > 0:
            pct = -pct

        today = datetime.date.today().strftime("%Y-%m-%d")
        result = {
            "label": label + " (KRX)",
            "date": today,
            "price": price,
            "change": change,
            "change_pct": pct,
            "yoy_change": None,
            "yoy_pct": None,
        }

        # Get year-ago price from historical chart data
        try:
            from_date = (datetime.date.today() - datetime.timedelta(days=370)).strftime("%Y%m%d")
            to_date = (datetime.date.today() - datetime.timedelta(days=355)).strftime("%Y%m%d")
            hist_url = (
                f"https://finance.naver.com/item/sise_day.naver?code={krx_code}"
                f"&startDate={from_date[:4]}.{from_date[4:6]}.{from_date[6:]}"
                f"&endDate={to_date[:4]}.{to_date[4:6]}.{to_date[6:]}&page=1"
            )
            page.goto(hist_url, wait_until="domcontentloaded", timeout=10000)
            rows = page.query_selector_all("table tbody tr")
            for row in rows[:5]:
                tds = row.query_selector_all("td")
                if len(tds) >= 2:
                    close_text = (tds[1].inner_text() or "").strip()
                    v = _clean_num(close_text)
                    if v and v > 100:
                        if price:
                            yoy_change = price - v
                            yoy_pct = yoy_change / v * 100
                            result["yoy_change"] = round(yoy_change, 0)
                            result["yoy_pct"] = round(yoy_pct, 2)
                        break
        except Exception:
            pass

        return result

    except Exception as e:
        print(f"[market_data] _scrape_naver_stock({krx_code}) error: {e}")
        return {"label": label + " (KRX)", "date": None, "price": None, "change": None, "change_pct": None}


def _scrape_naver_exchange(page) -> dict:
    """Scrape USD/KRW exchange rate from Naver Finance."""
    try:
        url = "https://finance.naver.com/marketindex/exchangeDetail.naver?marketindexCd=FX_USDKRW"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1000)

        price_el = page.query_selector(".today .rate") or \
                   page.query_selector("span.rate_num") or \
                   page.query_selector(".tit em")
        price = _clean_num(price_el.inner_text()) if price_el else None

        change_el = page.query_selector(".today .change") or page.query_selector(".today em")
        change_raw = (change_el.inner_text() or "").strip() if change_el else ""
        change = _parse_sign_change(change_raw)

        down_el = page.query_selector(".today .down")
        if down_el and change and change > 0:
            change = -change

        pct = (change / (price - change) * 100) if price and change else None

        today = datetime.date.today().strftime("%Y-%m-%d")
        return {
            "label": "환율 (USD/KRW)",
            "date": today,
            "price": price,
            "unit": "원",
            "change": change,
            "change_pct": round(pct, 2) if pct else None,
            "yoy_change": None,
            "yoy_pct": None,
        }
    except Exception as e:
        print(f"[market_data] _scrape_naver_exchange error: {e}")
        return {"label": "환율 (USD/KRW)", "date": None, "price": None, "unit": "원"}


def _scrape_naver_oil(page) -> dict:
    """Scrape Dubai crude oil price from Naver Finance."""
    try:
        url = "https://finance.naver.com/marketindex/oilDetail.naver?marketindexCd=OIL_DXB"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1000)

        price_el = page.query_selector(".today .rate") or page.query_selector("span.rate_num")
        price = _clean_num(price_el.inner_text()) if price_el else None

        change_el = page.query_selector(".today .change")
        change_raw = (change_el.inner_text() or "").strip() if change_el else ""
        change = _parse_sign_change(change_raw)

        down_el = page.query_selector(".today .down")
        if down_el and change and change > 0:
            change = -change

        pct = (change / (price - change) * 100) if price and change else None

        today = datetime.date.today().strftime("%Y-%m-%d")
        return {
            "label": "유가 (Dubai)",
            "date": today,
            "price": price,
            "unit": "USD/배럴",
            "change": change,
            "change_pct": round(pct, 2) if pct else None,
            "yoy_change": None,
            "yoy_pct": None,
        }
    except Exception as e:
        print(f"[market_data] _scrape_naver_oil error: {e}")
        return {"label": "유가 (Dubai)", "date": None, "price": None, "unit": "USD/배럴"}


def _scrape_nyse_stock(page, ticker: str, label: str) -> dict:
    """Scrape NYSE stock from Yahoo Finance."""
    try:
        url = f"https://finance.yahoo.com/quote/{ticker}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)

        # Yahoo Finance price selector
        price_el = page.query_selector(f'[data-symbol="{ticker}"] fin-streamer[data-field="regularMarketPrice"]') or \
                   page.query_selector('fin-streamer[data-field="regularMarketPrice"]') or \
                   page.query_selector('span[data-testid="qsp-price"]')
        price = _clean_num(price_el.inner_text()) if price_el else None

        change_el = page.query_selector('fin-streamer[data-field="regularMarketChange"]') or \
                    page.query_selector('span[data-testid="qsp-price-change"]')
        change_raw = (change_el.inner_text() or "").strip() if change_el else ""
        change = _parse_sign_change(change_raw)

        pct_el = page.query_selector('fin-streamer[data-field="regularMarketChangePercent"]') or \
                 page.query_selector('span[data-testid="qsp-price-change-percent"]')
        pct_raw = re.sub(r'[()%]', '', (pct_el.inner_text() or "")) if pct_el else ""
        pct = _clean_num(pct_raw)

        today = datetime.date.today().strftime("%Y-%m-%d")
        return {
            "label": f"{label} (NYSE)",
            "date": today,
            "price": price,
            "change": change,
            "change_pct": pct,
            "yoy_change": None,
            "yoy_pct": None,
        }
    except Exception as e:
        print(f"[market_data] _scrape_nyse_stock({ticker}) error: {e}")
        return {"label": f"{label} (NYSE)", "date": None, "price": None, "change": None, "change_pct": None}


def _scrape_smp_kpx(page) -> dict:
    """Scrape SMP (육지) from KPX EPSIS."""
    try:
        today = datetime.date.today()
        from_dt = (today - datetime.timedelta(days=30)).strftime("%Y%m%d")
        to_dt = today.strftime("%Y%m%d")

        url = (
            "https://epsis.kpx.or.kr/epsisnew/selectEkmaSmpShdGrid.do"
        )
        # POST request via Playwright fetch
        result_json = page.evaluate(
            f"""async () => {{
                const resp = await fetch('{url}', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                    body: 'searchStartDate={from_dt}&searchEndDate={to_dt}&areaCd=01'
                }});
                return await resp.json();
            }}"""
        )
        rows = (result_json or {}).get("smpShdList", [])
        if rows:
            latest = rows[-1]
            price = float(latest.get("avgSmp", 0) or 0)
            date_str = str(latest.get("ym", today.strftime("%Y-%m")))
            prev_rows = [r for r in rows if r != latest]
            prev_price = float(prev_rows[-1].get("avgSmp", price)) if prev_rows else price
            change = price - prev_price

            return {
                "label": "SMP (육지)",
                "date": date_str,
                "price": round(price, 2),
                "unit": "원/kWh",
                "change": round(change, 2) if change != 0 else None,
                "change_pct": round(change / prev_price * 100, 2) if prev_price and change != 0 else None,
                "yoy_change": None,
                "yoy_pct": None,
            }
    except Exception:
        pass

    # Fallback: scrape KPX board
    try:
        url2 = "https://www.kpx.or.kr/board.do?boardConfigNo=2&menuId=297"
        page.goto(url2, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1000)
        rows = page.query_selector_all("table tbody tr")
        for row in rows[:3]:
            tds = row.query_selector_all("td")
            if len(tds) >= 2:
                date_text = (tds[0].inner_text() or "").strip()
                price_text = (tds[1].inner_text() or "").strip()
                price = _clean_num(price_text)
                if price:
                    return {
                        "label": "SMP (육지)",
                        "date": date_text,
                        "price": price,
                        "unit": "원/kWh",
                        "change": None,
                        "change_pct": None,
                        "yoy_change": None,
                        "yoy_pct": None,
                    }
    except Exception as e:
        print(f"[market_data] _scrape_smp_kpx error: {e}")

    return {"label": "SMP (육지)", "date": None, "price": None, "unit": "원/kWh"}


# ─── YFINANCE FALLBACK ────────────────────────────────────────────────────────

def _yf_get(ticker: str, label: str) -> dict:
    """Fallback yfinance data fetch."""
    try:
        import yfinance as yf
        import pandas as pd
        df = yf.download(ticker, period="5d", progress=False, auto_adjust=True)
        if df.empty:
            return {"label": label}
        closes = df["Close"].dropna()
        if len(closes) < 1:
            return {"label": label}
        price = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) >= 2 else price
        change = price - prev
        pct = change / prev * 100 if prev else 0
        date_str = closes.index[-1].strftime("%Y-%m-%d")

        # YoY
        df_yr = yf.download(ticker, period="13mo", progress=False, auto_adjust=True)
        yoy_change = yoy_pct = None
        if not df_yr.empty:
            closes_yr = df_yr["Close"].dropna()
            target = closes_yr.index[-1] - pd.Timedelta(days=365)
            past = closes_yr[closes_yr.index <= target]
            if not past.empty:
                year_ago = float(past.iloc[-1])
                yoy_change = round(price - year_ago, 2)
                yoy_pct = round(yoy_change / year_ago * 100, 2)

        return {
            "label": label,
            "date": date_str,
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(pct, 2),
            "yoy_change": yoy_change,
            "yoy_pct": yoy_pct,
        }
    except Exception:
        return {"label": label}


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def collect_market_data(keyword: str, company_info: dict) -> list[dict]:
    """
    Collect all market data rows.
    Tries Naver Finance via Playwright first, then yfinance as fallback.
    """
    from playwright.sync_api import sync_playwright

    exe = _get_browser_executable()
    launch_kwargs = {"args": _PLAYWRIGHT_ARGS}
    if exe:
        launch_kwargs["executable_path"] = exe

    rows = []
    p = browser = page = None

    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(**launch_kwargs)
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="ko-KR",
            ignore_https_errors=True,
        )
        page = ctx.new_page()

        print("      → KOSPI 수집 중...")
        kospi = _scrape_naver_index(page, "KOSPI")
        kospi["label"] = "KOSPI"
        rows.append(kospi)

        print("      → KOSDAQ 수집 중...")
        kosdaq = _scrape_naver_index(page, "KOSDAQ")
        kosdaq["label"] = "KOSDAQ"
        rows.append(kosdaq)

        print("      → NYSE 수집 중...")
        # NYSE Composite
        nyse = _yf_get("^NYA", "NYSE 종합")
        if not nyse.get("price"):
            nyse = _yf_get("^IXIC", "NASDAQ")
        rows.append(nyse)

        krx_code = company_info.get("krx")
        nyse_ticker = company_info.get("nyse")
        label = company_info.get("name", keyword)

        if krx_code:
            print(f"      → {label} (KRX) 수집 중...")
            stock_krx = _scrape_naver_stock(page, krx_code, label)
            rows.append(stock_krx)

        if nyse_ticker:
            print(f"      → {label} (NYSE) 수집 중...")
            stock_nyse = _scrape_nyse_stock(page, nyse_ticker, label)
            rows.append(stock_nyse)

        print("      → 환율 수집 중...")
        exchange = _scrape_naver_exchange(page)
        rows.append(exchange)

        print("      → SMP 수집 중...")
        smp = _scrape_smp_kpx(page)
        rows.append(smp)

        print("      → 유가(Dubai) 수집 중...")
        oil = _scrape_naver_oil(page)
        rows.append(oil)

    except Exception as e:
        print(f"[market_data] Playwright session error: {e}")
        # Full yfinance fallback
        rows = [
            _yf_get("^KS11", "KOSPI"),
            _yf_get("^KQ11", "KOSDAQ"),
            _yf_get("^NYA", "NYSE 종합"),
        ]
        if company_info.get("nyse"):
            rows.append(_yf_get(company_info["nyse"], company_info.get("name", keyword) + " (NYSE)"))
        rows += [
            _yf_get("USDKRW=X", "환율 (USD/KRW)"),
            {"label": "SMP (육지)", "price": None, "unit": "원/kWh"},
            _yf_get("BZ=F", "유가 (Dubai 추정, Brent 기준)"),
        ]

    finally:
        try:
            if browser:
                browser.close()
        except Exception:
            pass
        try:
            if 'pw' in dir():
                pw.stop()
        except Exception:
            pass

    return rows
