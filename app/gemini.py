"""Thin wrappers over the Gen AI SDK.

Default auth can use Vertex/ADC or a server-side GEMINI_API_KEY. A request can
also supply an API key for BYOK demos; that key is used only for that call.
"""
from google import genai
from google.genai import types
from . import config


def _default_client():
    if config.GEMINI_API_KEY:
        return genai.Client(api_key=config.GEMINI_API_KEY, vertexai=False)
    # Picks up GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION / GOOGLE_GENAI_USE_VERTEXAI
    return genai.Client()


_client = _default_client()


def _client_for(api_key: str | None = None):
    key = (api_key or "").strip()
    if key:
        return genai.Client(api_key=key, vertexai=False)
    return _client


def embed(
    texts: list[str],
    *,
    is_query: bool,
    api_key: str | None = None,
) -> list[list[float]]:
    """Return one 768-dim vector per input string."""
    task = "RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"
    resp = _client_for(api_key).models.embed_content(
        model=config.EMBED_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type=task,
            output_dimensionality=config.EMBED_DIM,
        ),
    )
    return [e.values for e in resp.embeddings]


def generate(
    prompt: str,
    system: str | None = None,
    api_key: str | None = None,
) -> tuple[str, dict]:
    """Return (text, usage_dict)."""
    cfg = types.GenerateContentConfig(system_instruction=system) if system else None
    resp = _client_for(api_key).models.generate_content(
        model=config.GEN_MODEL,
        contents=prompt,
        config=cfg,
    )
    usage = {}
    if getattr(resp, "usage_metadata", None):
        usage = {
            "prompt_tokens": resp.usage_metadata.prompt_token_count,
            "output_tokens": resp.usage_metadata.candidates_token_count,
        }
    return (resp.text or ""), usage
