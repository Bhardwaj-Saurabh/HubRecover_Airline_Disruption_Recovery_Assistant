# Implementation status

Updated 17 October 2026. Profile: local Python/Google ADK. The deterministic foundation and healthy reference-data increment are implemented; this is not yet a runnable recovery application.

## Implemented

- AGENT.md working conventions and AGENTS.md discovery entry point.
- Python project with google-adk[db] 2.11.0, isolated environment and uv.lock.
- Immutable initial policy constants for monitoring and descriptor selection. The full policy configuration is still pending.
- Typed restriction events and pure single-episode monitoring reducer: strict duration/impact trigger, brief lift continuity, exact reset boundary, version deduplication, unconfirmed/late-history blocking and missing-precheck handoff.
- RECOVERY_UNIVERSE_V1 descriptor construction: four families, ordered spare selection, round-robin cap, counts and deterministic descriptor digest. Descriptors are not validated recovery plans.

- Strict schedule/resource/passenger/inventory schemas and cross-record invariants; malformed fields fail validation.
- Reproducible healthy reference bank: 18 day-one flights, six next-day alternatives, 300 passengers in 150 parties, 12 aircraft and 12 crews. Restriction/dispatch sources and disruption trade-offs are still pending.

- Pure whole-party itinerary search/allocation: exact-operation dispatch evidence, completed prefixes, connection/eligibility/assistance checks, net-seat shared-leg accounting, deterministic priority and passenger ranking metrics. This is a read-only calculation, not an executable plan.

## Observed verification

Command: `.venv/bin/python -m pytest -q`

Result: **68 passed**, one third-party OpenTelemetry deprecation warning. Python 3.11.4, pytest 8.4.2. Mode: deterministic/offline; no model requests, bookings or messages.

The suite covers 17 monitoring checks, eight universe checks, 24 fixture checks, 17 allocation checks and two ADK compatibility checks. The cap test independently constructs the expected 100-descriptor selection from 279 raw descriptors. The ADK spike executes two function nodes through Runner and observes a human-input pause; it also instantiates a single-turn, structured-output agent without tools. This does not validate provider output, human resume, durable session recovery or full orchestration.

## Next implementation gates

1. Complete compatibility evidence for human resume, SQLite sessions and provider token counting before enabling real AI; freeze a verified model then.
2. Extend the validated healthy seed with restriction, dispatch and source envelopes; author disrupted reference trade-offs. Existing seed invariants do not establish proposed-operation feasibility.
3. Extend monitoring with consistent late-history reconciliation and authoritative episode/scope aggregation. The current reducer conservatively sends late effective-time changes for classification; it does not reconstruct multi-record history.
4. Add impact propagation, full operational feasibility, supported edits, canonical plan fingerprints and the independent calculation oracle. Allocation/metrics now have hand-calculated tests, including next-day retained arrivals and refusing to borrow later-party releases.
5. Add durable business ledger, approval/prerequisite/version guards, jobs/fences, global write control, atomic booking/outbox and fault tests.
6. Build the Operations review UI, bounded explanation/edit agents, handoff inbox and evaluation records.

The 18 end-to-end development families and 20 held-out variants have not been run. Real-AI, human review, manual/rules-only comparisons, product acceptance, business value and pilot readiness remain unproven. No LMS ZIP or hosted application has been produced. Learner verdicts remain unassigned.
