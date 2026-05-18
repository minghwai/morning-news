"""
Market data scraper: KOSPI, KOSDAQ, NYSE, 환율, SMP(육지), 유가(Dubai).
"""

import time
import datetime
import requests
from bs4 import BeautifulSoup

# yfinance import with fallback
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False

try:
    from pykrx import stock as krx_stock
    HAS_PYKRX = True
except ImportError:
    HAS_PYKRX = False


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _safe_yf_download(ticker: str, period: str = "5d") -> dict:
    """Download recent OHLCV from yfinance and return last two close prices."""
    if not HAS_YFINANCE:
        return {}
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if df.empty:
            return {}
        closes = df["Close"].dropna()
        if len(closes) < 1:
            return {}
        latest_date = closes.index[-1]
        latest_close = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else latest_close
        change = latest_close - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        return {
            "date": latest_date.strftime("%Y-%m-%d"),
            "price": latest_close,
            "change": change,
            "change_pct": change_pct,
        }
    except Exception:
        return {}


def _yf_annual_compare(ticker: str) -> dict:
    """Fetch ~1 year of data to get year-ago price for comparison."""
    if not HAS_YFINANCE:
        return {}
    try:
        df = yf.download(ticker, period="13mo", progress=False, auto_adjust=True)
        if df.empty:
            return {}
        closes = df["Close"].dropna()
        if len(closes) < 2:
            return {}
        latest = float(closes.iloc[-1])
        # Find the price approximately 1 year ago
        target = closes.index[-1] - datetime.timedelta(days=365)
        past = closes[closes.index <= target]
        if past.empty:
            return {}
        year_ago = float(past.iloc[-1])
        yoy_change = latest - year_ago
        yoy_pct = (yoy_change / year_ago * 100) if year_ago else 0
        return {"yoy_change": yoy_change, "yoy_pct": yoy_pct, "year_ago_price": year_ago}
    except Exception:
        return {}


def get_kospi() -> dict:
    data = _safe_yf_download("^KS11")
    yoy = _yf_annual_compare("^KS11")
    return {"label": "KOSPI", **data, **yoy}


def get_kosdaq() -> dict:
    data = _safe_yf_download("^KQ11")
    yoy = _yf_annual_compare("^KQ11")
    return {"label": "KOSDAQ", **data, **yoy}


def get_nyse() -> dict:
    data = _safe_yf_download("^NYA")
    yoy = _yf_annual_compare("^NYA")
    return {"label": "NYSE 종합", **data, **yoy}


def get_company_stock_krx(krx_code: str, label: str) -> dict:
    """Get Korean listed company stock price via pykrx."""
    if not HAS_PYKRX or not krx_code:
        return {"label": label + " (KRX)"}
    try:
        today = datetime.date.today()
        from_date = (today - datetime.timedelta(days=10)).strftime("%Y%m%d")
        to_date = today.strftime("%Y%m%d")
        df = krx_stock.get_market_ohlcv_by_date(from_date, to_date, krx_code)
        if df.empty:
            return {"label": label + " (KRX)"}
        closes = df["종가"].dropna()
        if len(closes) < 1:
            return {"label": label + " (KRX)"}
        latest_date = closes.index[-1]
        latest_close = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else latest_close
        change = latest_close - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        # Year-ago
        from_yr = (today - datetime.timedelta(days=370)).strftime("%Y%m%d")
        to_yr = (today - datetime.timedelta(days=355)).strftime("%Y%m%d")
        df_yr = krx_stock.get_market_ohlcv_by_date(from_yr, to_yr, krx_code)
        yoy_change = yoy_pct = year_ago_price = None
        if not df_yr.empty:
            closes_yr = df_yr["종가"].dropna()
            if len(closes_yr) > 0:
                year_ago_price = float(closes_yr.iloc[-1])
                yoy_change = latest_close - year_ago_price
                yoy_pct = (yoy_change / year_ago_price * 100) if year_ago_price else 0
        return {
            "label": label + " (KRX)",
            "date": str(latest_date.date()),
            "price": latest_close,
            "change": change,
            "change_pct": change_pct,
            "yoy_change": yoy_change,
            "yoy_pct": yoy_pct,
            "year_ago_price": year_ago_price,
        }
    except Exception as e:
        return {"label": label + " (KRX)", "error": str(e)}


def get_company_stock_nyse(nyse_ticker: str, label: str) -> dict:
    """Get NYSE-listed company stock price."""
    if not nyse_ticker:
        return {}
    data = _safe_yf_download(nyse_ticker)
    yoy = _yf_annual_compare(nyse_ticker)
    return {"label": label + " (NYSE)", **data, **yoy}


def get_exchange_rate() -> dict:
    """USD/KRW exchange rate."""
    data = _safe_yf_download("USDKRW=X", period="5d")
    yoy = _yf_annual_compare("USDKRW=X")
    return {"label": "환율 (USD/KRW)", **data, **yoy}


def get_smp_land() -> dict:
    """SMP (System Marginal Price) 육지 - scrape from KPX."""
    try:
        url = "https://www.kpx.or.kr/board.do?boardConfigNo=2&menuId=297"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "lxml")
        # Find the most recent SMP table row
        rows = soup.select("table tbody tr")
        for row in rows[:3]:
            cols = [td.get_text(strip=True) for td in row.select("td")]
            if len(cols) >= 3:
                try:
                    date_str = cols[0]
                    price = float(cols[1].replace(",", ""))
                    prev_price = float(cols[2].replace(",", "")) if len(cols) > 2 else price
                    change = price - prev_price
                    change_pct = (change / prev_price * 100) if prev_price else 0
                    return {
                        "label": "SMP (육지)",
                        "date": date_str,
                        "price": price,
                        "unit": "원/kWh",
                        "change": change,
                        "change_pct": change_pct,
                    }
                except (ValueError, IndexError):
                    continue
    except Exception:
        pass
    # Fallback: try alternative URL
    try:
        url2 = "https://epsis.kpx.or.kr/epsisnew/selectEkmaSmpShdGrid.do"
        today = datetime.date.today()
        payload = {
            "searchStartDate": (today - datetime.timedelta(days=7)).strftime("%Y%m%d"),
            "searchEndDate": today.strftime("%Y%m%d"),
            "areaCd": "01",  # 육지
        }
        resp = requests.post(url2, data=payload, headers=HEADERS, timeout=10)
        data = resp.json()
        rows = data.get("smpShdList", [])
        if rows:
            latest = rows[-1]
            price = float(latest.get("smp", 0))
            return {
                "label": "SMP (육지)",
                "date": latest.get("ym", today.strftime("%Y-%m-%d")),
                "price": price,
                "unit": "원/kWh",
                "change": None,
                "change_pct": None,
            }
    except Exception:
        pass
    return {"label": "SMP (육지)", "price": None, "date": None, "unit": "원/kWh"}


def get_dubai_oil() -> dict:
    """Dubai crude oil price - try multiple sources."""
    # Try yfinance MCO=F (not ideal for Dubai but is crude proxy)
    # Best: scrape Investing.com or KESIS
    try:
        url = "https://www.kesis.net/sub/sub_0100300.jsp"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "lxml")
        rows = soup.select("table tbody tr")
        for row in rows[:5]:
            cols = [td.get_text(strip=True) for td in row.select("td")]
            if len(cols) >= 2:
                try:
                    price = float(cols[1].replace(",", ""))
                    return {
                        "label": "유가 (Dubai)",
                        "date": cols[0],
                        "price": price,
                        "unit": "USD/배럴",
                        "change": None,
                        "change_pct": None,
                    }
                except (ValueError, IndexError):
                    continue
    except Exception:
        pass
    # Fallback: Brent crude via yfinance as proxy
    if HAS_YFINANCE:
        try:
            data = _safe_yf_download("BZ=F")
            yoy = _yf_annual_compare("BZ=F")
            if data.get("price"):
                return {
                    "label": "유가 (Dubai 추정, Brent 기준)",
                    "unit": "USD/배럴",
                    **data,
                    **yoy,
                }
        except Exception:
            pass
    return {"label": "유가 (Dubai)", "price": None, "date": None, "unit": "USD/배럴"}


def collect_market_data(keyword: str, company_info: dict) -> list[dict]:
    """
    Collect all market data rows for the given company keyword.
    Returns list of dicts suitable for PDF table rendering.
    """
    rows = []

    rows.append(get_kospi())
    rows.append(get_kosdaq())
    rows.append(get_nyse())

    krx_code = company_info.get("krx")
    nyse_ticker = company_info.get("nyse")
    company_label = company_info.get("name", keyword)

    if krx_code:
        rows.append(get_company_stock_krx(krx_code, company_label))

    if nyse_ticker:
        rows.append(get_company_stock_nyse(nyse_ticker, company_label))

    rows.append(get_exchange_rate())
    rows.append(get_smp_land())
    rows.append(get_dubai_oil())

    return rows
