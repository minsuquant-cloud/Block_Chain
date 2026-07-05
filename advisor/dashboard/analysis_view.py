"""분석 탭: 기술 지표 + 종합 매매 의견."""
import streamlit as st

from advisor import config
from advisor.analysis import indicators, strategy
from advisor.data import binance_client


@st.cache_data(ttl=60, show_spinner=False)
def _analyze(symbol: str, interval: str):
    df = binance_client.klines(symbol, interval, limit=200)
    df = indicators.add_all(df)
    return df, strategy.recommend(df)


def render():
    c1, c2 = st.columns([1.5, 1])
    symbol = c1.text_input("심볼", config.DEFAULT_SYMBOL, key="an_sym").upper().strip()
    interval = c2.selectbox("주기", ["15m", "1h", "4h", "1d", "1w"], index=3, key="an_int")

    try:
        df, rec = _analyze(symbol, interval)
    except Exception as e:
        st.error(f"조회 실패: {symbol} — 심볼을 확인하세요. ({e})")
        return

    last = df.iloc[-1]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("현재가", f"{last['close']:,.8g}")
    m2.metric(f"RSI({config.RSI_WINDOW})", f"{last['rsi']:.1f}")
    m3.metric(f"SMA{config.SMA_FAST}", f"{last['sma_fast']:,.8g}")
    m4.metric(f"SMA{config.SMA_SLOW}", f"{last['sma_slow']:,.8g}")

    opinion_color = {"매수 우세": "green", "매도 우세": "red"}.get(rec["opinion"], "gray")
    st.markdown(f"### 종합 의견: :{opinion_color}[{rec['opinion']}] (점수 {rec['score']:+d})")
    for r in rec["reasons"]:
        st.markdown(f"- {r}")
    st.caption("※ 투자 판단의 참고 자료일 뿐, 수익을 보장하지 않습니다.")
