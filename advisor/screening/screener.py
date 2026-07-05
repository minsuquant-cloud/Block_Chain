"""장기 투자 적합도 스크리너.

"오래 살아남는 것은 필요조건일 뿐, 자기 분야 지위를 유지해야 한다"는 기준을 점수화한다.

평가 항목 (근거는 각 함수 주석 참고):
  1. 생존 연차   — 여러 사이클을 버틴 실적 (필요조건)
  2. 유동성 지위 — 거래대금 순위 = 시장이 부여한 현재 지위
  3. 고점 대비 낙폭 — -85% 이하는 '천천히 죽는 생존자' 신호 (LTC, ADA 사례)
  4. 장기 성과   — 4년(한 사이클) 보유 시 수익 여부
  5. 현재 추세   — 주봉 SMA50(약 1년) 위/아래
"""
import time
from dataclasses import dataclass, field

import pandas as pd

from advisor import config
from advisor.analysis import indicators
from advisor.data import binance_client

WEEKS_PER_YEAR = 52


@dataclass
class CoinScore:
    symbol: str
    years_listed: float          # 바이낸스 상장 연차 (주봉 개수 기반, 최대 ~9.6년)
    volume_rank: int             # 거래대금 순위 (1이 최고)
    dd_from_ath: float           # 역대 고점 대비 낙폭 (-0.5 = -50%)
    ret_4y: float | None         # 4년 보유 수익률 (데이터 부족 시 None)
    above_trend: bool            # 주봉 SMA50 위인가
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    @property
    def grade(self) -> str:
        if self.score >= 4:
            return "장기보유 후보"
        if self.score >= 2:
            return "관찰"
        return "부적합(트레이딩만)"


def _evaluate(symbol: str, volume_rank: int, weekly: pd.DataFrame) -> CoinScore:
    close = weekly["close"]
    now = close.iloc[-1]
    years = len(weekly) / WEEKS_PER_YEAR
    dd = now / weekly["high"].max() - 1
    ret_4y = None
    if len(weekly) > 4 * WEEKS_PER_YEAR + 1:
        ret_4y = now / close.iloc[-(4 * WEEKS_PER_YEAR + 1)] - 1
    sma_w = indicators.sma(close, config.SCREEN_TREND_WEEKS).iloc[-1]
    above_trend = bool(pd.notna(sma_w) and now > sma_w)

    s = CoinScore(symbol=symbol, years_listed=years, volume_rank=volume_rank,
                  dd_from_ath=dd, ret_4y=ret_4y, above_trend=above_trend)

    # 1. 생존 연차 — 최소 한 번의 하락장(사이클)을 통과했는가
    if years >= config.SCREEN_YEARS_VETERAN:
        s.score += 2
        s.reasons.append(f"{years:.0f}년 생존 (2개 이상 사이클 통과)")
    elif years >= config.SCREEN_YEARS_MIN:
        s.score += 1
        s.reasons.append(f"{years:.0f}년 생존")
    else:
        s.score -= 1
        s.reasons.append(f"상장 {years:.1f}년 — 하락장 검증 안 됨")

    # 2. 유동성 지위 — 시장이 부여한 현재 순위
    if volume_rank <= 10:
        s.score += 2
        s.reasons.append(f"거래대금 {volume_rank}위 (최상위 지위)")
    elif volume_rank <= 30:
        s.score += 1
        s.reasons.append(f"거래대금 {volume_rank}위")

    # 3. 고점 대비 낙폭 — 지위 상실(존재 이유 상실)의 신호
    if dd <= config.SCREEN_DD_DEAD:
        s.score -= 2
        s.reasons.append(f"고점 대비 {dd:.0%} — 지위 상실 신호 (LTC형)")
    elif dd <= config.SCREEN_DD_WARN:
        s.score -= 1
        s.reasons.append(f"고점 대비 {dd:.0%} — 경고 수준")
    else:
        s.reasons.append(f"고점 대비 {dd:.0%}")

    # 4. 장기 성과 — 한 사이클(4년) 보유가 보상받았는가
    if ret_4y is not None:
        if ret_4y > 0:
            s.score += 1
            s.reasons.append(f"4년 보유 수익 {ret_4y:+.0%}")
        else:
            s.reasons.append(f"4년 보유 손실 {ret_4y:+.0%}")

    # 5. 현재 추세 — 1년 추세선 위인가
    if above_trend:
        s.score += 1
        s.reasons.append("주봉 SMA50 위 (장기 상승 추세)")
    else:
        s.score -= 1
        s.reasons.append("주봉 SMA50 아래 (장기 하락 추세)")

    return s


def evaluate_symbols(symbols: list[str]) -> list[CoinScore]:
    """지정한 심볼 목록을 평가 (신뢰도 탭의 코인 선별 옵션에서 사용)."""
    markets = binance_client.top_markets(top=200)
    ranks = {s: i + 1 for i, s in enumerate(markets["symbol"])}
    results = []
    for sym in symbols:
        weekly = binance_client.klines(sym, "1w", limit=500)
        results.append(_evaluate(sym, ranks.get(sym, 999), weekly))
        time.sleep(0.1)
    return results


def screen(top: int = 20) -> list[CoinScore]:
    """거래대금 상위 코인을 장기 투자 적합도 순으로 평가."""
    markets = binance_client.top_markets(top=top + len(config.STABLECOINS))
    results = []
    rank = 0
    for _, row in markets.iterrows():
        symbol = row["symbol"]
        base = symbol[: -len(config.QUOTE_ASSET)]
        if base in config.STABLECOINS:
            continue  # 스테이블코인은 투자 대상이 아님
        rank += 1
        if rank > top:
            break
        weekly = binance_client.klines(symbol, "1w", limit=500)
        results.append(_evaluate(symbol, rank, weekly))
        time.sleep(0.1)  # rate limit 여유
    return sorted(results, key=lambda s: s.score, reverse=True)
