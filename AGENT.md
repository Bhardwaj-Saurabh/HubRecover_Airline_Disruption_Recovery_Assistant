# HubRecover implementation guide

## Source of truth

Read START-HERE.md, PRD.md, ARCHITECTURE-ADK.md, DESIGN.md and TEST-PLAN.md before changing behaviour. PRD.md owns product policy; ARCHITECTURE-ADK.md selects the backend and adds durable execution contracts. Review documents are historical. Preserve manifest.json as export provenance.

Build the local Python/Google ADK profile first. The LMS browser ZIP is a separate deliverable, only when requested. Preserve the original starter and its design tokens; the web interface uses the Operations skin.

## Implementation boundaries

- Keep domain calculations pure Python, independent of HTTP, ADK and model calls.
- Use synthetic data only, seed HUBRECOVER-001. Never add credentials or runtime databases to Git.
- Code owns trigger decisions, candidate enumeration, allocation, ranking, policy gates and all write authority. Models only select validated explanation claims or propose supported edits.
- Unknown required inputs fail closed. Do not invent restriction release, resource availability, dispatch evidence or passenger outcomes.
- No passenger effects before current Duty Manager approval, matching prerequisites and final transaction guards. Approval is not completion.
- Preserve parties, enforce net-seat atomic replacement, keep immutable booking history, and separate communication retries from booking retries.
- Bind cards and commands to generation, constraints, source/policy versions, expiry and application control. Stop and global disable must survive retries/restarts.
- No live operational integrations, compensation, refunds or production safety claims.

## Build sequence

1. Execute the pinned ADK compatibility spike; document unsupported APIs or install failures honestly.
2. Implement strict schemas, frozen policy, fixture invariants, event reducer and bounded candidate universe, then impact/allocation and independent oracle.
3. Add SQLite ledger, guarded commands, workflow and review interface.
4. Add atomic mock execution, outbox, restart/race verification and reconciliation.
5. Add bounded Gemini explanation/edit agents and separately recorded evaluations.

## Verification and reporting

Run `.venv/bin/python -m pytest` for implemented domain checks. Keep independent expected calculations outside runtime model context. Test exact boundaries and rejected paths, not just the happy path. Do not expose held-out labels during tuning. Human verdicts start empty.

Record actual checks and remaining gaps in BUILD-STATUS.md. A passing unit suite does not establish completion of the 18 development families, 20 held-out cases, real-AI validation, human review, value gates or pilot readiness. Keep commits focused; never overwrite user changes or force-push.

## Delivery preference

The user requests continuing development with a commit and push to `origin/main` after each tested feature or functionality. Run appropriate checks, update BUILD-STATUS.md with actual results, and push each coherent increment. Ordinary feature pushes are authorised; do not force-push or claim unimplemented gates are complete.
