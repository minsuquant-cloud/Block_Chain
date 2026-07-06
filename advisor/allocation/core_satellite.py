"""코어-새틀라이트 배분 계획.

- 코어: 스크리너 통과 코인(기본 BTC·ETH) 장기 보유. 단, 주봉 SMA50이 무너지면
  해당 코인 몫을 현금 대기로 전환하는 '재난 보험' 추세 필터를 단다.
- 새틀라이트: 자동매매/실험용 자본.
- 리밸런싱: 현재 보유액이 목표에서 임계치(%p) 이상 벗어난 코인만 매수/매도 제안.
"""
from dataclasses import dataclass

from advisor import config
from advisor.analysis import indicators
from advisor.data import binance_client

# 기본 배분 (합 100이 되어야 함)
DEFAULT_CORE = {"BTCUSDT": 45.0, "ETHUSDT": 30.0}
DEFAULT_SATELLITE_PCT = 25.0
DRIFT_THRESHOLD_PCT = 5.0     # 총자본 대비 이만큼(%p) 벗어나면 리밸런싱 제안


@dataclass
class TrendStatus:
    symbol: str
    ok: bool                  # 주봉 SMA50 위 = 보유 유지
    close: float
    sma: float

    @property
    def gap_pct(self) -> float:
        """추세선과의 이격 (양수 = 여유, 음수 = 이탈 깊이)."""
        return (self.close / self.sma - 1) * 100


def check_trend(symbol: str) -> TrendStatus:
    df = binance_client.klines(symbol, "1w", limit=config.SCREEN_TREND_WEEKS + 30)
    close = df["close"]
    sma = float(indicators.sma(close, config.SCREEN_TREND_WEEKS).iloc[-1])
    cur = float(close.iloc[-1])
    return TrendStatus(symbol=symbol.upper(), ok=cur > sma, close=cur, sma=sma)


def build_plan(capital: float,
               core: dict[str, float] | None = None,
               satellite_pct: float = DEFAULT_SATELLITE_PCT,
               current: dict[str, float] | None = None,
               drift_pct: float = DRIFT_THRESHOLD_PCT) -> dict:
    """배분 계획 계산.

    capital: 총 운용 자본 (USDT)
    core: {심볼: 목표 %} — satellite_pct와 합쳐 100 이하여야 함 (잔여는 현금)
    current: {심볼: 현재 보유 평가액 USDT} (없으면 0으로 간주)
    """
    core = core or dict(DEFAULT_CORE)
    current = current or {}
    rows = []
    cash_target = capital * max(0.0, 100 - sum(core.values()) - satellite_pct) / 100

    for sym, weight in core.items():
        trend = check_trend(sym)
        target = capital * weight / 100 if trend.ok else 0.0
        if not trend.ok:
            cash_target += capital * weight / 100  # 추세 이탈 → 그 몫은 현금 대기
        cur_val = current.get(sym.upper(), 0.0)
        diff = target - cur_val
        if abs(diff) >= capital * drift_pct / 100:
            action = f"매수 {diff:,.0f} USDT" if diff > 0 else f"매도 {-diff:,.0f} USDT"
        else:
            action = "유지"
        rows.append({
            "symbol": sym.upper(),
            "role": "코어",
            "trend": trend,
            "target_usdt": target,
            "current_usdt": cur_val,
            "diff_usdt": diff,
            "action": action if trend.ok or cur_val > 0 else "현금 대기",
        })

    sat_target = capital * satellite_pct / 100
    sat_current = current.get("SATELLITE", 0.0)
    rows.append({
        "symbol": "새틀라이트(자동매매)",
        "role": "위성",
        "trend": None,
        "target_usdt": sat_target,
        "current_usdt": sat_current,
        "diff_usdt": sat_target - sat_current,
        "action": "자동매매 봇 예산",
    })
    return {
        "capital": capital,
        "rows": rows,
        "cash_target": cash_target,
        "broken": [r["symbol"] for r in rows if r["trend"] is not None and not r["trend"].ok],
    }
