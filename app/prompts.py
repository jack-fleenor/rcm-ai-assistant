from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_file(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "id" not in data or "version" not in data:
        raise ValueError(f"Invalid prompt file: {path.name}")
    data["_file"] = path.name
    return data


def list_prompts() -> list[dict[str, Any]]:
    prompts = [_load_file(p) for p in sorted(PROMPTS_DIR.glob("*.yaml"))]
    return [
        {
            "id": p["id"],
            "version": p["version"],
            "description": p.get("description", ""),
            "file": p["_file"],
        }
        for p in prompts
    ]


def get_prompt(prompt_id: str, version: str | None = None) -> dict[str, Any]:
    matches = []
    for path in PROMPTS_DIR.glob("*.yaml"):
        p = _load_file(path)
        if p["id"] != prompt_id:
            continue
        matches.append(p)
    if not matches:
        raise HTTPException(status_code=404, detail=f"Unknown prompt id: {prompt_id}")
    if version is None:
        # Highest semver-ish string sort is fine for v1/v2 demo.
        return sorted(matches, key=lambda x: x["version"])[-1]
    for p in matches:
        if p["version"] == version:
            return p
    raise HTTPException(
        status_code=404,
        detail=f"Prompt {prompt_id} version {version} not found",
    )


def render_user_prompt(template: str, values: dict[str, str]) -> str:
    out = template
    for key, value in values.items():
        out = out.replace("{{" + key + "}}", value)
    return out
