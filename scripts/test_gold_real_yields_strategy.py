# scripts/test_gold_real_yields_strategy.py

from slice.quant_engine.data.loader import load_price_data
from slice.quant_engine.core.cerebro import run_cerebro
from slice.quant_engine.strategies.gold_real_yields import GoldRealYieldsStrategy


def main():
    # TEMP: until GLD / RINF exist in DB.
    price_symbol = "SPY"

    df = load_price_data(price_symbol)

    # Cerebro expects feeds dict: {symbol: DataFrame}
    feeds = {price_symbol: df}

    # Our strategy expects p.symbols for tradeable assets.
    strat, analyzers = run_cerebro(
        strategy_cls=GoldRealYieldsStrategy,
        strategy_params={"symbols": [price_symbol]},
        datafeeds=feeds,
    )

    # Simple analyzer sanity output
    returns = analyzers["time_return"].get_analysis()
    dd = analyzers["drawdown"].get_analysis()
    sharpe = analyzers["sharpe"].get_analysis()

    print("Num returns:", len(returns))
    print("Sharpe:", sharpe)
    print("Max drawdown:", dd.max.drawdown, "Max DD len:", dd.max.len)


if __name__ == "__main__":
    main()