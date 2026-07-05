"""신뢰도 탭: 전략 신뢰도 측정 + 개선 옵션 시뮬레이션."""
import pandas as pd
import streamlit as st

from advisor.dashboard import backtest_view
from advisor.reliability import evaluator
from advisor.screening import screener

DEFAULT_COINS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
COIN_POOL = DEFAULT_COINS + ["ADAUSDT", "DOGEUSDT", "TRXUSDT", "LTCUSDT", "XLMUSDT",
                             "LINKUSDT", "DOTUSDT", "AVAXUSDT"]


@st.cache_data(ttl=600, show_spinner=False)
def _evaluate(symbols: tuple, strategy_key: str, candles: int):
    return evaluator.evaluate(list(symbols), strategy_key, candles=candles)


@st.cache_data(ttl=600, show_spinner=False)
def _screen_symbols(symbols: tuple):
    return screener.evaluate_symbols(list(symbols))


def render():
    st.markdown(
        "같은 전략을 **여러 코인에 돌려** 결과가 우연이 아닌지 확인합니다. "
        "한 코인의 백테스트 성적은 신뢰도의 근거가 되지 못합니다."
    )
    c1, c2, c3 = st.columns([2, 1, 1])
    symbols = c1.multiselect("측정할 코인", COIN_POOL, default=DEFAULT_COINS, key="rel_syms")
    strat_key = c2.selectbox("전략", list(backtest_view.STRATEGY_LABELS), index=2,
                             key="rel_st", format_func=backtest_view.STRATEGY_LABELS.get)
    candles = c3.slider("일봉 수", 365, 1460, 730, step=5, key="rel_n")

    if st.button("신뢰도 측정 실행", type="primary", key="rel_run"):
        if len(symbols) < 3:
            st.warning("재현성을 보려면 코인을 3개 이상 선택하세요.")
            return
        with st.spinner(f"{len(symbols)}개 코인 백테스트 중 (코인당 2~3초)..."):
            st.session_state["rel_evals"] = _evaluate(tuple(symbols), strat_key, candles)
            st.session_state["rel_params"] = (tuple(symbols), strat_key, candles)

    if "rel_evals" not in st.session_state:
        st.info("코인·전략을 고르고 '신뢰도 측정 실행'을 누르세요.")
        return

    evals = st.session_state["rel_evals"]
    s = evaluator.summarize(evals)

    # ── 1. 신뢰도 지표 ──────────────────────────────────────────
    st.divider()
    st.subheader("신뢰도 지표")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("관측 승률", f"{s['win_rate']:.0f}%" if s["win_rate"] is not None else "—",
              help="수익으로 끝난 거래 비율")
    m2.metric("승률 95% 신뢰구간", f"{s['ci_low']:.0f}~{s['ci_high']:.0f}%",
              help="표본(거래 수)이 적을수록 구간이 넓어집니다. 50%를 포함하면 동전던지기와 통계적으로 구분 불가")
    m3.metric("단순보유 대비 승리", f"{s['beat_bh']}/{s['coins']} 코인",
              help="전략이 그냥 보유보다 나았던 코인 수 = 재현성")
    m4.metric("총 거래 표본", f"{s['trades']}건",
              help="30건 미만이면 통계적 판단 자체가 어렵습니다")

    if s["win_rate"] is not None and s["ci_low"] <= 50 <= s["ci_high"]:
        st.warning("신뢰구간이 50%를 포함합니다 — 현재 표본으로는 이 전략의 신호 적중률이 "
                   "동전던지기보다 낫다고 통계적으로 말할 수 없습니다. "
                   "수익의 원천은 적중률이 아니라 손익비·낙폭 방어입니다.")

    rows = [{
        "심볼": e.symbol,
        "전략 수익률": f"{e.strat_return_pct:+.1f}%",
        "단순보유": f"{e.bh_return_pct:+.1f}%",
        "MDD": f"{e.mdd_pct:.1f}%",
        "거래": e.trades,
        "판정": "승" if e.beat_bh else "패",
    } for e in evals]
    st.dataframe(pd.DataFrame(rows), hide_index=True)

    # ── 2. 신뢰도 개선 옵션 ─────────────────────────────────────
    st.divider()
    st.subheader("신뢰도 개선 옵션 — 켜고 끄며 효과를 비교하세요")

    o1, o2, o3 = st.columns(3)
    use_screen = o1.checkbox("① 코인 선별 (스크리너)", key="rel_o1",
                             help="장기 적합도 '부적합' 등급 코인을 제외합니다. "
                                  "XRP형 참사(급등락 코인에서 추세전략 붕괴)를 예방")
    use_div = o2.checkbox("② 분산 투자 (동일비중)", value=True, key="rel_o2",
                          help="자본을 코인별로 나눠 한 코인의 실패를 희석합니다")
    pos_pct = o3.slider("③ 포지션 비중(%)", 10, 100, 100, step=10, key="rel_o3",
                        help="신호당 투입 비율. 낮출수록 수익과 MDD가 함께 줄어 생존 확률이 올라갑니다")

    kept = evals
    dropped: list[str] = []
    if use_screen:
        with st.spinner("스크리너 평가 중..."):
            scores = {sc.symbol: sc for sc in _screen_symbols(tuple(e.symbol for e in evals))}
        kept = [e for e in evals if scores[e.symbol].score >= 2]
        dropped = [f"{e.symbol}({scores[e.symbol].score:+d}점)" for e in evals
                   if scores[e.symbol].score < 2]
        if dropped:
            st.caption(f"제외됨: {', '.join(dropped)}")
        if not kept:
            st.error("선별 결과 남은 코인이 없습니다. 옵션을 조정하세요.")
            return

    if not use_div:
        kept = kept[:1]
        st.caption(f"분산 끔 → 첫 번째 코인({kept[0].symbol}) 단독 투자로 계산")

    base_curve = evaluator.portfolio_curve(evals, position_pct=100)
    new_curve = evaluator.portfolio_curve(kept, position_pct=pos_pct)
    base = evaluator.curve_stats(base_curve)
    new = evaluator.curve_stats(new_curve)

    st.markdown("**개선 전(전체 코인·전량 투입) → 개선 후(옵션 적용)**")
    r1, r2 = st.columns(2)
    r1.metric("수익률", f"{new['return_pct']:+.1f}%",
              delta=f"{new['return_pct'] - base['return_pct']:+.1f}%p")
    r2.metric("최대낙폭(MDD)", f"{new['mdd_pct']:.1f}%",
              delta=f"{new['mdd_pct'] - base['mdd_pct']:+.1f}%p", delta_color="inverse")

    chart_df = pd.concat(
        [base_curve.rename("개선 전"), new_curve.rename("개선 후")], axis=1
    ).ffill().dropna()
    st.line_chart(chart_df)

    # ── 3. 시뮬레이션 밖의 추천 방향 ────────────────────────────
    with st.expander("여기서 시뮬레이션할 수 없는 신뢰도 개선 방향"):
        st.markdown(
            "- **표본 늘리기**: 일봉 수를 늘리거나(위 슬라이더) 코인을 추가해 거래 표본을 "
            "30건 이상으로 — 신뢰구간이 좁아집니다.\n"
            "- **워크포워드 검증**: 과거 구간으로 전략을 고르고 그 뒤 구간에서 검증 "
            "(현재는 전 구간 동시 평가라 낙관 편향 가능).\n"
            "- **슬리피지 반영**: 실제 체결가는 백테스트보다 불리합니다. 수익률에서 1~2%p를 "
            "빼고 보는 습관.\n"
            "- **테스트넷 검증**: 자동매매 전 가짜 돈으로 시스템 오류·주문 로직을 먼저 검증.\n"
            "- **파라미터 민감도**: SMA 20/50을 15/45, 25/55로 바꿔도 결과가 비슷해야 "
            "과최적화가 아닙니다."
        )
    st.caption("※ 모든 수치는 과거 데이터 기반이며 미래 수익을 보장하지 않습니다.")
