# Opportunity Intelligence Agent

> **Don't just find opportunities. Run them like missions.**

An 8-agent system that discovers, investigates, verifies, matches, prepares,
cold-outreach drafts, human-approves and continuously monitors opportunities —
on live SerpApi intelligence, via OpenRouter tool-calling, with Gmail execution.

## Problem / Solution

Opportunities are fragmented across jobs, labs, research and news; users manually
verify, match, draft and remember follow-ups, and saved links go stale. This system
turns that into a closed loop: **Discover → Investigate → Verify → Match →
Prepare → Approve → Act → Monitor → re-verify on change.**

## Architecture

```
React(Vite/Tailwind/three/GSAP/Lenis) :5173
        │ REST
FastAPI backend :8000 ── SerpApi (7 engines, cached, budgeted)
        │          └──── OpenRouter (chat + real tool-calling loop)
        └──── MongoDB (or local JSON-file fallback in ./data)
Orchestrator + Planner, Discovery, Investigator, Verifier, Match,
Application, Outreach(+Followup), Monitor. Approval gate before any send.
```

## Agents (all real, in `backend/app/agents.py`)

Planner · Discovery · Investigator · Verifier · Match · Application ·
Outreach · Monitor (+Followup) · Orchestrator control plane with budget
enforcement, retries, dedupe, persisted resumable state, activity timeline.

## Setup

```bash
cp .env.example .env   # then fill keys (never commit .env)
# backend
cd backend && pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
# frontend
cd frontend && npm install && npm run dev   # :5173
```

## Environment

| Var | Purpose |
|---|---|
| `SERPAPI_API_KEY` / `SERPAPI_MONTHLY_BUDGET` (250) | live search + quota cap |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` (default `openai/gpt-4o-mini` + fallbacks) | LLM + tool calling |
| `MONGODB_URI` (empty → local JSON fallback) | persistence |
| `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI` | Gmail OAuth (optional) |
| `DEMO_MODE=true` | enables simulated change-detection demos |

## API docs / tests

- Swagger: `http://localhost:8000/api/docs` · OpenAPI JSON: `/api/openapi.json`
- Unit + zero-credit E2E: `cd backend && python -m pytest tests/test_unit.py tests/test_e2e.py -q`
- Live integration (spends ~5 SerpApi credits): `GET /api/test/all`, per-engine `/api/test/serpapi/*`, `/api/test/openrouter`, `/api/test/openrouter/tools`
- CLI: `npm run test:integrations` (safe default) · `npm run test:integrations:live`

## Demo (2 min)

1. Open `/` landing → **Live demo** (or sign up).
2. Console → **Demo data** (or Discover — spends ~2 searches).
3. Open an opportunity → Investigate → Verify → Match → Prepare application.
4. Outreach tab → Find contact + draft → Approvals → Approve → Gmail draft/`.eml` → Send.
5. Watch → Check now. With `DEMO_MODE=true`, check-now accepts `{"simulated": {...}}`
   to demo deadline-change → re-verify → notification.

## Quota design

`SEARCH_CACHE` (1h) · `SEARCH_USAGE` vs monthly budget · `SEARCH_HISTORY`.
Doctrine: 1 broad search → shortlist → selective deep dives. Cached = free.

## Gmail

OAuth only (no API-key shortcut): connect in Setup → draft → approve → send.
Unconnected = local draft + downloadable `.eml`; sends are never faked.

## Troubleshooting

- `bg-paper does not exist` in dev → restart `npm run dev` (stale Tailwind config).
- Port busy → stop old `uvicorn`/`vite` processes.
- SerpApi 400 on Maps → client auto-adds `z=13` (required with `location`).
- OpenRouter timeouts → model fallback chain engages automatically.

## Security

Keys server-side only · secrets never logged · pbkdf2 password hashes ·
bearer sessions · approval gate + daily outreach cap (20) + follow-up cap (2).

## Limitations / roadmap

File-fallback DB is single-node; universal auto-apply is intentionally absent
(official links + adapter stubs instead); Flights/Hotels wired but unused by
default; scheduler is on-demand (cron/APScheduler next).
