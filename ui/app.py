import streamlit as st
import asyncio
from datetime import date

from slice.intelligence.context.data_access import DataAccess
from slice.api.deps import (
    get_data_access_instance,
    get_price_source_instance,
    get_orchestrator_client_instance,
)
from slice.evaluation.thesis_evaluation import ThesisEvaluationService
from slice.llm.llm_tools import LLMTools
from slice.sessions.thesis_evaluation_session import ThesisEvaluationSession
from slice.sessions.daily_update_session import DailyUpdateSession
from slice.execution.paper import PaperExecutionAdapter
from slice.models.common import ThesisStatus


@st.cache_resource
def get_data_access() -> DataAccess:
    """
    E6: Fully wired DataAccess with all E4 repositories and price source.
    """
    return get_data_access_instance()


@st.cache_resource
def get_price_source():
    """
    E6: Price source for portfolio P&L calculations and trade execution.
    """
    return get_price_source_instance()


@st.cache_resource
def get_llm_tools() -> LLMTools:
    """
    E6: LLM tools wrapper for thesis review, daily summary, and Q&A.
    """
    from slice.llm.tools import OrchestratorProtocol
    from slice.session.models import SessionOptions, SessionResponse
    
    orchestrator_client = get_orchestrator_client_instance()
    
    class OrchestratorAdapter(OrchestratorProtocol):
        """Adapter to make OrchestratorClient compatible with OrchestratorProtocol."""
        
        def __init__(self, client):
            self._client = client
        
        async def run_session(self, text: str, options: SessionOptions) -> SessionResponse:
            mode = options.mode
            include_memory = options.use_memory and not options.skip_memory
            include_risk = options.use_risk and not options.skip_risk
            skip_ingest = options.skip_ingest
            
            return await self._client.run_session(
                user_text=text,
                mode=mode,
                include_memory=include_memory,
                include_risk=include_risk,
                skip_ingest=skip_ingest,
            )
    
    adapter = OrchestratorAdapter(orchestrator_client)
    return LLMTools(adapter)


@st.cache_resource
def get_eval_service():
    """
    E6: Thesis evaluation service for quant metrics.
    """
    return ThesisEvaluationService(price_source=get_price_source())


# Initialize session state
if "selected_thesis_id" not in st.session_state:
    st.session_state["selected_thesis_id"] = None
if "last_daily_update" not in st.session_state:
    st.session_state["last_daily_update"] = None
if "last_evaluation_result" not in st.session_state:
    st.session_state["last_evaluation_result"] = None


def render_theses_tab(data_access: DataAccess, eval_service, llm_tools: LLMTools):
    """Milestone 2: Theses List tab with Evaluate/View actions."""
    st.subheader("Theses List")
    
    # Load all theses
    theses = data_access.get_all_theses()
    
    if not theses:
        st.info("No theses found.")
        return
    
    # Display each thesis in a card-like format
    for thesis in theses:
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 2])
            
            with col1:
                st.write(f"**{thesis.title}**")
                st.caption(f"ID: {thesis.id}")
            
            with col2:
                st.write("**Status**")
                st.write(thesis.status.value)
            
            with col3:
                st.write("**Last Evaluated**")
                eval_data = data_access.get_latest_evaluation(thesis.id)
                if eval_data:
                    st.write("Evaluated")
                else:
                    st.write("Never")
            
            with col4:
                st.write("**P&L**")
                if thesis.status == ThesisStatus.ACTIVE:
                    try:
                        pnl = data_access.get_thesis_pnl(thesis.id)
                        if pnl.unrealized_pnl_pct is not None:
                            st.write(f"${pnl.unrealized_pnl:,.2f}")
                            st.caption(f"({pnl.unrealized_pnl_pct:.2f}%)")
                        else:
                            st.write(f"${pnl.current_value:,.2f}")
                    except Exception:
                        st.write("N/A")
                else:
                    st.write("—")
            
            with col5:
                st.write("**Risk Flags**")
                eval_data = data_access.get_latest_evaluation(thesis.id)
                if eval_data:
                    _, review = eval_data
                    if review.risk_flags:
                        flags_display = ", ".join(review.risk_flags[:2])
                        if len(review.risk_flags) > 2:
                            flags_display += f" (+{len(review.risk_flags) - 2} more)"
                        st.write(flags_display)
                    else:
                        st.write("None")
                else:
                    st.write("—")
            
            # Action buttons
            btn_col1, btn_col2 = st.columns([1, 1])
            with btn_col1:
                eval_key = f"eval_{thesis.id}"
                if st.button("Evaluate", key=eval_key, use_container_width=True):
                    with st.spinner(f"Evaluating {thesis.title}..."):
                        try:
                            session = ThesisEvaluationSession(
                                data_access=data_access,
                                eval_service=eval_service,
                                llm_tools=llm_tools,
                                exec_adapter=None,
                            )
                            result = asyncio.run(session.run(thesis.id))
                            st.session_state["last_evaluation_result"] = result
                            st.session_state[f"eval_result_{thesis.id}"] = result
                            st.success(f"Evaluation completed for {thesis.title}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Evaluation failed: {e}")
            
            with btn_col2:
                view_key = f"view_{thesis.id}"
                if st.button("View", key=view_key, use_container_width=True):
                    st.session_state["selected_thesis_id"] = thesis.id
                    st.success(f"Selected {thesis.title}. Switch to 'Thesis Detail' tab.")
                    st.rerun()
            
            st.divider()


def render_thesis_detail_tab(data_access: DataAccess, eval_service, llm_tools: LLMTools, price_source):
    """Milestone 3: Thesis Detail tab with evaluation display and Approve Plan."""
    st.subheader("Thesis Detail")
    
    thesis_id = st.session_state.get("selected_thesis_id")
    if not thesis_id:
        st.info("Select a thesis from the Theses tab to view details.")
        return
    
    # Load thesis
    thesis = data_access.get_thesis(thesis_id)
    if not thesis:
        st.error(f"Thesis {thesis_id} not found.")
        return
    
    # Display thesis content
    st.header(thesis.title)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Status", thesis.status.value)
    with col2:
        st.metric("Start Date", thesis.start_date)
    
    st.subheader("Hypothesis")
    st.write(thesis.hypothesis)
    
    st.subheader("Drivers")
    for driver in thesis.drivers:
        st.write(f"• {driver}")
    
    st.subheader("Disconfirmers")
    for disconfirmer in thesis.disconfirmers:
        st.write(f"• {disconfirmer}")
    
    st.subheader("Expression Legs")
    expr_data = []
    for leg in thesis.expression:
        expr_data.append({
            "Asset": leg.asset,
            "Direction": leg.direction.value,
            "Size %": f"{leg.size_pct:.1f}%" if leg.size_pct else "N/A",
        })
    st.dataframe(expr_data, use_container_width=True, hide_index=True)
    
    # Latest Evaluation
    st.subheader("Latest Quant Evaluation")
    eval_data = data_access.get_latest_evaluation(thesis_id)
    
    if eval_data:
        evaluation, review = eval_data
        
        # Performance metrics
        st.write("**Performance Metrics**")
        perf_cols = st.columns(4)
        metrics = evaluation.performance
        if metrics:
            metric_names = ["total_return", "CAGR", "volatility", "sharpe", "max_drawdown"]
            for idx, metric_name in enumerate(metric_names):
                if metric_name in metrics:
                    with perf_cols[idx % 4]:
                        st.metric(metric_name.replace("_", " ").title(), f"{metrics[metric_name]:.2f}")
        
        # Scenario impacts
        if evaluation.scenarios:
            st.write("**Scenario Impacts**")
            scenario_data = []
            for scenario in evaluation.scenarios:
                scenario_data.append({
                    "Scenario": scenario.name,
                    "P&L %": f"{scenario.pnl_pct:.2f}%",
                    "P&L $": f"${scenario.pnl_abs:,.2f}",
                })
            st.dataframe(scenario_data, use_container_width=True, hide_index=True)
    else:
        st.info("No evaluation run yet.")
    
    # Latest LLM Review
    st.subheader("Latest LLM Review")
    if eval_data:
        _, review = eval_data
        
        st.write("**Critique**")
        st.write(review.critique)
        
        if review.questions:
            st.write("**Questions**")
            for question in review.questions:
                st.write(f"• {question}")
        
        if review.risk_flags:
            st.write("**Risk Flags**")
            for flag in review.risk_flags:
                st.warning(f"⚠️ {flag}")
        
        if review.insufficient_context:
            st.error("⚠️ Insufficient context - LLM could not fully evaluate from provided data.")
    else:
        st.info("No LLM review available. Run evaluation first.")
    
    # Trade Plan Preview
    st.subheader("Trade Plan")
    if thesis.status == ThesisStatus.ACTIVE:
        st.info(f"Thesis is ACTIVE. Trades have been executed.")
        # Show existing trades if available
        try:
            trades = data_access.trade_repo.list_by_thesis(thesis_id)
            if trades:
                trade_data = []
                for trade in trades:
                    trade_data.append({
                        "Asset": trade.asset,
                        "Action": trade.action,
                        "Quantity": f"{trade.quantity:.4f}",
                        "Price": f"${trade.price:.2f}",
                        "Value": f"${trade.quantity * trade.price:,.2f}",
                    })
                st.dataframe(trade_data, use_container_width=True, hide_index=True)
        except Exception:
            pass
    else:
        # Generate plan preview
        try:
            adapter = PaperExecutionAdapter(
                trade_repo=data_access.trade_repo,
                price_source=price_source,
            )
            DEFAULT_NOTIONAL = 100_000.0
            plan = adapter.create_plan_from_thesis(thesis, total_notional=DEFAULT_NOTIONAL)
            
            st.write(f"**Proposed Notional:** ${plan.total_notional:,.2f}")
            st.write("**Legs:**")
            plan_data = []
            for leg in plan.legs:
                notional = plan.total_notional * (leg.size_pct / 100.0)
                plan_data.append({
                    "Asset": leg.asset,
                    "Direction": leg.direction,
                    "Size %": f"{leg.size_pct:.1f}%",
                    "Notional": f"${notional:,.2f}",
                })
            st.dataframe(plan_data, use_container_width=True, hide_index=True)
        except Exception as e:
            st.warning(f"Could not generate trade plan: {e}")
    
    # Actions
    st.subheader("Actions")
    action_col1, action_col2 = st.columns(2)
    
    with action_col1:
        if st.button("Run Evaluation", use_container_width=True):
            with st.spinner(f"Evaluating {thesis.title}..."):
                try:
                    session = ThesisEvaluationSession(
                        data_access=data_access,
                        eval_service=eval_service,
                        llm_tools=llm_tools,
                        exec_adapter=None,
                    )
                    result = asyncio.run(session.run(thesis_id))
                    st.session_state["last_evaluation_result"] = result
                    st.session_state[f"eval_result_{thesis_id}"] = result
                    st.success("Evaluation completed!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Evaluation failed: {e}")
    
    with action_col2:
        if thesis.status == ThesisStatus.ACTIVE:
            st.button("Approve Plan", disabled=True, use_container_width=True, help="Thesis is already ACTIVE")
        else:
            if st.button("Approve Plan", use_container_width=True):
                with st.spinner(f"Approving plan for {thesis.title}..."):
                    try:
                        adapter = PaperExecutionAdapter(
                            trade_repo=data_access.trade_repo,
                            price_source=price_source,
                        )
                        DEFAULT_NOTIONAL = 100_000.0
                        plan = adapter.create_plan_from_thesis(thesis, total_notional=DEFAULT_NOTIONAL)
                        trades = adapter.execute_plan(plan)
                        
                        # Mark thesis as ACTIVE
                        thesis.status = ThesisStatus.ACTIVE
                        data_access.thesis_repo.update(thesis)
                        
                        st.success(f"Plan approved! {len(trades)} trades executed.")
                        st.rerun()
                    except ValueError as e:
                        st.error(f"Plan validation failed: {e}")
                    except Exception as e:
                        st.error(f"Execution failed: {e}")


def render_portfolio_tab(data_access: DataAccess, price_source):
    """Milestone 4: Portfolio tab with P&L, totals, and risk highlights."""
    st.subheader("Portfolio")
    
    # Get portfolio snapshot
    portfolio = data_access.get_current_portfolio()
    theses = data_access.get_all_theses()
    depth = data_access.get_portfolio_depth(theses)
    
    if not portfolio or not portfolio.positions:
        st.info("No positions in portfolio.")
        return
    
    # Totals
    totals = portfolio.totals
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Portfolio Value", f"${totals.portfolio_value:,.2f}")
    with col2:
        st.metric("Gross Exposure", f"${totals.gross_exposure:,.2f}")
    with col3:
        st.metric("Net Exposure", f"${totals.net_exposure:,.2f}")
    
    # Positions table with P&L
    st.subheader("Positions")
    positions_data = []
    
    for pos in portfolio.positions:
        # Calculate P&L if we have price source
        pnl_display = "N/A"
        pnl_pct_display = ""
        current_price_display = "N/A"
        try:
            current_price = price_source.get_current_price(pos.asset)
            current_price_display = f"${current_price:.2f}"
            current_value = pos.quantity * current_price
            # For P&L, we'd need cost basis - approximate using position value
            # This is simplified - real P&L would track cost basis per trade
            pnl = current_value - pos.value
            pnl_pct = (pnl / pos.value * 100) if pos.value > 0 else 0
            pnl_display = f"${pnl:,.2f}"
            pnl_pct_display = f"({pnl_pct:.2f}%)"
        except Exception:
            pass
        
        pct_of_portfolio = (pos.value / totals.portfolio_value * 100) if totals.portfolio_value > 0 else 0
        
        positions_data.append({
            "Asset": pos.asset,
            "Quantity": f"{pos.quantity:.4f}",
            "Current Price": current_price_display,
            "Current Value": f"${pos.value:,.2f}",
            "% of Portfolio": f"{pct_of_portfolio:.2f}%",
            "P&L": pnl_display,
            "P&L %": pnl_pct_display,
        })
    
    st.dataframe(positions_data, use_container_width=True, hide_index=True)
    
    # Risk highlights
    st.subheader("Risk Highlights")
    
    # Largest position
    if positions_data:
        largest_pos = max(positions_data, key=lambda x: float(x["% of Portfolio"].replace("%", "")))
        st.write(f"**Largest Position:** {largest_pos['Asset']} ({largest_pos['% of Portfolio']})")
    
    # Concentration metrics
    if depth.concentration:
        st.write("**Concentration Metrics**")
        conc_data = []
        for asset, pct in depth.concentration.items():
            conc_data.append({
                "Asset": asset,
                "Concentration %": f"{pct:.2f}%",
            })
        st.dataframe(conc_data, use_container_width=True, hide_index=True)
    
    # Per-thesis allocation
    if depth.thesis_exposures:
        st.write("**Per-Thesis Allocation**")
        thesis_data = []
        for thesis_id, weight in depth.thesis_exposures.items():
            thesis = data_access.get_thesis(thesis_id) if thesis_id != "unassigned" else None
            title = thesis.title if thesis else "Unassigned"
            thesis_data.append({
                "Thesis": title,
                "Weight %": f"{weight:.2f}%",
            })
        st.dataframe(thesis_data, use_container_width=True, hide_index=True)


def render_alerts_tab(data_access: DataAccess, llm_tools: LLMTools):
    """Milestone 5: Alerts & Daily Runs tab with Run Daily Update and LLM diagnostics."""
    st.subheader("Alerts & Daily Runs")
    
    # Recent Alerts
    st.subheader("Recent Alerts")
    alerts = data_access.list_recent_alerts(limit=20)
    
    if alerts:
        for alert in alerts:
            with st.container():
                st.warning(f"**{alert.thesis_title}** - {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                st.write(alert.message)
                st.caption(f"Thesis ID: {alert.thesis_id}")
                if alert.observation_id:
                    st.caption(f"Observation ID: {alert.observation_id}")
                st.divider()
    else:
        st.info("No alerts found.")
    
    # Daily Update Runs
    st.subheader("Daily Update Runs")
    
    last_update = st.session_state.get("last_daily_update")
    if last_update:
        st.write(f"**Last Run:** {last_update.get('time', 'N/A')}")
        st.write(f"**Status:** {last_update.get('status', 'N/A')}")
        if 'duration' in last_update:
            st.write(f"**Duration:** {last_update['duration']:.2f}s")
    else:
        st.info("No daily update run yet.")
    
    if st.button("Run Daily Update Now", use_container_width=True):
        with st.spinner("Running daily update..."):
            try:
                import time
                start_time = time.time()
                
                session = DailyUpdateSession(
                    data_access=data_access,
                    llm_tools=llm_tools,
                )
                result = asyncio.run(session.run())
                
                duration = time.time() - start_time
                
                st.session_state["last_daily_update"] = {
                    "time": result.date.isoformat(),
                    "status": "success",
                    "duration": duration,
                }
                
                st.success(f"Daily update completed! Generated {len(result.alerts)} alerts.")
                st.rerun()
            except Exception as e:
                st.error(f"Daily update failed: {e}")
                st.session_state["last_daily_update"] = {
                    "time": date.today().isoformat(),
                    "status": "failed",
                    "error": str(e),
                }
    
    # LLM Diagnostics
    st.subheader("LLM Diagnostics")
    from slice.llm.metrics import llm_stats
    
    diagnostics_data = []
    for tool_name, stats in llm_stats.items():
        diagnostics_data.append({
            "Tool": tool_name,
            "Calls": stats.calls,
            "Errors": stats.errors,
            "Avg Latency (ms)": f"{stats.avg_latency_ms:.2f}",
        })
    
    st.dataframe(diagnostics_data, use_container_width=True, hide_index=True)


def render_qa_tab(data_access: DataAccess, llm_tools: LLMTools):
    """Milestone 6: Observations & Q&A tab with intuition query."""
    st.subheader("Observations & Q&A")
    
    # Recent Observations
    st.subheader("Recent Observations")
    observations = data_access.get_recent_observations(limit=15)
    
    if observations:
        # Store observations in session state for Q&A
        st.session_state["recent_observations"] = observations
        
        obs_data = []
        for obs in observations:
            obs_data.append({
                "Timestamp": obs.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "Text": obs.text[:100] + "..." if len(obs.text) > 100 else obs.text,
                "Categories": ", ".join(obs.categories) if obs.categories else "None",
                "Thesis Refs": ", ".join(obs.thesis_ref) if obs.thesis_ref else "None",
                "ID": obs.id,
            })
        
        st.dataframe(obs_data, use_container_width=True, hide_index=True)
        
        # Store full observations by ID for reference lookup
        obs_by_id = {obs.id: obs for obs in observations}
        st.session_state["observations_by_id"] = obs_by_id
    else:
        st.info("No observations found.")
        st.session_state["recent_observations"] = []
        st.session_state["observations_by_id"] = {}
    
    # Q&A Input
    st.subheader("Ask a Question")
    
    question = st.text_input(
        "Enter your question:",
        placeholder="e.g., What is the outlook for inflation?",
        key="qa_question_input"
    )
    
    # Optional: Filter by thesis or category (simplified for now)
    selected_thesis_filter = "All"
    if observations:
        thesis_ids = set()
        for obs in observations:
            if obs.thesis_ref:
                thesis_ids.update(obs.thesis_ref)
        
        if thesis_ids:
            selected_thesis_filter = st.selectbox(
                "Filter by thesis (optional):",
                options=["All"] + sorted(list(thesis_ids)),
                key="qa_thesis_filter"
            )
    
    if st.button("Submit Question", use_container_width=True):
        if not question:
            st.warning("Please enter a question.")
        else:
            # Get observations to use (filtered if needed)
            obs_to_use = observations
            if observations and selected_thesis_filter != "All":
                obs_to_use = [
                    obs for obs in observations
                    if selected_thesis_filter in obs.thesis_ref
                ]
            
            if not obs_to_use:
                st.warning("No observations available for the selected filter.")
            else:
                with st.spinner("Querying intuition..."):
                    try:
                        answer = asyncio.run(llm_tools.query_intuition(question, obs_to_use))
                        
                        st.session_state["last_qa_answer"] = answer
                        st.session_state["last_qa_question"] = question
                        st.rerun()
                    except Exception as e:
                        st.error(f"Q&A query failed: {e}")
    
    # Display last answer
    if st.session_state.get("last_qa_answer"):
        st.subheader("Answer")
        answer = st.session_state["last_qa_answer"]
        question = st.session_state.get("last_qa_question", "Previous question")
        
        st.write(f"**Q:** {question}")
        st.write("**A:**")
        st.markdown(answer.answer)
        
        if answer.insufficient_context:
            st.warning("⚠️ Insufficient context - answer may not be fully based on observations.")
        
        # Show referenced observations
        if answer.references:
            st.subheader("Referenced Observations")
            obs_by_id = st.session_state.get("observations_by_id", {})
            
            for ref_id in answer.references:
                if ref_id in obs_by_id:
                    obs = obs_by_id[ref_id]
                    with st.expander(f"Observation {ref_id} - {obs.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"):
                        st.write(f"**Text:** {obs.text}")
                        st.write(f"**Categories:** {', '.join(obs.categories) if obs.categories else 'None'}")
                        st.write(f"**Thesis Refs:** {', '.join(obs.thesis_ref) if obs.thesis_ref else 'None'}")
                else:
                    st.write(f"Observation {ref_id} (not found in recent observations)")


def main():
    st.set_page_config(page_title="Slice E6 UI", layout="wide")

    st.title("Slice – E6 Evaluation Harness")
    st.markdown(
        "Interactive dashboard for thesis evaluation, portfolio management, and Q&A."
    )

    # Get dependencies
    try:
        data_access = get_data_access()
        llm_tools = get_llm_tools()
    except Exception as e:
        st.error(f"Failed to initialize dependencies: {e}")
        st.stop()

    # Create 5 tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Theses", "Thesis Detail", "Portfolio", "Alerts & Daily Runs", "Observations & Q&A"]
    )

    with tab1:
        render_theses_tab(data_access, get_eval_service(), llm_tools)
    with tab2:
        render_thesis_detail_tab(data_access, get_eval_service(), llm_tools, get_price_source())
    with tab3:
        render_portfolio_tab(data_access, get_price_source())
    with tab4:
        render_alerts_tab(data_access, llm_tools)
    with tab5:
        render_qa_tab(data_access, llm_tools)


if __name__ == "__main__":
    main()
