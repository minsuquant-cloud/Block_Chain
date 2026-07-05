"""스크리너 탭: 장기 투자 적합도 평가."""
import pandas as pd
import streamlit as st

from advisor.screening import screener


@st.cache_data(ttl=300, show_spinner=False)
def _screen(top: int):
    return screener.screen(top=top)


def render():
    c1, c2 = st.columns([1, 3])
    top = c1.slider("평가할 코인 수", 5, 30, 15, key="sc_top")
    run = c1.button("스크리닝 실행", type="primary", key="sc_run")
    c2.markdown(
        "**평가 기준** — ① 생존 연차(사이클 통과) ② 유동성 지위 "
        "③ 고점 대비 낙폭(지위 상실 신호) ④ 4년 보유 성과 ⑤ 주봉 SMA50 추세"
    )

    if not run and "sc_results" not in st.session_state:
        st.info("코인 수를 정하고 '스크리닝 실행'을 누르세요. (코인당 1~2초 소요)")
        return
    if run:
        with st.spinner(f"상위 {top}개 코인 주봉 수집·평가 중..."):
            st.session_state["sc_results"] = _screen(top)

    results = st.session_state["sc_results"]
    rows = [{
        "점수": s.score,
        "심볼": s.symbol,
        "등급": s.grade,
        "상장연차": round(s.years_listed, 1),
        "고점대비": f"{s.dd_from_ath:+.0%}",
        "4년수익": f"{s.ret_4y:+.0%}" if s.ret_4y is not None else "—",
        "1년추세": "상승" if s.above_trend else "하락",
    } for s in results]
    st.dataframe(pd.DataFrame(rows), hide_index=True)

    with st.expander("코인별 평가 근거 보기"):
        for s in results:
            st.markdown(f"**{s.symbol}** ({s.score:+d}점, {s.grade})")
            for r in s.reasons:
                st.markdown(f"  - {r}")
    st.caption("※ 점수는 과거 데이터 기반 필터일 뿐, 미래 수익을 보장하지 않습니다.")
