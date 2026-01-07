import os
import yfinance as yf
import pandas_datareader.data as web
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- [환경 변수 로드: 보안 강화] ---
# GitHub Secrets에 등록된 값을 불러옵니다.
TELEGRAM_TOKEN = os.environ.get('TELE_TOKEN')
CHAT_ID = os.environ.get('USER_ID')

def send_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Error: Telegram Token or Chat ID missing.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.get(url, params=params)
    except Exception as e:
        print(f"Telegram Send Error: {e}")

def get_market_data():
    try:
        # 1. 압력계 데이터
        # VIX (최근 5일치)
        vix = yf.download('^VIX', period='5d', progress=False)['Close']
        
        # 하이일드 스프레드 (FRED) - 데이터 지연 고려하여 넉넉히 호출
        start_date = datetime.now() - timedelta(days=20)
        hy_spread_data = web.get_data_fred('BAMLH0A0HYM2', start=start_date)
        hy_spread = hy_spread_data.iloc[-1].item() # 마지막 값 추출
        
        # 2. 첫 눈/눈보라 체크용 데이터
        # 실업률 (최근 1년치 - 추세 확인용)
        unrate = web.get_data_fred('UNRATE', start=datetime.now()-timedelta(days=365))
        
        # 시장 지수 (SPY)
        spy = yf.download('SPY', period='3mo', progress=False)['Close']
        
        # AI 주변부 (Vertiv - VRT)
        vrt = yf.download('VRT', period='3mo', progress=False)['Close']
        
        return vix, hy_spread, unrate, spy, vrt
    except Exception as e:
        send_telegram(f"⚠️ *데이터 수집 오류 발생*\n시스템을 점검해주세요.\nError: {str(e)}")
        raise e

def analyze_season():
    try:
        vix_series, hy_spread, unrate, spy, vrt = get_market_data()
        
        # 데이터 전처리 (Series에서 값 추출)
        current_vix = vix_series.iloc[-1].item()
        current_spy = spy.iloc[-1].item()
        current_vrt = vrt.iloc[-1].item()
        
        report = f"👑 *왕의 계기판 보고서* ({datetime.now().strftime('%Y-%m-%d')})\n\n"
        
        # --- [Ⅰ. 계절 압력계 측정] ---
        # 1. 신용 압력계 (HY Spread)
        credit_status = "여름" if hy_spread < 4.0 else "가을" if hy_spread < 5.5 else "겨울(폭락)"
        report += f"1. 🟥 *신용 압력*: {hy_spread:.2f}% ({credit_status})\n"
        
        # 2. 공포 압력계 (VIX)
        fear_status = "여름" if current_vix < 15 else "가을" if current_vix < 25 else "겨울(문턱)"
        if current_vix >= 30: fear_status = "한겨울(패닉)"
        report += f"2. 🟥 *공포 압력*: {current_vix:.2f} ({fear_status})\n\n"

        # --- [Ⅱ. 트리거 판정] ---
        first_snow_count = 0
        first_snow_msg = "❄️ *첫 눈(확정 신호) 관측*\n"
        
        # 신호: 고점 대비 -20% 체크
        spy_max = spy.max().item()
        if current_spy < spy_max * 0.8:
            first_snow_msg += "- SPY 고점 대비 -20% 진입\n"
            first_snow_count += 1
        
        # 신호: VRT 고점 대비 10% 이상 하락 (단기 모멘텀 상실)
        vrt_max_recent = vrt.max().item()
        if current_vrt < vrt_max_recent * 0.9:
            first_snow_msg += f"- AI주변부(VRT) 고점 대비 -10% 이상 하락\n"
            first_snow_count += 1

        snowstorm_count = 0
        snowstorm_msg = "🌨️ *눈보라(시스템 붕괴) 트리거*\n"
        
        # 트리거: 실업률 2회 연속 상승 (최근 3달 데이터 비교)
        # FRED 데이터는 월 단위이므로 최근 3개 데이터를 비교
        if len(unrate) >= 3:
            u_last = unrate.iloc[-1].item()
            u_prev = unrate.iloc[-2].item()
            u_prev2 = unrate.iloc[-3].item()
            if u_last > u_prev > u_prev2:
                snowstorm_msg += "- 실업률 2회 연속 상승 확인\n"
                snowstorm_count += 1
            
        # 트리거: 신용 스프레드 5.5 돌파
        if hy_spread >= 5.5:
            snowstorm_msg += "- 신용 스프레드 5.5% 돌파(생존 모드)\n"
            snowstorm_count += 1

        # --- [Ⅲ. 최종 판결] ---
        if snowstorm_count >= 1: # 보수적 관점: 트리거 1개라도 발생 시 경고 격상
             # 원래 로직은 2개였으나, 시스템 붕괴는 선제 대응이 중요하므로 1개 발생 시에도 강력 경고 필요 (구도자의 블라인드 스팟)
             verdict = "🚨 *결론: 눈보라 징후 포착. 주력 투입 준비 및 방어 태세*" if snowstorm_count < 2 else "🚨 *결론: 눈보라 개시. 시스템 리스크 현실화*"
        elif first_snow_count >= 1 or hy_spread >= 4.5:
            verdict = "🍂 *결론: 늦가을~초겨울. 현금 비중 확대 필요*"
        else:
            verdict = "☀️ *결론: 가을 국면. 파티 지속되나 출구 전략 고민*"

        final_msg = report + (first_snow_msg if first_snow_count > 0 else "") + \
                    (snowstorm_msg if snowstorm_count > 0 else "") + "\n" + verdict
        
        send_telegram(final_msg)
        print("Report Sent Successfully.")

    except Exception as e:
        print(f"Logic Error: {e}")
        send_telegram(f"❌ *분석 중 오류 발생*: {e}")

if __name__ == "__main__":
    analyze_season()
