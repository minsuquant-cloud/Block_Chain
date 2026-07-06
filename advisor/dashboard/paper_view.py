"""모의투자 탭: 가상 자본으로 실시간 매매 연습."""
import pandas as pd
import streamlit as st

from advisor import config
from advisor.data import binance_client
from advisor.paper import portfolio


@st.cache_data(ttl=60, show_spinner=False)
def _symbols():
    return binance_client.top_markets(top=50)["symbol"].tolist()


def render():
    st.markdown("**가상 자본**으로 실시간 실제 시세에 사고파는 연습입니다. "
                f"수수료 {config.FEE_RATE:.1%}까지 실거래와 동일하게 계산됩니다.")

    try:
        s = portfolio.status()
    except Exception as e:
        st.error(f"시세 조회 실패: {e}")
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("총자산", f"{s['total_value']:,.2f} USDT",
              delta=f"{s['total_return_pct']:+.2f}%")
    m2.metric("현금", f"{s['cash']:,.2f} USDT")
    m3.metric("보유 코인", f"{len(s['holdings'])}종")

    # ── 주문 ──────────────────────────────────────────────
    buy_col, sell_col = st.columns(2)
    with buy_col:
        st.subheader("매수")
        b1, b2 = st.columns(2)
        buy_sym = b1.selectbox("코인", _symbols(), key="pp_bsym")
        buy_amt = b2.number_input("금액 (USDT)", min_value=10.0,
                                  max_value=max(s["cash"], 10.0),
                                  value=min(1000.0, max(s["cash"], 10.0)), step=100.0,
                                  key="pp_bamt")
        if st.button("모의 매수", type="primary", key="pp_buy",
                     disabled=s["cash"] < 10):
            try:
                t = portfolio.buy(buy_sym, buy_amt)
                st.success(f"{t['symbol']} {t['qty']:.6g}개 @ {t['price']:,.6g} 매수 완료")
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    with sell_col:
        st.subheader("매도")
        if s["holdings"]:
            s1, s2 = st.columns(2)
            sell_sym = s1.selectbox("보유 코인", [h["symbol"] for h in s["holdings"]],
                                    key="pp_ssym")
            sell_pct = s2.slider("매도 비율 (%)", 10, 100, 100, step=10, key="pp_spct")
            if st.button("모의 매도", key="pp_sell"):
                try:
                    t = portfolio.sell(sell_sym, sell_pct)
                    st.success(f"{t['symbol']} 매도 완료 — 실현손익 {t['realized_pnl_pct']:+.2f}%")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        else:
            st.info("보유 코인이 없습니다. 먼저 매수해보세요.")

    # ── 보유 현황 ─────────────────────────────────────────
    if s["holdings"]:
        st.subheader("보유 현황 (실시간 평가)")
        st.dataframe(pd.DataFrame([{
            "심볼": h["symbol"],
            "수량": f"{h['qty']:.6g}",
            "평단가": f"{h['avg_price']:,.6g}",
            "현재가": f"{h['cur_price']:,.6g}",
            "평가액(USDT)": f"{h['value']:,.2f}",
            "손익": f"{h['pnl_pct']:+.2f}%",
        } for h in s["holdings"]]), hide_index=True)

    # ── 거래 내역 / 초기화 ────────────────────────────────
    if s["trades"]:
        with st.expander(f"거래 내역 ({len(s['trades'])}건)"):
            st.dataframe(pd.DataFrame([{
                "시각": t["time"],
                "구분": t["side"],
                "심볼": t["symbol"],
                "가격": f"{t['price']:,.6g}",
                "수량": f"{t['qty']:.6g}",
                "금액(USDT)": f"{t['usdt']:,.2f}",
                "실현손익": f"{t['realized_pnl_pct']:+.2f}%"
                            if t["realized_pnl_pct"] is not None else "—",
            } for t in reversed(s["trades"])]), hide_index=True)

    with st.expander("초기화"):
        cap = st.number_input("시작 자본 (USDT)", 1000.0, 1_000_000.0,
                              float(config.INITIAL_CAPITAL), step=1000.0, key="pp_cap")
        confirm = st.checkbox("보유 코인과 거래 내역이 모두 삭제됩니다. 확인했습니다.",
                              key="pp_conf")
        if st.button("모의투자 초기화", disabled=not confirm, key="pp_reset"):
            portfolio.reset(cap)
            st.rerun()
