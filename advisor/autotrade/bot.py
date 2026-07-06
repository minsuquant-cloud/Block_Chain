"""자동매매 봇 (모의투자 체결).

전략 신호를 주기적으로 확인해 모의 포트폴리오에 자동 주문한다. API 키 불필요.
실계좌 전환 시에는 체결 부분(portfolio.buy/sell)만 advisor/trading의
실주문 함수로 바꾸면 된다 — 신호 로직은 그대로 재사용.
"""
import time
from datetime import datetime

from advisor import config
from advisor.analysis import indicators
from advisor.analysis import strategy as strat_mod
from advisor.data import binance_client
from advisor.paper import portfolio


def check_signal(symbol: str, strategy_key: str, interval: str):
    """마지막으로 '완성된' 캔들의 신호를 반환 (진행 중 캔들은 판단에서 제외)."""
    df = binance_client.klines(symbol, interval, limit=max(200, config.SMA_SLOW + 60))
    df = indicators.add_all(df)
    df = strat_mod.STRATEGIES[strategy_key](df)
    last_closed = df.iloc[-2]
    return int(last_closed["signal"]), float(df["close"].iloc[-1]), float(last_closed["rsi"])


def run_once(symbols: list[str], strategy_key: str = "ma_rsi", interval: str = "1m",
             budget: float = 1000.0, log=print) -> int:
    """전 심볼 신호 1회 점검 후 필요한 주문 실행. 체결 건수를 반환."""
    executed = 0
    for sym in symbols:
        sym = sym.upper()
        stamp = datetime.now().strftime("%H:%M:%S")
        try:
            sig, price, rsi = check_signal(sym, strategy_key, interval)
            state = portfolio.status()
            held = {h["symbol"] for h in state["holdings"]}

            if sig == 1 and sym not in held:
                amount = min(budget, state["cash"])
                if amount < 10:
                    log(f"[{stamp}] {sym} 🟢 매수 신호 — 현금 부족({state['cash']:,.0f} USDT)으로 건너뜀")
                    continue
                t = portfolio.buy(sym, amount)
                executed += 1
                log(f"[{stamp}] 🟢 매수 체결: {sym} {t['qty']:.6g}개 @ {t['price']:,.6g} ({amount:,.0f} USDT)")
            elif sig == -1 and sym in held:
                t = portfolio.sell(sym, 100)
                executed += 1
                log(f"[{stamp}] 🔴 매도 체결: {sym} 전량 @ {t['price']:,.6g} (실현손익 {t['realized_pnl_pct']:+.2f}%)")
            else:
                pos = "보유중" if sym in held else "현금"
                log(f"[{stamp}] {sym} {price:,.6g} | RSI {rsi:.0f} | {pos} | 신호 없음(관망)")
        except Exception as e:
            log(f"[{stamp}] {sym} 오류 (다음 주기 재시도): {e}")
    return executed


def run_loop(symbols: list[str], strategy_key: str = "ma_rsi", interval: str = "1m",
             poll: float = 30.0, budget: float = 1000.0) -> None:
    """Ctrl+C로 멈출 때까지 poll초마다 신호 점검 + 자동 주문."""
    print(f"자동매매(모의) 시작 — 심볼 {', '.join(s.upper() for s in symbols)} | "
          f"전략 {strategy_key} | {interval} 캔들 | {poll:.0f}초마다 점검")
    print("중지: Ctrl+C  (포지션은 paper_portfolio.json에 안전하게 남습니다)\n")
    try:
        while True:
            run_once(symbols, strategy_key, interval, budget)
            time.sleep(poll)
    except KeyboardInterrupt:
        s = portfolio.status()
        print(f"\n중지됨. 총자산 {s['total_value']:,.2f} USDT ({s['total_return_pct']:+.2f}%), "
              f"보유 {len(s['holdings'])}종 — 'paper status -v'로 확인하세요.")
