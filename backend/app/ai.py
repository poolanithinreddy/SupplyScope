import json
import os

import httpx


def optional_llm_explanation(outlook: dict, deterministic: dict) -> dict:
    """Rewrite a deterministic explanation without delegating decisions to the model."""
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        return deterministic
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gpt-5-mini")
    prompt = (
        "Explain why this synthetic order is at risk in 2-3 concise sentences. "
        "Use only the supplied calculation and records. Do not recompute quantities, rank options, "
        "or recommend an approval. Preserve all IDs, quantities, and dates exactly.\n\n"
        + json.dumps({"deterministic_explanation": deterministic["answer"], "order_outlook": outlook}, default=str)
    )
    try:
        response = httpx.post(
            f"{base_url}/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "input": prompt},
            timeout=8.0,
        )
        response.raise_for_status()
        text = response.json().get("output_text")
        return {**deterministic, "answer": text, "mode": "llm_grounded"} if text else deterministic
    except (httpx.HTTPError, ValueError, KeyError):
        return deterministic
