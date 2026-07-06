# 가상화폐 로보어드바이저 (바이낸스)

바이낸스 시세를 조회하고, 기술 지표로 분석하고, 전략을 백테스트하는 Python CLI.
자동매매는 API 키 등록 후 `advisor/trading/`에 구현 예정.

## 설치

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

## 사용법

```powershell
.\.venv\Scripts\python main.py markets                # 거래대금 상위 20개 코인
.\.venv\Scripts\python main.py price BTCUSDT ETHUSDT  # 현재가 조회
.\.venv\Scripts\python main.py analyze BTCUSDT --interval 4h   # 지표 분석 + 의견
.\.venv\Scripts\python main.py backtest BTCUSDT --interval 1d --candles 730 --strategy ma_rsi
.\.venv\Scripts\python main.py screen --top 20 -v                       # 장기 투자 적합도 평가
.\.venv\Scripts\streamlit run app.py                                    # 웹 대시보드
.\.venv\Scripts\python main.py paper buy BTCUSDT 1000                   # 모의 매수
.\.venv\Scripts\python main.py paper status -v                          # 모의투자 현황
.\.venv\Scripts\python main.py autotrade --strategy rsi --poll 30       # 자동매매 실험 (모의)
.\.venv\Scripts\python main.py walkforward BTCUSDT --strategy ma_cross  # 워크포워드 검증
.\.venv\Scripts\python main.py chart BTCUSDT --interval 1m              # 실시간 캔들 차트
.\.venv\Scripts\python main.py chart BTCUSDT --interval 1h --save c.png # PNG 1장 저장
```

가상환경을 활성화하면 `python main.py ...`로 바로 실행 가능:
```powershell
.\.venv\Scripts\Activate.ps1
```

## 구조

```
advisor/
├── config.py            # 공통 설정 (수수료, 전략 파라미터)
├── data/binance_client.py    # 바이낸스 공개 API (시세/캔들)
├── analysis/indicators.py    # 기술 지표 (SMA, EMA, RSI, MACD, 볼린저)
├── analysis/strategy.py      # 매매 신호 전략 (ma_cross, rsi, ma_rsi)
├── screening/screener.py     # 장기 투자 적합도 스크리너 (생존·지위·낙폭·성과·추세)
├── backtest/engine.py        # 백테스트 엔진 (수수료 반영, MDD/승률)
├── chart/live.py             # 실시간 캔들 차트 (matplotlib)
├── dashboard/                # Streamlit 웹 대시보드 (탭별 화면: 시세·분석·스크리너·백테스트·신뢰도)
├── reliability/evaluator.py  # 전략 신뢰도 측정 (다중 코인 재현성, 승률 신뢰구간, 개선 옵션)
├── paper/portfolio.py        # 모의투자 엔진 (실시간 시세, 가상 자본, 수수료 반영)
├── autotrade/bot.py          # 자동매매 봇 (신호 감시→모의 체결, 실계좌 전환 시 executor만 교체)
├── validation/               # 검증 도구 (walkforward: 과최적화 판별, expectancy: 거래당 기대값)
├── allocation/               # 코어-새틀라이트 배분 (주봉 SMA50 재난 보험, 리밸런싱 제안)
└── trading/executor.py       # 자동매매 (API 키 등록 후 구현)
```

## 전략

| 이름 | 설명 |
|---|---|
| `ma_cross` | 골든크로스 매수 / 데드크로스 매도 |
| `rsi` | RSI 과매도 탈출 매수 / 과매수 이탈 매도 |
| `ma_rsi` | 골든크로스 + RSI 필터 복합 |

새 전략은 `advisor/analysis/strategy.py`에 함수를 추가하고 `STRATEGIES`에 등록하면 CLI에서 바로 사용 가능.

> ⚠️ 백테스트 결과와 매매 의견은 참고 자료일 뿐 수익을 보장하지 않습니다.
