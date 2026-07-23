# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

바이낸스 공개 API로 시세를 조회하고 기술 지표 분석·백테스트·모의투자를 하는 가상화폐 로보어드바이저. CLI(`main.py`)와 Streamlit 웹 대시보드(`app.py`) 두 가지 진입점을 가진다. 실계좌 자동매매(`advisor/trading/executor.py`)는 API 키 등록 전까지 미구현 스텁 상태.

## 실행 환경

레포 자체 `.venv` 사용 (D:\dev\Block_Chain\.venv). 활성화 없이 실행하려면 `.\.venv\Scripts\python`, `.\.venv\Scripts\streamlit`를 직접 호출.

```powershell
.\.venv\Scripts\pip install -r requirements.txt
```

## 자주 쓰는 명령어

```powershell
.\.venv\Scripts\python main.py markets                # 거래대금 상위 코인
.\.venv\Scripts\python main.py price BTCUSDT ETHUSDT  # 현재가
.\.venv\Scripts\python main.py analyze BTCUSDT --interval 4h
.\.venv\Scripts\python main.py backtest BTCUSDT --interval 1d --candles 730 --strategy ma_rsi
.\.venv\Scripts\python main.py screen --top 20 -v     # 장기 투자 적합도
.\.venv\Scripts\python main.py walkforward BTCUSDT --strategy ma_cross  # 과최적화 검증
.\.venv\Scripts\python main.py paper buy BTCUSDT 1000 # 모의 매수 (status/sell/reset도 있음)
.\.venv\Scripts\python main.py autotrade --strategy rsi --poll 30  # 자동매매 실험 (모의 체결)
.\.venv\Scripts\python main.py chart BTCUSDT --interval 1m
.\.venv\Scripts\streamlit run app.py                  # 웹 대시보드
```

테스트 스위트는 없다.

## 아키텍처

- **데이터 흐름**: `advisor/data/binance_client.py`(공개 API, 키 불필요) → `advisor/analysis/indicators.py`(SMA/EMA/RSI/MACD/볼린저 컬럼 추가) → `advisor/analysis/strategy.py`(signal 컬럼 생성) → `advisor/backtest/engine.py` 또는 `advisor/autotrade/bot.py`가 소비.
- **전략 등록 패턴**: 새 전략은 `advisor/analysis/strategy.py`에 함수를 추가하고 `STRATEGIES` dict에 등록하면 CLI `--strategy` 선택지와 백테스트/워크포워드/자동매매에 자동 반영된다.
- **설정 집중화**: 수수료율, SMA/RSI 파라미터, 스크리너 임계값 등 모든 튜닝 값은 `advisor/config.py` 한 곳에 있다.
- **모의투자 상태**: `advisor/paper/portfolio.py`가 프로젝트 루트의 `paper_portfolio.json`(git 제외)에 상태를 저장. 자동매매 봇도 이 모의 포트폴리오로 체결하며, 실계좌 전환 시 `advisor/trading/executor.py`만 교체하는 구조.
- **대시보드**: `app.py`가 `advisor/dashboard/*_view.py`의 `render()`를 탭별로 호출. CLI와 대시보드는 동일한 advisor 모듈을 공유한다.
- **실계좌 주문 규칙**: API 키/시크릿은 환경변수(`BINANCE_API_KEY`, `BINANCE_API_SECRET`)로 관리하고 코드에 하드코딩 금지. 테스트넷(testnet.binance.vision) 검증 후 실계좌 전환.
