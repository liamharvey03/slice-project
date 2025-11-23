from slice.memory.context_builder import MemoryContextBuilder


class PromptBuilder:

    @staticmethod
    def observation_prompt(raw: dict) -> str:
        """
        Builds the complete LLM prompt for validating an observation, including:
        - Raw user payload
        - Retrieved memory context
        """
        text = raw.get("text", "")

        # Pull relevant memory
        ctx = MemoryContextBuilder.build_for_text(
            text=text,
            k=5,
            max_chars=2500,
        )

        memory_block = ctx["context_block"]

        base = f"""You are validating a macro-market observation.

New observation:
{text}

Metadata:
- timestamp: {raw.get("timestamp")}
- thesis_ref: {raw.get("thesis_ref")}
- sentiment: {raw.get("sentiment")}
- categories: {raw.get("categories")}
- actionable: {raw.get("actionable")}

"""

        if memory_block:
            base += f"""Relevant prior observations:
{memory_block}

"""

        base += """Validation task:
1. Ensure schema correctness.
2. Normalize fields if appropriate.
3. DO NOT change factual content.
4. Return corrected structure without commentary."""

        return base