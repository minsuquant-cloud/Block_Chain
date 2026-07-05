"""백테스트 탭: 전략 시뮬레이션 + 수익 곡선."""
import streamlit as st

from advisor import config
from advisor.analysis import indicators, strategy
from advisor.backtest import engine
from advisor.data import binance_client

STRATEGY_LABELS = {
    "ma_cross": "ma_cross — 골든/데드크로스",
    "rsi": "rsi — RSI 과매도/과매수 역추세",
    "ma_rsi": "ma_rsi — 크로스 + RSI 필터",
}


@st.cache_data(ttl=300, show_spinner=False)
def _history(symbol: str, interval: str, candles: int):
    return binance_client.klines_history(symbol, interval, total=candles)


def render():
    c1, c2, c3, c4 = st.columns([1.3, 1, 1, 1.6])
    symbol = c1.text_input("심볼", config.DEFAULT_SYMBOL, key="bt_sym").upper().strip()
    interval = c2.selectbox("주기", ["1h", "4h", "1d", "1w"], index=2, key="bt_int")
    candles = c3.slider("캔들 수", 200, 2000, 730, step=10, key="bt_n")
    strat_key = c4.selectbox("전략", list(STRATEGY_LABELS), key="bt_st",
                             format_func=STRATEGY_LABELS.get)

    if not st.button("백테스트 실행", type="primary", key="bt_run"):
        return

    with st.spinner(f"{symbol} 캔들 {candles}개 수집 및 시뮬레이션 중..."):
        try:
            df = _history(symbol, interval, candles)
        except Exception as e:
            st.error(f"조회 실패: {symbol} — 심볼을 확인하세요. ({e})")
            return
        if len(df) < config.SMA_SLOW + 10:
            st.warning(f"데이터 부족 (수집 {len(df)}개) — 상장 기간이 짧은 코인일 수 있습니다.")
            return
        df = indicators.add_all(df)
        df = strategy.STRATEGIES[strat_key](df)
        result = engine.run(df, symbol, interval)
        bh = engine.buy_and_hold_return_pct(df)

    st.markdown(f"**기간**: {result.start:%Y-%m-%d} ~ {result.end:%Y-%m-%d} ({len(df)}캔들, 수수료 {config.FEE_RATE:.1%} 반영)")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("전략 수익률", f"{result.total_return_pct:+.1f}%",
              delta=f"{result.total_return_pct - bh:+.1f}%p vs 보유")
    m2.metric("단순보유", f"{bh:+.1f}%")
    m3.metric("최대낙폭(MDD)", f"{result.max_drawdown_pct:.1f}%")
    closed = [t for t in result.trades if t.pnl_pct is not None]
    m4.metric("거래 횟수", f"{len(closed)}회")
    m5.metric("승률", f"{result.win_rate_pct:.0f}%" if result.win_rate_pct is not None else "—")

    st.line_chart(result.equity_curve.rename("자본 (USDT)"))

    if closed:
        with st.expander("개별 거래 내역"):
            st.dataframe([{
                "매수일": f"{t.entry_time:%Y-%m-%d %H:%M}",
                "매수가": round(t.entry_price, 6),
                "매도일": f"{t.exit_time:%Y-%m-%d %H:%M}",
                "매도가": round(t.exit_price, 6),
                "수익률": f"{t.pnl_pct:+.1f}%",
            } for t in closed], hide_index=True)
    st.caption("※ 과거 성과가 미래 수익을 보장하지 않습니다.")
