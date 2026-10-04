from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_PATH = ROOT / "evals" / "golden_set.json"
SAMPLES_PATH = ROOT / "data" / "sample_denials.json"


def load_samples() -> dict[str, dict[str, Any]]:
    rows = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    return {row["id"]: row for row in rows}


def load_golden() -> list[dict[str, Any]]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def score_case(result: dict[str, Any], expect: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    notes: list[str] = []

    if "priority" in expect:
        checks["priority"] = str(result.get("priority", "")).lower() == expect["priority"]
        if not checks["priority"]:
            notes.append(
                f"priority expected={expect['priority']} got={result.get('priority')}"
            )

    if "needs_clinical_review" in expect:
        checks["needs_clinical_review"] = bool(result.get("needs_clinical_review")) == bool(
            expect["needs_clinical_review"]
        )
        if not checks["needs_clinical_review"]:
            notes.append("needs_clinical_review mismatch")

    if "denial_category_contains" in expect:
        category = str(result.get("denial_category", "")).lower()
        needles = [n.lower() for n in expect["denial_category_contains"]]
        checks["denial_category"] = any(n in category for n in needles)
        if not checks["denial_category"]:
            notes.append(f"denial_category '{category}' missing any of {needles}")

    passed = all(checks.values()) if checks else False
    return {"passed": passed, "checks": checks, "notes": notes}
