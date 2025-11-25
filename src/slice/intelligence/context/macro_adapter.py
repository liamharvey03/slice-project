from __future__ import annotations

from typing import Any, Dict, Mapping


def build_macro_snapshot(latest_values: Mapping[str, float]) -> Dict[str, Any]:
    """Group flat latest macro values into a structured macro snapshot.

    Input keys (all optional, missing keys become None):
      - pmi
      - payrolls_3m_avg
      - cpi_yoy
      - core_cpi_yoy
      - us_2y_yield
      - us_10y_yield
      - real_10y_yield
      - on_rrp
      - reserves
      - tga
      - dxy
      - eurusd
    """
    def get(name: str) -> float | None:
        value = latest_values.get(name)
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    snapshot: Dict[str, Any] = {
        "growth": {
            "pmi": get("pmi"),
            "payrolls_3m_avg": get("payrolls_3m_avg"),
        },
        "inflation": {
            "cpi_yoy": get("cpi_yoy"),
            "core_cpi_yoy": get("core_cpi_yoy"),
        },
        "rates": {
            "us_2y_yield": get("us_2y_yield"),
            "us_10y_yield": get("us_10y_yield"),
            "real_10y_yield": get("real_10y_yield"),
        },
        "liquidity": {
            "on_rrp": get("on_rrp"),
            "reserves": get("reserves"),
            "tga": get("tga"),
        },
        "fx": {
            "dxy": get("dxy"),
            "eurusd": get("eurusd"),
        },
    }
    return snapshot


def compute_regimes(macro_snapshot: Dict[str, Any]) -> Dict[str, str]:
    """Compute coarse macro regimes from a macro snapshot.

    Returns:
      {
          "growth": "expansion" | "slowdown" | "contraction" | "unknown",
          "inflation": "low" | "moderate" | "high" | "unknown",
          "liquidity": "tight" | "neutral" | "loose" | "unknown",
          "usd": "strong" | "neutral" | "weak" | "unknown",
      }
    """
    growth = macro_snapshot.get("growth", {})
    inflation = macro_snapshot.get("inflation", {})
    rates = macro_snapshot.get("rates", {})
    liquidity = macro_snapshot.get("liquidity", {})
    fx = macro_snapshot.get("fx", {})

    # --- Growth regime ---
    pmi = growth.get("pmi")
    if pmi is None:
        growth_regime = "unknown"
    elif pmi >= 52:
        growth_regime = "expansion"
    elif pmi <= 48:
        growth_regime = "contraction"
    else:
        growth_regime = "slowdown"

    # --- Inflation regime ---
    cpi = inflation.get("cpi_yoy")
    core = inflation.get("core_cpi_yoy")
    inflation_ref = core if core is not None else cpi

    if inflation_ref is None:
        inflation_regime = "unknown"
    elif inflation_ref >= 4.0:
        inflation_regime = "high"
    elif inflation_ref <= 2.0:
        inflation_regime = "low"
    else:
        inflation_regime = "moderate"

    # --- Liquidity regime ---
    # crude proxy: higher reserves and lower ON RRP -> looser; inverse -> tighter
    reserves = liquidity.get("reserves")
    on_rrp = liquidity.get("on_rrp")
    # Build a simple index where positive = loose, negative = tight
    liq_index = None
    if reserves is not None and on_rrp is not None:
        liq_index = reserves - on_rrp

    if liq_index is None:
        liquidity_regime = "unknown"
    elif liq_index <= 0:
        liquidity_regime = "tight"
    elif liq_index < 1e12:  # arbitrary upper bound, can be tuned
        liquidity_regime = "neutral"
    else:
        liquidity_regime = "loose"

    # --- USD regime ---
    dxy = fx.get("dxy")
    if dxy is None:
        usd_regime = "unknown"
    elif dxy >= 110:
        usd_regime = "strong"
    elif dxy <= 95:
        usd_regime = "weak"
    else:
        usd_regime = "neutral"

    return {
        "growth": growth_regime,
        "inflation": inflation_regime,
        "liquidity": liquidity_regime,
        "usd": usd_regime,
    }
