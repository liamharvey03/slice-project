from typing import Optional, Dict, Any, List

from .models import SessionOptions, SessionMode


SYSTEM_PROMPT = """
You are Slice, a deterministic macro reasoning assistant.

Rules:
1. You NEVER compute returns, greeks, vol, risk metrics, or forecasts.
2. You NEVER hallucinate trades, positions, or portfolio state.
3. You ONLY reason over the explicit text blocks I give you:
   - Memory Context (if provided)
   - Risk Snapshot (if provided)
   - User Message
4. You do NOT assume any hidden data.
5. No autonomous actions. You only provide structured reasoning and explanations.
6. Never contradict provided memory or risk data.
7. Be concise in CONCISE mode; be structured and analytic in ANALYST mode.
"""

def _format_memory_block(memory_ctx: Dict[str, Any]) -> str:
    if not memory_ctx:
        return ""
    lines = ["[MEMORY CONTEXT]"]
    for item in memory_ctx.get("items", []):
        lines.append(
            f"- (obs {item['observation_id']}, sim={item['similarity']:.3f}) "
            f"{item['text']} | thesis_ref={item['thesis_ref']}"
        )
    return "\n".join(lines)


def _format_risk_block(risk_ctx: Dict[str, Any]) -> str:
    if not risk_ctx:
        return ""
    lines = ["[RISK SNAPSHOT]"]
    lines.append(f"Book Gross: {risk_ctx.get('book_gross')}")
    lines.append(f"Book Net: {risk_ctx.get('book_net')}")
    if risk_ctx.get("duration") is not None:
        lines.append(f"Duration: {risk_ctx['duration']}")
    if risk_ctx.get("dv01") is not None:
        lines.append(f"DV01: {risk_ctx['dv01']}")
    lines.append("Exposures:")
    for exp in risk_ctx.get("exposures", []):
        lines.append(f"- {exp}")
    lines.append("Backtests:")
    for bt in risk_ctx.get("backtests", []):
        lines.append(f"- {bt}")
    return "\n".join(lines)


def build_prompt(
    memory_ctx: Optional[dict],
    risk_ctx: Optional[dict],
    user_text: str,
    options: SessionOptions,
) -> List[Dict[str, str]]:
    """
    Deterministic prompt assembly:
      1. SYSTEM message
      2. USER message containing:
           - Memory block (if any)
           - Risk block (if any)
           - User text
    """

    blocks = []

    # 1. Memory first
    if memory_ctx:
        blocks.append(_format_memory_block(memory_ctx))

    # 2. Risk next
    if risk_ctx:
        blocks.append(_format_risk_block(risk_ctx))

    # 3. User message last
    blocks.append(f"[USER MESSAGE]\n{user_text}")

    # Mode-specific header
    if options.mode == SessionMode.ANALYST:
        mode_header = "[MODE: ANALYST — structured, multi-step, grounded in provided data]"
    elif options.mode == SessionMode.CONCISE:
        mode_header = "[MODE: CONCISE — short, compressed reasoning]"
    else:
        mode_header = "[MODE: STANDARD]"

    full_user_prompt = mode_header + "\n\n" + "\n\n".join(blocks)

    return [
        {"role": "system", "content": SYSTEM_PROMPT.strip()},
        {"role": "user", "content": full_user_prompt.strip()},
    ]