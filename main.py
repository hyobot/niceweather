import os
import yfinance as yf
import pandas_datareader.data as web
import requests
import pandas as pd
from datetime import datetime, timedelta

# =========================
# 환경 변수
# =========================
TELEGRAM_TOKEN = os.environ.get('TELE_TOKEN')
CHAT_ID = os.environ.get('USER_ID')

def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.get(url, params=params)

# =========================
# 데이터 수집
# =========================
def get_market_data():
    start_1y = datetime.now() - timedelta(days=400)

    vix = yf.download('^VIX', period='5d', progress=False)['Close']
    spy = yf.download('SPY', period='6mo', progress=False)['Close']
    vrt = yf.download('VRT', period='6mo', progress=False)['Close']

    hy = web.get_data_fred('BAMLH0A0HYM2', start=start_1y)
    unrate = web.get_data_fred('UNRATE', start=start_1y)

    # 🔥 EPS 데이터
    sp500_eps = web.get_data_fred('EPS', start=start_1y)  # S&P500 EPS
    spy_eps = yf.Ticker('SPY').info.get('trailingEps', None)

    return vix, spy, vrt, hy, unrate, sp500_eps, spy_eps

# =========================
# 시즌 분석
# =========================
def analyze_season():
    vix, spy, vrt, hy, unrate, sp_eps, spy_eps = get_market_data()

    current_vix = vix.iloc[-1]
    current_hy = hy.iloc[-1].item()

    # -------------------------
    # EPS 압력계
    # -------------------------
    eps_pressure = "여름"
    eps_trend = ""

    if len(sp_eps) >= 3:
        e0 = sp_eps.iloc[-1].item()
        e1 = sp_eps.iloc[-2].item()
        e2 = sp_eps.iloc[-3].item()

        if e0 < e1 < e2:
            eps_pressure = "겨울"
            eps_trend = "지수 EPS 2회 연속 하락"
        elif e0 < e1:
            eps_pressure = "가을"
            eps_trend = "지수 EPS 하락 시작"

    # -------------------------
    # 첫 눈 / 눈보라 트리거
    # -------------------------
    first_snow = []
    snowstorm = []

    # 가격 트리거
    if spy.iloc[-1] < spy.max() * 0.8:
        first_snow.append("SPY 고점 대비 -20%")

    if vrt.iloc[-1] < vrt.max() * 0.9:
        first_snow.append("AI 주변부(VRT) 모멘텀 붕괴")

    # EPS 트리거
    if eps_pressure != "여름":
        first_snow.append(f"EPS 신호: {eps_trend}")

    # 눈보라
    if current_hy >= 5.5:
        snowstorm.append("신용 스프레드 붕괴")

    if len(unrate) >= 3:
        if unrate.iloc[-1].item() > unrate.iloc[-2].item() > unrate.iloc[-3].item():
            snowstorm.append("실업률 2회 연속 상승")

    if eps_pressure == "겨울" and snowstorm:
        snowstorm.append("EPS 전염 확인")

    # -------------------------
    # 최종 판결
    # -------------------------
    if len(snowstorm) >= 2:
        verdict = "🌨️ *눈보라 개시 — 시스템 리스크 현실화*"
    elif len(first_snow) >= 2:
        verdict = "❄️ *첫 눈 확정 — 겨울 진입 준비*"
    elif current_vix >= 15 or current_hy >= 4.5:
        verdict = "🍂 *늦가을 — 현금 비중 확대*"
    else:
        verdict = "☀️ *가을 — 추세 유지*"

    # -------------------------
    # 리포트
    # -------------------------
    msg = f"""👑 *왕의 계기판 보고서* ({datetime.now().strftime('%Y-%m-%d')})

🟥 신용 압력: {current_hy:.2f}%
🟥 공포 압력(VIX): {current_vix:.2f}
🟥 EPS 압력: {eps_pressure} {eps_trend}

"""

    if first_snow:
        msg += "❄️ *첫 눈 신호*\n" + "\n".join(f"- {x}" for x in first_snow) + "\n\n"
    if snowstorm:
        msg += "🌨️ *눈보라 트리거*\n" + "\n".join(f"- {x}" for x in snowstorm) + "\n\n"

    msg += verdict

    send_telegram(msg)
    print(msg)

# =========================
if __name__ == "__main__":
    analyze_season()
