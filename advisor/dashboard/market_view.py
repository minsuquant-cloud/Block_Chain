"""시세·차트 탭: 상위 코인 목록 + 캔들 차트 (자동 갱신 지원)."""
import mplfinance as mpf
import streamlit as st

from advisor import config
from advisor.chart import live
from advisor.data import binance_client

INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]


@st.cache_data(ttl=30, show_spinner=False)
def _markets(top: int):
    return binance_client.top_markets(top=top)


def _draw_chart(symbol: str, interval: str, candles: int):
    fig = mpf.figure(style=live._STYLE, figsize=(12, 6))
    ax_price = fig.add_subplot(4, 1, (1, 3))
    ax_vol = fig.add_subplot(4, 1, 4, sharex=ax_price)
    fig.subplots_adjust(hspace=0.05, left=0.08, right=0.97, top=0.92, bottom=0.1)
    live._draw(fig, ax_price, ax_vol, symbol, interval, candles)
    st.pyplot(fig, clear_figure=True)


def render():
    left, right = st.columns([1, 2])

    with left:
        st.subheader("거래대금 상위")
        top = st.slider("코인 수", 5, 50, 20, key="mk_top")
        df = _markets(top).copy()
        df["volume_24h"] = (df["volume_24h"] / 1e6).round(1)
        df = df.rename(columns={"price": "가격", "change_24h_%": "24h %",
                                "volume_24h": "거래대금(M)"})
        st.dataframe(df, height=480, hide_index=True)

    with right:
        st.subheader("캔들 차트")
        c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1])
        symbol = c1.selectbox("심볼", _markets(50)["symbol"].tolist(), key="mk_sym")
        interval = c2.selectbox("주기", INTERVALS, index=3, key="mk_int")
        candles = c3.slider("캔들 수", 60, 300, 120, key="mk_n")
        auto = c4.toggle("자동 갱신(10초)", key="mk_auto")

        if auto:
            st.fragment(run_every="10s")(_draw_chart)(symbol, interval, candles)
        else:
            _draw_chart(symbol, interval, candles)
