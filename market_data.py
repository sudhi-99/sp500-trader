"""Download and cache daily OHLCV history for the S&P 500 universe."""
import pandas as pd
import yfinance as yf

UNIVERSE_CSV = "data/sp500_universe.csv"
CACHE_PATH = "data/price_history.parquet"


def load_universe() -> list[str]:
    df = pd.read_csv(UNIVERSE_CSV)
    return df["Symbol"].tolist()


def download_history(tickers: list[str], period: str = "10y", interval: str = "1d") -> pd.DataFrame:
    """Returns a long-format DataFrame: columns = [Date, Ticker, Open, High, Low, Close, Volume]."""
    raw = yf.download(
        tickers,
        period=period,
        interval=interval,
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=True,
    )

    frames = []
    for ticker in tickers:
        if ticker not in raw.columns.get_level_values(0):
            continue
        sub = raw[ticker].dropna(how="all").copy()
        if sub.empty:
            continue
        sub["Ticker"] = ticker
        frames.append(sub.reset_index())

    long_df = pd.concat(frames, ignore_index=True)
    long_df = long_df.rename(columns={"Date": "date", "Ticker": "ticker"})
    long_df.columns = [c.lower() if c not in ("Ticker",) else c for c in long_df.columns]
    return long_df


def save_cache(df: pd.DataFrame, path: str = CACHE_PATH) -> None:
    df.to_parquet(path, index=False)


def load_cache(path: str = CACHE_PATH) -> pd.DataFrame:
    return pd.read_parquet(path)


if __name__ == "__main__":
    import sys

    period = sys.argv[1] if len(sys.argv) > 1 else "10y"
    tickers = load_universe()
    print(f"Downloading {len(tickers)} tickers ({period})...")
    history = download_history(tickers, period=period)
    save_cache(history)
    print(f"Saved {len(history):,} rows across {history['ticker'].nunique()} tickers to {CACHE_PATH}")
