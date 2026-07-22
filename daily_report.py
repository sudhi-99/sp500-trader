"""Generates a daily report: positions to exit and new breakout signals sized to current equity."""
from pathlib import Path

import pandas as pd

from portfolio import load_portfolio
from screener import (
    ATR_STOP_MULT,
    MAX_CONCURRENT_POSITIONS,
    MAX_HOLD_DAYS,
    compute_indicators,
    load_history,
    size_position,
)

REPORTS_DIR = Path("reports")


def build_report() -> tuple[str, pd.Timestamp]:
    portfolio = load_portfolio()
    df = compute_indicators(load_history())

    latest_date = df["date"].max()
    today = df[df["date"] == latest_date].set_index("ticker")
    price_lookup = today["close"].to_dict()

    cash = portfolio["cash"]
    equity = cash + sum(
        pos["shares"] * price_lookup.get(ticker, pos["entry_price"])
        for ticker, pos in portfolio["positions"].items()
    )

    lines = [
        f"# Daily Trading Report — {latest_date.date()}",
        "",
        f"Cash: ${cash:,.2f}  |  Equity: ${equity:,.2f}  |  Open positions: {len(portfolio['positions'])}",
        "",
        "## Positions to review",
    ]

    any_exit = False
    for ticker, pos in portfolio["positions"].items():
        if ticker not in today.index:
            continue
        bar = today.loc[ticker]
        days_held = (latest_date.date() - pd.to_datetime(pos["entry_date"]).date()).days
        if bar["low"] <= pos["stop_price"]:
            lines.append(f"- **SELL {ticker}** — stop triggered (low {bar['low']:.2f} <= stop {pos['stop_price']:.2f})")
            any_exit = True
        elif days_held >= MAX_HOLD_DAYS:
            lines.append(f"- **SELL {ticker}** — max hold reached ({days_held} days), close at market")
            any_exit = True
    if not any_exit:
        lines.append("- No exits triggered today.")

    lines += ["", "## New breakout signals"]

    today["breakout"] = (
        (today["close"] > today["rolling_high"])
        & (today["close"] > today["sma_trend"])
        & (today["momentum"] > 0)
    )
    signals = today[today["breakout"]].sort_values("momentum", ascending=False)
    signals = signals[~signals.index.isin(portfolio["positions"].keys())]

    open_slots = MAX_CONCURRENT_POSITIONS - len(portfolio["positions"])
    if open_slots <= 0:
        lines.append("- No open slots (max concurrent positions reached).")
    elif signals.empty:
        lines.append("- No breakout signals today.")
    else:
        shown = 0
        for ticker, row in signals.iterrows():
            if shown >= open_slots:
                break
            stop_price = row["close"] - ATR_STOP_MULT * row["atr"]
            sized = size_position(row["close"], stop_price, equity)
            if sized["shares"] == 0:
                continue
            lines.append(
                f"- **BUY {ticker}** — ~{sized['shares']} sh @ ${row['close']:.2f}, "
                f"stop ${stop_price:.2f}, risk ${sized['dollar_risk']:.2f}, "
                f"value ${sized['position_value']:.2f}"
            )
            shown += 1

    return "\n".join(lines), latest_date


def save_report(report: str, latest_date: pd.Timestamp) -> str:
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"{latest_date.date()}.md"
    path.write_text(report)
    return str(path)


if __name__ == "__main__":
    report, latest_date = build_report()
    print(report)
    path = save_report(report, latest_date)
    print(f"\nSaved to {path}")
