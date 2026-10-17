# Design: the look ships in the kit

A capstone prototype should look like a product on its first screen. Nobody chooses a font. starter/index.html carries a complete design block, between `PF-DESIGN-START` and `PF-DESIGN-END` in its styles: tokens for colour, type, spacing and shape, and ready-made parts. Build the learner's product from those.

For this kit, the product is **HubRecover** and PRD.md selects `<html data-skin="ops">` for the OCC audience. The generic starter demonstrates reusable parts, not the current airline workflow. Keep its design tokens unchanged while replacing its content and controls.

These appearance and workflow-display rules also apply to the web interface in ARCHITECTURE-ADK.md. That interface is served by the ADK application's backend; LMS single-page packaging and PFAI instructions belong to the separate browser profile.

## Rules

1. Keep the design block as it is. Write your own layout rules after it, using only its tokens (`var(--...)`).
2. No new colours and no new fonts.
3. Status colours mean the same thing everywhere and are never restyled: green for pass or approved, amber for needs work or pending, red for fail, refused or escalated, blue for working.
4. No emoji as icons. Use words, the numbered stage labels and the status badges.
5. Nothing smaller than 13px. Body text is 14px.
6. One skin per product, set once on `<html data-skin="...">`. Never mix skins or change a token for one element.
7. One column on a narrow screen, no sideways scrolling, controls at least 36px tall.
8. No dead screens: a first screen that explains the product in one line, a visible working state, an error in words.

## The three skins

Pick by the product's audience (the specific user in PRD.md), not by taste.

| Skin | Attribute | Mood | Fits |
| --- | --- | --- | --- |
| Operations | `data-skin="ops"` | Dark, calm | Internal tools, operations teams, queues, triage |
| Studio | `data-skin="studio"` | Light, clean | Customer-facing tools, business users, anything shown in daylight |
| Terminal | `data-skin="term"` | Mono, green on black | Developer tools, data and infrastructure workflows |

Tell the learner which one you chose and why in one line. Switch when they ask: it is one attribute.

## The tokens

| For | Tokens |
| --- | --- |
| Type sizes | `--fs-0` 13px (labels, log lines), `--fs-1` 14px (body), `--fs-2` 16px (emphasis), `--fs-3` 20px (headlines), `--fs-4` 28px (numbers) |
| Fonts | `--font-body` (set by the skin), `--font-mono` (ids, log, sources) |
| Spacing | `--sp-1` 4px, `--sp-2` 8px, `--sp-3` 12px, `--sp-4` 16px, `--sp-5` 24px, `--sp-6` 32px |
| Shape | `--radius` 10px (panels), `--radius-sm` 6px (buttons, cards, fields), `--shadow` |
| Surfaces | `--bg` (page), `--bg-raise` (panels, cards), `--bg-inset` (wells, log, fields), `--line` (borders), `--chip` |
| Text | `--ink` (main), `--ink-2` (secondary), `--ink-3` (labels) |
| Accent | `--accent`, `--accent-ink` (text on accent) |
| Status | `--ok`, `--warn`, `--danger`, `--info` |

## The parts

| Part | Classes | Use it for |
| --- | --- | --- |
| Top bar | `.topbar`, `.product`, `.meta`, `.tabs`, `.tab` | Product name, mode, the "Use real AI" button, the view switch |
| Layouts | `.console` (three columns), `.page` (one column) | The working screen; the Evals view |
| Panel | `.panel`, `.panel-head`, `.panel-body` | Every block of the screen |
| Stage label | `.stage` with `data-n="1"` | Naming the stages of the loop, in order |
| Case card | `.case-card`, `.id`, `.title`, `.is-active` | The queue of cases |
| Chip | `.chip`; `.chip.cite` for sources; `data-state="Approved"`, `"Edited"`, `"Escalated"` or `"Rejected"` for an outcome | One-click test cases; the sources a decision used |
| Labelled field | `.field`, `.k`, `.v`, `.v.why` | Records, the decision's reason, every output field |
| Status badge | `.badge` with `.ok`, `.warn`, `.danger`, `.info` or `.neutral` | OK, refused, approved, edited, escalated, mode |
| Buttons | `.btn`, `.btn.primary`, `.btn.approve`, `.btn.danger` | Run; approve; escalate or reject |
| Boundary line | `.boundary-note` | "Nothing is sent without human approval." |
| Form controls | `.input`, `.label` | Text boxes, selects, their labels |
| Run log | `.log`, `.line`, `.t`, `.action-approve`, `.action-edit`, `.action-escalate`, `.action-reject` | Every run and human decision |
| Scoreboard | `.scoreboard`, `.stat`, `.n`, `.l` | Pass, needs work, fail, cases run |
| Evals table | `.evals-table` (stacks on a phone when cells carry `data-label`) | Case, expected, actual, verdict |
| States | `.thinking`, `.empty` with `.headline`, `.error-note` | Working; first screen; a failure in words |
| Picture, sources | `figure.picture` (add `.is-large` for a document a person compares with the output), `details.source` | A shown attachment; rules the agent reads, folded away |

## What finished looks like

HubRecover shows Input, Context, Decision, Output, and Review, then an execution summary. Context exposes verified source ages and evidence. Decision/Output display computed ranking components, passenger outcomes, evidence coverage, warnings, and disabled rejected options. Review contains Approve, Edit, and Reject; automatic manual handoff is not an Escalate peer button.

Use the existing parts for prerequisite acknowledgements, expiry, final revalidation, Stop/Reset, mock bookings/communication, and trace download. An Approved badge means the decision was recorded, not that recovery is complete. Pending acknowledgements and unresolved communication retain their own statuses. COMPLETED and PARTIAL_MANUAL use the PRD definitions and remain visually distinct; rejected evidence is never selectable.

The Evals view contains the 18 visible development families, recorded subvariants, a separate 20-case held-out section, automatic diagnostics, learner-entered verdicts, versions/modes, observed results, limitations, and any evidenced improvement. Do not prefill verdicts or fabricate an improvement. The starter's five support-tool cases and Escalate control are examples to replace.
