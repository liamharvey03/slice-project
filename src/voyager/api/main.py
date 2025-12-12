import os
from fastapi import FastAPI

# Routers
from voyager.api.session_routes import router as session_router
from voyager.api.intelligence_routes import router as intelligence_router
from voyager.api.memory_app import app as memory_app
from voyager.api.ui_routes import router as ui_router
from voyager.api.diagnostics_routes import router as diagnostics_router
from voyager.api.session_routes_e4 import router as e4_session_router
from voyager.api.v3_routes import router as v3_router

# Dependency wiring
from voyager.api.deps import (
    get_data_access_instance,
    get_orchestrator_client_instance,
    get_price_source_instance,
)
from voyager.intelligence.context.data_access import DataAccess
from voyager.intelligence.orchestrator_client import OrchestratorClient
from voyager.evaluation.thesis_evaluation import ThesisEvaluationService

app = FastAPI(title="Voyager API", version="0.1")


@app.on_event("startup")
def wire_dependencies():
    """Wire production dependencies for E4 and related endpoints."""
    # Create singleton instances
    data_access = get_data_access_instance()
    orchestrator_client = get_orchestrator_client_instance()
    price_source = get_price_source_instance()
    
    # Use dependency_overrides for all dependencies
    # (Cannot directly reassign classmethods; must use app.dependency_overrides)
    app.dependency_overrides[DataAccess.depends] = lambda: data_access
    app.dependency_overrides[OrchestratorClient.depends] = lambda: orchestrator_client
    
    # For session_routes_e4.py dependency providers
    import voyager.api.session_routes_e4 as e4_routes
    # Override get_eval_service to use real price source
    def get_eval_service_override():
        return ThesisEvaluationService(price_source=price_source)
    app.dependency_overrides[e4_routes.get_eval_service] = get_eval_service_override
    
    # Optionally apply E4 schema if enabled (dev/testing only)
    if os.getenv("VOYAGER_AUTO_APPLY_SCHEMA", "false").lower() == "true":
        from voyager.db import apply_e4_schema
        apply_e4_schema()

# Core APIs
app.include_router(session_router, prefix="/session", tags=["session"])
app.include_router(intelligence_router, prefix="/intelligence", tags=["intelligence"])

# E4 Session APIs
app.include_router(e4_session_router)

# UI-facing APIs
app.include_router(ui_router, prefix="/ui", tags=["ui"])

# Diagnostics APIs
app.include_router(diagnostics_router, tags=["diagnostics"])

# V3 APIs
app.include_router(v3_router)

# Memory app
app.mount("/memory", memory_app)
