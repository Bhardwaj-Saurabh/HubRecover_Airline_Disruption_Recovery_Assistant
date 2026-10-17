# HubRecover ADK architecture review

**Review date:** 11 October 2026. **Basis:** PRD.md, ARCHITECTURE-ADK.md, TEST-PLAN.md, and the referenced official ADK documentation. This is the historical review of the pre-revision design. No ADK application, concurrency behaviour, model response, latency, or deployment was tested during this review.

**Revision status:** The subsequent authorised document update addresses A1–A9 as design contracts in [ARCHITECTURE-ADK.md](ARCHITECTURE-ADK.md), with shared PRD decisions and mirrored tests updated. The findings below describe the earlier baseline; they are preserved as rationale, not current unresolved design omissions. Implementation, compatibility, safety, performance and product-value evidence remain pending.

| Finding | Current design response | Verification status |
| --- | --- | --- |
| A1 | Architecture section 17: finite universe, cap selection and independent oracle | Not implemented/tested |
| A2 | Section 18: net-seat replacement transaction and preserved completed parties | Not implemented/tested |
| A3 | Section 19: ledger-owned active state, coherent snapshots and change classification | Not implemented/tested |
| A4 | Section 20: transition guards, fencing and crash reconciliation | Not implemented/tested |
| A5 | Section 21: typed claims, deterministic predicates and template rendering | Not implemented/tested |
| A6 | Section 22: owned handoffs, fallback and acceptance interaction | Not implemented/tested |
| A7 | Section 23: observations, verdicts, review/comparison and feedback records | Not implemented/tested |
| A8 | Section 24: call/token/context/concurrency budgets and cost basis | Not implemented/tested |
| A9 | Section 25: durable global write disable, shadow isolation and restoration | Not implemented/tested |

Architecture section 26 maps every finding to required verification and existing test families. The original assessment and recommendation below apply to the reviewed baseline, not evidence that the revised design has passed those checks.

**Assessment:** The high-level architecture follows the PRD well and is appropriate for the bounded synthetic capstone. Keep the deterministic recovery engine, two constrained AI roles, guarded human approval, operational acknowledgements, transactional mock execution, and modular application structure. Five important implementation contracts remain underspecified. Resolve them before claiming that the decision cards and passenger execution satisfy the PRD. Data validation and independent domain-engine work can begin while those contracts are completed.

The main issue is specificity: the architecture often states the correct guarantee without defining the mechanism that makes it hold. These findings identify missing contracts, not observed runtime failures.

**Requirements coverage**

| PRD requirement | Architecture assessment |
| --- | --- |
| Scoped trigger, strict 60-minute boundary, 15-minute reset, duplicate/late events | Covered in the monitoring reducer design. |
| Deterministic feasibility, ranking, whole-party allocation, supported edits | Correct responsibility boundary; candidate construction needs a precise specification. |
| Version-bound Duty Manager approval, 300-second expiry, operational acknowledgements | Covered; restart and transition enforcement require a more concrete protocol. |
| Freshness, material changes, matching approved postconditions, own-batch deductions | Covered conceptually; canonical mutable source ownership needs clarification. |
| Atomic capacity and duplicate prevention | Correct transaction direction; full itinerary replacement accounting is incomplete. |
| Grounded evidence and rejection of unsupported critical claims | Correct intent; validation of the free-form explanation is unresolved. |
| Booking/message separation, partial progress, truthful completion | Covered. Keep these controls. |
| Owned manual handoffs and acknowledgment status | Handoff storage is named; the packet, ownership routing, and acceptance interaction are incomplete. |
| Evals view, learner verdicts, comparison evidence, feedback | Evaluation criteria are strong; the application contracts for recording this evidence are incomplete. |
| Write suspension on critical incidents | Per-episode Stop exists; an application-wide write-disable control is not specified. Needed before pilot use. |
| Single-page LMS packaging | The incompatibility is explicitly handled with separate runtime profiles. This is a delivery constraint, not a hidden architecture defect. |

**Priorities**

| Finding | Timing | Required result |
| --- | --- | --- |
| A1. Candidate universe | Before planner/oracle implementation | Versioned finite construction rules and deterministic cap behaviour. |
| A2. Replacement-booking accounting | Before passenger execution acceptance | Atomic old/new itinerary transition with auditable seat conservation. |
| A3. Mutable scenario-state ownership | Before source-update and execution race tests | One authoritative active state with an atomic version protocol. |
| A4. Workflow/worker recovery contract | Before crash/replay acceptance | Transition guards, fenced stage writes, and a crash-reconciliation table. |
| A5. AI claim-validation contract | Before accepting real-AI decision cards | A defined boundary between verified claims and unconstrained prose. |
| A6. Handoff contract | Before capstone completion | Owned, reviewable handoff packets with explicit acceptance status. |
| A7. Evaluation/feedback recording | Before capstone completion | Versioned observed-run, verdict, reviewer, and comparison records. |
| A8. Model/resource budgets | Before repeated AI evaluation or shared hosting | Enforced call, token, context, and concurrency ceilings. |
| A9. Application-wide write disable | Before a pilot that could execute consequential actions | Durable write inhibition that covers workers and notifications. |

**A1. The declared candidate universe is not yet defined precisely enough.**

Architecture section 5 names delay, tail-swap, and cancel/rebook templates and limits each round to 100 candidates. PRD sections 14 and 20 require an independent oracle evaluating the same declared bounded universe. Neither document defines the delay choices, planning horizon, allowable combinations of changes, itinerary-search limits, or ordering when construction would exceed the cap.

A limit of 100 does not identify which 100 candidates are considered. Two implementations can satisfy that limit but produce different plans and different “best” outcomes. Sharing the production generator with the oracle would conceal that discrepancy rather than independently validate it. A planner could also exhaust the cap on one template family and miss a known viable alternative from another.

Specify a versioned candidate-construction contract: horizon and permitted times, compatible resource alternatives, supported combinations, eligibility/connection search, canonical deduplication, and deterministic selection when the cap binds. State what happens when enumeration reaches its time limit before the declared search is complete. Do not silently treat an incomplete search as proof that no viable plan exists. Distinguish verified existing candidates from any unproven best-in-universe claim.

The oracle may share input schemas and the declarative specification, but its enumeration/calculation implementation should be separate. Prove the contract with hand-auditable small cases, exact ties, supported edits, and a case where more than 100 possible constructions would otherwise exist. This is also a small remaining PRD specification gap, not solely an ADK issue.

**A2. Atomic allocation needs a complete replacement-booking transaction.**

Architecture section 9 correctly commits a whole party and all itinerary legs together. It describes checking/reserving destination capacity and updating bookings, but does not explicitly specify the treatment of original reservations, unchanged shared legs, superseded bookings, or a party already committed in an earlier partial run. PRD sections 14, 16, and 20 require valid passenger accounting and preservation of completed actions.

For example, replacing itinerary A–B with A–C must not deduct the shared A leg twice, leave both itineraries active, or release the old seats before the replacement can commit. Replanning after partial execution must not treat an already rebooked party as a fresh original reservation.

Define the transaction using an expected active-booking version and the difference between old/new leg allocations. Specify reserve/release rules, status history, one current itinerary per passenger, whole-party consistency, and what remains active if the replacement fails. Preserve completed outcomes during regeneration unless a separately reviewed plan explicitly authorises a further change. Lock every affected inventory row in stable order, including rows released by the replacement where appropriate.

Required tests include a shared-leg replacement, failure after proposed seat release, replay after a committed replacement, and regeneration after some parties have already completed. Assert active itineraries and occupied seats against the independent ledger/oracle, not only action counts.

**A3. Define the authoritative mutable scenario state.**

Architecture sections 3, 5, and 7 combine fixture-backed operational records, read adapters, immutable snapshots, and a business ledger. Section 9 requires Stop, restriction changes, and booking commits to share a locking/version protocol. That is a sound intention, but the design does not say where the latest committed flight/crew/dispatch/assistance state lives or how a driver update becomes atomically visible to all readers and the execution guard.

If one adapter reads a changed JSON record while another reads the prior ledger state, a joined snapshot can represent no actual coherent scenario. Similarly, checking a persisted material digest cannot protect a booking commit if the underlying active source changes outside the same version protocol.

Treat fixture JSON as immutable seed data. Establish one authoritative versioned active scenario state, preferably ledger-owned for the synthetic prototype, and route all labelled source updates through its transaction protocol. Immutable snapshots reference that state version. Define a field-level change classification contract for nonmaterial refreshes, expected approved operational postconditions, own-batch deductions, and unexpected material changes. Allow expected changes only when their plan/action references and resulting content match.

Prove that an update during parallel reads is either retried/blocked or represented by a consistent snapshot. Prove that a restriction change, Stop command, and competing inventory mutation cannot be missed between validation and a new mock commit. This recommendation concerns the local synthetic adapters; it does not promise atomicity across future airline systems.

**A4. State transitions and crash reconciliation need an executable contract.**

Architecture section 8 explicitly recognises that an ADK checkpoint and a business commit are separate operations. It names durable jobs, a reconciler, leases, and fencing, but does not define the recovery algorithm or the exact guards on non-booking stage writes. The main diagram omits many failure transitions, which its explanatory text acknowledges. The missing formal transition/recovery table matters more than the simplified diagram.

For each command/stage, specify current business state, expected episode/plan generation, allowed actor, deadline, required guards, committed effects, and next state. The ledger remains authoritative; ADK invocation progress is a mapped execution detail. Define how the worker knows whether to resume an invocation, rebuild a safe stage, return an already committed result, or hand off.

In particular, a worker whose lease expired must not publish an old card, overwrite a newer plan, resume a superseded review request, or send an outbox action. A fencing token should be checked on every consequential stage commit, not only booking transactions. Define Stop's accepted cutoff and how an already-started action is reconciled; do not imply an in-flight effect can always be undone.

Write a recovery table for at least: card committed before the ADK pause is recorded; approval committed before resume dispatch; ADK node completion before its domain result is recorded; booking committed before the worker receives confirmation; and an old worker completing after lease takeover. Record how pending requests, immutable outputs, unique action keys, and expected versions resolve each case.

The framework caveat is real: ADK documents that tools may execute more than once on resume, so domain idempotency cannot be delegated to resumability. [Official ADK resume documentation](https://adk.dev/runtime/resume/). The architecture already calls for a compatibility spike; that is an outstanding proof obligation, not an additional missing feature.

**A5. The AI explanation contract does not yet make critical-claim rejection enforceable.**

Architecture section 6 proposes strict IDs and schemas, while allowing a short free-form “noncritical explanation.” It then promises to reject unsupported critical assertions. PRD sections 15, 17, and 20 make such rejection mandatory. No mechanism currently determines whether an arbitrary explanation contains a critical assertion or whether its cited facts actually support it.

A structurally valid response with genuine source IDs can still say that all crew are legal, all passengers are accommodated, or execution may begin immediately. Calling that field noncritical does not constrain its meaning. This is a semantic validation gap, not a reason to abandon structured output. ADK documents output schemas and invalid-output handling; those framework checks do not establish factual support for unrestricted language. [Official ADK LLM agent documentation](https://adk.dev/agents/llm-agents/).

Specify an allowed claim representation with typed claim kinds, fact references, and approved comparison/reason codes. Recompute factual comparisons and render critical claims from code-owned templates. Decide explicitly whether raw explanatory prose is excluded from the approval card or subjected to a separately defined rejection policy; any uncertainty about a critical claim must fail closed as the PRD requires. A second model can support evaluation but should not become the sole authority proving a safety-relevant claim.

Test genuine citations supporting a false conclusion, invented crew legality, hidden numerical assertions, and instructions disguised as rationale. Separately assess whether the constrained explanation remains useful versus the rules-only baseline. Safe output and useful output are both necessary; neither follows from a valid JSON shape.

**A6. Manual handoffs need a defined product interaction.**

The architecture includes `handoffs` and manual states, but does not specify the complete packet, role routing, fallback, or acceptance interaction required by PRD sections 12, 18, and 31. An error status alone does not establish that the next human knows what remains to be done.

Define a packet containing reason, verified evidence, episode/plan version, committed versus proposed actions, affected parties, communication state, next responsible specialist, and acknowledgment status. Route recovery exceptions to the Duty Manager with the OCC operations lead fallback; route unresolved/assistance/overnight/manual-contact work to passenger operations as the PRD specifies. Provide a labelled simulated handoff-acceptance interaction and show unaccepted work in the summary. Receipt of the packet must not imply that the passenger problem is resolved.

Prove missing-contact, unavailable-assistance, and partial-booking cases produce the appropriate owned packets without fabricated resolution or service commitments.

**A7. Evaluation and feedback need application records, not only test criteria.**

Architecture section 12 preserves strong criteria and the independent oracle, but section 11's API and section 7's ledger do not define how observed evaluation results, learner verdicts, reviewer scores, comparative timings, or version-linked feedback are stored and exported. PRD sections 20, 25–28, 33, and the planned demo in section 28 require these user-visible artifacts. Existing DESIGN.md references the Evals experience, so this is an application-contract omission rather than absence of evaluation intent.

Define observed-run/result records separately from frozen expectations and oracle labels. Add a means to record learner verdicts, reviewer expertise/rubric scores, edit/rejection feedback, manual/rules-only/AI task timings, and before/change/after evidence. Verdicts start empty. Link records to runtime profile, mode, model/prompt/data/policy versions, case/repeat IDs, and traces. Keep evaluator labels unavailable to the runtime model.

Ensure the interface can export the 18-family development results, separately frozen 20-case evaluation, reviewer evidence, comparison denominators, and unresolved checks. Deterministic arithmetic and transition unit tests should agree exactly; the PRD's 90% system-level ranking gate should not be used to excuse an incorrect sort or accounting formula.

**A8. Time limits do not fully bound model/resource use.**

Architecture section 10 correctly adopts the PRD's deadlines, regeneration ceiling, and retry ceiling. It does not define whether explanation is one batch call for the displayed plans or a call per plan, nor input/output-token limits, retrieval-context size, total calls during repeated clarification, or active-run concurrency. These are implementation resource decisions beyond the current PRD's time budgets.

Define per-role and per-round call/token/context limits, one shared retry allowance as specified by the PRD, clarification-call ceilings, and global/per-user active-run limits before exposing repeated AI runs. Record consumption and a cost estimate using a configured price basis rather than an invented savings claim. Enforce the same counters across worker retry/restart. Budget rejection must be explicit and must not silently change to sample output or relax a safety check.

Test repeated ambiguous edits and parallel evaluation runs so clarification or queue retries cannot create unbounded model calls. Final model selection and observed costs remain implementation validation tasks.

**A9. Add a durable application-wide write-disable control before consequential pilot use.**

Architecture sections 9–11 specify per-episode Stop. PRD section 32 also requires immediate suspension of automated writes after an actual unauthorised action, hard-rule/prerequisite bypass, oversell, duplicate booking, false confirmation, or compensation commitment. A per-run flag can be lost in a new/reset episode and does not specify suspension across workers/outboxes.

Define an application-wide write-disabled state checked by every booking and notification guard, including queued/replayed work. State who may disable and restore it, what evidence and review restoration requires, and how runtime modes prevent a read-only shadow deployment from obtaining write-capable adapters. Distinguish an actual invariant violation from a correctly rejected bypass attempt; a negative test should not be mistaken for a realised safety incident.

For the synthetic capstone, this can be a labelled local control and test. Production enforcement, authenticated restoration, alert delivery, and runbooks belong before a separately authorised live-write pilot. This finding does not call for live integration now.

**Known assumptions to validate, without counting them as missing design controls**

The architecture already explicitly defers authenticated production identity, actual airline rules, external PSS transaction guarantees, privacy/retention approval, named operating owners, and live integration. Their absence is appropriate in the synthetic first build. The LMS/ADK incompatibility is also already disclosed and cannot be fixed by adding an API call inside the locked LMS frame.

The five-minute card window includes specialist acknowledgment waiting. Confirm in simulation that this produces useful coverage; before a real pilot, measure whether operational confirmation can fit that window. Do not extend authorisation secretly to make the demo pass. Similarly, the 120-second execution budget for 300 passengers is a hypothesis until measured. An exact available Gemini model and the pinned ADK pause/resume APIs still need the compatibility and performance checks already required by the architecture.

The product-value evaluation is well framed: compare against the actual manual task and isolate AI's incremental value against rules-only output. No architecture inspection can establish the claimed 50% task-time improvement or airline savings.

**Recommended decision**

Approve the architecture's direction for the synthetic capstone. Preserve the current technology choices and safety responsibilities. Complete A1–A5 as design contracts while building the data/domain foundation; complete A6–A8 before final capstone acceptance; demonstrate A9 and the already documented production prerequisites before any consequential pilot. This review provides no live-write approval and makes no claim that the proposed controls have been implemented.
