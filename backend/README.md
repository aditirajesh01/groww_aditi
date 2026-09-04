# Backend — Delta

FastAPI + the signal engine described in `../DESIGN.md`. Runs with **zero
configuration**: no Postgres, no Redis, no LLM API keys. Every one of those has
a working fallback (see `config.py`), which is a deliberate product property,
not a convenience — `DESIGN.md` §7 argues the template summariser has to be
real for the free-tier story to hold.

## Run it

```bash
python -m venv .venv
.venv/Scripts/activate        # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/api/v1/health`. On first boot the app:

1. connects SQLite (or Postgres if `DATABASE_URL` is set and reachable),
2. runs one ingest cycle over the whole simulated universe — this is what
   populates `GET /digest` before anyone has clicked "add",
3. starts serving.

Every new `device_id` (one per browser — see `frontend/src/api/http.ts`) is
seeded with a watchlist reproducing the eight scenarios in
`app/ingest/simulator.py::SCENARIO_NOTES` (Tata Motors contradiction, Sun
Pharma drift, HDFC Bank regime change, Infosys absence, Wipro correction,
Eternal SUSPECT, TCS/DMart quiet-by-design). That is what makes the app show a
live, populated product for *anyone* who opens the hosted URL — see
`app/seed.py`.

## Optional configuration

Copy `.env.example` to `.env` only to change a default:

- `GEMINI_API_KEY` / `OPENROUTER_API_KEY` — free-tier LLM providers. Unset ->
  the router cascades straight to the deterministic template summariser.
- `DATABASE_URL` — Postgres. Unset or unreachable -> SQLite.
- `REDIS_URL` — Redis/Valkey. Unset or unreachable -> in-process dict cache.
- `FEED_ADAPTER` — `simulator` (default, the demo) or `yahoo`.

## Advancing the demo clock

```bash
curl -X POST localhost:8000/api/v1/sim/advance -d '{"hours": 24}' -H 'content-type: application/json'
```

Runs another ingest cycle at the new simulated session. See `DEMO.md` in the
repo root for the full walkthrough.

## Tests

```bash
pytest
```
