"""전략 신뢰도 측정.

한 코인의 백테스트 결과는 우연일 수 있다. 여러 코인에 같은 전략을 돌려
(1) 재현성(단순보유 대비 승리 비율), (2) 승률의 통계적 신뢰구간(Wilson),
(3) 개선 옵션(코인 선별·분산·포지션 축소) 적용 시 효과를 계산한다.
"""
import math
from dataclasses import dataclass

import pandas as pd

from advisor import config
from advisor.analysis import indicators
from advisor.analysis import strategy as strat_mod
from advisor.backtest import engine
from advisor.data import binance_client


@dataclass
class CoinEval:
    symbol: str
    strat_return_pct: float      # 전략 수익률
    bh_return_pct: float         # 단순보유 수익률
    mdd_pct: float               # 전략 최대낙폭
    trades: int                  # 청산 완료 거래 수
    wins: int                    # 수익 거래 수
    equity_norm: pd.Series       # 시작=1.0 정규화 자본곡선 (시간 인덱스)

    @property
    def beat_bh(self) -> bool:
        return self.strat_return_pct > self.bh_return_pct


def evaluate(symbols: list[str], strategy_key: str,
             interval: str = "1d", candles: int = 730) -> list[CoinEval]:
    """선택한 코인들에 같은 전략을 돌려 코인별 결과를 수집."""
    out: list[CoinEval] = []
    for sym in symbols:
        df = binance_client.klines_history(sym, interval, total=candles)
        if len(df) < config.SMA_SLOW + 10:
            continue  # 상장 기간이 짧아 평가 불가
        df = indicators.add_all(df)
        df = strat_mod.STRATEGIES[strategy_key](df)
        r = engine.run(df, sym, interval)
        closed = [t for t in r.trades if t.pnl_pct is not None]
        out.append(CoinEval(
            symbol=sym,
            strat_return_pct=r.total_return_pct,
            bh_return_pct=engine.buy_and_hold_return_pct(df),
            mdd_pct=r.max_drawdown_pct,
            trades=len(closed),
            wins=sum(1 for t in closed if t.pnl_pct > 0),
            equity_norm=r.equity_curve / r.initial_capital,
        ))
    return out


def wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """승률의 Wilson 95% 신뢰구간 (%). 표본이 적을수록 구간이 넓어진다."""
    if n == 0:
        return (0.0, 100.0)
    p = wins / n
    mid = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return ((mid - half) * 100, (mid + half) * 100)


def summarize(evals: list[CoinEval]) -> dict:
    """코인별 결과를 신뢰도 지표로 요약."""
    n = sum(e.trades for e in evals)
    wins = sum(e.wins for e in evals)
    lo, hi = wilson_ci(wins, n)
    return {
        "coins": len(evals),
        "trades": n,
        "win_rate": wins / n * 100 if n else None,
        "ci_low": lo,
        "ci_high": hi,
        "beat_bh": sum(1 for e in evals if e.beat_bh),
        "avg_return": sum(e.strat_return_pct for e in evals) / len(evals) if evals else 0,
        "avg_bh_return": sum(e.bh_return_pct for e in evals) / len(evals) if evals else 0,
        "avg_mdd": sum(e.mdd_pct for e in evals) / len(evals) if evals else 0,
    }


def portfolio_curve(evals: list[CoinEval], position_pct: float = 100.0) -> pd.Series:
    """동일비중 포트폴리오 자본곡선.

    position_pct: 신호당 투입 비중(%). 나머지는 현금 보유 —
    전량 매매(f=1)의 자본곡선 E에 대해 f*E + (1-f)로 정확히 환산된다.
    """
    f = position_pct / 100.0
    curves = [f * e.equity_norm + (1 - f) for e in evals]
    aligned = pd.concat(curves, axis=1).ffill().dropna()
    return aligned.mean(axis=1)


def curve_stats(curve: pd.Series) -> dict:
    """자본곡선에서 수익률과 최대낙폭 계산."""
    peak = curve.cummax()
    return {
        "return_pct": (curve.iloc[-1] / curve.iloc[0] - 1) * 100,
        "mdd_pct": ((curve - peak) / peak).min() * 100,
    }
