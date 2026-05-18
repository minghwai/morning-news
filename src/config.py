import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
FONTS_DIR = BASE_DIR / "fonts"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

CHROME_EXECUTABLE = os.getenv(
    "CHROME_EXECUTABLE",
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
)

FONT_REGULAR = str(FONTS_DIR / "NanumGothic.ttf")
FONT_BOLD = str(FONTS_DIR / "NanumGothicBold.ttf")

# 12 newspapers in 가나다 order for the headline section
NEWSPAPERS = [
    {"name": "경향신문",  "url": "https://www.khan.co.kr/",            "section": ".headline, .art-tit, h1, h2"},
    {"name": "국민일보",  "url": "https://www.kmib.co.kr/",            "section": ".headline, .tit, h1, h2"},
    {"name": "동아일보",  "url": "https://www.donga.com/",             "section": ".title, h1, h2"},
    {"name": "서울신문",  "url": "https://www.seoul.co.kr/",           "section": ".title, h1, h2"},
    {"name": "세계일보",  "url": "https://www.segye.com/",             "section": ".title, h1, h2"},
    {"name": "조선일보",  "url": "https://www.chosun.com/",            "section": ".title, h1, h2"},
    {"name": "중앙일보",  "url": "https://www.joongang.co.kr/",        "section": ".title, h1, h2"},
    {"name": "한겨레",   "url": "https://www.hani.co.kr/",            "section": ".title, h1, h2"},
    {"name": "한국일보",  "url": "https://www.hankookilbo.com/",       "section": ".title, h1, h2"},
    {"name": "매일경제",  "url": "https://www.mk.co.kr/",             "section": ".title, h1, h2"},
    {"name": "서울경제",  "url": "https://www.sedaily.com/",           "section": ".title, h1, h2"},
    {"name": "한국경제",  "url": "https://www.hankyung.com/",          "section": ".title, h1, h2"},
]

# Map of company keyword → KRX stock code + NYSE ticker
COMPANY_STOCK_MAP = {
    "한국전력공사": {"krx": "015760", "nyse": "KEP",  "name": "한국전력"},
    "한국가스공사": {"krx": "036460", "nyse": None,   "name": "한국가스공사"},
    "한국수력원자력": {"krx": None,    "nyse": None,   "name": "한수원"},
    "한국도로공사": {"krx": None,     "nyse": None,   "name": "한국도로공사"},
    "한국철도공사": {"krx": None,     "nyse": None,   "name": "코레일"},
    "LH":          {"krx": None,     "nyse": None,   "name": "LH"},
}

NEWS_COUNT = 20
SCHEDULE_HOUR = 8
SCHEDULE_MINUTE = 0
