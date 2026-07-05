"""공통 설정값. 전략/백테스트 파라미터를 한곳에서 관리한다."""

# 거래소
BASE_URL = "https://api.binance.com"
QUOTE_ASSET = "USDT"          # 기준 마켓
FEE_RATE = 0.001              # 바이낸스 현물 기본 수수료 0.1%

# 기본값
DEFAULT_SYMBOL = "BTCUSDT"
DEFAULT_INTERVAL = "1d"       # 1m, 5m, 15m, 1h, 4h, 1d, 1w ...
DEFAULT_CANDLES = 500

# 전략 파라미터
SMA_FAST = 20                 # 단기 이동평균
SMA_SLOW = 50                 # 장기 이동평균
RSI_WINDOW = 14
RSI_OVERSOLD = 30             # 과매도 기준
RSI_OVERBOUGHT = 70           # 과매수 기준

# 백테스트
INITIAL_CAPITAL = 10_000.0    # 시작 자본 (USDT)

# 스크리너 (장기 투자 적합도)
STABLECOINS = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "USD1", "EURI", "AEUR", "XUSD", "USDE"}
SCREEN_YEARS_VETERAN = 5      # 이 이상 생존 시 고참 가점
SCREEN_YEARS_MIN = 3          # 최소 생존 연차 가점 기준
SCREEN_DD_DEAD = -0.85        # 고점 대비 이 밑이면 '지위 상실' 강한 감점 (예: LTC -89%)
SCREEN_DD_WARN = -0.70        # 고점 대비 이 밑이면 경고 감점
SCREEN_TREND_WEEKS = 50       # 주봉 SMA 기간 (약 1년 추세)
