class MockLLMClient:
    def __init__(self):
        self.calls = []

    async def generate(self, messages, temperature=0):
        self.calls.append(messages)
        # simulate an LLM response object
        return {
            "response": "Mock LLM output",
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
            "latency_ms": 1,
        }