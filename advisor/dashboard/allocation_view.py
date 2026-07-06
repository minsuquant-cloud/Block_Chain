"""포트폴리오 탭: 코어-새틀라이트 배분 + 주봉 추세 신호등 + 리밸런싱 제안."""
import pandas as pd
import streamlit as st

from advisor.allocation import core_satellite as cs


@st.cache_data(ttl=300, show_spinner=False)
def _plan(capital: float, core_tuple: tuple, satellite_pct: float, current_tuple: tuple):
    return cs.build_plan(capital, dict(core_tuple), satellite_pct, dict(current_tuple))


def render():
    st.markdown(
        "**코어**(장기 보유 + 주봉 SMA50 재난 보험) + **새틀라이트**(자동매매 예산) 배분입니다. "
        "코어 코인의 주봉 추세가 무너지면 그 몫을 현금 대기로 돌리라고 알려줍니다."
    )

    c1, c2, c3, c4 = st.columns(4)
    capital = c1.number_input("총 운용 자본 (USDT)", 100.0, 10_000_000.0, 10_000.0,
                              step=1000.0, key="al_cap")
    btc_pct = c2.number_input("BTC %", 0.0, 100.0, 45.0, step=5.0, key="al_btc")
    eth_pct = c3.number_input("ETH %", 0.0, 100.0, 30.0, step=5.0, key="al_eth")
    sat_pct = c4.number_input("새틀라이트 %", 0.0, 100.0, 25.0, step=5.0, key="al_sat")

    total = btc_pct + eth_pct + sat_pct
    if total > 100:
        st.error(f"배분 합계가 {total:.0f}%입니다 — 100% 이하로 맞춰주세요.")
        return
    if total < 100:
        st.caption(f"잔여 {100 - total:.0f}%는 상시 현금으로 계산됩니다.")

    with st.expander("현재 보유액 입력 (리밸런싱 제안용, 선택)"):
        h1, h2, h3 = st.columns(3)
        cur_btc = h1.number_input("BTC 평가액 (USDT)", 0.0, 10_000_000.0, 0.0, key="al_cb")
        cur_eth = h2.number_input("ETH 평가액 (USDT)", 0.0, 10_000_000.0, 0.0, key="al_ce")
        cur_sat = h3.number_input("새틀라이트 평가액", 0.0, 10_000_000.0, 0.0, key="al_cs")

    core = (("BTCUSDT", btc_pct), ("ETHUSDT", eth_pct))
    current = (("BTCUSDT", cur_btc), ("ETHUSDT", cur_eth), ("SATELLITE", cur_sat))

    with st.spinner("주봉 추세 확인 중..."):
        plan = _plan(capital, core, sat_pct, current)

    # ── 추세 신호등 ──────────────────────────────────────
    st.subheader("코어 추세 신호등 (주봉 SMA50)")
    cols = st.columns(len([r for r in plan["rows"] if r["trend"] is not None]) or 1)
    for col, row in zip(cols, [r for r in plan["rows"] if r["trend"] is not None]):
        t = row["trend"]
        if t.ok:
            col.success(f"🟢 {t.symbol}\n\n보유 유지 — 추세선 위 {t.gap_pct:+.1f}%")
        else:
            col.error(f"🔴 {t.symbol}\n\n**현금화 신호** — 추세선 아래 {t.gap_pct:+.1f}%")
    if plan["broken"]:
        st.warning(f"재난 보험 발동: {', '.join(plan['broken'])} 몫은 목표 배분에서 "
                   f"현금 대기로 전환됐습니다. 추세 회복(주봉 종가가 SMA50 재돌파) 시 재매수.")

    # ── 배분표 ──────────────────────────────────────────
    st.subheader("목표 배분과 리밸런싱 제안")
    df = pd.DataFrame([{
        "자산": r["symbol"],
        "역할": r["role"],
        "목표 (USDT)": f"{r['target_usdt']:,.0f}",
        "현재 (USDT)": f"{r['current_usdt']:,.0f}",
        "차이": f"{r['diff_usdt']:+,.0f}",
        "제안": r["action"],
    } for r in plan["rows"]])
    df.loc[len(df)] = ["현금", "대기", f"{plan['cash_target']:,.0f}", "—", "—", "예비 자금"]
    st.dataframe(df, hide_index=True)

    st.caption(
        f"※ 리밸런싱은 총자본의 {cs.DRIFT_THRESHOLD_PCT:.0f}%p 이상 벗어난 자산만 제안합니다 — "
        "잦은 리밸런싱은 수수료만 낭비합니다. 점검 주기는 주 1회면 충분합니다."
    )
