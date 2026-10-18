# HubRecover build status

Updated 18 October 2026. **The local Python/Google ADK synthetic prototype is runnable. Full PRD/architecture acceptance and pilot readiness are not claimed.**

## Delivered application

- Operations web interface with scenario selection, context, ranked options, disabled rejected evidence, supported edits, Duty Manager approval, specialist acknowledgement controls, execution progress, handoffs and trace download.
- Strict synthetic reference-data contracts and invariant checks: 18 day-one flights, six next-day alternatives and 300 passengers in 150 parties.
- Event-time trigger boundaries, finite descriptor selection, rotation/crew timing propagation, operational gate, whole-party itinerary search, net-seat accounting, passenger metrics and canonical action fingerprints.
- Durable SQLite business ledger and separate ADK session database. ADK review pauses resume after restart; the business ledger owns authority.
- Version-bound and idempotent commands; exact-plan approvals and simulated operational postcondition commits; expiry, source changes, Stop, worker leases/fencing, global write disable and evidence-bound restoration.
- Atomic party receipts, immutable superseded booking history, outbox records, separate notification attempts, manual contact and next-day care handoffs. No live messages or bookings.
- Optional bounded Gemini explanation/edit agents with no operational tools, strict claim/reason validation, verified token counting, persistent reservations, explicit timeouts and no silent sample fallback.
- Separate development and held-out deterministic runners, blank human verdicts, reviewer scores, observed comparison timing, feedback records and JSON exports.
- One-command and Mac double-click launch paths. See README.md.

Ambiguous AI edits now enter a version-bound clarification wait, with a supported-constraint submission and original expiry. Persistent review/acknowledgement deadlines are checked by the server without needing another user command.

## Observed verification

| Check | Actual evidence |
| --- | --- |
| Python regression | **120 passed** in the regression run, plus the subsequently added server-restart integration test passed separately; two third-party deprecation warnings; no provider credentials used |
| Reference fixture | 24 flights and 300 passengers; invariant checks pass |
| Independent oracle | All 18 selected reference descriptors agree on feasibility, party allocations and ranking; separate cap-selection oracle covers 279 raw descriptors |
| Development demonstrations | 18/18 implemented subvariants pass automatic diagnostics; learner verdicts remain null |
| Held-out deterministic variants | 20/20 pass. This suite was exposed during implementation and is conformance evidence, not a blind model-quality holdout |
| Local HTTP integration | Through actual FastAPI and durable ADK: protect connection → fresh review → approve → four acknowledgements → 150 party receipts and 300 sent mock messages → COMPLETED |
| Source and monitoring additions | 11 source/restart checks and 20 monitoring boundary checks passed; source snapshots stored separately from mutable execution records |
| Evidence and spare tails | Warning thresholds, precedent scope/eligibility and spare-tail/resource oracle checks pass |
| Durable ADK jobs | Missing-card mapping recovery preserves request/expiry; expired lease takeover and changed-state mapping rejection pass |
| Handoff lifecycle | Return, coordinator reassignment, owner acceptance and evidence-backed manual handling survive restart; stale/wrong-role requests and authority revival are refused |
| Automatic execution recovery | Server restart resumes from one committed party to 150 receipts/300 mock messages; original deadlines, fencing, Stop/source/disable boundaries verified |
| Rebooking transaction | A next-day option produces two superseded booking records, preserves shared-leg occupancy and creates a care handoff |
| Timing | 30/30 rules-only qualifying runs produce a card, zero failed/handoff runs; local trigger-to-card p95 0.1593 seconds. No inference of human time savings |
| JavaScript / launch checks | `node --check`, shell syntax, Python compilation, design-block preservation and DOM-control contract checks |

Detailed reports are in `evaluation/results/`. Every real-AI stand-in test runs in an isolated test ledger; these tests are not provider evidence. Third-party OpenTelemetry and Starlette deprecation warnings do not fail the suite.

## Unrun or broader acceptance work

- **Real Gemini calls are unrun:** neither `GOOGLE_API_KEY` nor `HUBRECOVER_GEMINI_MODEL` is configured. Exact provider/model availability, token counting, structured responses, repeated quality/cost evaluation and real-AI usefulness still need observation.
- **Browser visual/interaction QA is unrun:** the in-app browser is unavailable and computer-use access to Chrome was not approved. HTTP integration, JS syntax and DOM-contract checks passed; they do not substitute for a rendered-browser inspection.
- Human/proxy comprehension scoring, matched manual/rules-only/AI task comparisons and actual benefit claims require user/reviewer observations. No verdict or business benefit has been invented.
- The 18 development observations each cover one executable subvariant. They do not establish all subvariants, crash rows and acceptance thresholds in TEST-PLAN.md. A fresh independently held-out quality set is needed before final model acceptance.

## Explicit implementation limits

- Local, single-process, synthetic-only deployment with simulated roles; no shared authentication, live airline adapters, production audit claim or LMS ZIP.
- Typed local source adapters now persist per-source revisions, verified timestamps, material digests, immutable planning snapshots and classified update history. Server-verified refreshes/display labels preserve cards; unexpected material and invalid changes hand off. Exact prerequisite and own-batch changes have transaction-bound evidence. Live external adapters remain outside this synthetic application.
- Monitoring reconstructs consistent late history across explicitly mapped authority streams, preserves overlapping active restrictions and refuses contradictory or retroactively changed emitted decisions. The UI retains the scripted trigger/brief-lift paths.
- Execution now automatically reclaims expired worker leases from the durable ledger on server startup and while running. Recovery preserves original deadlines and receipts, rechecks authority and fences old workers. ADK continuation jobs now persist stable keys, attempts, leases, five-second renewal, fences and capped retries; stale workers cannot publish review mappings. Pure planning remains synchronous inside the serialized business transaction, so an interrupted computation rolls back instead of publishing a partial stage. Interrupted model calls retain reservations and hand off because provider outcome is unknown.
- Handoffs now support assigned-owner acceptance/return, coordinator reassignment and evidence-backed manual-handling records, with immutable history and frozen receipt/communication evidence. These records never change passenger outcomes or revive execution authority; verified external outcome adapters remain outside the synthetic profile.
- The independent oracle now also covers compatible spare-tail selection and resource/dispatch mutations. A frozen fictional playbook catalog filters approval status, dates, hub, strategy and policy; evidence is explicitly synthetic. Inclusive high-impact warning thresholds are implemented. This is bounded-network conformance, not a claim of global optimality or real airline precedent approval.

These limits are deliberate boundaries of what is actually built, not claims that the complete architecture has been implemented. Production, business-value and full PRD safety/quality acceptance remain open.
