import backtrader as bt

from slice.quant_engine.data.loader import load_price_data
from slice.quant_engine.core.cerebro import run_cerebro
from slice.quant_engine.strategies.strategy_base import StrategyBase


class DumbOneAssetStrat(StrategyBase):
    """
    Sanity strategy:
    - 100% long the first symbol at all times
    """

    def compute_target_weights(self):
        # take the first symbol we were given and go 100% long
        # StrategyBase put symbol list into self.p.symbols
        symbols = self.p.symbols
        if not symbols:
            raise RuntimeError("No symbols configured for DumbOneAssetStrat")

        first = symbols[0]
        return {first: 1.0}


def main():
    # adjust to a ticker you know exists in market_data
    symbol = "SPY"

    df = load_price_data(symbol)
    if df.empty:
        raise RuntimeError(f"No rows returned for {symbol} from market_data")

    strat, analyzers = run_cerebro(
        strategy_cls=DumbOneAssetStrat,
        price_data={symbol: df},
        cash=100_000.0,
        commission=0.0,
    )

    returns = analyzers["returns"].get_analysis()
    sharpe = analyzers["sharpe"].get_analysis()
    drawdown = analyzers["drawdown"].get_analysis()

    print(f"Loaded {len(df)} bars for {symbol}")
    print(f"Returns dict length: {len(returns)}")
    print("Sharpe:", sharpe)
    print("Max drawdown:", drawdown.max.drawdown)


if __name__ == "__main__":
    main()