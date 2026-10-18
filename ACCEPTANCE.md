# Local delivery and acceptance

The local synthetic application and its restart/exception workflows are implemented and runnable. This is not a declaration of full PRD, airline, model-quality or business-value acceptance. See `evaluation/results/verification.json` for observed checks and BUILD-STATUS.md for their scope.

| Architecture contract | Implemented path | Evidence |
| --- | --- | --- |
| A1 finite universe | Delay, compatible spare suffix, single/pair cancellation; deterministic cap, deduplication and ranking | Universe, planning and independent oracle tests, including spare/resource variants |
| A2 passenger effects | Whole-party allocation, net-seat atomic replacement, immutable history, unique receipts, separate outbox retries | Allocation/service tests; injected pre-commit crash; actual HTTP completion |
| A3 source ownership | Typed synthetic source commands, revisions, material comparison, frozen snapshots, classified expected changes | Source tests for seven adapters; snapshots readable through API |
| A4 durability | Transactional planning, current approval guards, execution leases/fences, durable ADK continuation jobs, persisted wait deadlines | Restart, missing mapping, takeover, stale result, retry ceiling and rollback tests |
| A5 bounded AI | Schema-only claims, scoped citations and predicate witnesses, explicit edit clarification, no operational tools | Stand-in/rejection tests plus live 3/3 smoke; repeated 6/9 with quota errors, so acceptance remains open |
| A6 manual ownership | Acceptance, return, reassignment and evidence-backed manual handling; immutable history | Wrong-role, stale version, restart and no-fabricated-outcome tests |
| A7 evaluation | Isolated development/conformance runners, independent bounded oracle, reviewer forms and observed timing | 18/18 and 20/20 deterministic observations; human verdicts remain blank |
| A8 budgets | Persisted model reservations, token preflight, time/call limits, no unknown-outcome budget reset | Stand-in failure/budget tests; actual provider cost remains unmeasured |
| A9 write control | Persistent disable, cutoff/fencing, incident evidence and explicit restoration | Service and deterministic conformance tests across restart |

The implementation uses a serialized SQLite transaction for pure planning rather than distributed stage workers. Model and ADK calls cannot authorise effects. Business state remains authoritative when ADK is unavailable; reconciliation jobs expose exhausted retries. Simulated source commands are local fixture adapters, not airline connectors. The generic API uses `/api/runs/{id}/{action}` with revision, role and idempotency bindings.

## Checks that still require access or independent observations

1. The local `.env` now supplies `GOOGLE_API_KEY` and `HUBRECOVER_GEMINI_MODEL`. Initial live smoke passed 3/3; repeated evaluation passed 6/9 with free-tier quota errors and remains incomplete. Once quota is available, run `uv run python -m evaluation.live_ai` for repeated explanation/edit/clarification conformance. The isolated runner never approves a plan, records missing configuration as `NOT_RUN`, and leaves human verdicts blank. The local `.env` is ignored by Git; no credentials are accepted in chat or committed.
2. Inspect the running UI in an available browser: narrow and wide screens, keyboard navigation, review/edit/clarification, acknowledgements, execution, handoffs and evaluations. Computer-use currently returns no available browser and a native startup failure.
3. Collect the PRD's reviewer scores and matched manual/rules-only/AI comparisons. Reviewers must enter their own observations; no benefit or approval is prefilled.
4. Independently freeze a fresh quality holdout and complete the full PRD matrix before acceptance. The exposed 20-case deterministic suite is conformance evidence, not a blind quality study.

These checks cannot be replaced by more passing unit tests. Live airline integration, shared-user authentication, production deployment and the separate LMS ZIP are outside this local deliverable.
