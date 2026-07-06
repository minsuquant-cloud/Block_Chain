"""모의투자(페이퍼 트레이딩) 엔진.

실시간 바이낸스 시세로 가상 자본을 사고판다. API 키 불필요.
상태는 프로젝트 루트의 paper_portfolio.json에 저장된다 (git 제외).
수수료는 실거래와 동일하게 config.FEE_RATE 반영.
"""
import json
from datetime import datetime
from pathlib import Path

from advisor import config
from advisor.data import binance_client

STATE_FILE = Path(__file__).resolve().parents[2] / "paper_portfolio.json"


def _default_state(capital: float = config.INITIAL_CAPITAL) -> dict:
    return {"initial": capital, "cash": capital, "holdings": {}, "trades": []}


def _load() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return _default_state()


def _save(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                          encoding="utf-8")


def reset(capital: float = config.INITIAL_CAPITAL) -> dict:
    state = _default_state(capital)
    _save(state)
    return state


def buy(symbol: str, usdt_amount: float) -> dict:
    """시장가 매수. usdt_amount만큼 현금을 써서 코인을 산다."""
    symbol = symbol.upper()
    state = _load()
    if usdt_amount <= 0:
        raise ValueError("매수 금액은 0보다 커야 합니다.")
    if usdt_amount > state["cash"]:
        raise ValueError(f"현금 부족: 보유 {state['cash']:,.2f} USDT, 요청 {usdt_amount:,.2f} USDT")

    price = binance_client.price(symbol)["price"]
    qty = usdt_amount * (1 - config.FEE_RATE) / price

    h = state["holdings"].get(symbol, {"qty": 0.0, "avg_price": 0.0})
    total_cost = h["qty"] * h["avg_price"] + qty * price
    h["qty"] += qty
    h["avg_price"] = total_cost / h["qty"]
    state["holdings"][symbol] = h
    state["cash"] -= usdt_amount

    trade = {"time": datetime.now().isoformat(timespec="seconds"), "side": "매수",
             "symbol": symbol, "price": price, "qty": qty, "usdt": usdt_amount,
             "realized_pnl_pct": None}
    state["trades"].append(trade)
    _save(state)
    return trade


def sell(symbol: str, pct: float = 100.0) -> dict:
    """시장가 매도. 보유 수량의 pct%를 판다."""
    symbol = symbol.upper()
    state = _load()
    h = state["holdings"].get(symbol)
    if not h or h["qty"] <= 0:
        raise ValueError(f"{symbol} 보유 수량이 없습니다.")
    if not 0 < pct <= 100:
        raise ValueError("매도 비율은 0~100% 사이여야 합니다.")

    price = binance_client.price(symbol)["price"]
    qty = h["qty"] * pct / 100.0
    proceeds = qty * price * (1 - config.FEE_RATE)
    pnl_pct = (price * (1 - config.FEE_RATE) ** 2 / h["avg_price"] - 1) * 100

    h["qty"] -= qty
    if h["qty"] < 1e-12:
        del state["holdings"][symbol]
    state["cash"] += proceeds

    trade = {"time": datetime.now().isoformat(timespec="seconds"), "side": "매도",
             "symbol": symbol, "price": price, "qty": qty, "usdt": proceeds,
             "realized_pnl_pct": pnl_pct}
    state["trades"].append(trade)
    _save(state)
    return trade


def status() -> dict:
    """실시간 시세로 평가한 포트폴리오 현황."""
    state = _load()
    holdings = []
    total_value = state["cash"]
    for symbol, h in state["holdings"].items():
        price = binance_client.price(symbol)["price"]
        value = h["qty"] * price
        total_value += value
        holdings.append({
            "symbol": symbol,
            "qty": h["qty"],
            "avg_price": h["avg_price"],
            "cur_price": price,
            "value": value,
            "pnl_pct": (price / h["avg_price"] - 1) * 100,
        })
    return {
        "initial": state["initial"],
        "cash": state["cash"],
        "holdings": holdings,
        "total_value": total_value,
        "total_return_pct": (total_value / state["initial"] - 1) * 100,
        "trades": state["trades"],
    }
