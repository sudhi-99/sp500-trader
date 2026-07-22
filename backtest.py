"""Day-by-day backtest of the momentum/breakout screener strategy with ATR-stop position sizing."""
import pandas as pd

from screener import (
    ATR_STOP_MULT,
    MAX_CONCURRENT_POSITIONS,
    MAX_HOLD_DAYS,
    compute_indicators,
    load_history,
    size_position,
)

STARTING_EQUITY = 1000.0


def run_backtest(
    starting_equity: float = STARTING_EQUITY,
    max_hold_days: int = MAX_HOLD_DAYS,
    risk_pct: float | None = None,
) -> dict:
    df = load_history()
    df = compute_indicators(df)

    df["breakout"] = (
        (df["close"] > df["rolling_high"])
        & (df["close"] > df["sma_trend"])
        & (df["momentum"] > 0)
    )
    df["stop_price"] = df["close"] - ATR_STOP_MULT * df["atr"]

    dates = sorted(df["date"].unique())
    by_date = {d: g.set_index("ticker") for d, g in df.groupby("date")}
    by_ticker = {t: g.set_index("date") for t, g in df.groupby("ticker")}

    cash = starting_equity
    positions = {}  # ticker -> {shares, entry_price, stop_price, entry_date, days_held}
    equity_curve = []
    trades = []

    for i, date in enumerate(dates):
        day = by_date[date]

        # 1. Manage open positions: stop-loss or max-hold exit on today's bar
        for ticker in list(positions):
            if ticker not in day.index:
                continue
            pos = positions[ticker]
            bar = day.loc[ticker]
            pos["days_held"] += 1
            exit_price = None
            if bar["low"] <= pos["stop_price"]:
                exit_price = min(bar["open"], pos["stop_price"])  # gap-down aware
            elif pos["days_held"] >= max_hold_days:
                exit_price = bar["close"]

            if exit_price is not None:
                proceeds = pos["shares"] * exit_price
                cash += proceeds
                trades.append({
                    "ticker": ticker,
                    "entry_date": pos["entry_date"],
                    "exit_date": date,
                    "entry_price": pos["entry_price"],
                    "exit_price": exit_price,
                    "shares": pos["shares"],
                    "pnl": proceeds - pos["shares"] * pos["entry_price"],
                    "exit_reason": "stop" if bar["low"] <= pos["stop_price"] else "time",
                })
                del positions[ticker]

        # 2. Mark-to-market equity for today
        positions_value = sum(
            positions[t]["shares"] * day.loc[t]["close"] for t in positions if t in day.index
        )
        equity = cash + positions_value
        equity_curve.append({"date": date, "equity": equity})

        # 3. Enter new positions from today's signals, filled at next day's open
        if i + 1 < len(dates):
            next_date = dates[i + 1]
            todays_signals = day[day["breakout"]].sort_values("momentum", ascending=False)

            for ticker, row in todays_signals.iterrows():
                if len(positions) >= MAX_CONCURRENT_POSITIONS:
                    break
                if ticker in positions:
                    continue
                ticker_hist = by_ticker.get(ticker)
                if ticker_hist is None or next_date not in ticker_hist.index:
                    continue

                entry_price = ticker_hist.loc[next_date, "open"]
                stop_distance = row["close"] - row["stop_price"]
                stop_price = entry_price - stop_distance
                sized = (
                    size_position(entry_price, stop_price, equity, risk_pct)
                    if risk_pct is not None
                    else size_position(entry_price, stop_price, equity)
                )
                if sized["shares"] == 0 or sized["position_value"] > cash:
                    continue

                positions[ticker] = {
                    "shares": sized["shares"],
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "entry_date": next_date,
                    "days_held": 0,
                }
                cash -= sized["shares"] * entry_price

    equity_df = pd.DataFrame(equity_curve).set_index("date")
    trades_df = pd.DataFrame(trades)
    return {"equity_curve": equity_df, "trades": trades_df}


def summarize(result: dict) -> None:
    equity_df = result["equity_curve"]
    trades_df = result["trades"]

    start_equity = equity_df["equity"].iloc[0]
    end_equity = equity_df["equity"].iloc[-1]
    total_return = end_equity / start_equity - 1

    running_max = equity_df["equity"].cummax()
    drawdown = equity_df["equity"] / running_max - 1
    max_drawdown = drawdown.min()

    print(f"Start equity:     ${start_equity:,.2f}")
    print(f"End equity:       ${end_equity:,.2f}")
    print(f"Total return:     {total_return:+.1%}")
    print(f"Max drawdown:     {max_drawdown:.1%}")
    print(f"Total trades:     {len(trades_df)}")

    if not trades_df.empty:
        win_rate = (trades_df["pnl"] > 0).mean()
        print(f"Win rate:         {win_rate:.1%}")
        print(f"Avg P&L/trade:    ${trades_df['pnl'].mean():,.2f}")
        print(f"Exit via stop:    {(trades_df['exit_reason'] == 'stop').sum()}")
        print(f"Exit via time:    {(trades_df['exit_reason'] == 'time').sum()}")
        avg_hold = (pd.to_datetime(trades_df["exit_date"]) - pd.to_datetime(trades_df["entry_date"])).dt.days.mean()
        print(f"Avg hold (days):  {avg_hold:.0f}")

    print("\nReturn by calendar year:")
    yearly = equity_df["equity"].resample("YE").last()
    yearly_start = equity_df["equity"].resample("YE").first()
    yearly_return = (yearly / yearly_start - 1).dropna()
    for year, ret in yearly_return.items():
        print(f"  {year.year}: {ret:+.1%}")


if __name__ == "__main__":
    result = run_backtest()
    summarize(result)
