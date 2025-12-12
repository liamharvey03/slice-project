import os
from typing import List
from openai import OpenAI

_client = None

def _get_openai():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def embed_observation_text(text: str) -> List[float]:
    """
    Compute embedding for observation text using the model declared in .env:
      OPENAI_EMBEDDING_MODEL="text-embedding-3-large"
    """
    model = os.getenv("OPENAI_EMBEDDING_MODEL")
    if not model:
        raise RuntimeError("OPENAI_EMBEDDING_MODEL not set in environment")

    client = _get_openai()

    # This uses the current OpenAI Python SDK format
    resp = client.embeddings.create(
        model=model,
        input=text,
    )
    return resp.data[0].embedding