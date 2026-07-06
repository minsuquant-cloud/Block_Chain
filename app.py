"""가상화폐 로보어드바이저 웹 대시보드.

실행: streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="가상화폐 로보어드바이저", page_icon="📈", layout="wide")

from advisor.dashboard import (allocation_view, analysis_view, backtest_view,
                               market_view, paper_view, reliability_view,
                               screener_view)

st.title("📈 가상화폐 로보어드바이저 — 바이낸스")

(tab_market, tab_analysis, tab_screen, tab_backtest, tab_rel, tab_paper,
 tab_alloc) = st.tabs(
    ["시세·차트", "분석", "스크리너", "백테스트", "신뢰도", "모의투자", "포트폴리오"]
)
with tab_market:
    market_view.render()
with tab_analysis:
    analysis_view.render()
with tab_screen:
    screener_view.render()
with tab_backtest:
    backtest_view.render()
with tab_rel:
    reliability_view.render()
with tab_paper:
    paper_view.render()
with tab_alloc:
    allocation_view.render()
