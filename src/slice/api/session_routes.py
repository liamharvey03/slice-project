from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.slice.session.orchestrator import SessionOrchestrator
from src.slice.session.models import SessionOptions, SessionResponse

# LLM client must be injected; for now use a placeholder or DI pattern
# Your actual implementation will replace DummyLLM when wiring FastAPI app.

class DummyLLM:
    model_name = "dummy-llm"

    async def chat(self, messages):
        return {
            "content": "LLM_NOT_CONFIGURED",
            "usage": {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
            },
        }


router = APIRouter()


class SessionRequest(BaseModel):
    text: str
    options: SessionOptions


@router.post("/api/v1/session/step", response_model=SessionResponse)
async def session_step(payload: SessionRequest):
    """
    Calls the SessionOrchestrator with provided text + options.
    """
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    orchestrator = SessionOrchestrator(llm_client=DummyLLM())

    return await orchestrator.run_session(
        text=payload.text,
        options=payload.options,
    )