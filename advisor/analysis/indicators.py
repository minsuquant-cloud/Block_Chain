"""기술 지표 계산. 입력은 binance_client.klines()가 반환하는 DataFrame."""
import pandas as pd

from advisor import config


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window).mean()


def ema(close: pd.Series, window: int) -> pd.Series:
    return close.ewm(span=window, adjust=False).mean()


def rsi(close: pd.Series, window: int = config.RSI_WINDOW) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, adjust=False).mean()
    rs = gain / loss
    return 100 - 100 / (1 + rs)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "hist": macd_line - signal_line}
    )


def bollinger(close: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    mid = sma(close, window)
    std = close.rolling(window).std()
    return pd.DataFrame(
        {"bb_mid": mid, "bb_upper": mid + num_std * std, "bb_lower": mid - num_std * std}
    )


def add_all(df: pd.DataFrame) -> pd.DataFrame:
    """캔들 DataFrame에 주요 지표 컬럼을 모두 추가."""
    out = df.copy()
    close = out["close"]
    out["sma_fast"] = sma(close, config.SMA_FAST)
    out["sma_slow"] = sma(close, config.SMA_SLOW)
    out["rsi"] = rsi(close)
    out = pd.concat([out, macd(close), bollinger(close)], axis=1)
    return out
