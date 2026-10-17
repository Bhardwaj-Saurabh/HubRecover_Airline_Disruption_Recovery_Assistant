# HubRecover: product and architecture review

Review date: 11 October 2026. Scope: the current PRD, TEST-PLAN, and build-kit constraints. This is a review of the specification, not evidence of implemented behaviour, airline validation, or production readiness.

**Review status:** This report records the gaps found in the earlier PRD. The revised PRD now incorporates the decisions, demo defaults, data contracts, execution controls, and evaluation gates. Its current development set has 18 visible test families plus 20 held-out variants. Recommendations below are historical review findings; they are not claims that implementation or testing has occurred.

## Verdict

HubRecover is a worthwhile capstone concept with a clear user and a useful decision boundary. Its strongest proposition is that the Duty Manager sees passenger consequences alongside aircraft, crew, and dispatch constraints before choosing a recovery plan. The PRD covers the important workflow, human control, synthetic demonstration, failure paths, and pilot governance.

It is ready for preliminary synthetic scenario design. It needs a short implementation specification before generating the final dataset or building the full loop. The main gaps are executable-plan dependencies, ranking policy, data contracts, state transitions, and measurable evaluation gates. A credible product hypothesis exists; user demand, comparative advantage, and business impact remain unproven.

| Question | Assessment |
| --- | --- |
| Does the PRD cover the important aspects? | Yes at the product-workflow level; several architecture and acceptance details remain open. |
| Can synthetic data be created? | Yes. Define schemas, invariants, and independently labelled expected outcomes first. |
| Is it worth building? | Worth prototyping and evaluating. No evidence yet justifies a production investment. |
| Is evaluation clear? | Scenario coverage is strong. Scoring rules, thresholds, comparison baselines, and holdout separation are incomplete. |
| Is it ready for live operations? | No, as the PRD correctly acknowledges. |

## What is strong

- Sections 1, 5, and 11 identify a specific decision-maker and a concrete information-ordering problem rather than a general chatbot opportunity.
- One hub, one disruption, a bounded flight bank, and 200–500 affected passengers provide a manageable demonstration scope.
- The Duty Manager's approval, deterministic Policy Gate, compensation restriction, and stop-on-unverifiable-data rule give the design clear boundaries.
- Sections 20 and 24 cover positive, negative, adversarial, degradation, and retry scenarios. Correct abstention is recognised as success.
- Passenger impact is part of option review, not a lookup performed after the decision.
- Sections 25–28 distinguish planned behaviour from tested results. Sections 29–34 describe ownership, monitoring, feedback, and a staged pilot.

## Decisions needed before the full build

### 1. Separate recovery approval from operational readiness

Priority: critical. Relevant sections: 12, 15, 19, 21, 28, and 31.

Approval immediately permits rebooking and notification, but aircraft swaps and crew changes remain human handoffs. The tool list also does not include committing flight delays or cancellations. A plan can therefore be approved without the operational changes that make its passenger itinerary possible.

Example: an option relies on a spare tail and a replacement crew. A manager approves it, but the specialist subsequently cannot supply the tail. Passengers must not already have received a confirmed itinerary based on that uncommitted operation.

Recommended prototype decision: keep one Duty Manager approval, then wait for mocked operational acknowledgements for any dependent flight, aircraft, crew, or dispatch changes. These acknowledgements confirm execution prerequisites; they are not another recovery-choice approval. Rebook only onto confirmed operating alternatives. If prerequisites fail or the plan changes, invalidate approval, regenerate, and return to the Duty Manager. An option requiring no operational changes can proceed after approval and final revalidation.

The demo must show that these acknowledgements are simulated. Distinguish planned recovery, acknowledged operational changes, completed passenger actions, and outstanding manual work in the final status.

### 2. Define how options are generated and ranked

Priority: high. Relevant sections: 6, 12–14, 17, and 24.

“Rank by feasibility and passenger impact” is not enough to reproduce or judge a recommendation. Many options can affect the same 300 passengers but differ greatly in final arrival times, overnight disruption, connections, and cancellations.

Recommended prototype policy: remove hard-infeasible options first, enforce supported Duty Manager constraints, then compare a published tuple such as unresolved passengers, next-day arrivals, total passenger arrival-delay minutes, cancelled flights, and total flight delay. Use a deterministic tie-breaker. This ordering is a proposed capstone policy, not an established airline preference; validate it with a domain reviewer and show component values on the card.

Generate bounded candidates from delay, swap, and cancel/rebook templates and calculate their consequences in code. Do not rely on an LLM to invent schedules, allocate scarce seats, calculate duty limits, or supply passenger counts. Use AI for grounded explanation and supported edit interpretation. Unsupported or ambiguous edits need clarification rather than being silently ignored.

Aim for 2–4 meaningfully different candidates when available. Define whether this is before or after filtering; one viable option should remain reviewable, and zero causes manual handoff. Do not fabricate alternatives to satisfy a count requirement. Rejections should refer to plan structure and outcomes, not merely an option label or its wording; a materially corrected plan can be rechecked.

### 3. Specify approval validity and changes during human review

Priority: critical. Relevant sections: 16, 22, 24, 29, and 30.

Binding approval to a plan version helps, but the underlying restriction, crew availability, or seat inventory can change without the displayed plan changing.

Define source versions and maximum age, a plan expiry rule, and a final pre-execution check. Material changes invalidate the plan and require fresh checks and approval. Reserve seats or perform an atomic capacity check at write time. Repeated execution uses an idempotency key for episode, plan, passenger, and action. Repeated approval clicks cannot cause repeated writes.

Handle partial completion explicitly: retain successful bookings, mark unsuccessful ones for recovery, and send a confirmation only for a booking that actually succeeded. A notification failure must not cause another booking. Do not promise a global rollback after passenger messages have already been sent; use reconciliation and manual handling for irreversible partial outcomes.

### 4. Resolve the trigger's input dependency and event semantics

Priority: high. Relevant sections: 3, 12, 13, 23, and 24.

Monitoring must know the downline-flight count or a crew conflict to trigger, but the impact queries are described as starting after the trigger. Give Monitoring a lightweight read-only schedule/rotation and crew precheck, then perform the full consolidated analysis after triggering.

A ground stop and a runway closure should have distinct event types and applicability. The FAA describes a ground stop as holding flights destined for the affected airport at their departure points. That is not automatically a stop on every departure from the hub. Model the inbound delay and its causal propagation through tail rotations and passenger connections. A runway closure can constrain a subset of airport capacity. [FAA traffic-management definitions](https://www.fly.faa.gov/ais/Help/ais_message_help.html).

Include authority, event ID, event version, effective time, received time, active/lifted status, affected airport/runway, and scope. Define behaviour at exactly 60 minutes and exactly 15 minutes, during an unconfirmed lift, and for duplicate, late, or out-of-order updates. The 60-minute threshold is a proposed escalation policy, not an instruction to postpone ordinary human operations or all monitoring until then. The PRD's generic buffer claim needs validation.

### 5. Complete the model of hard feasibility

Priority: high. Relevant sections: 11–15 and 23.

Aircraft qualification and turnaround checks are necessary but do not guarantee a complete feasible recovery. The prototype also needs rotation continuity, aircraft location and availability, overlapping assignments, crew rest and availability, restriction compatibility, dispatch permission, seat capacity, and connection timing.

Dispatch is part of the promise and later fixture list, but is absent from the earlier tools and observations. Add a read-only dispatch adapter and explicit verified/blocked/unknown outcomes. “Unknown” cannot count as feasible.

Write down simplified fictional rules for the capstone. Maintenance, curfews, slots, airport capacity, full fatigue regulation, interline ticketing, and immigration constraints must either be represented or explicitly excluded. The output should say “passed the configured demo checks,” not imply comprehensive operational legality.

Integrated recovery research explicitly models resource continuity and capacities; this supports the recommendation to model schedules and allocations rather than accept a plausible narrative as a plan. This is an architectural inference from the work, not a requirement to implement its full solver. [AIRS solver-based recovery research](https://arxiv.org/abs/2510.26831).

### 6. Distinguish the capstone architecture from the enterprise vision

Priority: high. Relevant sections: 6, 15–16, 23, 27, and BUILD-INSTRUCTIONS.

The kit requires a single HTML page, in-memory state, embedded data, and AI calls through PFAI. The PRD also describes APIs, Azure AI Search, Teams/Copilot Studio, and permanent trace storage. Section 27 partly reconciles this, but a build agent still has conflicting instructions.

Recommended decision: in the capstone, the Supervisor is a deterministic JavaScript state machine, specialist roles are modules, adapters are in-memory functions, retrieval is a local mock, and the approval card is browser UI. Use the kit's AI helper only where needed and label sample versus real-AI modes. Export an audit trace, but do not claim it is durable or tamper-resistant storage. Explain that no live airline or messaging calls occur; authorised helper AI calls are separate from operational integrations.

Suggested states: MONITORING → ANALYSING → GENERATING → VALIDATING → AWAITING_APPROVAL → AWAITING_OPERATIONAL_ACK → REVALIDATING → EXECUTING → COMPLETED or PARTIAL_MANUAL. Edits and rejections return to GENERATING; missing data or no viable option enters MANUAL_HANDOFF. Define timeouts, a finite regeneration budget, and reset/cancellation behaviour. A plan without operational dependencies can skip AWAITING_OPERATIONAL_ACK.

For this small scope, separate autonomous LLM agents are not automatically necessary. Multiple roles may be useful boundaries while still using one controlled orchestration layer. Deterministic monitoring, calculations, and execution are more readily testable. This is a recommendation to test, not a claim that agents cannot add value.

## Readiness for synthetic data

The data inventory is sufficient to start. It is not yet a complete data contract. Create one reference scenario before scaling the dataset.

1. Define IDs, relationships, required fields, enums, UTC timestamps with service dates, units, source versions, and absent-data behaviour. Separate scheduled, estimated, proposed, and committed flight times.
2. Clarify that 200–500 is the affected cohort, not necessarily the entire fixture population. A flight's passenger count must fit its modelled aircraft capacity. Provide next-day alternative records because the proposed one-day schedule otherwise cannot support next-day outcomes.
3. Include passenger itineraries and legs, minimum connection times, eligibility, booking-party relationships, and contact availability. Make an explicit scope decision for party separation and passengers needing assistance; do not let fare class silently determine priority without an approved rule.
4. Validate relationships and invariants: no orphan flight/tail/crew/passenger IDs, no negative seats, chronological itineraries, consistent location changes, no overlapping use of the same resource, and one final booking state per passenger.
5. Define “affected,” “rebooked same day,” “rebooked next day,” “retained itinerary,” and “unresolved.” Use mutually exclusive categories that reconcile to the affected cohort. Track notification state separately from booking state.
6. Label expected outcomes independently from implementation. Record the exact rule arithmetic and expected allocations for each reference case. Invalid variants should normally change one variable so the cause of failure is inspectable.
7. Freeze a dataset version and random seed. Keep demo/prompt examples separate from held-out evaluation scenarios, including different flight graphs and trade-offs rather than only renamed passengers.

The scenario should create real trade-offs: the fastest aircraft solution must sometimes strand more passengers, and the best passenger outcome must sometimes increase flight delay. If one option always dominates every other option, the data proves display and filtering but provides little evidence about recovery judgement.

## Product value: what can be claimed and what must be proved

The credible value hypothesis is: consolidating constraints and passenger impact before approval reduces reconciliation work and avoids some poor recovery choices while preserving human authority.

The PRD does not yet provide interviews, observed workflow evidence, a measured manual baseline, or evidence that an airline's existing tools lack these capabilities. Statements such as “no system watches this” or “notification is inconsistent by design” should be scoped to a validated target workflow or labelled as assumptions. The OCC Duty Manager's exact authority also needs confirmation for the intended airline.

Integrated recovery is already an active research area. A study using KLM data investigates combined aircraft/crew recovery and compares it with traditional methods. It supports the importance of integrated planning, but its reported results cannot be transferred to HubRecover. [Integrated fleet and crew recovery research](https://arxiv.org/abs/2505.04274).

The product should therefore demonstrate its particular advantage: explainable passenger-aware options, an effective edit loop, and traceable approval over disconnected data sources. Neither “AI” nor “multi-agent” is a sufficient differentiator.

Run two comparisons: a manual scenario task to evaluate reconciliation and decision usefulness, and a rules-only recovery baseline to evaluate whether AI explanation, retrieval, and edit interpretation add value. Use matched scenarios and counterbalance order to reduce practice effects.

Measure task time, missing critical facts, passenger outcomes, expert-rated recommendation quality, and correction effort. Faster output alone could simply move the reconciliation burden onto the manager. Include integration effort, operating cost, support ownership, and failure recovery in the investment case. A hypothetical value formula is episodes × labour time saved × blended labour rate + evidenced avoided disruption costs − integration/operating costs. Do not double-count elapsed time and staff effort or populate it with invented savings.

## Proposed evaluation contract

These are recommended capstone targets, not adopted PRD requirements, regulatory standards, or achieved results. Confirm them before generating the final labelled evaluation set.

| Dimension | Measurement | Proposed acceptance criterion |
| --- | --- | --- |
| Approval and scope | Out-of-order, replayed, rejected, expired, wrong-version, and double-click attempts | Zero unauthorised writes, policy overrides, or compensation commitments across all boundary tests. Any violation fails the release gate. |
| Trigger correctness | Compare event decisions and episode boundaries with independently labelled scripts | Exact agreement for all deterministic scripts, including 60/15-minute boundaries and duplicates; ambiguous or insufficient data produces the specified handoff. |
| Feasibility | Independently recompute each selectable plan's configured constraints | Zero selectable plans with a hard violation or unknown required constraint. Do not treat a model score as a substitute. |
| Passenger accounting | Reconcile affected IDs, final assignments, eligibility, connections, seats, and unresolved outcomes | Exact accounting; no oversold seats, duplicate bookings, lost passengers, or confirmations for failed bookings. |
| Ranking quality | Compare with an independently computed optimum or acceptable set under the published objective | Top option belongs to the acceptable set in at least 90% of eligible held-out cases; report component outcomes and any deterioration from baseline. |
| Rationale and grounding | Verify source existence and manually score claim support | All cited IDs exist; no fabricated critical facts; at least 90% of scored noncritical claims are supported. Unsupported critical claims fail the case. |
| Edits and rejection | Supported constraints, unsupported instructions, corrected plans, and bounded retries | All supported hard edits are enforced; ambiguous edits prompt clarification; no rejected unchanged plan becomes executable; exhausted retries hand off. |
| Reliability | Required-source outages, inconsistent records, stale plans, inventory changes, write and message failures | Correct stop/revalidation path for every labelled failure; repeated actions do not duplicate; no false completed status. |
| Speed | Actual threshold-to-validated-card time, excluding scenario clock and human waiting | 95th percentile at or below 300 seconds over at least 30 qualifying runs. Report failures and handoffs alongside latency, not as omitted slow cases. |
| User decision support | Observed scenario task and a 1–5 reviewer rubric for clarity, evidence, and passenger trade-offs | Proposed target: at least 80% of assessed cards score 4 or 5, with no missed critical warning. Record reviewer expertise and sample size. |
| Business value | Matched manual comparison: task time plus quality and outcomes | Demonstrate a pre-agreed meaningful time reduction without worse feasibility or passenger outcomes. A 50% median reduction is a candidate target to validate, not a known benefit. |

Do not average a serious boundary failure away into a high overall score. Also report unnecessary handoffs: a system that abstains on every valid case is safe from writes but fails its product purpose. For labelled baseline scenarios with valid inputs and known feasible options, it must actually produce the required reviewable plan.

Use the 13 visible scenario families in section 24 for development and demonstration. Add approximately 20 held-out scenario variants with independent labels and run AI-dependent cases at least three times where practical. Report case-level results, repeated-run variability, denominators, data/model/prompt/config versions, and mode (sample, stand-in, or real AI). This is a modest capstone evidence set, not proof of production reliability.

Section 14 currently permits the golden cases as few-shot grounding. Keep those in the development set: evaluation answers and held-out cases must never appear in the prompt or retrieval corpus. Human rubric review should assess whether sources support claims, not just whether citation IDs exist. Where experts are unavailable, state that the assessment used proxies and leave domain validity unproven. Keep the kit's learner-entered verdicts separate from computed diagnostic checks.

## Other important omissions and contradictions

- Section 10 reports trigger-to-approval as the final metric, while sections 9 and 24 use trigger-to-card-ready. Use the latter as the primary processing metric and show human waiting separately.
- Sections 7 and 23 describe per-flight manifests and a total affected cohort differently. They can coexist, but need capacity-consistent counts and a declared affected subset.
- Section 19 calls the card the only interaction point, although ambiguous triggers require human classification. Call it the single recovery-choice approval checkpoint; exception handling is another human interaction.
- Sections 18–19 contain conversational notes rather than finished requirements. The later sections settle these decisions; update the earlier wording and remove obsolete questions.
- “All options stay equally clickable” in section 17 must apply only to viable options. Show rejected evidence with selection disabled.
- Section 16 describes a permanent full trace, while the capstone stores data only for the visit. Provide a downloadable trace and separate production audit retention from working memory. Define which trace fields need masking rather than promising indefinite passenger-record retention.
- Define confidence and high-impact flags with concrete rules. For the capstone, evidence coverage or explicit uncertainty reasons may be more honest than an unexplained percentage. Hard feasibility remains binary and separate.
- Define notification unavailable-contact, channel failure, retry, and manual-contact states. Mandatory notification means every affected passenger has a tracked communication outcome; it cannot guarantee delivery to a missing or invalid contact.
- Define airline-editable passenger prioritisation, party cohesion, assistance handoffs, and treatment of unresolved or overnight passengers. Do not interpret exclusion of compensation actions as exclusion of all passenger-care responsibilities; those can remain explicit human handoffs.
- Set retry/analysis time budgets, maximum regeneration attempts, approval waiting/expiry behaviour, and a human-readable reason for manual takeover. These are needed even in a one-episode demo.
- Add explicit cancelled-episode and changed-restriction behaviour. A confirmed lift resets monitoring according to policy but does not automatically undo passenger bookings that have already completed.

## Recommended order of work

1. Reconcile the existing contradictions and document the capstone architecture and states.
2. Agree the executable-plan prerequisites, ranking objective, simplified rules, and passenger-scope decisions.
3. Define schemas and one capacity-consistent reference flight bank with independently checked outcomes.
4. Adopt an evaluation contract and separate development examples from held-out cases.
5. Build the deterministic trigger, constraint checks, approval enforcement, and mock execution before adding AI explanations and edit interpretation.
6. Validate the product hypothesis through comparative scenario testing, then replace the planned-results sections with observed evidence.

No expansion to additional hubs, compensation automation, live crew/tail writes, or network-wide optimisation is needed to make this a credible capstone. The immediate priority is to make the bounded decision loop measurable and internally consistent.
