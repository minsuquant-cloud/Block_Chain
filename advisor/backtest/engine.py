"""백테스트 엔진.

신호(signal 컬럼)가 있는 DataFrame을 받아 전량 매수/전량 매도 방식으로 시뮬레이션한다.
수수료는 config.FEE_RATE 반영. 신호 발생 다음 캔들 시가로 체결해 선견 편향을 피한다.
"""
from dataclasses import dataclass, field

import pandas as pd

from advisor import config


@dataclass
class Trade:
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp | None = None
    exit_price: float | None = None

    @property
    def pnl_pct(self) -> float | None:
        if self.exit_price is None:
            return None
        gross = self.exit_price / self.entry_price
        net = gross * (1 - config.FEE_RATE) ** 2  # 매수+매도 수수료
        return (net - 1) * 100


@dataclass
class Result:
    symbol: str
    interval: str
    start: pd.Timestamp
    end: pd.Timestamp
    initial_capital: float
    final_capital: float
    equity_curve: pd.Series = field(repr=False, default=None)
    trades: list[Trade] = field(default_factory=list)

    @property
    def total_return_pct(self) -> float:
        return (self.final_capital / self.initial_capital - 1) * 100

    @property
    def max_drawdown_pct(self) -> float:
        peak = self.equity_curve.cummax()
        dd = (self.equity_curve - peak) / peak
        return dd.min() * 100

    @property
    def win_rate_pct(self) -> float | None:
        closed = [t for t in self.trades if t.pnl_pct is not None]
        if not closed:
            return None
        wins = sum(1 for t in closed if t.pnl_pct > 0)
        return wins / len(closed) * 100


def run(df: pd.DataFrame, symbol: str, interval: str,
        initial_capital: float = config.INITIAL_CAPITAL) -> Result:
    """signal 컬럼(1/-1/0)이 있는 DataFrame으로 백테스트 실행."""
    cash = initial_capital
    coin = 0.0
    trades: list[Trade] = []
    equity = []

    for i in range(len(df) - 1):
        signal = df["signal"].iloc[i]
        next_open = df["open"].iloc[i + 1]
        next_time = df["time"].iloc[i + 1]

        if signal == 1 and cash > 0:
            coin = cash * (1 - config.FEE_RATE) / next_open
            cash = 0.0
            trades.append(Trade(entry_time=next_time, entry_price=next_open))
        elif signal == -1 and coin > 0:
            cash = coin * next_open * (1 - config.FEE_RATE)
            coin = 0.0
            trades[-1].exit_time = next_time
            trades[-1].exit_price = next_open
        equity.append(cash + coin * df["close"].iloc[i + 1])

    equity_curve = pd.Series(equity, index=df["time"].iloc[1:])
    final = equity_curve.iloc[-1] if len(equity_curve) else initial_capital
    return Result(
        symbol=symbol,
        interval=interval,
        start=df["time"].iloc[0],
        end=df["time"].iloc[-1],
        initial_capital=initial_capital,
        final_capital=final,
        equity_curve=equity_curve,
        trades=trades,
    )


def buy_and_hold_return_pct(df: pd.DataFrame) -> float:
    """비교 기준: 처음부터 끝까지 그냥 보유했을 때 수익률."""
    gross = df["close"].iloc[-1] / df["open"].iloc[0]
    return (gross * (1 - config.FEE_RATE) ** 2 - 1) * 100
