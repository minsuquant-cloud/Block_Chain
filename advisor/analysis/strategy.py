"""매매 신호 생성 전략.

모든 전략은 지표가 추가된 DataFrame을 받아 'signal' 컬럼(1=매수, -1=매도, 0=관망)을
추가해 반환한다. 새 전략을 만들려면 함수를 추가하고 STRATEGIES에 등록하면 된다.
"""
import numpy as np
import pandas as pd

from advisor import config


def ma_cross(df: pd.DataFrame) -> pd.DataFrame:
    """골든크로스/데드크로스: 단기 SMA가 장기 SMA를 상향 돌파하면 매수, 하향 돌파하면 매도."""
    out = df.copy()
    above = out["sma_fast"] > out["sma_slow"]
    crossed_up = above & ~above.shift(1, fill_value=False)
    crossed_down = ~above & above.shift(1, fill_value=False)
    out["signal"] = np.where(crossed_up, 1, np.where(crossed_down, -1, 0))
    return out


def rsi_reversal(df: pd.DataFrame) -> pd.DataFrame:
    """RSI 역추세: 과매도(30 미만) 탈출 시 매수, 과매수(70 초과) 이탈 시 매도."""
    out = df.copy()
    rsi = out["rsi"]
    prev = rsi.shift(1)
    buy = (prev < config.RSI_OVERSOLD) & (rsi >= config.RSI_OVERSOLD)
    sell = (prev > config.RSI_OVERBOUGHT) & (rsi <= config.RSI_OVERBOUGHT)
    out["signal"] = np.where(buy, 1, np.where(sell, -1, 0))
    return out


def ma_rsi(df: pd.DataFrame) -> pd.DataFrame:
    """복합 전략: 상승 추세(단기>장기 SMA)에서 RSI가 과열이 아닐 때만 매수 신호를 인정.

    매도는 데드크로스 또는 RSI 과매수 이탈 시.
    """
    out = df.copy()
    above = out["sma_fast"] > out["sma_slow"]
    crossed_up = above & ~above.shift(1, fill_value=False)
    crossed_down = ~above & above.shift(1, fill_value=False)
    rsi = out["rsi"]
    buy = crossed_up & (rsi < config.RSI_OVERBOUGHT)
    sell = crossed_down | ((rsi.shift(1) > config.RSI_OVERBOUGHT) & (rsi <= config.RSI_OVERBOUGHT))
    out["signal"] = np.where(buy, 1, np.where(sell, -1, 0))
    return out


STRATEGIES = {
    "ma_cross": ma_cross,
    "rsi": rsi_reversal,
    "ma_rsi": ma_rsi,
}


def recommend(df: pd.DataFrame) -> dict:
    """최신 캔들 기준 종합 의견. analyze 명령에서 사용."""
    last = df.iloc[-1]
    score = 0
    reasons = []

    if last["sma_fast"] > last["sma_slow"]:
        score += 1
        reasons.append("단기 이동평균이 장기 위 (상승 추세)")
    else:
        score -= 1
        reasons.append("단기 이동평균이 장기 아래 (하락 추세)")

    if last["rsi"] < config.RSI_OVERSOLD:
        score += 1
        reasons.append(f"RSI {last['rsi']:.1f} 과매도 구간")
    elif last["rsi"] > config.RSI_OVERBOUGHT:
        score -= 1
        reasons.append(f"RSI {last['rsi']:.1f} 과매수 구간")
    else:
        reasons.append(f"RSI {last['rsi']:.1f} 중립")

    if last["hist"] > 0:
        score += 1
        reasons.append("MACD 히스토그램 양수 (상승 모멘텀)")
    else:
        score -= 1
        reasons.append("MACD 히스토그램 음수 (하락 모멘텀)")

    if last["close"] < last["bb_lower"]:
        score += 1
        reasons.append("볼린저밴드 하단 이탈 (반등 가능)")
    elif last["close"] > last["bb_upper"]:
        score -= 1
        reasons.append("볼린저밴드 상단 돌파 (과열 가능)")

    if score >= 2:
        opinion = "매수 우세"
    elif score <= -2:
        opinion = "매도 우세"
    else:
        opinion = "중립/관망"
    return {"score": score, "opinion": opinion, "reasons": reasons}
