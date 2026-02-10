import os
import yfinance as yf
import pandas_datareader.data as web
import requests
import pandas as pd
from datetime import datetime, timedelta

# =========================
# [설정] 환경 변수 및 텔레그램 함수
# =========================
TELEGRAM_TOKEN = os.environ.get('TELE_TOKEN')
CHAT_ID = os.environ.get('USER_ID')

def send_telegram(message, parse_mode="Markdown"):
    """
    메시지 전송 함수
    parse_mode: 'Markdown' (기존 보고서용) 또는 'HTML' (표 정렬용)
    """
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram Token/ID missing.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": parse_mode
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code != 200:
            print(f"Telegram Send Failed: {response.text}")
    except Exception as e:
        print(f"Telegram Send Error: {e}")

# ==============================================================================
# [Part 1] 왕의 계기판 (기존 로직 유지)
# ==============================================================================
def get_price_reaction(ticker, days=5):
    try:
        df = yf.download(ticker, period="1mo", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            close = df['Close'][ticker]
        else:
            close = df['Close']
        returns = close.pct_change(days)
        return returns.iloc[-1]
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return 0.0

def get_macro_data():
    """거시 경제 데이터 수집"""
    try:
        start_date = datetime.now() - timedelta(days=730) 
        cpatax = web.get_data_fred('CPATAX', start=start_date)
        vix = yf.download('^VIX', period='1mo', progress=False)['Close']
        hy_spread = web.get_data_fred('BAMLH0A0HYM2', start=start_date)
        unrate = web.get_data_fred('UNRATE', start=start_date)
        return cpatax, vix, hy_spread, unrate
    except Exception as e:
        print(f"Macro Data Error: {e}")
        return None, None, None, None

def report_kings_dashboard():
    """왕의 계기판 보고서 생성 및 전송"""
    print(">>> [Part 1] 왕의 계기판 분석 시작...")
    try:
        cpatax, vix, hy, unrate = get_macro_data()
        
        if cpatax is None:
            send_telegram("❌ [왕의 계기판] 데이터 수집 실패")
            return

        # 데이터 가공
        curr_vix = vix.iloc[-1].item()
        curr_hy = hy.iloc[-1].item()
        c0 = cpatax.iloc[-1].item()
        c1 = cpatax.iloc[-2].item()
        c2 = cpatax.iloc[-3].item()

        # 계절 판단
        real_season = "여름"
        season_msg = "이익 성장 지속 (Safe)"
        if c0 < c1 < c2:
            real_season = "겨울"
            season_msg = "📉 *기업이익 2분기 연속 하락*"
        elif c0 < c1:
            real_season = "가을"
            season_msg = "📉 *기업이익 꺾임*"

        # 트리거 분석
        first_snow = []
        snowstorm = []
        
        target_assets = ["SPY", "QQQ", "VRT"]
        earnings_bad = []
        for t in target_assets:
            r = get_price_reaction(t, days=5)
            if r < -0.03:
                earnings_bad.append(f"{t} 급락 ({r*100:.1f}%)")
        
        eps_contagion = False
        if len(earnings_bad) >= 2:
            eps_contagion = True
            first_snow.append("🚨 *EPS 전염 시작*")
            first_snow.extend(earnings_bad)

        if curr_hy >= 5.5:
            snowstorm.append(f"신용 스프레드 폭발 ({curr_hy:.2f}%)")

        # 메시지 작성
        msg = f"👑 *왕의 계기판 (Price Action)* ({datetime.now().strftime('%Y-%m-%d')})\n\n"
        msg += f"📊 *1. 실물 압력계*\n- 상태: {real_season}\n- 진단: {season_msg}\n\n"
        msg += f"📊 *2. 시장 반응성*\n- 상태: {'🔥 투매 발생' if eps_contagion else '✅ 지지력 확인'}\n\n"
        msg += f"📊 *3. 시스템 위험도*\n- VIX: {curr_vix:.2f}\n- Spread: {curr_hy:.2f}%\n\n"
        
        if first_snow:
            msg += "❄️ *[경고] 첫 눈*\n" + "\n".join(f"- {x}" for x in first_snow) + "\n"
        if snowstorm:
            msg += "🌩️ *[위험] 눈보라*\n" + "\n".join(f"- {x}" for x in snowstorm)

        send_telegram(msg, parse_mode="Markdown")
        print(">>> [Part 1] 전송 완료")

    except Exception as e:
        print(f"Dashboard Error: {e}")
        send_telegram(f"❌ 분석 중 오류: {e}")

# ==============================================================================
# [Part 2] 22개 종목 실시간 시세표 (HTML 포맷)
# ==============================================================================
def report_22_tickers():
    """22개 종목 표 생성 및 전송"""
    print(">>> [Part 2] 22개 종목 시세 조회 시작...")
    
    # 티커 매핑 (야후 파이낸스 기준)
    TICKERS = {
        "Dollar Idx": "DX-Y.NYB", "Euro FX": "6E=F", "Jap Yen": "6J=F", "CNH(Yuan)": "CNY=X", "Bitcoin": "BTC-USD",
        "VIX": "^VIX", "S&P 500": "ES=F", "Nasdaq": "NQ=F", "Dow Jones": "YM=F", "Russell": "RTY=F",
        "Euro Stoxx": "^STOXX50E", "Hang Seng": "^HSI", "H-Share": "^HSCE", "Nikkei 225": "^N225",
        "US 2Y Yld": "^IRX", "US 10Y Yld": "^TNX", "US 30Y Yld": "^TYX",
        "Gold": "GC=F", "Silver": "SI=F", "Copper": "HG=F", "Crude Oil": "CL=F", "Nat Gas": "NG=F"
    }

    lines = []
    lines.append(f"📊 <b>[Global Market Brief]</b>")
    lines.append(f"<pre>{'Item':<10} {'Price':>9} {'Chg%':>6}")
    lines.append("-" * 28)

    for name, ticker in TICKERS.items():
        try:
            data = yf.Ticker(ticker)
            hist = data.history(period="2d")
            
            if len(hist) < 1:
                continue

            curr = hist['Close'].iloc[-1]
            
            # 등락률
            pct = 0.0
            if len(hist) >= 2:
                prev = hist['Close'].iloc[-2]
                pct = ((curr - prev) / prev) * 100
            
            # 국채 수익률 보정 (^TNX 등은 42.5 -> 4.25%로 표기됨)
            # 하지만 사용자는 원본 수치를 원할 수 있으므로 값 자체는 유지하되
            # 만약 %단위 변환이 필요하면 여기서 curr / 10 처리
            
            symbol = "▲" if pct > 0 else "▼" if pct < 0 else "."
            
            # 포맷팅
            if curr > 1000:
                p_str = f"{curr:,.0f}"
            else:
                p_
