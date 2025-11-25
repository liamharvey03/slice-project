import streamlit as st

from slice.intelligence.context.data_access import DataAccess
from slice.intelligence.context.context_builder import ContextBuilder
from slice.repositories.thesis_repo import ThesisRepository
from slice.repositories.observation_repo import ObservationRepository
from slice.repositories.trade_repo import TradeRepository


@st.cache_resource
def get_data_access() -> DataAccess:
    """
    Minimal Phase 8 wiring:
    - deterministic repos
    - no LLMs or orchestrator
    """
    thesis_repo = ThesisRepository()
    obs_repo = ObservationRepository()
    trade_repo = TradeRepository()
    return DataAccess(thesis_repo=thesis_repo, obs_repo=obs_repo, trade_repo=trade_repo)


@st.cache_data
def load_portfolio_view():
    da = get_data_access()
    portfolio = da.get_current_portfolio()
    theses = da.get_all_theses()
    depth = da.get_portfolio_depth(theses)
    return portfolio, depth


@st.cache_data
def load_strategy_context():
    da = get_data_access()
    cb = ContextBuilder(da)
    return cb.build_strategy_context_from_data()


@st.cache_data
def load_diagnostics_context():
    da = get_data_access()
    cb = ContextBuilder(da)
    return cb.build_portfolio_diagnostics_context_from_data()


@st.cache_data
def load_narrative_context():
    da = get_data_access()
    cb = ContextBuilder(da)
    # No window label at Phase 8 – just a generic snapshot
    return cb.build_narrative_coherence_context_from_data(window_label=None)


def render_portfolio_tab():
    portfolio, depth = load_portfolio_view()

    st.subheader("Portfolio Snapshot")
    if portfolio:
        # Prefer explicit top-level total_value if present, otherwise fall back
        # to totals["portfolio_value"] from the portfolio adapter.
        totals = portfolio.get("totals") or {}
        total_val = portfolio.get("total_value")
        if total_val is None:
            total_val = totals.get("portfolio_value", 0.0)

        st.metric(
            "Total Value",
            f"{total_val:,.2f}" if isinstance(total_val, (int, float)) else total_val,
        )

        positions = portfolio.get("positions", [])
        if positions:
            st.write("Positions")
            st.dataframe(positions, use_container_width=True)
        else:
            st.info("No positions found.")
    else:
        st.info("Empty portfolio snapshot.")

    st.subheader("Concentration & Thesis Map")
    st.write("Concentration")
    st.json(depth.get("concentration", {}))

    st.write("Factor Exposures")
    st.json(depth.get("factors", {}))

    st.write("Thesis Exposures")
    st.json(depth.get("thesis_exposures", {}))


def render_strategy_tab():
    ctx = load_strategy_context()
    st.subheader("Strategy Context (Phase 8)")

    st.caption("Active theses")
    st.json(ctx.get("active_theses", []))

    st.caption("Current portfolio")
    st.json(ctx.get("current_portfolio", {}))

    st.caption("Risk profile")
    st.json(ctx.get("risk_profile", {}))

    st.caption("Macro view")
    st.json(ctx.get("macro_view", {}))

    st.caption("Constraints")
    st.json(ctx.get("constraints", {}))


def render_diagnostics_tab():
    ctx = load_diagnostics_context()
    st.subheader("Portfolio Diagnostics Context (Phase 8)")

    st.caption("Portfolio")
    st.json(ctx.get("current_portfolio", {}))

    st.caption("Risk profile")
    st.json(ctx.get("risk_profile", {}))

    st.caption("Factor exposures")
    st.json(ctx.get("factor_exposures", {}))

    st.caption("Thesis exposures")
    st.json(ctx.get("thesis_exposures", {}))

    st.caption("Stress tests (placeholders)")
    st.json(ctx.get("stress_tests", []))

    st.caption("Recent performance (placeholders)")
    st.json(ctx.get("recent_performance", {}))


def render_narrative_tab():
    ctx = load_narrative_context()
    st.subheader("Narrative Context (Phase 8)")

    st.caption("Theses")
    st.json(ctx.get("theses", []))

    st.caption("Macro view")
    st.json(ctx.get("macro_view", {}))

    st.caption("Portfolio snapshot")
    st.json(ctx.get("portfolio_snapshot", {}))

    st.caption("Quant summaries")
    st.json(ctx.get("quant_summaries", {}))

    st.caption("Commentary window")
    st.json(ctx.get("commentary_window", {}))


def main():
    st.set_page_config(page_title="Slice Phase 8 UI", layout="wide")

    st.title("Slice – Phase 8 Minimal UI")
    st.markdown(
        "Read-only, deterministic dashboard wired to `DataAccess` and `ContextBuilder`."
    )

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Portfolio", "Strategy Context", "Diagnostics Context", "Narrative Context"]
    )

    with tab1:
        render_portfolio_tab()
    with tab2:
        render_strategy_tab()
    with tab3:
        render_diagnostics_tab()
    with tab4:
        render_narrative_tab()


if __name__ == "__main__":
    main()
