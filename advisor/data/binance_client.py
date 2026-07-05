"""바이낸스 공개 REST API 클라이언트 (API 키 불필요)."""
import time

import pandas as pd
import requests

from advisor import config

_session = requests.Session()


def _get(path: str, params: dict | None = None) -> dict | list:
    resp = _session.get(config.BASE_URL + path, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def top_markets(quote: str = config.QUOTE_ASSET, top: int = 20) -> pd.DataFrame:
    """24시간 거래대금 기준 상위 마켓 목록."""
    tickers = _get("/api/v3/ticker/24hr")
    rows = []
    for t in tickers:
        symbol = t["symbol"]
        if not symbol.endswith(quote):
            continue
        # 레버리지 토큰(UP/DOWN/BULL/BEAR) 제외
        base = symbol[: -len(quote)]
        if base.endswith(("UP", "DOWN", "BULL", "BEAR")):
            continue
        rows.append(
            {
                "symbol": symbol,
                "price": float(t["lastPrice"]),
                "change_24h_%": float(t["priceChangePercent"]),
                "volume_24h": float(t["quoteVolume"]),
            }
        )
    df = pd.DataFrame(rows)
    df = df[df["volume_24h"] > 0]
    return df.sort_values("volume_24h", ascending=False).head(top).reset_index(drop=True)


def price(symbol: str) -> dict:
    """현재가 + 24시간 통계."""
    t = _get("/api/v3/ticker/24hr", {"symbol": symbol.upper()})
    return {
        "symbol": t["symbol"],
        "price": float(t["lastPrice"]),
        "change_24h_%": float(t["priceChangePercent"]),
        "high_24h": float(t["highPrice"]),
        "low_24h": float(t["lowPrice"]),
        "volume_24h": float(t["quoteVolume"]),
    }


def klines(symbol: str, interval: str = config.DEFAULT_INTERVAL, limit: int = 500,
           end_time: int | None = None) -> pd.DataFrame:
    """캔들(OHLCV) 조회. limit은 최대 1000."""
    params = {"symbol": symbol.upper(), "interval": interval, "limit": min(limit, 1000)}
    if end_time is not None:
        params["endTime"] = end_time
    raw = _get("/api/v3/klines", params)
    df = pd.DataFrame(
        raw,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore",
        ],
    )
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = df[col].astype(float)
    df["time"] = pd.to_datetime(df["open_time"], unit="ms")
    return df[["time", "open", "high", "low", "close", "volume"]]


def klines_history(symbol: str, interval: str = config.DEFAULT_INTERVAL,
                   total: int = 1000) -> pd.DataFrame:
    """1000개 제한을 넘는 과거 캔들을 페이지네이션으로 수집."""
    frames: list[pd.DataFrame] = []
    end_time = None
    remaining = total
    while remaining > 0:
        batch = klines(symbol, interval, limit=min(remaining, 1000), end_time=end_time)
        if batch.empty:
            break
        frames.insert(0, batch)
        remaining -= len(batch)
        if len(batch) < 2:
            break
        end_time = int(batch["time"].iloc[0].timestamp() * 1000) - 1
        time.sleep(0.15)  # rate limit 여유
    if not frames:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    df = pd.concat(frames, ignore_index=True)
    return df.drop_duplicates(subset="time").sort_values("time").reset_index(drop=True)
