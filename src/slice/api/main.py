from fastapi import FastAPI

# Routers
from slice.api.session_routes import router as session_router
from slice.api.intelligence_routes import router as intelligence_router
from slice.api.memory_app import app as memory_app
from slice.api.ui_routes import router as ui_router

app = FastAPI(title="Slice API", version="0.1")

# Core APIs
app.include_router(session_router, prefix="/session", tags=["session"])
app.include_router(intelligence_router, prefix="/intelligence", tags=["intelligence"])

# UI-facing APIs
app.include_router(ui_router, prefix="/ui", tags=["ui"])

# Memory app
app.mount("/memory", memory_app)
