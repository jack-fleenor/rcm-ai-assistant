from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.eval import load_golden, load_samples, score_case
from app.llm import LLMError, complete, parse_json_response
from app.phi import mask_phi
from app.prompts import get_prompt, list_prompts, render_user_prompt

app = FastAPI(
    title=settings.app_name,
    description=(
        "Basic internal AI tool demo: versioned prompts, PHI minimization, "
        "LLM triage for RCM denials, and a tiny evaluation harness."
    ),
    version="0.1.0",
)


class DenialInput(BaseModel):
    payer: str
    cpt: str
    denial_code: str
    denial_reason: str
    notes: str = ""
    prompt_id: str = "denial_review"
    prompt_version: str | None = None


class TriageResponse(BaseModel):
    prompt_id: str
    prompt_version: str
    provider: str
    phi_redactions: int
    result: dict[str, Any]
    masked_notes: str


class MaskRequest(BaseModel):
    text: str = Field(..., examples=["Patient MRN 12345 called 555-010-9999"])


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RCM AI Assistant</title>
  <style>
    :root { --bg:#f3efe6; --ink:#1c2416; --accent:#0f5c4c; --line:#c9c0b0; }
    body { margin:0; font-family: "IBM Plex Sans", "Segoe UI", sans-serif; background:
      radial-gradient(circle at top left, #dff0e8, transparent 40%),
      linear-gradient(160deg, #f3efe6, #e7ddd0); color:var(--ink); }
    main { max-width: 880px; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }
    h1 { font-family: "Iowan Old Style", "Palatino Linotype", serif; font-size: clamp(2rem, 5vw, 3rem); margin:0 0 .4rem; }
    p { line-height:1.5; max-width: 60ch; }
    a { color: var(--accent); }
    .panel { margin-top:1.5rem; padding:1rem 1.1rem; border:1px solid var(--line); background: rgba(255,255,255,.55); }
    code, pre { font-family: "IBM Plex Mono", ui-monospace, monospace; font-size:.9rem; }
    pre { white-space: pre-wrap; background:#1c2416; color:#eef6f1; padding:1rem; overflow:auto; }
    button { background:var(--accent); color:white; border:0; padding:.65rem 1rem; cursor:pointer; }
    label { display:block; font-size:.85rem; margin-top:.75rem; }
    textarea, select, input { width:100%; box-sizing:border-box; margin-top:.25rem; padding:.55rem; border:1px solid var(--line); background:white; }
  </style>
</head>
<body>
<main>
  <h1>RCM AI Assistant</h1>
  <p>Basic FastAPI + LLM denial triage demo: versioned prompts, PHI masking, and a golden-set eval loop. Built as a portfolio slice for internal healthcare ops tooling.</p>
  <p><a href="/docs">OpenAPI docs</a> · <a href="/api/prompts">Prompt library</a> · <a href="/api/samples">Sample denials</a></p>

  <div class="panel">
    <label>Sample denial
      <select id="sample"></select>
    </label>
    <label>Prompt version
      <select id="version">
        <option value="">latest</option>
        <option value="1.0.0">1.0.0</option>
        <option value="2.0.0">2.0.0</option>
      </select>
    </label>
    <label>Notes
      <textarea id="notes" rows="4"></textarea>
    </label>
    <p style="margin-top:1rem"><button id="run">Triage denial</button></p>
    <pre id="out">Ready.</pre>
  </div>
</main>
<script>
async function boot() {
  const samples = await fetch('/api/samples').then(r => r.json());
  const sel = document.getElementById('sample');
  samples.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s.id; opt.textContent = `${s.id} · ${s.payer} · ${s.denial_code}`;
    sel.appendChild(opt);
  });
  const apply = () => {
    const s = samples.find(x => x.id === sel.value);
    document.getElementById('notes').value = s.notes;
    window.__sample = s;
  };
  sel.onchange = apply; apply();
  document.getElementById('run').onclick = async () => {
    const s = window.__sample;
    const body = {
      payer: s.payer, cpt: s.cpt, denial_code: s.denial_code,
      denial_reason: s.denial_reason,
      notes: document.getElementById('notes').value,
      prompt_id: 'denial_review',
      prompt_version: document.getElementById('version').value || null
    };
    document.getElementById('out').textContent = 'Running...';
    const res = await fetch('/api/triage', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
    const data = await res.json();
    document.getElementById('out').textContent = JSON.stringify(data, null, 2);
  };
}
boot();
</script>
</body>
</html>
"""


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "provider": settings.llm_provider}


@app.get("/api/prompts")
async def api_list_prompts() -> list[dict[str, Any]]:
    return list_prompts()


@app.get("/api/samples")
async def api_samples() -> list[dict[str, Any]]:
    return list(load_samples().values())


@app.post("/api/mask")
async def api_mask(body: MaskRequest) -> dict[str, Any]:
    masked, hits = mask_phi(body.text)
    return {"masked": masked, "redactions": hits}


@app.post("/api/triage", response_model=TriageResponse)
async def api_triage(body: DenialInput) -> TriageResponse:
    prompt = get_prompt(body.prompt_id, body.prompt_version)
    masked_notes, hits = mask_phi(body.notes)
    values = {
        "payer": body.payer,
        "cpt": body.cpt,
        "denial_code": body.denial_code,
        "denial_reason": body.denial_reason,
        "notes": masked_notes,
    }
    user = render_user_prompt(prompt["user_template"], values)
    try:
        raw = await complete(prompt["system"], user)
        result = parse_json_response(raw)
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"Invalid model JSON: {exc}") from exc

    return TriageResponse(
        prompt_id=prompt["id"],
        prompt_version=prompt["version"],
        provider=settings.llm_provider,
        phi_redactions=hits,
        result=result,
        masked_notes=masked_notes,
    )


@app.post("/api/eval/run")
async def api_eval_run(
    prompt_version: str | None = Query(default=None),
) -> dict[str, Any]:
    """Run the golden set through the current prompt + provider."""
    samples = load_samples()
    golden = load_golden()
    cases = []
    passed = 0
    for item in golden:
        sample = samples.get(item["case_id"])
        if not sample:
            cases.append({"case_id": item["case_id"], "error": "sample missing"})
            continue
        triage = await api_triage(
            DenialInput(
                payer=sample["payer"],
                cpt=sample["cpt"],
                denial_code=sample["denial_code"],
                denial_reason=sample["denial_reason"],
                notes=sample["notes"],
                prompt_version=prompt_version,
            )
        )
        scored = score_case(triage.result, item["expect"])
        if scored["passed"]:
            passed += 1
        cases.append(
            {
                "case_id": item["case_id"],
                "prompt_version": triage.prompt_version,
                "result": triage.result,
                **scored,
            }
        )
    total = len(golden)
    return {
        "provider": settings.llm_provider,
        "prompt_version": prompt_version or "latest",
        "passed": passed,
        "total": total,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "cases": cases,
    }
