"""Fetch the current S&P 500 constituent list from Wikipedia and save it locally."""
import io
import pandas as pd
import requests

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
HEADERS = {"User-Agent": "Mozilla/5.0 (sp500-trader research script)"}


def fetch_sp500_tickers() -> pd.DataFrame:
    resp = requests.get(WIKI_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    df = tables[0][["Symbol", "Security", "GICS Sector"]]
    df["Symbol"] = df["Symbol"].str.replace(".", "-", regex=False)  # yfinance format, e.g. BRK.B -> BRK-B
    return df


if __name__ == "__main__":
    df = fetch_sp500_tickers()
    df.to_csv("data/sp500_universe.csv", index=False)
    print(f"Saved {len(df)} tickers to data/sp500_universe.csv")
