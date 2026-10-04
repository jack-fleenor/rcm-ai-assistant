# RCM AI Assistant (v0.1)

Basic FastAPI + LLM demo for **internal RCM denial triage**.

Built as a portfolio slice aligned with AI fullstack / ops-tooling roles: versioned prompts, application-layer PHI minimization, structured LLM output, and a tiny evaluation harness.

## What it demonstrates

- **Python / FastAPI** REST API with validation and production-style error handling
- **Prompt library** with versioned YAML prompts (`denial_review` v1 / v2)
- **LLM integration** via local Ollama (swap-friendly provider seam; `mock` for offline demos)
- **PHI minimization** before model calls (phone / MRN / SSN / email patterns)
- **Eval loop** against a golden set (`POST /api/eval/run`)
- **Ops-oriented UI** — minimal coordinator-facing triage page at `/`

## Quick start

```bash
cd rcm-ai-assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Offline deterministic demo (no model required)
export LLM_PROVIDER=mock
uvicorn app.main:app --reload --port 8088
```

Open [http://127.0.0.1:8088](http://127.0.0.1:8088) or docs at `/docs`.

### With local Ollama

```bash
export LLM_PROVIDER=ollama
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OLLAMA_MODEL=gpt-oss:20b   # or any local model
uvicorn app.main:app --reload --port 8088
```

## Useful endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Simple triage UI |
| GET | `/api/prompts` | List prompt versions |
| POST | `/api/triage` | Run denial triage |
| POST | `/api/mask` | Preview PHI masking |
| POST | `/api/eval/run` | Score golden set |
| GET | `/api/samples` | Sample denial fixtures |

Example:

```bash
curl -s -X POST http://127.0.0.1:8088/api/triage \
  -H 'content-type: application/json' \
  -d '{
    "payer":"Aetna",
    "cpt":"64483",
    "denial_code":"CO-197",
    "denial_reason":"Precertification/authorization absent",
    "notes":"Patient MRN 99881 called 555-010-9999 about ESI auth."
  }' | python3 -m json.tool
```

## Project layout

```
app/           FastAPI app, LLM client, PHI helpers, eval scoring
prompts/       Versioned prompt definitions
data/          Sample denials (synthetic)
evals/         Golden expectations for prompt regression
```

## Not in v0.1 (intentional)

Retool UI, Snowflake/dbt connectors, enterprise IdP/RBAC, full HIPAA program controls, Bedrock/Claude Enterprise adapters.

Those are natural next increments — this repo is the thin vertical slice.

## Disclaimer

Synthetic denial data only. PHI patterns are **demo-level** application controls, not a compliance certification.
