from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import settings


class LLMError(Exception):
    pass


async def complete(system: str, user: str) -> str:
    provider = settings.llm_provider.lower()
    if provider == "mock":
        return _mock_complete(user)
    if provider == "ollama":
        return await _ollama_complete(system, user)
    raise LLMError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")


async def _ollama_complete(system: str, user: str) -> str:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise LLMError(
            f"Ollama request failed ({exc}). Start Ollama or set LLM_PROVIDER=mock."
        ) from exc
    content = data.get("message", {}).get("content")
    if not content:
        raise LLMError("Empty response from Ollama")
    return content


def _mock_complete(user: str) -> str:
    """Deterministic offline response for demos without a model runtime."""
    lower = user.lower()
    if "precert" in lower or "authorization" in lower or "auth" in lower:
        return json.dumps(
            {
                "priority": "high",
                "denial_category": "missing authorization",
                "likely_root_cause": "Auth not obtained before date of service",
                "recommended_actions": [
                    "Confirm auth submission timestamp vs DOS",
                    "File retrospective auth if payer allows",
                    "Update scheduling checklist to block unauth DOS",
                ],
                "needs_clinical_review": False,
                "appeal_ready": False,
                "summary_for_coordinator": "High priority auth miss. Verify timing, attempt retro auth, prevent repeat.",
            }
        )
    if "medical necessity" in lower or "non-covered" in lower:
        return json.dumps(
            {
                "priority": "high",
                "denial_category": "medical necessity",
                "likely_root_cause": "Insufficient conservative care documentation",
                "recommended_actions": [
                    "Pull therapy/med trial notes",
                    "Request clinical addendum if warranted",
                    "Draft appeal with guideline citations",
                ],
                "needs_clinical_review": True,
                "appeal_ready": False,
                "summary_for_coordinator": "Needs clinical review for medical necessity; gather conservative-care evidence before appeal.",
            }
        )
    return json.dumps(
        {
            "priority": "medium",
            "denial_category": "coding",
            "likely_root_cause": "Modifier or code pairing issue",
            "recommended_actions": [
                "Review modifier -25 documentation",
                "Correct claim if coding error confirmed",
                "Resubmit with supporting note",
            ],
            "needs_clinical_review": False,
            "appeal_ready": True,
            "summary_for_coordinator": "Likely coding/modifier issue; coding review then correct and resubmit.",
        }
    )


def parse_json_response(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        data = json.loads(match.group(0))
        if isinstance(data, dict):
            return data
    raise LLMError("Model response was not valid JSON")
