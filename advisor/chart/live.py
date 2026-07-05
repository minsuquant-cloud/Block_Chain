"""실시간 캔들 차트.

바이낸스 REST API를 주기적으로 폴링해 캔들·SMA를 다시 그린다.
마지막 캔들은 진행 중인 캔들이라 갱신될 때마다 실시간으로 움직인다.
"""
import matplotlib.pyplot as plt
import mplfinance as mpf
from matplotlib import animation
from matplotlib.lines import Line2D

from advisor import config
from advisor.analysis import indicators
from advisor.data import binance_client

# 한글 라벨용 폰트 (Windows 기본)
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

# 캔들: 상승/하락 극성 (바이낸스 관례). SMA 선: 팔레트 검증 통과 색.
COLOR_UP = "#16A34A"
COLOR_DOWN = "#DC2626"
COLOR_SMA_FAST = "#2563EB"
COLOR_SMA_SLOW = "#B45309"
SURFACE = "#FCFCFB"
GRID = "#E5E7EB"

_STYLE = mpf.make_mpf_style(
    marketcolors=mpf.make_marketcolors(
        up=COLOR_UP, down=COLOR_DOWN, edge="inherit", wick="inherit", volume="inherit"
    ),
    facecolor=SURFACE,
    figcolor=SURFACE,
    gridcolor=GRID,
    gridstyle="-",
    rc={"axes.edgecolor": GRID, "font.size": 9,
        "font.family": "Malgun Gothic", "axes.unicode_minus": False},
)


def _fetch(symbol: str, interval: str, candles: int):
    """캔들 + SMA 계산. mplfinance가 요구하는 형식(대문자 컬럼, 시간 인덱스)으로 변환."""
    df = binance_client.klines(symbol, interval, limit=min(candles + config.SMA_SLOW, 1000))
    df["sma_fast"] = indicators.sma(df["close"], config.SMA_FAST)
    df["sma_slow"] = indicators.sma(df["close"], config.SMA_SLOW)
    df = df.tail(candles).set_index("time")
    return df.rename(
        columns={"open": "Open", "high": "High", "low": "Low",
                 "close": "Close", "volume": "Volume"}
    )


def _draw(fig, ax_price, ax_vol, symbol: str, interval: str, candles: int):
    df = _fetch(symbol, interval, candles)
    ax_price.clear()
    ax_vol.clear()

    addplots = []
    if df["sma_fast"].notna().any():
        addplots.append(mpf.make_addplot(df["sma_fast"], ax=ax_price,
                                         color=COLOR_SMA_FAST, width=1.6))
    if df["sma_slow"].notna().any():
        addplots.append(mpf.make_addplot(df["sma_slow"], ax=ax_price,
                                         color=COLOR_SMA_SLOW, width=1.6))
    mpf.plot(df, type="candle", ax=ax_price, volume=ax_vol,
             addplot=addplots, style=_STYLE, xrotation=0, datetime_format="%m-%d %H:%M")

    last = df.iloc[-1]
    change = (last["Close"] / df["Close"].iloc[0] - 1) * 100
    color = COLOR_UP if last["Close"] >= last["Open"] else COLOR_DOWN
    ax_price.set_title(
        f"{symbol}  {interval}   {last['Close']:,.8g} USDT   (표시구간 {change:+.2f}%)",
        fontsize=12, color=color, fontweight="bold", loc="left",
    )
    ax_price.legend(
        handles=[
            Line2D([], [], color=COLOR_SMA_FAST, lw=1.6, label=f"SMA {config.SMA_FAST}"),
            Line2D([], [], color=COLOR_SMA_SLOW, lw=1.6, label=f"SMA {config.SMA_SLOW}"),
        ],
        loc="upper left", frameon=False, fontsize=8,
    )
    ax_price.set_ylabel("가격 (USDT)")
    ax_vol.set_ylabel("거래량")
    return df


def show(symbol: str, interval: str = "1m", candles: int = 120, refresh: float = 3.0):
    """실시간 차트 창을 띄운다. 창을 닫으면 종료."""
    symbol = symbol.upper()
    fig = mpf.figure(style=_STYLE, figsize=(12, 7))
    ax_price = fig.add_subplot(4, 1, (1, 3))
    ax_vol = fig.add_subplot(4, 1, 4, sharex=ax_price)
    fig.subplots_adjust(hspace=0.05, left=0.08, right=0.97, top=0.94, bottom=0.08)

    def update(_frame):
        try:
            _draw(fig, ax_price, ax_vol, symbol, interval, candles)
        except Exception as e:  # 네트워크 일시 오류 시 이전 화면 유지
            print(f"갱신 실패(다음 주기 재시도): {e}")

    ani = animation.FuncAnimation(fig, update, interval=int(refresh * 1000),
                                  cache_frame_data=False)
    print(f"{symbol} 실시간 차트 실행 중 ({refresh}초마다 갱신). 창을 닫으면 종료됩니다.")
    plt.show()
    return ani  # 가비지 컬렉션 방지


def snapshot(symbol: str, interval: str, candles: int, path: str):
    """차트 1장을 PNG로 저장 (실시간 아님)."""
    import matplotlib
    matplotlib.use("Agg")
    symbol = symbol.upper()
    fig = mpf.figure(style=_STYLE, figsize=(12, 7))
    ax_price = fig.add_subplot(4, 1, (1, 3))
    ax_vol = fig.add_subplot(4, 1, 4, sharex=ax_price)
    fig.subplots_adjust(hspace=0.05, left=0.08, right=0.97, top=0.94, bottom=0.08)
    _draw(fig, ax_price, ax_vol, symbol, interval, candles)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"차트 저장: {path}")
