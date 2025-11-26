from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List

import pandas as pd

from slice.models.common import Direction
from slice.models.thesis import Thesis, ThesisExpressionLeg
from slice.models.evaluation import EquityPoint, ScenarioImpact, ThesisEvaluationResult
from slice.quant.price_source import PriceSource


@dataclass
class ThesisEvaluationService:
    """
    Deterministic, non-LLM service to evaluate a Thesis with expression legs.

    Responsibilities:
      - validate thesis expression legs
      - determine the backtest window
      - fetch and align price history via PriceSource
      - compute daily returns and an equity curve
      - compute performance metrics
      - compute basic risk metrics
      - compute simple scenarios (All -10%, All +10%)
    """

    price_source: PriceSource

    # ---------- validation / window ----------

    def _validate_thesis_expression(self, thesis: Thesis) -> List[ThesisExpressionLeg]:
        """
        Basic structural validation of the thesis expression legs.

        - must have at least one leg
        - each leg must have LONG or SHORT direction
        - size_pct must be present and non-negative
        - total size_pct across legs cannot exceed 100%
        """
        legs = thesis.expression  # current field name on Thesis

        if not legs:
            raise ValueError("Thesis has no expression legs.")

        total_size_pct = 0.0

        for leg in legs:
            if leg.direction not in (Direction.LONG, Direction.SHORT):
                raise ValueError(
                    f"Invalid direction for asset {leg.asset}: {leg.direction}"
                )

            if leg.size_pct is None:
                raise ValueError(f"Leg for asset {leg.asset} is missing size_pct.")

            if leg.size_pct < 0.0:
                raise ValueError(
                    f"Leg for asset {leg.asset} has negative size_pct: {leg.size_pct}"
                )

            total_size_pct += leg.size_pct

        if total_size_pct > 100.0 + 1e-6:
            raise ValueError(
                f"Total allocation across legs exceeds 100%: {total_size_pct:.2f}%"
            )

        return legs

    def _determine_backtest_window(self, thesis: Thesis) -> tuple[date, date]:
        """
        Determine the evaluation window from thesis.start_date / review_date.

        - Tries to parse ISO strings on Thesis (YYYY-MM-DD)
        - Falls back to [today - 2y, today] if missing/invalid
        - Ensures end > start
        """
        today = date.today()

        start: date | None = None
        end: date | None = None

        # best-effort parse; swallow format errors
        try:
            if thesis.start_date:
                start = date.fromisoformat(thesis.start_date)
        except Exception:
            start = None

        try:
            review_date = getattr(thesis, "review_date", None)
            if review_date:
                end = date.fromisoformat(review_date)
        except Exception:
            end = None

        if start is None:
            start = today - timedelta(days=252 * 2)  # approx 2 years

        if end is None or end <= start:
            end = today

        return start, end

    # ---------- data loading / weights ----------

    def _load_price_history(
        self,
        legs: List[ThesisExpressionLeg],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        """
        Fetch and align price history for all assets in the thesis.

        - Uses the injected PriceSource
        - Requires non-empty series for each asset
        - Inner-joins on the date index and drops any rows with missing values
        """
        series_by_asset: dict[str, pd.Series] = {}

        for leg in legs:
            series = self.price_source.get_history(leg.asset, start, end)
            if series is None or series.empty:
                raise ValueError(f"No price data for asset {leg.asset}.")
            series_by_asset[leg.asset] = series

        prices_df = pd.DataFrame(series_by_asset)

        # strict overlap: any date with a missing price for any asset is dropped
        prices_df = prices_df.dropna(how="any")

        if prices_df.empty:
            raise ValueError("No overlapping price history for thesis assets.")

        return prices_df

    def _build_weights(self, legs: List[ThesisExpressionLeg]) -> dict[str, float]:
        """
        Convert legs into constant portfolio weights.

        - LONG: positive weight
        - SHORT: negative weight
        - Remaining capital (if sum < 1.0) is treated as cash at 0% return.
        """
        weights: dict[str, float] = {}

        for leg in legs:
            direction_sign = 1.0 if leg.direction == Direction.LONG else -1.0
            weights[leg.asset] = (leg.size_pct / 100.0) * direction_sign

        return weights

    # ---------- metrics / scenarios ----------

    def _compute_performance_metrics(
        self,
        equity_curve: pd.Series,
        daily_returns: pd.Series,
    ) -> dict[str, float]:
        """
        Compute total return, CAGR, annualized volatility, Sharpe, max drawdown.

        All percentage outputs are in percent (not fractions).
        """
        if equity_curve.empty:
            return {
                "total_return": 0.0,
                "cagr": 0.0,
                "volatility": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
            }

        initial_value = float(equity_curve.iloc[0])
        final_value = float(equity_curve.iloc[-1])
        n_days = len(equity_curve)

        if n_days <= 0 or initial_value <= 0.0:
            return {
                "total_return": 0.0,
                "cagr": 0.0,
                "volatility": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
            }

        total_return_frac = final_value / initial_value - 1.0
        years = n_days / 252.0 if n_days > 0 else 0.0

        if years > 0.0 and final_value > 0.0:
            cagr_frac = (final_value / initial_value) ** (1.0 / years) - 1.0
        else:
            cagr_frac = 0.0

        vol_daily = float(daily_returns.std()) if n_days >= 2 else 0.0
        vol_annual = vol_daily * (252.0**0.5)

        sharpe = cagr_frac / vol_annual if vol_annual > 0.0 else 0.0

        running_max = equity_curve.cummax()
        drawdowns = equity_curve / running_max - 1.0
        max_dd_frac = -float(drawdowns.min()) if not drawdowns.empty else 0.0

        return {
            "total_return": total_return_frac * 100.0,
            "cagr": cagr_frac * 100.0,
            "volatility": vol_annual * 100.0,
            "sharpe": sharpe,
            "max_drawdown": max_dd_frac * 100.0,
        }

    def _compute_risk_metrics(
        self,
        weights: dict[str, float],
        daily_returns: pd.Series,
        max_drawdown_frac: float,
    ) -> dict[str, float]:
        """
        Basic risk metrics:
          - max_weight_pct: largest absolute leg weight
          - VaR_95: 95% one-day loss magnitude (positive number, in %)
          - max_drawdown_pct: max peak-to-trough drawdown (in %)
        """
        max_weight_abs = max((abs(w) for w in weights.values()), default=0.0)

        if daily_returns.empty:
            var_95_pct = 0.0
        else:
            q = float(daily_returns.quantile(0.05))
            var_95_pct = -q * 100.0  # express as positive loss magnitude

        return {
            "max_weight_pct": max_weight_abs * 100.0,
            "VaR_95": var_95_pct,
            "max_drawdown_pct": max_drawdown_frac * 100.0,
        }

    def _compute_scenarios(
        self,
        prices_df: pd.DataFrame,
        weights: dict[str, float],
        equity_curve: pd.Series,
    ) -> List[ScenarioImpact]:
        """
        Simple shock scenarios applied to the latest price vector.

        Scenarios:
          - "All -10%": all assets -10%
          - "All +10%": all assets +10%
        """
        if prices_df.empty or equity_curve.empty:
            return []

        current_prices = prices_df.iloc[-1].to_dict()
        final_equity = float(equity_curve.iloc[-1])

        def scenario_pnl_frac(new_prices: dict[str, float]) -> float:
            pnl_frac = 0.0
            for asset, old_price in current_prices.items():
                new_price = new_prices[asset]
                if old_price == 0:
                    continue
                asset_return = (new_price - old_price) / old_price
                pnl_frac += weights.get(asset, 0.0) * asset_return
            return pnl_frac

        scenarios: List[ScenarioImpact] = []

        # All -10%
        prices_down = {a: p * 0.9 for a, p in current_prices.items()}
        pnl_frac_down = scenario_pnl_frac(prices_down)
        scenarios.append(
            ScenarioImpact(
                name="All -10%",
                pnl_pct=pnl_frac_down * 100.0,
                pnl_abs=pnl_frac_down * final_equity,
            )
        )

        # All +10%
        prices_up = {a: p * 1.1 for a, p in current_prices.items()}
        pnl_frac_up = scenario_pnl_frac(prices_up)
        scenarios.append(
            ScenarioImpact(
                name="All +10%",
                pnl_pct=pnl_frac_up * 100.0,
                pnl_abs=pnl_frac_up * final_equity,
            )
        )

        return scenarios

    # ---------- public entrypoint ----------

    def evaluate_thesis(self, thesis: Thesis) -> ThesisEvaluationResult:
        """
        Run the end-to-end evaluation for a single thesis.
        """
        # 1) Validate and extract legs
        legs = self._validate_thesis_expression(thesis)

        # 2) Determine evaluation window
        start_date, end_date = self._determine_backtest_window(thesis)

        # 3) Load aligned price history
        prices_df = self._load_price_history(legs, start_date, end_date)

        # 4) Compute daily returns
        daily_returns_df = prices_df.pct_change().fillna(0.0)

        # 5) Build weights and portfolio returns
        weights = self._build_weights(legs)
        weight_series = pd.Series(weights)
        daily_portfolio_returns = daily_returns_df.mul(weight_series, axis=1).sum(axis=1)

        # 6) Equity curve
        equity_curve = (1.0 + daily_portfolio_returns).cumprod()

        # 7) Performance metrics
        performance = self._compute_performance_metrics(
            equity_curve=equity_curve,
            daily_returns=daily_portfolio_returns,
        )

        # Need max drawdown fraction for risk metrics
        running_max = equity_curve.cummax()
        drawdowns = equity_curve / running_max - 1.0
        max_dd_frac = -float(drawdowns.min()) if not drawdowns.empty else 0.0

        # 8) Risk metrics
        risk_metrics = self._compute_risk_metrics(
            weights=weights,
            daily_returns=daily_portfolio_returns,
            max_drawdown_frac=max_dd_frac,
        )

        # 9) Scenarios
        scenarios = self._compute_scenarios(
            prices_df=prices_df,
            weights=weights,
            equity_curve=equity_curve,
        )

        # 10) Timeseries DTOs
        if equity_curve.empty:
            timeseries: List[EquityPoint] = []
        else:
            dt_index = pd.to_datetime(equity_curve.index)
            timeseries = [
                EquityPoint(date=ts.to_pydatetime(), value=float(val))
                for ts, val in zip(dt_index, equity_curve)
            ]

        return ThesisEvaluationResult(
            performance=performance,
            timeseries=timeseries,
            risk_metrics=risk_metrics,
            scenarios=scenarios,
        )