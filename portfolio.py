"""Tracks cash/positions for manually-filled trades (e.g. via Robinhood)."""
import json
import sys
from datetime import date
from pathlib import Path

PORTFOLIO_PATH = Path("data/portfolio.json")
STARTING_CASH = 1000.0


def load_portfolio() -> dict:
    if not PORTFOLIO_PATH.exists():
        return {"cash": STARTING_CASH, "positions": {}}
    return json.loads(PORTFOLIO_PATH.read_text())


def save_portfolio(portfolio: dict) -> None:
    PORTFOLIO_PATH.write_text(json.dumps(portfolio, indent=2))


def record_buy(ticker: str, shares: int, price: float, stop_price: float, entry_date: str) -> None:
    portfolio = load_portfolio()
    cost = shares * price
    if cost > portfolio["cash"]:
        raise ValueError(f"Insufficient cash: need ${cost:,.2f}, have ${portfolio['cash']:,.2f}")
    portfolio["cash"] -= cost
    portfolio["positions"][ticker] = {
        "shares": shares,
        "entry_price": price,
        "stop_price": stop_price,
        "entry_date": entry_date,
    }
    save_portfolio(portfolio)


def record_sell(ticker: str, price: float) -> None:
    portfolio = load_portfolio()
    pos = portfolio["positions"].pop(ticker, None)
    if pos is None:
        raise ValueError(f"No open position in {ticker}")
    portfolio["cash"] += pos["shares"] * price
    save_portfolio(portfolio)


def current_equity(portfolio: dict, price_lookup: dict) -> float:
    positions_value = sum(
        pos["shares"] * price_lookup.get(ticker, pos["entry_price"])
        for ticker, pos in portfolio["positions"].items()
    )
    return portfolio["cash"] + positions_value


def _usage() -> None:
    print("Usage:")
    print("  portfolio.py buy TICKER SHARES PRICE STOP_PRICE")
    print("  portfolio.py sell TICKER PRICE")
    print("  portfolio.py show")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        _usage()
        sys.exit(1)

    command = sys.argv[1]
    if command == "buy" and len(sys.argv) == 6:
        _, _, ticker, shares, price, stop_price = sys.argv
        record_buy(ticker.upper(), int(shares), float(price), float(stop_price), str(date.today()))
        print(f"Recorded BUY {shares} {ticker.upper()} @ {price}, stop {stop_price}")
    elif command == "sell" and len(sys.argv) == 4:
        _, _, ticker, price = sys.argv
        record_sell(ticker.upper(), float(price))
        print(f"Recorded SELL {ticker.upper()} @ {price}")
    elif command == "show":
        print(json.dumps(load_portfolio(), indent=2))
    else:
        _usage()
        sys.exit(1)
