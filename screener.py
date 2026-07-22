"""Momentum/breakout screener for the S&P 500 universe with ATR-based risk position sizing."""
import pandas as pd

CACHE_PATH = "data/price_history.parquet"

LOOKBACK_BREAKOUT = 20     # N-day high breakout window
LOOKBACK_MOMENTUM = 63     # ~3 month rate-of-change window
ATR_WINDOW = 14
TREND_FILTER_WINDOW = 50   # price must be above this SMA to confirm uptrend

RISK_PCT = 0.05            # risk 5% of account equity per trade
ATR_STOP_MULT = 2.0        # stop placed 2x ATR below entry
MAX_POSITION_PCT = 0.25    # cap any single position at 25% of equity, regardless of stop distance

MAX_CONCURRENT_POSITIONS = 5
MAX_HOLD_DAYS = 60


def load_history(path: str = CACHE_PATH) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["ticker", "date"])


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("ticker", group_keys=False)

    df["sma_trend"] = g["close"].transform(lambda s: s.rolling(TREND_FILTER_WINDOW).mean())
    df["rolling_high"] = g["close"].transform(lambda s: s.shift(1).rolling(LOOKBACK_BREAKOUT).max())
    df["momentum"] = g["close"].transform(lambda s: s.pct_change(LOOKBACK_MOMENTUM))

    prev_close = g["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.groupby(df["ticker"]).transform(lambda s: s.rolling(ATR_WINDOW).mean())

    return df


def latest_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Breakout signal: close breaks the prior N-day high while above the trend SMA with positive momentum."""
    latest_date = df["date"].max()
    today = df[df["date"] == latest_date].copy()

    today["breakout"] = (
        (today["close"] > today["rolling_high"])
        & (today["close"] > today["sma_trend"])
        & (today["momentum"] > 0)
    )

    signals = today[today["breakout"]].copy()
    signals["stop_price"] = signals["close"] - ATR_STOP_MULT * signals["atr"]
    signals = signals.sort_values("momentum", ascending=False)
    return signals[["ticker", "date", "close", "atr", "stop_price", "momentum"]]


def size_position(
    entry_price: float,
    stop_price: float,
    account_equity: float,
    risk_pct: float = RISK_PCT,
    max_position_pct: float = MAX_POSITION_PCT,
) -> dict:
    """Size a whole-share position so entry->stop loss equals risk_pct of account equity.

    Capped by available cash AND by max_position_pct of equity — without the latter cap, a
    tight stop (small risk_per_share) makes the risk-target share count demand far more capital
    than the account has, which used to fall through to "buy as many shares as cash allows,"
    dumping the whole account into one name instead of respecting the risk budget.
    """
    risk_per_share = entry_price - stop_price
    if risk_per_share <= 0:
        return {"shares": 0, "dollar_risk": 0.0, "position_value": 0.0}

    risk_dollars = account_equity * risk_pct
    shares = int(risk_dollars // risk_per_share)

    max_position_value = min(account_equity, account_equity * max_position_pct)
    if shares * entry_price > max_position_value:
        shares = int(max_position_value // entry_price)

    position_value = shares * entry_price

    return {
        "shares": shares,
        "dollar_risk": round(shares * risk_per_share, 2),
        "position_value": round(position_value, 2),
    }


def screen(account_equity: float = 1000.0) -> pd.DataFrame:
    df = load_history()
    df = compute_indicators(df)
    signals = latest_signals(df)

    if signals.empty:
        return signals

    signals = signals.reset_index(drop=True)
    sized = signals.apply(
        lambda row: size_position(row["close"], row["stop_price"], account_equity),
        axis=1,
        result_type="expand",
    )
    result = pd.concat([signals, sized], axis=1)
    return result[result["shares"] > 0]


if __name__ == "__main__":
    results = screen()
    if results.empty:
        print("No breakout signals today.")
    else:
        pd.set_option("display.float_format", lambda x: f"{x:,.2f}")
        print(results.to_string(index=False))
