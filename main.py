import os
import yfinance as yf
import pandas_datareader.data as web
import requests
import pandas as pd
from datetime import datetime, timedelta

# =========================
# [설정] 환경 변수
# =========================
TELEGRAM_TOKEN = os.environ.get('TELE_TOKEN')
CHAT_ID = os.environ.get('USER_ID')

def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram Token/ID missing.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.get(url, params=params)
    except Exception as e:
        print(f"Telegram Send Error: {e}")

# =========================
# [함수] 가격 반응성 체크 (핵심 로직)
# =========================
def get_price_reaction(ticker, days=5):
    """
    최근 n일간의 수익률을 계산하여 시장의 반응(모멘텀)을 확인
    """
    try:
        # 최근 1달 데이터만 가볍게 호출
        df = yf.download(ticker, period="1mo", progress=False)
        
        # yfinance 버전 호환성 처리 (MultiIndex 컬럼인 경우 처리)
        if isinstance(df.columns, pd.MultiIndex):
            close = df['Close'][ticker] # 해당 티커의 Close만 추출
        else:
            close = df['Close']
            
        # pct_change로 n일 수익률 계산
        returns = close.pct_change(days)
        
        # 최신 수익률 반환 (스칼라 값)
        return returns.iloc[-1]
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return 0.0

# =========================
# [1단계] 데이터 수집
# =========================
def get_market_data():
    try:
        start_date = datetime.now() - timedelta(days=730) 

        # 1. [실물 압력계] CPATAX
        cpatax = web.get_data_fred('CPATAX', start=start_date)

        # 2. [시스템/심리 데이터]
        vix = yf.download('^VIX', period='1mo', progress=False)['Close']
        hy_spread = web.get_data_fred('BAMLH0A0HYM2', start=start_date)
        unrate = web.get_data_fred('UNRATE', start=start_date)

        return cpatax, vix, hy_spread, unrate

    except Exception as e:
        send_telegram(f"❌ 데이터 수집 오류: {e}")
        raise e

# =========================
# [2단계] 시즌 및 트리거 분석
# =========================
def analyze_season():
    try:
        # 기본 데이터 로드
        cpatax, vix, hy, unrate = get_market_data()

        # 최신값 추출
        curr_vix = vix.iloc[-1].item()
        curr_hy = hy.iloc[-1].item()
        
        # ------------------------------------------------
        # 1️⃣ [실물 압력계] CPATAX (구조적 계절)
        # ------------------------------------------------
        c0 = cpatax.iloc[-1].item()
        c1 = cpatax.iloc[-2].item()
        c2 = cpatax.iloc[-3].item()

        real_season = "여름"
        season_msg = "이익 성장 지속 (Safe)"

        if c0 < c1 < c2:
            real_season = "겨울"
            season_msg = "📉 *기업이익(CPATAX) 2분기 연속 하락*"
        elif c0 < c1:
            real_season = "가을"
            season_msg = "📉 *기업이익 꺾임* (하락 반전)"
        
        # ------------------------------------------------
        # 2️⃣ [트리거] EPS 전염 (Price Action)
        # ------------------------------------------------
        first_snow = [] # 첫 눈 (경고)
        snowstorm = []  # 눈보라 (대피)

        # [핵심 변경] SPY, QQQ, VRT의 5일 수익률 반응 체크
        # 논리: 주도주들이 동시에 -3% 이상 빠지면 실적 호재도 안 먹히는 구간임
        target_assets = ["SPY", "QQQ", "VRT"]
        earnings_bad = []
        
        for t in target_assets:
            r = get_price_reaction(t, days=5)
            # 5일간 -3% 이상 하락 시 '반응 악성'으로 판단
            if r < -0.03:
                earnings_bad.append(f"{t} 급락 ({r*100:.1f}%)")
        
        # 2개 이상 자산에서 동시 다발적 하락 발생 시
        eps_contagion = False
        if len(earnings_bad) >= 2:
            eps_contagion = True
            first_snow.append("🚨 *EPS 전염 시작*: 주도주 동반 투매")
            first_snow.extend(earnings_bad)
        elif len(earnings_bad) == 1:
            first_snow.append(f"⚠️ 개별 종목 균열: {earnings_bad[0]}")

        # ------------------------------------------------
        # 3️⃣ [트리거] 시스템 리스크 (신용/실업)
        # ------------------------------------------------
        if curr_hy >= 5.5:
            snowstorm.append(f"신용 스프레드 폭발 ({curr_hy:.2f}%)")
        
        if len(unrate) >= 3:
            u0 = unrate.iloc[-1].item()
            u1 = unrate.iloc[-2].item()
            u2 = unrate.iloc[-3].item()
            if u0 > u1 > u2:
                snowstorm.append("실업률 2개월 연속 상승")

        # ------------------------------------------------
        # 4️⃣ [최종 판결]
        # ------------------------------------------------
        verdict = ""
        
        if len(snowstorm) >= 1:
            verdict = "🚨 *결론: 눈보라(System Failure). 즉시 대피.*"
        elif real_season == "겨울" and eps_contagion:
            verdict = "🌨️ *결론: 겨울 진입 + 투매 확산. 주식 비중 축소.*"
        elif real_season == "가을" or eps_contagion:
            verdict = "🍂 *결론: 늦가을. 리스크 관리 모드(현금 확보).*"
        else:
            verdict = "☀️ *결론: 여름/초가을. 추세 추종.*"

        # ------------------------------------------------
        # 5️⃣ [보고서 작성]
        # ------------------------------------------------
        msg = f"""👑 *왕의 계기판 (Price Action)* ({datetime.now().strftime('%Y-%m-%d')})

📊 *1. 실물 압력계 (CPATAX)*
- 상태: {real_season}
- 진단: {season_msg}

📊 *2. 시장 반응성 (Momentum)*
- 모니터링: SPY, QQQ, VRT
- 상태: {"🔥 투매 발생" if eps_contagion else "✅ 지지력 확인"}

📊 *3. 시스템 위험도*
- VIX: {curr_vix:.2f}
- 신용 스프레드: {curr_hy:.2f}%

"""
        if first_snow:
            msg += "❄️ *[경고] 첫 눈 (가격 균열)*\n" + "\n".join(f"- {x}" for x in first_snow) + "\n\n"
        
        if snowstorm:
            msg += "🌩️ *[위험] 눈보라 (시스템 붕괴)*\n" + "\n".join(f"- {x}" for x in snowstorm) + "\n\n"

        msg += verdict

        send_telegram(msg)
        print("Report Sent Successfully.")

    except Exception as e:
        print(f"Analysis Error: {e}")
        send_telegram(f"❌ 분석 중 오류 발생: {e}")

if __name__ == "__main__":
    analyze_season()
