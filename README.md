# HubRecover

A runnable, local **Airline Disruption Recovery Assistant** for a fictional Operations Control Center. It uses Python, Google ADK graph workflows, FastAPI, SQLite and an Operations review interface. All airline records, specialist roles, bookings and messages are synthetic.

## Start

On this Mac, double-click **Start HubRecover.command**, or run:

```sh
uv sync --locked
uv run python -m hubrecover
```

Open **http://127.0.0.1:8765**. Keep the terminal open while using the app. Stop the server with Ctrl+C. Python 3.11+ and uv are required. Port 8000 is deliberately avoided because another local application uses it.

No AI key is needed for the complete rules-only demonstration. Runtime data persists in `.hubrecover/` (ignored by Git). An alternate isolated environment can be started with `--data-dir /tmp/hubrecover-demo --port 8766`.

## Try the recovery loop

1. Start **Complete recovery**. Inspect the scoped restriction, source context, ranked options and disabled rejected candidate.
2. Apply **Protect international connection**. A fresh card and review request replace the previous generation.
3. Approve a current plan as the simulated Duty Manager.
4. Click each explicitly labelled specialist acknowledgement. Approval alone cannot execute.
5. Execute the approved mock recovery. Watch party receipts and notification outcomes reconcile; download the trace.
6. Reset after completion. Try **Fail after 3 parties**, expiry, source change, missing contact or Stop to see preserved receipts and owned manual work.

To demonstrate an actual itinerary replacement, reject the first displayed set with feedback, then approve an option with next-day arrivals. Whole parties move together; shared-leg reservations are not deducted twice. Next-day care remains a human operational responsibility.

The **Evaluations** view runs 18 development demonstrations and a separate 20-variant deterministic suite in isolated ledgers. It stores automatic diagnostics separately from blank human verdicts. Reviewer, comparison-task timing and feedback forms record actual user observations; they do not manufacture a benefit claim.

## Optional Gemini

Set `GOOGLE_API_KEY` and an available exact `HUBRECOVER_GEMINI_MODEL` identifier in the server environment before starting. Do not put secrets in the repository, browser forms or chat. The app does not load a credentials file. An example variable list without credentials is in `.env.example`.

When configured, the review panel enables bounded explanation and edit interpretation. ADK agents have no operational tools. Provider token counting, strict output schemas and deterministic fact/claim checks are mandatory. Failures hand off without silently switching to rules-only output. New deterministic edits are labelled rules-only; AI-interpreted edits with code-generated explanations have their own explicit mode label.

**Real-provider calls were not run in this environment:** neither the Gemini key nor model identifier is configured. Stand-in tests do not establish real-model correctness or usefulness. Confirm model availability and run the real-AI evaluation before claiming provider compatibility or quality.

## Verify

```sh
uv run pytest -q
uv run python -m hubrecover.fixtures.reference
uv run python -m evaluation.held_out
uv run python -m evaluation.benchmark
node --check hubrecover/web/app.js
```

Observed evidence and remaining verification limits are in [BUILD-STATUS.md](BUILD-STATUS.md). Checked-in JSON reports are under `evaluation/results/`. The independent reference oracle is evaluator-only and is never included in model context.

## Boundaries

- Local, single-process demo with explicitly simulated roles; not authenticated shared hosting.
- No live airline/dispatch/PSS/messaging integration and no compensation commitments.
- One active episode per ledger. Stop and global write disable preserve completed receipts. Restoration needs recorded incident, fix, regression and reviewer evidence; old approvals remain invalid.
- The initial source is a validated synthetic snapshot. Material-change simulation conservatively hands off rather than claiming a complete production adapter protocol.
- The finite search covers the declared synthetic universe only. This is not network-wide optimisation or aviation legal certification.
- This Python backend is separate from the LMS browser ZIP profile. No LMS ZIP is produced by this application.

[PRD.md](PRD.md) and [ARCHITECTURE-ADK.md](ARCHITECTURE-ADK.md) remain the design baseline. Some broader design acceptance checks require additional evidence; see the explicit limitations in BUILD-STATUS.md. Development instructions live in [AGENT.md](AGENT.md).
