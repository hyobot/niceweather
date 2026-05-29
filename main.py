import os
import requests
import yfinance as yf
import pandas as pd
import pandas_datareader.data as web
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from datetime import datetime, timedelta
from pathlib import Path


# =========================
# [설정]
# =========================

TELEGRAM_TOKEN = os.environ.get("TELE_TOKEN")
CHAT_ID = os.environ.get("USER_ID")

DATA_DIR = Path("data")
CHART_DIR = Path("charts")

DATA_DIR.mkdir(exist_ok=True)
CHART_DIR.mkdir(exist_ok=True)

MARKET_HISTORY_PATH = DATA_DIR / "market_history.csv"
DASHBOARD_HISTORY_PATH = DATA_DIR / "dashboard_history.csv"

TODAY = datetime.now().strftime("%Y-%m-%d")


MARKET_DATA = {
    "1. Currencies & Crypto": {
        "Dollar Idx": "DX-Y.NYB",
        "Euro FX": "6E=F",
        "Jap Yen": "6J=F",
        "CNH(Yuan)": "CNY=X",
        "Bitcoin": "BTC-USD",
    },
    "2. US Indices & VIX": {
        "VIX": "^VIX",
        "S&P 500": "ES=F",
        "Nasdaq": "NQ=F",
        "Dow Jones": "YM=F",
        "Russell": "RTY=F",
    },
    "3. Global Indices": {
        "Euro Stoxx": "^STOXX50E",
        "Hang Seng": "^HSI",
        "H-Share": "^HSCE",
        "Nikkei 225": "^N225",
    },
    "4. US Treasuries (Yield)": {
        "US 2Y Yld": "^IRX",
        "US 10Y Yld": "^TNX",
        "US 30Y Yld": "^TYX",
    },
    "5. Commodities": {
        "Gold": "GC=F",
        "Silver": "SI=F",
        "Copper": "HG=F",
        "Crude Oil": "CL=F",
        "Nat Gas": "NG=F",
    },
}


# =========================
# [텔레그램]
# =========================

def send_telegram_text(message, parse_mode="HTML"):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram Token/ID missing.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    params = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": parse_mode,
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        if response.status_code != 200:
            print(f"Telegram text send failed: {response.text}")
    except Exception as e:
        print(f"Telegram text send error: {e}")


def send_telegram_photo(image_path, caption=None):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram Token/ID missing.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"

    try:
        with open(image_path, "rb") as photo:
            files = {"photo": photo}
            data = {"chat_id": CHAT_ID}

            if caption:
                data["caption"] = caption

            response = requests.post(url, data=data, files=files, timeout=30)

        if response.status_code != 200:
            print(f"Telegram photo send failed: {response.text}")

    except Exception as e:
        print(f"Telegram photo send error: {e}")


# =========================
# [공통 유틸]
# =========================

def safe_float(value):
    try:
        if hasattr(value, "item"):
            return float(value.item())
        return float(value)
    except Exception:
        return None


def load_csv(path):
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def save_csv(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")


def get_close_series(ticker, period="2mo"):
    df = yf.download(ticker, period=period, progress=False, auto_adjust=False)

    if df.empty:
        return pd.Series(dtype=float)

    if isinstance(df.columns, pd.MultiIndex):
        try:
            close = df["Close"][ticker]
        except Exception:
            close = df.xs(ticker, level=1, axis=1)["Close"]
    else:
        close = df["Close"]

    close = close.dropna()
    return close


def get_price_reaction(ticker, days=5):
    try:
        close = get_close_series(ticker, period="1mo")
        if len(close) <= days:
            return 0.0
        return float(close.pct_change(days).iloc[-1])
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return 0.0


# =========================
# [Part 1] 왕의 계기판
# =========================

def get_macro_data():
    try:
        start_date = datetime.now() - timedelta(days=730)

        cpatax = web.get_data_fred("CPATAX", start=start_date)
        hy_spread = web.get_data_fred("BAMLH0A0HYM2", start=start_date)
        vix = get_close_series("^VIX", period="2mo")

        return cpatax.dropna(), vix.dropna(), hy_spread.dropna()

    except Exception as e:
        print(f"Macro Data Error: {e}")
        return None, None, None


def report_kings_dashboard():
    print(">>> [Part 1] 왕의 계기판 분석 시작...")

    cpatax, vix, hy = get_macro_data()

    if cpatax is None or vix is None or hy is None:
        send_telegram_text("❌ [왕의 계기판] 데이터 수집 실패")
        return None

    curr_vix = safe_float(vix.iloc[-1])
    curr_hy = safe_float(hy.iloc[-1])

    c0 = safe_float(cpatax.iloc[-1])
    c1 = safe_float(cpatax.iloc[-2])
    c2 = safe_float(cpatax.iloc[-3])

    real_season = "여름"
    season_msg = "이익 성장 지속"

    if c0 < c1 < c2:
        real_season = "겨울"
        season_msg = "기업이익 2분기 연속 하락"
    elif c0 < c1:
        real_season = "가을"
        season_msg = "기업이익 꺾임"

    first_snow = []
    snowstorm = []

    target_assets = ["SPY", "QQQ", "VRT"]
    earnings_bad = []

    for ticker in target_assets:
        r = get_price_reaction(ticker, days=5)
        if r < -0.03:
            earnings_bad.append(f"{ticker} 급락 ({r * 100:.1f}%)")

    eps_contagion = len(earnings_bad) >= 2

    if eps_contagion:
        first_snow.append("EPS 전염 시작")
        first_snow.extend(earnings_bad)

    if curr_hy is not None and curr_hy >= 5.5:
        snowstorm.append(f"신용 스프레드 위험 ({curr_hy:.2f}%)")

    row = {
        "date": TODAY,
        "season": real_season,
        "cpatax": c0,
        "vix": curr_vix,
        "hy_spread": curr_hy,
        "eps_contagion": eps_contagion,
    }

    hist = load_csv(DASHBOARD_HISTORY_PATH)
    hist = pd.concat([hist, pd.DataFrame([row])], ignore_index=True)
    hist = hist.drop_duplicates(subset=["date"], keep="last")
    save_csv(hist, DASHBOARD_HISTORY_PATH)

    msg = f"""
👑 <b>왕의 계기판</b> ({TODAY})

<b>1. 실물 압력계</b>
- 상태: {real_season}
- 진단: {season_msg}

<b>2. 시장 반응성</b>
- 상태: {"🔥 투매 발생" if eps_contagion else "✅ 지지력 확인"}

<b>3. 시스템 위험도</b>
- VIX: {curr_vix:.2f}
- Spread: {curr_hy:.2f}%
"""

    if first_snow:
        msg += "\n❄️ <b>[경고] 첫 눈</b>\n"
        msg += "\n".join(f"- {x}" for x in first_snow)

    if snowstorm:
        msg += "\n\n🌩️ <b>[위험] 눈보라</b>\n"
        msg += "\n".join(f"- {x}" for x in snowstorm)

    send_telegram_text(msg.strip(), parse_mode="HTML")

    return hist


# =========================
# [Part 2] 시장 데이터 수집
# =========================

def collect_market_rows():
    rows = []

    for category, tickers in MARKET_DATA.items():
        for name, ticker in tickers.items():
            try:
                close = get_close_series(ticker, period="5d")

                if len(close) < 1:
                    price = None
                    chg_pct = None
                else:
                    price = safe_float(close.iloc[-1])

                    if len(close) >= 2:
                        prev = safe_float(close.iloc[-2])
                        chg_pct = ((price - prev) / prev) * 100 if prev else None
                    else:
                        chg_pct = None

                rows.append({
                    "date": TODAY,
                    "category": category,
                    "item": name,
                    "ticker": ticker,
                    "price": price,
                    "chg_pct": chg_pct,
                })

            except Exception as e:
                print(f"Market data error: {name} / {ticker} / {e}")
                rows.append({
                    "date": TODAY,
                    "category": category,
                    "item": name,
                    "ticker": ticker,
                    "price": None,
                    "chg_pct": None,
                })

    return pd.DataFrame(rows)


def update_market_history(today_df):
    hist = load_csv(MARKET_HISTORY_PATH)
    hist = pd.concat([hist, today_df], ignore_index=True)
    hist = hist.drop_duplicates(subset=["date", "item", "ticker"], keep="last")
    save_csv(hist, MARKET_HISTORY_PATH)
    return hist


def format_price(value):
    if value is None or pd.isna(value):
        return "N/A"

    if value > 1000:
        return f"{value:,.0f}"
    elif value < 5:
        return f"{value:.3f}"
    else:
        return f"{value:,.2f}"


def report_market_text(today_df):
    lines = []
    lines.append("📊 <b>[Global Market Brief]</b>")
    lines.append("<pre>")

    for category in MARKET_DATA.keys():
        part = today_df[today_df["category"] == category]

        lines.append(f"\n[{category}]")
        lines.append(f"{'Item':<10} {'Price':>9} {'Chg%':>7}")
        lines.append("-" * 29)

        for _, row in part.iterrows():
            name = row["item"]
            price = format_price(row["price"])
            chg = row["chg_pct"]

            if chg is None or pd.isna(chg):
                chg_str = "-"
            else:
                symbol = "▲" if chg > 0 else "▼" if chg < 0 else "."
                chg_str = f"{symbol}{abs(chg):.1f}"

            lines.append(f"{name:<10} {price:>9} {chg_str:>7}")

    lines.append("</pre>")

    send_telegram_text("\n".join(lines), parse_mode="HTML")


# =========================
# [Part 3] 그래프 생성
# =========================

def plot_dashboard_chart(dashboard_hist):
    if dashboard_hist.empty or len(dashboard_hist) < 2:
        return None

    df = dashboard_hist.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").tail(90)

    fig, ax1 = plt.subplots(figsize=(10, 5))

    ax1.plot(df["date"], df["vix"], marker="o", linewidth=2, label="VIX")
    ax1.set_ylabel("VIX")
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(df["date"], df["hy_spread"], marker="o", linewidth=2, label="HY Spread")
    ax2.set_ylabel("HY Spread (%)")

    plt.title("King's Dashboard: System Risk Trend")
    fig.autofmt_xdate()

    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper left")

    path = CHART_DIR / "dashboard_risk.png"
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()

    return path


def plot_daily_change_bar(today_df):
    df = today_df.dropna(subset=["chg_pct"]).copy()
    if df.empty:
        return None

    df = df.sort_values("chg_pct")

    plt.figure(figsize=(10, 8))
    plt.barh(df["item"], df["chg_pct"])
    plt.axvline(0, linewidth=1)
    plt.title(f"Daily Change % Snapshot ({TODAY})")
    plt.xlabel("Change (%)")
    plt.grid(axis="x", alpha=0.3)

    path = CHART_DIR / "daily_change_bar.png"
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()

    return path


def plot_category_trend(market_hist):
    if market_hist.empty:
        return []

    df = market_hist.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    paths = []

    for category in MARKET_DATA.keys():
        part = df[df["category"] == category].copy()

        if part["date"].nunique() < 2:
            continue

        pivot = part.pivot_table(
            index="date",
            columns="item",
            values="price",
            aggfunc="last"
        ).sort_index()

        pivot = pivot.tail(30)
        pivot = pivot.dropna(axis=1, how="all")

        if pivot.empty or len(pivot) < 2:
            continue

        normalized = pivot / pivot.iloc[0] * 100

        plt.figure(figsize=(10, 5))

        for col in normalized.columns:
            plt.plot(normalized.index, normalized[col], marker="o", linewidth=2, label=col)

        plt.axhline(100, linewidth=1)
        plt.title(f"{category} - 30D Normalized Trend")
        plt.ylabel("Start = 100")
        plt.grid(True, alpha=0.3)
        plt.legend(fontsize=8)
        plt.xticks(rotation=30)

        safe_name = category.replace(" ", "_").replace(".", "").replace("&", "and").replace("(", "").replace(")", "")
        path = CHART_DIR / f"{safe_name}.png"

        plt.tight_layout()
        plt.savefig(path, dpi=160)
        plt.close()

        paths.append(path)

    return paths


# =========================
# [실행]
# =========================

if __name__ == "__main__":
    dashboard_hist = report_kings_dashboard()

    today_market_df = collect_market_rows()
    market_hist = update_market_history(today_market_df)

    report_market_text(today_market_df)

    dashboard_chart = plot_dashboard_chart(dashboard_hist)
    daily_bar_chart = plot_daily_change_bar(today_market_df)
    category_charts = plot_category_trend(market_hist)

    if dashboard_chart:
        send_telegram_photo(dashboard_chart, "👑 왕의 계기판: 시스템 위험 추이")

    if daily_bar_chart:
        send_telegram_photo(daily_bar_chart, "📊 오늘의 자산별 등락률")

    for chart in category_charts:
        send_telegram_photo(chart, "📈 30일 정규화 추이")
