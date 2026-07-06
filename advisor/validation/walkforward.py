"""워크포워드 검증: '과거에 맞춘 착시'인지 '진짜 우위'인지 판별한다.

방법: 데이터를 앞(학습)/뒤(검증) 구간으로 잘라,
  1) 학습 구간에서 성적이 가장 좋았던 전략을 고른 뒤
  2) 그 전략이 본 적 없는 검증 구간에서 성적을 측정한다.
이를 검증 구간 길이만큼 밀어가며 반복한다. 검증 구간 성적만 모은 것이
"미래를 몰랐을 때의 실제 성적"에 가장 가깝다.
"""
from dataclasses import dataclass

import pandas as pd

from advisor.analysis import indicators
from advisor.analysis import strategy as strat_mod
from advisor.backtest import engine
from advisor.data import binance_client
from advisor.validation import expectancy as exp_mod


@dataclass
class Fold:
    train_start: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    chosen_strategy: str         # 학습 구간 1등 전략
    train_return_pct: float      # 학습 구간 성적 (참고용)
    test_return_pct: float       # 검증 구간 성적 (진짜 성적)
    test_bh_return_pct: float    # 검증 구간 단순보유
    test_pnls: list[float]       # 검증 구간 청산 거래 수익률들

    @property
    def beat_bh(self) -> bool:
        return self.test_return_pct > self.test_bh_return_pct


@dataclass
class WalkForwardResult:
    symbol: str
    folds: list[Fold]
    # 전략 고정 시: 검증 전체를 구간 경계 없이 이어서 평가한 성적.
    # (구간별 평가는 경계에서 포지션이 강제 청산돼 추세추종에 불리한 편향이 있음)
    continuous_return_pct: float | None = None
    continuous_bh_pct: float | None = None
    continuous_pnls: list[float] | None = None

    @property
    def test_compound_return_pct(self) -> float:
        """검증 구간들만 이어 붙인 누적 수익률."""
        acc = 1.0
        for f in self.folds:
            acc *= 1 + f.test_return_pct / 100
        return (acc - 1) * 100

    @property
    def bh_compound_return_pct(self) -> float:
        acc = 1.0
        for f in self.folds:
            acc *= 1 + f.test_bh_return_pct / 100
        return (acc - 1) * 100

    @property
    def expectancy(self) -> exp_mod.Expectancy:
        pnls = [p for f in self.folds for p in f.test_pnls]
        return exp_mod.compute(pnls)

    @property
    def verdict(self) -> str:
        if not self.folds:
            return "폴드가 없습니다 — 캔들 수를 늘리세요."
        # 전략 고정 모드면 경계 편향 없는 연속 평가를 기준으로 판정
        if self.continuous_return_pct is not None and self.continuous_pnls:
            e = exp_mod.compute(self.continuous_pnls)
            diff = self.continuous_return_pct - (self.continuous_bh_pct or 0)
            base = (f"연속 평가: 거래당 기대값 {e.expectancy_pct:+.2f}%, "
                    f"단순보유 대비 {diff:+.1f}%p")
            if (e.expectancy_pct or 0) > 0:
                return base + " → 플러스 기대값 구조 (표본 수 확인 필수)"
            return base + " → 마이너스 기대값 (전략/기간 재검토 필요)"
        won = sum(1 for f in self.folds if f.beat_bh)
        e = self.expectancy
        edge = (e.expectancy_pct or 0) > 0 and won >= len(self.folds) / 2
        base = (f"검증 구간 {len(self.folds)}개 중 {won}개에서 단순보유를 이김, "
                f"거래당 기대값 {e.expectancy_pct:+.3f}%" if e.expectancy_pct is not None
                else f"검증 구간 {len(self.folds)}개 중 {won}개 승, 거래 표본 없음")
        if edge:
            return base + " → 미래 미인지 구간에서도 우위 유지 (과최적화 아님)"
        return base + " → 검증 구간에서 우위 소멸 (전략/기간 재검토 필요)"


def run(symbol: str, interval: str = "1d", candles: int = 1460,
        train: int = 365, test: int = 91,
        strategy_key: str | None = None) -> WalkForwardResult:
    """워크포워드 실행. 기본값: 4년 일봉, 1년 학습 → 3개월 검증 반복.

    strategy_key를 주면 전략을 고정하고(선택 과정 없이) 순수하게
    그 전략의 미래 미인지 성적만 측정한다.
    """
    symbol = symbol.upper()
    raw = binance_client.klines_history(symbol, interval, total=candles)
    if len(raw) < train + test:
        return WalkForwardResult(symbol, [])

    # 지표·신호는 각 행이 자기 과거만 사용하므로 전체 계산 후 잘라도 선견 편향 없음
    base_df = indicators.add_all(raw)
    sig_dfs = {k: fn(base_df) for k, fn in strat_mod.STRATEGIES.items()}

    folds: list[Fold] = []
    start = 0
    while start + train + test <= len(raw):
        tr = slice(start, start + train)
        te = slice(start + train, start + train + test)

        if strategy_key is not None:
            best_key = strategy_key
            best_ret = engine.run(sig_dfs[best_key].iloc[tr].reset_index(drop=True),
                                  symbol, interval).total_return_pct
        else:
            best_key, best_ret = None, float("-inf")
            for key, sdf in sig_dfs.items():
                r = engine.run(sdf.iloc[tr].reset_index(drop=True), symbol, interval)
                if r.total_return_pct > best_ret:
                    best_key, best_ret = key, r.total_return_pct

        r_test = engine.run(sig_dfs[best_key].iloc[te].reset_index(drop=True),
                            symbol, interval)
        folds.append(Fold(
            train_start=raw["time"].iloc[tr.start],
            test_start=raw["time"].iloc[te.start],
            test_end=raw["time"].iloc[te.stop - 1],
            chosen_strategy=best_key,
            train_return_pct=best_ret,
            test_return_pct=r_test.total_return_pct,
            test_bh_return_pct=engine.buy_and_hold_return_pct(raw.iloc[te]),
            test_pnls=[t.pnl_pct for t in r_test.trades if t.pnl_pct is not None],
        ))
        start += test

    result = WalkForwardResult(symbol, folds)
    if strategy_key is not None and folds:
        te_all = slice(train, train + len(folds) * test)
        r_cont = engine.run(sig_dfs[strategy_key].iloc[te_all].reset_index(drop=True),
                            symbol, interval)
        result.continuous_return_pct = r_cont.total_return_pct
        result.continuous_bh_pct = engine.buy_and_hold_return_pct(raw.iloc[te_all])
        result.continuous_pnls = [t.pnl_pct for t in r_cont.trades
                                  if t.pnl_pct is not None]
    return result
