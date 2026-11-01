# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

HubRecover is a local, synthetic airline disruption-recovery prototype (Python 3.11+, Google ADK 2.11 graph workflows, Gemini, FastAPI, SQLite, vanilla JS web UI). **[AGENT.md](AGENT.md) holds the binding implementation conventions, safety boundaries and delivery preferences — read it first.** Product policy lives in PRD.md; ARCHITECTURE-ADK.md defines the backend and durable-execution contracts; DESIGN.md and TEST-PLAN.md cover UI and evaluation.

## Commands

```sh
uv sync --locked                      # install (uv.lock is pinned)
uv run python -m hubrecover           # serve on http://127.0.0.1:8765 (port 8000 deliberately avoided)
uv run python -m hubrecover --data-dir /tmp/hubrecover-demo --port 8766   # isolated ledger
make test                             # pytest -q + node --check hubrecover/web/app.js
uv run pytest tests/test_allocation.py -q            # single file
uv run pytest tests/test_gate.py::test_name -q       # single test
uv run python -m hubrecover.fixtures.reference       # reference fixture invariants
uv run python -m evaluation.held_out                 # 20-variant deterministic suite
uv run python -m evaluation.benchmark                # rules-only trigger-to-card benchmark
uv run python -m evaluation.smoke                    # real FastAPI + ADK end-to-end workflow
uv run python -m evaluation.live_ai --repeats 1      # real Gemini calls; needs .env credentials
```

AGENT.md also names `.venv/bin/python -m pytest`. The full suite takes about 75 s. Unit tests use stand-in transports and never call the real provider. `evaluation.live_ai` makes billable, paced requests (exit codes: 0 pass, 1 fail, 2 NOT_RUN for missing config), so run it only when asked.

Gemini is optional: the full demo runs rules-only. `hubrecover/config.py` loads only `GOOGLE_API_KEY` and `HUBRECOVER_GEMINI_MODEL` from the repo-local `.env`, and existing environment variables take precedence. Runtime data (business ledger + ADK session DB) lives in `.hubrecover/` (git-ignored).

Deployment: Fly.io app `hubrecover` (https://hubrecover.fly.dev), deployed with `fly deploy --ha=false` (single machine, SQLite on the `/data` volume). The API middleware rejects non-loopback hosts unless `HUBRECOVER_PASSWORD` is set, in which case `HUBRECOVER_ALLOWED_HOSTS` (set in `fly.toml`) is honoured behind HTTP Basic auth. `FORWARDED_ALLOW_IPS=*` is needed so the same-origin check sees `https`.

## Architecture

Three layers, with authority flowing strictly downward:

- **`hubrecover/domain/`**: pure Python with no HTTP, ADK or model imports. `monitoring` decides triggers from restriction events. `universe` selects the finite candidate descriptors. `gate` validates operations. `allocation` does whole-party, net-seat passenger allocation. `planning` materialises and ranks plans and produces canonical digests/fingerprints. `evidence` handles playbook retrieval and warnings. `claims` defines the AI output schemas and the explanation validator. `invariants`, `schemas` and `policy` hold the frozen policy and strict models.
- **`hubrecover/application/`**:
  - `service.py` (`RecoveryService`) is the authoritative state machine. Every mutation goes through `service.command(run_id, action, revision=, key=, role=, payload=)`, which is revision-bound, idempotency-keyed and role-checked, and raises `Refusal` on stale or invalid authority. Terminal states are `COMPLETED`, `MANUAL_HANDOFF` and `PARTIAL_MANUAL`.
  - `store.py` is the SQLite business ledger.
  - `jobs.py` holds durable jobs with worker leases and fencing.
  - `sources.py` handles typed synthetic source updates.
  - `handoffs.py` covers manual work packets.
  - `workflow.py` wraps the service in an ADK `Workflow` graph. It uses `RequestInput` interrupts for Duty Manager review and reconciliation waits and persists to a separate ADK `DatabaseSessionService`. The ADK session coordinates; the domain ledger stays authoritative.
  - `ai.py` defines the only two LLM agents (explanation and edit interpretation). They have no tools, use strict schemas and token counting, and are validated by domain code. Failures hand off and never fall back silently to sample output.
  - `api.py` (`create_app`) is the FastAPI layer that also serves `hubrecover/web/`.
- **`hubrecover/fixtures/`**: the synthetic reference network (seed `HUBRECOVER-001`) and the named scenarios/`CASES`.
- **`evaluation/`**: evaluator-only code. `oracle.py` independently recomputes expected results. `runner.py` drives the service the way a user would (approve → acknowledge each `plan['prerequisites']` role → execute). `held_out.py` and `benchmark.py` write JSON reports. Keep this package out of any runtime or model context. Checked-in reports are under `evaluation/results/`.

Lifecycle: trigger → verified snapshot → enumerate/allocate/gate/rank → optional AI explanation → review card bound to generation/versions/expiry → (edit → new generation) → exact-plan approval → specialist acknowledgements → final revalidation → atomic mock party bookings + notification outbox → reconciliation and handoffs.

## Conventions

- Match the existing compact style: dense one-line bodies, `name=value` without spaces in calls/assignments, module docstrings stating the module's contract, few comments.
- `hubrecover/web/design.css` holds the preserved design tokens (Operations skin); put UI changes in `app.css`/`app.js`.
- After a tested increment, update BUILD-STATUS.md with the checks actually run and their results, then commit and push to `origin/main` (pre-authorised per AGENT.md; never force-push). README/ACCEPTANCE claims must match the recorded evidence: no claiming of unrun gates, human verdicts, or held-out/blind status.
