"""
E4: DailyUpdateSession - Daily portfolio update workflow with alert detection.
"""
from datetime import date, datetime, timedelta
from typing import List

from voyager.intelligence.context.data_access import DataAccess
from voyager.llm.llm_tools import LLMTools
from voyager.models.session_results import DailyUpdateSessionResult
from voyager.models.llm_inputs import DailyContext, Alert
from voyager.models.llm_outputs import DailySummary
from voyager.models.thesis import Thesis
from voyager.models.observation import Observation


class DailyUpdateSession:
    """
    Orchestrates daily portfolio update: load state, detect alerts, generate summary.
    
    Graceful degradation: alerts are persisted even if LLM summary fails.
    LLM failure results in DailySummary with insufficient_context=True.
    """

    def __init__(self, data_access: DataAccess, llm_tools: LLMTools) -> None:
        """
        Initialize the session with required dependencies.
        
        Args:
            data_access: Data access layer
            llm_tools: E3 LLM tools wrapper
        """
        self.data = data_access
        self.llm = llm_tools

    async def run(self, as_of: date | None = None) -> DailyUpdateSessionResult:
        """
        Run the daily update workflow.
        
        Steps:
        1. Load active theses and current portfolio state
        2. Compute portfolio depth/risk snapshot
        3. Load recent observations and detect alerts
        4. Persist alerts (before LLM call, so they survive LLM failure)
        5. Build DailyContext for LLM
        6. Run LLM summary with graceful degradation
        7. Persist summary and return result
        
        Args:
            as_of: Date to run update for (defaults to today)
            
        Returns:
            DailyUpdateSessionResult with portfolio snapshot, alerts, and summary
        """
        run_date = as_of or date.today()

        # 1. Load active theses and portfolio
        theses = self.data.get_active_theses()
        portfolio = self.data.get_current_portfolio()
        depth = self.data.get_portfolio_depth(theses)

        # 2. Load recent observations and detect alerts
        recent_obs = self.data.get_recent_observations(limit=50)
        alerts = self._detect_alerts(theses, recent_obs)

        # 3. Persist alerts BEFORE LLM call (survive LLM failure)
        if alerts:
            self.data.save_alerts(alerts)

        # 4. Build DailyContext for LLM
        # Get previous day's portfolio value for change calculation
        prev_snapshot = self.data.get_daily_summary(run_date - timedelta(days=1))
        prev_value: float | None = None
        if prev_snapshot and hasattr(prev_snapshot, "portfolio_value"):
            prev_value = getattr(prev_snapshot, "portfolio_value", None)
        
        portfolio_value = portfolio.totals.portfolio_value if portfolio else None
        portfolio_change_pct: float | None = None
        if portfolio_value is not None and prev_value is not None and prev_value > 0:
            portfolio_change_pct = ((portfolio_value / prev_value) - 1.0) * 100.0

        # Convert alerts to Alert objects for DailyContext (they're already Alert objects)
        context_alerts = alerts

        # Build DailyContext
        context = DailyContext(
            date=run_date,
            portfolio_snapshot=portfolio,
            alerts=context_alerts,
            observations=recent_obs[:10],  # Top 10 observations
            active_theses=theses,
        )

        # 5. Run LLM summary with graceful degradation
        try:
            summary = await self.llm.daily_summary(context)
        except Exception:
            # LLM failure: return synthetic summary with insufficient_context=True
            summary = DailySummary(
                key_narratives=[],
                risk_highlights=[],
                thesis_references=[],
                insufficient_context=True,
            )

        # 6. Persist summary and return result
        self.data.save_daily_summary(run_date, summary)

        return DailyUpdateSessionResult(
            date=run_date,
            portfolio_snapshot=portfolio,
            portfolio_depth=depth,
            alerts=alerts,
            summary=summary,
        )

    def _detect_alerts(
        self, theses: List[Thesis], observations: List[Observation]
    ) -> List[Alert]:
        """
        Detect alerts by matching observations to theses.
        
        An alert is generated when:
        - An observation has thesis_refs matching a thesis ID
        - The observation is actionable (actionable == "YES")
        
        Note: Full disconfirmation matching (comparing observation text to thesis
        disconfirmers) would require more sophisticated NLP and is simplified here
        for E4. In production, this could use LLM-based matching.
        
        Args:
            theses: List of active theses
            observations: Recent observations to check
            
        Returns:
            List of Alert objects
        """
        alerts: List[Alert] = []
        
        # Build thesis lookup by ID
        thesis_by_id = {t.id: t for t in theses}
        
        for obs in observations:
            # Get thesis references from observation
            thesis_refs = obs.thesis_ref
            if not isinstance(thesis_refs, list):
                thesis_refs = [thesis_refs] if thesis_refs else []
            
            # Check if observation is actionable
            actionable = obs.actionable.upper() == "YES"
            
            # Generate alerts for actionable observations linked to theses
            if actionable:
                for thesis_id in thesis_refs:
                    if thesis_id not in thesis_by_id:
                        continue
                    
                    thesis = thesis_by_id[thesis_id]
                    
                    # Build alert message from observation text (truncated)
                    message = obs.text[:200] if len(obs.text) > 200 else obs.text
                    
                    alerts.append(
                        Alert(
                            thesis_id=thesis.id,
                            thesis_title=thesis.title,
                            message=message,
                            observation_id=obs.id,
                            timestamp=obs.timestamp,
                        )
                    )
        
        return alerts

