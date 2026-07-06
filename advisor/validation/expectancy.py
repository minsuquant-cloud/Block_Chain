"""거래당 기대값(expectancy) 계산.

승률이 아니라 '거래 1회당 평균적으로 몇 %를 벌거나 잃는가'가 전략의 진짜 성적표다.
기대값 = 승률 × 평균이익 + 패률 × 평균손실 (pnl에 수수료 이미 반영).
이 값이 플러스면 반복할수록 돈이 되고, 마이너스면 반복할수록 잃는다.
"""
from dataclasses import dataclass


@dataclass
class Expectancy:
    trades: int
    win_rate_pct: float | None       # 승률
    avg_win_pct: float               # 평균 이익 (이긴 거래만)
    avg_loss_pct: float              # 평균 손실 (진 거래만, 음수)
    expectancy_pct: float | None     # 거래당 기대값
    profit_factor: float | None      # 총이익/총손실 (1.0 초과여야 우위)

    @property
    def verdict(self) -> str:
        if self.expectancy_pct is None:
            return "거래 없음 — 판단 불가"
        if self.trades < 20:
            return f"표본 {self.trades}건 — 참고만 (20건 미만은 통계적 판단 불가)"
        if self.expectancy_pct > 0.1:
            return "플러스 기대값 — 반복할수록 유리한 구조"
        if self.expectancy_pct > 0:
            return "기대값이 0 근처 — 수수료·슬리피지에 흔들리는 경계선"
        return "마이너스 기대값 — 반복할수록 잃는 구조"


def compute(pnls: list[float]) -> Expectancy:
    """pnls: 청산 거래들의 수익률(%) 목록 (수수료 반영된 값)."""
    n = len(pnls)
    if n == 0:
        return Expectancy(0, None, 0.0, 0.0, None, None)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    win_rate = len(wins) / n
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    exp = win_rate * avg_win + (1 - win_rate) * avg_loss
    gross_loss = abs(sum(losses))
    pf = (sum(wins) / gross_loss) if gross_loss > 0 else None
    return Expectancy(n, win_rate * 100, avg_win, avg_loss, exp, pf)


def describe(e: Expectancy) -> list[str]:
    """CLI/대시보드 공용 설명 줄."""
    if e.trades == 0:
        return ["청산된 거래가 없습니다."]
    lines = [
        f"거래 {e.trades}건 | 승률 {e.win_rate_pct:.0f}% | "
        f"평균이익 {e.avg_win_pct:+.2f}% | 평균손실 {e.avg_loss_pct:+.2f}%",
        f"거래당 기대값: {e.expectancy_pct:+.3f}%"
        + (f" | 손익비(PF): {e.profit_factor:.2f}" if e.profit_factor is not None else ""),
        f"판정: {e.verdict}",
    ]
    return lines
