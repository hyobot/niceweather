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
# [1단계] 데이터 수집
# =========================
def get_market_data():
    try:
        # FRED 데이터는 지연 공시되므로 넉넉히 2년치 조회
        start_date = datetime.now() - timedelta(days=730) 

        # 1. [실물 압력계] Corporate Profits After Tax (NIPA)
        # FRED 코드: CPATAX (분기별 데이터)
        cpatax = web.get_data_fred('CPATAX', start=start_date)

        # 2. [시장/심리 데이터]
        vix = yf.download('^VIX', period='1mo', progress=False)['Close']
        spy = yf.download('SPY', period='6mo', progress=False)['Close']
        vrt = yf.download('VRT', period='6mo', progress=False)['Close']
        
        # 3. [시스템 위기 데이터]
        hy_spread = web.get_data_fred('BAMLH0A0HYM2', start=start_date) # 하이일드 스프레드
        unrate = web.get_data_fred('UNRATE', start=start_date) # 실업률

        # 4. [단기 트리거] SPY Trailing EPS
        # yfinance info는 실시간 메타데이터
        try:
            spy_info = yf.Ticker("SPY").info
            spy_trailing_eps = spy_info.get('trailingEps', 0)
            spy_forward_eps = spy_info.get('forwardEps', 0)
        except:
            spy_trailing_eps = 0
            spy_forward_eps = 0

        return cpatax, vix, spy, vrt, hy_spread, unrate, spy_trailing_eps, spy_forward_eps

    except Exception as e:
        send_telegram(f"❌ 데이터 수집 오류: {e}")
        raise e

# =========================
# [2단계] 시즌 및 트리거 분석
# =========================
def analyze_season():
    try:
        # 데이터 로드
        cpatax, vix, spy, vrt, hy, unrate, spy_t_eps, spy_f_eps = get_market_data()

        # 최신값 추출 (.item()으로 스칼라 변환)
        curr_vix = vix.iloc[-1].item()
        curr_hy = hy.iloc[-1].item()
        curr_spy = spy.iloc[-1].item()
        curr_vrt = vrt.iloc[-1].item()
        
        # ------------------------------------------------
        # 1️⃣ [실물 압력계] CPATAX (계절 판독)
        # ------------------------------------------------
        # 분기 데이터이므로 최근 3개 분기 비교
        c0 = cpatax.iloc[-1].item() # 최신 분기
        c1 = cpatax.iloc[-2].item() # 전 분기
        c2 = cpatax.iloc[-3].item() # 전전 분기

        real_season = "여름"
        season_msg = "이익 성장 지속 (Safe)"

        if c0 < c1 < c2:
            real_season = "겨울"
            season_msg = "📉 *기업이익(CPATAX) 2분기 연속 하락* (구조적 침체)"
        elif c0 < c1:
            real_season = "가을"
            season_msg = "📉 *기업이익 꺾임* (하락 반전)"
        
        # ------------------------------------------------
        # 2️⃣ [트리거] 단기 신호 (눈보라 조건)
        # ------------------------------------------------
        first_snow = [] # 첫 눈 (경고)
        snowstorm = []  # 눈보라 (대피)

        # (A) SPY EPS 트리거 (단기 이익 충격)
        # Trailing(과거)보다 Forward(미래)가 낮으면 이익 전망 악화로 해석
        eps_trigger = False
        if spy_f_eps < spy_t_eps and spy_t_eps > 0:
            first_snow.append(f"EPS 전망 악화 (Forward {spy_f_eps} < Trailing {spy_t_eps})")
            eps_trigger = True
        
        # (B) 가격/모멘텀 트리거
        spy_max = spy.max().item()
        if curr_spy < spy_max * 0.8:
            first_snow.append("SPY 고점 대비 -20% 진입")
        
        vrt_max = vrt.max().item()
        if curr_vrt < vrt_max * 0.9:
            first_snow.append("AI 주도주(VRT) 모멘텀 붕괴")

        # (C) 시스템 붕괴 트리거 (신용/실업)
        if curr_hy >= 5.5:
            snowstorm.append(f"신용 스프레드 폭발 ({curr_hy:.2f}%)")
        
        if len(unrate) >= 3:
            u0 = unrate.iloc[-1].item()
            u1 = unrate.iloc[-2].item()
            u2 = unrate.iloc[-3].item()
            if u0 > u1 > u2:
                snowstorm.append("실업률 2개월 연속 상승 추세")

        # ------------------------------------------------
        # 3️⃣ [최종 판결] 전염(Contagion) 여부
        # ------------------------------------------------
        # 로직: 실물(겨울) + 심리(트리거) = 눈보라 확정
        verdict = ""
        
        if len(snowstorm) >= 1:
            verdict = "🚨 *결론: 눈보라(System Failure). 즉시 대피.*"
        elif real_season == "겨울" and eps_trigger:
            verdict = "🌨️ *결론: EPS 하향 전염 확정 (실물↓ + 전망↓). 주식 비중 축소.*"
        elif real_season == "가을" or len(first_snow) >= 1:
            verdict = "🍂 *결론: 늦가을. 현금 확보 후 리스트업.*"
        else:
            verdict = "☀️ *결론: 여름/초가을. 추세 추종.*"

        # ------------------------------------------------
        # 4️⃣ [보고서 작성]
        # ------------------------------------------------
        msg = f"""👑 *왕의 계기판 (EPS Ver.)* ({datetime.now().strftime('%Y-%m-%d')})

📊 *1. 실물 압력계 (CPATAX)*
- 상태: {real_season}
- 진단: {season_msg}

📊 *2. 단기 이익 트리거 (SPY)*
- Trailing EPS: ${spy_t_eps:.2f}
- Forward EPS: ${spy_f_eps:.2f}
- 상태: {"⚠️ 전망 악화" if eps_trigger else "✅ 양호"}

📊 *3. 시장 위험도*
- VIX: {curr_vix:.2f}
- 신용 스프레드: {curr_hy:.2f}%

"""
        if first_snow:
            msg += "❄️ *[경고] 첫 눈 관측*\n" + "\n".join(f"- {x}" for x in first_snow) + "\n\n"
        
        if snowstorm:
            msg += "🌩️ *[위험] 눈보라 발생*\n" + "\n".join(f"- {x}" for x in snowstorm) + "\n\n"

        msg += verdict

        send_telegram(msg)
        print("Report Sent Successfully.")

    except Exception as e:
        print(f"Analysis Error: {e}")
        send_telegram(f"❌ 분석 중 오류 발생: {e}")

if __name__ == "__main__":
    analyze_season()
