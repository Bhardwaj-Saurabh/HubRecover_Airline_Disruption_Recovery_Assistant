# Build instructions for HubRecover

**Scope: LMS browser profile only.** For the requested Python/Google ADK prototype, follow [ARCHITECTURE-ADK.md](ARCHITECTURE-ADK.md). Its backend cannot run in the LMS frame. Both profiles preserve the PRD's behavioural controls; this file's no-server, JavaScript, PFAI, and ZIP instructions apply only to the browser deliverable.

You are building a prototype for a Product Faculty learner. They are a product person, not a developer. Decide the technical details yourself, keep your explanations plain, and never ask them to choose a framework, a host, a database or a command.

This kit builds **HubRecover — Airline Disruption Recovery Assistant**. PRD.md is the current product and policy baseline; TEST-PLAN.md mirrors its planned cases and acceptance gates. HOSTING-CONTRACT.md governs packaging and browser restrictions, and DESIGN.md governs appearance. Apply these together. PRD-REVIEW.md is a historical review, not a competing specification. manifest.json records the original LMS export and does not supersede the locally revised PRD.

## 1. What to build

Build the **one end-to-end loop** in PRD.md section 21, using the architecture, data contracts, and controls in sections 6 and 12–20. It is a synthetic prototype, not a production system. Leave out sign-in, live operational integrations, configuration screens, and unrelated dashboards. Include the evidence, execution summary, and Evals view required by the loop.

Keep the human in control exactly where PRD.md says a person approves, edits, rejects or is asked.

Implement the Supervisor as a deterministic JavaScript state machine. Specialist roles are modules and in-memory adapters. Calculate triggers, schedule/crew/aircraft/dispatch feasibility, passenger allocation, ranking, approval validity, and mock execution in code. AI may explain verified evidence and propose supported edits; it cannot invent operational values, rank by its own preferences, authorise writes, or select tools from source text.

Approval begins prerequisite waiting and final revalidation. It is not permission to skip matching operational acknowledgements, approval expiry, material-source checks, or atomic inventory checks. Enforce these in code in sample and real-AI modes. Preserve completed passenger actions on partial failure and keep notification retries separate from booking retries. Derive budgets and constants from one versioned configuration matching the PRD; do not invent different defaults in the UI.

## 2. What a strong prototype shows

starter/index.html is a finished example of the shape: a made-up support tool called Northstar Triage. **Copy the shape, never the content.** The learner's product, data, rules and names replace everything Northstar.

Whatever the product is, a viewer must be able to follow one case through five stages without anyone narrating. Label them on screen, in this order:

1. **Input.** An executable synthetic scenario selected with one click, with event applicability, episode clock, and mode visible. No upload or live operational source is required.
2. **Context.** The records and rules the agent read for this case, visible.
3. **Decision.** Calculated candidates, deterministic ranking components, gate results, and grounded explanations with named sources. Clearly distinguish proposed actions from committed ones.
4. **Output.** Labelled fields a person can judge in under a minute. Not a wall of chat.
5. **Review.** Duty Manager Approve, Edit, and Reject controls, with every run and decision in a visible trace. Trigger classification and edit clarification are exception interactions. Escalation is automatic, not a fourth approval-card button. Duplicate clicks cannot duplicate decisions or writes.

After Review, show prerequisite acknowledgements, final revalidation, passenger execution, communication outcomes, and reconciliation. A review click does not mark recovery complete. COMPLETED and PARTIAL_MANUAL must follow the PRD definitions; automatic near-miss and manual-handoff cases require no invented approval click. Include Stop, safe Reset, trace download, expiry visibility, and labelled driver controls for simulated acknowledgements and source updates.

Then the moment people remember: **the refusal.** The learner's boundary case, the one their agent must refuse or hand to a person, comes back refused on screen with the rule stated. It must do so in sample mode as well. If the plan has more than one case where the agent must stop, the one it must turn down outright is the refusal; a case where it stops to ask the person a question is not.

The starter's five cases are unrelated examples. Replace them with exactly **18 visible development case families**, with subvariants recorded under each family. Provide a separate final-evaluation runner/table for the **20 held-out variants**. Held-out labels and oracle outputs are evaluator-only and must not enter model context, retrieval, or sample explanations. Keep the final set separate from prompt examples and record any use that exposes it during development.

Build these too, as the starter does:

- **The test cases as one-click chips**, labelled by what each one tests ("Happy path", "Missing information", "Boundary: must refuse"). Demos fail while someone types.
- **An Evals view.** For each of the 18 visible families, copy its expected behaviour word for word from TEST-PLAN.md, fill actual results only from observed runs, and let the **learner** choose pass, needs work or fail. Record subvariants and modes separately. Give held-out cases a separate section with frozen expected outcomes and repeated-run records. Automatic deterministic diagnostics and acceptance metrics are permitted, but never prefill human verdicts or have the AI grade its own explanation. Include a scoreboard, before/change/after improvement card, and limitations. Evaluation runs use isolated test state, cannot authorise demo writes, and are marked as tests in traces.
- **A Copy results button** that gives the learner the table, the improvement and the limitations as text. Their next capstone questions ask for exactly these.
- **A permanent line at the review step**: "Passenger actions require current Duty Manager approval, confirmed prerequisites, and final checks."
- **No dead screens.** A first screen that says what the product is in one line and what to click; a visible working state while the AI runs; an error in words when something fails.

## 3. Decisions already made for you

- One web page: **index.html**, with its styles and scripts inside it. Plain HTML, CSS and JavaScript.
- No server, no database, no build step, no package manager, no framework that needs compiling.
- Nothing loaded from other websites. No CDN links, no web fonts, no analytics. If you want a library, copy it into the page.
- A small **assets/** folder is allowed for images the page shows.
- Data lives in memory for the visit. "Saving" means adding to a list or log on the page, plus a download where that helps. Never claim to update a real system.
- AI is reached only through the Product Faculty helper, `PFAI`, which is already inside starter/index.html. Keep it inside the page. (starter/pf-ai.js is the same helper as a separate file. Loading it as assets/pf-ai.js before your own script is also accepted.)
- The look is decided too. See section 8 and DESIGN.md.

HOSTING-CONTRACT.md lists the exact rules the finished file must meet and exactly what the hosted page allows. Read it before you start.

## 4. Start from the starter

Copy starter/index.html and build on it. Two blocks in it are not yours to change:

- **The helper**, between the comments `PFAI-HELPER-START` and `PFAI-HELPER-END`. The two comments are the first and last lines inside one `<script>` element: keep that whole element, unedited. Never shorten it, reformat it or put your own code inside it. starter/pf-ai.js holds the same text, if copying from there is easier.
- **The design block**, between `PF-DESIGN-START` and `PF-DESIGN-END` in the page's styles. Keep it as it is and build with it.

Everything else is an example to replace: the Northstar data, the agent's instructions, the fields, the test cases, the words on screen.

## 5. Calling AI

```js
// Calls back at once with the state so far, and again whenever a visitor connects or disconnects.
// Use it to keep a visible label up to date.
PFAI.onChange(function (state) {
  label.textContent = state.connected ? 'Live: results come from AI' : 'Sample mode: results are examples, not AI';
});

// The helper needs a moment to learn whether a key is connected.
// Wait for PFAI.ready before you choose between sample mode and a real call.
PFAI.ready.then(function () {
  if (!PFAI.connected()) { /* sample mode: show a built-in example result, labelled as a sample */ return; }
  return PFAI.generate({
    system: 'What the AI should do, and what it must never do.',
    prompt: 'The input for this request.',
    files: [part],            // optional, see "Files" below
    schema: {                 // optional: the reply arrives parsed as reply.json
      type: 'object',
      properties: {
        strategyId: { type: 'string' },
        factIds: { type: 'array', items: { type: 'string' } },
        precedentIds: { type: 'array', items: { type: 'string' } },
        explanation: { type: 'string' }
      },
      required: ['strategyId', 'factIds', 'precedentIds', 'explanation'],
      additionalProperties: false
    }
  }).then(function (reply) {
    // reply.text is the text; reply.json is the parsed object when schema or json: true was sent.
  });
}).catch(function (error) {
  // error.message is written for the person using the page. Show it as it is.
});
```

Rules for AI calls:

- Use `PFAI.generate` for every AI call. Do not call any AI service yourself. Direct calls are blocked on the hosted page.
- When `PFAI.connected()` is false, run **sample mode**: execute the same deterministic calculations and controls on embedded fixtures, using labelled example explanations and predefined edit chips for the AI-dependent portions. Never substitute scripted pass results for actual engine checks, present a scripted explanation as AI work, or silently switch to sample mode after a real call fails.
- In sample mode a person's own text or upload cannot be processed. Say so plainly and point to the "Use real AI" button, as the starter does. Never show a made-up result for it.
- When a call fails, show `error.message`, invalidate stale selectable results, and apply the PRD's retry and deadline limits. Preserve committed passenger actions and their trace. A retry or second click must never duplicate a decision, booking, or message.
- Show that work is in progress while a call runs, and disable the button that started it.

### Where a person connects a key

The helper owns the key. Your page never asks for one, stores one or sees one.

- When index.html is opened by itself (your preview, or the learner double-clicking the file), the helper shows a bar at the bottom of the window with a field for a Claude API key. The helper adds empty space at the end of the page so the bar does not cover your content. If your layout fills the window exactly, let the page scroll.
- On the hosted Product Faculty page there is no bar. The page around the prototype has a **Connect your AI key** button at the top.
- `PFAI.connect()` opens whichever of the two applies. Give your page one button for it, for example "Use real AI", and hide it while a key is connected. Do not build your own key field.

### Files

`files` takes up to 8 items of the shape `{ name, type, data }`, where data is base64. Make them with the helper:

- `PFAI.fileToPart(file)` for a file the person chose in an `<input type="file">`. It returns a promise.
- `PFAI.partFromDataUrl(dataUrl, name)` for a built-in example held as a `data:` address, for example `canvas.toDataURL('image/png')`.
- `PFAI.partFromText(text, name)` for a built-in text document.

The AI accepts PNG, JPEG, GIF and WebP images, PDFs, and text (plain text, CSV, Markdown, JSON). It does not accept SVG: draw it on a canvas and send the PNG. The helper refuses a file above about 6 MB and a request above about 10 MB. Check for 4 MB yourself and tell the person when a file is too large.

### Structured replies

- In a `schema`, every object needs `additionalProperties: false` and must list all its properties in `required`. For a value that may be missing, let the AI return an empty string.
- You may use `type`, `properties`, `required`, `items`, `enum`, `const`, `anyOf` and `description`.
- Do not use `minimum`, `maximum`, `minLength`, `maxLength`, `minItems` above 1, or a schema that refers to itself. Check numbers and lengths in your own code after the reply arrives.
- Validate strategy/fact/precedent IDs against the context actually supplied. Render critical operational claims from verified fact records; numerical changes, unknown IDs, tool requests, and unsupported critical claims invalidate the response. Supported edit proposals must pass the PRD's vocabulary/ID/value checks before regeneration.
- If the reply cannot be read as the data you asked for, the call fails with a message you can show. Treat it like any other failed call within the PRD budget.

## 6. The agent's instructions come from the plan

Compile the system prompt from PRD.md in five parts, as the starter does, and keep it as one constant near the top of your script so it is easy to find and change:

- **ROLE**: the agent's role in one sentence, from the learner's plan.
- **CONTEXT**: use only the data and rules given; never invent a fact.
- **RULES**: the learner's "must not" list, word for word.
- **OUTPUT**: existing plan/strategy IDs, typed fact/comparison claims, approved reason codes and precedent IDs, or a validated supported edit proposal. Follow PRD section 15's bounded schema and deterministic claim/predicate checks; render explanations from human-owned templates. Operational counts, ranking, approvals, and write permissions come from code.
- **ESCALATION**: the learner's triggers for refusing or handing over, and what to do when information is missing: ask or escalate, never guess.

Give every record and rule a short name the agent can cite, and send only the minimal synthetic facts and eligible excerpts belonging to the case. Never send full manifests, held-out labels, oracle answers, or expected traces. Validate fact scope, units/cohort, comparison arithmetic and approved reason predicates; source IDs alone do not establish support. Invalid claims produce a visible error and an unselectable result. No arbitrary model prose appears on cards. Human evaluation still assesses rendered conclusions and usefulness against the rules-only baseline.

## 7. Made-up data

Create the example inputs PRD.md and TEST-PLAN.md describe: documents, records, rules, expected results. Make them fictional and say so on the page. Never use a real person, company, customer record or document. Invent names that are plainly made up. Seed the data on purpose: every test case needs its matching records, including the missing-information case and the boundary case.

Use the PRD schema/invariant rules, `HUBRECOVER-001` authoring seed, 18 day-one flights, six next-day alternatives, and 300 affected reference passengers. Validate capacities, foreign keys, dates, resource continuity, parties, assistance, and mutually exclusive outcomes before scaling cases. Calculate expected results independently from the execution engine. Freeze and separate the 20 held-out variants. Logical fixture names describe authoring datasets; runtime copies belong inside the page and are not fetched from local JSON files.

Keep the examples inside the page, so the prototype works both when index.html is opened straight from a folder and when it is hosted:

- **Text and records:** data in your script.
- **Pictures a person only looks at:** inline SVG, a `data:` address, or an image file in assets/ shown with `<img>`.
- **Pictures or documents that are also sent to the AI:** a page opened from a folder cannot read its own files back, so do not keep these in assets/. Draw the example on a `<canvas>` (the packing slip in the starter is drawn this way) or keep it as a `data:` address, show it with `<img>`, and send it with `PFAI.partFromDataUrl(...)`. For a text document use `PFAI.partFromText(...)`.
- **PDF examples:** the hosted page cannot display a PDF. Show a picture of the document and send that picture, or send the PDF and show its content as text beside it.

Showing what a person uploaded:

- **A picture:** `<img>` with a `data:` address built from the part (`'data:' + part.type + ';base64,' + part.data`, as the starter does) or with `URL.createObjectURL(file)`. Both work on the hosted page.
- **A PDF:** it cannot be previewed on the hosted page. Show its name, say it was sent, and never leave an empty box.

## 8. The look ships in the kit

Nobody chooses a font. The starter's design block holds the colours, type sizes, spacing and ready-made parts: top bar, panels, stage labels, case cards, chips, labelled fields, status badges, buttons, run log, scoreboard, working and empty states. DESIGN.md lists them.

- Use only those tokens and parts. No new colours, no new fonts, no emoji as icons, nothing smaller than 13px.
- Use the PRD's Operations skin, `<html data-skin="ops">`, for the OCC audience. Keep the kit tokens unchanged. Switch only when the learner asks.
- It must work on a phone: one column on a narrow screen, no sideways scrolling.

## 9. Let the learner try it

When the prototype works, tell the learner how to open it: **unzip prototype.zip, then double-click index.html**. It opens in their browser. If you started a preview in your own environment, give them that link as well.

Tell them that real AI needs their own Claude API key, pasted into the bar at the bottom of the prototype page. Tell them never to paste a key into this conversation.

## 10. Check your work, and be honest about it

Go through TEST-PLAN.md. A case can be checked in three ways. Say which one you used for each case.

- **In sample mode.** Run the actual deterministic engine and state transitions against fixtures without a key. This checks the calculations, boundaries, acknowledgement/revalidation path, reconciliation, UI, trace, and exports. Sample explanations do not prove real-AI behaviour or product value.
- **With a stand-in AI.** In your own test only, you may replace `PFAI.connected` and `PFAI.generate` with functions that return prepared replies and failures, to check how the page handles results, errors, retries and double clicks. Never leave such a replacement in index.html. HOSTING-CONTRACT.md also describes how the hosted page talks to the helper, in case you want to imitate it.
- **With real AI.** You have no key and must not ask for one. Every case that depends on what the AI actually returns is the learner's to try. List those cases and say exactly how to try each one.

Then report in plain words:

- which cases you checked, in which of the three ways, and what happened,
- which cases the learner still needs to try by hand, and how,
- anything that does not work yet.

Never say a case passed unless you ran it, and never describe a sample-mode or stand-in run as a real AI result. The learner will write up real results in their capstone.

Apply the TEST-PLAN acceptance gates. Include wrong-version/expired approvals, changed inventory, unacknowledged operational changes, partial failures, and code-level duplicate prevention. Exercise the independent oracle and source-invariant checks, with no self-generated ground truth. Export modes, case/subvariant results, versions, repeats, and separate scenario/processing/human-wait/execution times. Report human-review and manual/rules-only comparisons as pending until actually conducted. Upload-check PASS verifies packaging only; it cannot establish recovery safety, model quality, or business value.

## 11. Hand back one file and one short note

Pack the result as **prototype.zip**:

```
prototype.zip
  index.html        the prototype, with the helper inside it
  capstone.json     copied from starter/capstone.json, with "title" set to the prototype's name
  assets/           only if needed
```

In capstone.json, set `"title"` to `"HubRecover"`. The hosted page shows it in the Product Faculty bar above the prototype. Leave `"contract"` and `"kit"` as they are.

If you can run commands, run the check on your file and fix everything it reports until it says PASS:

```
node path/to/kit/starter/check-upload.mjs path/to/prototype.zip
```

It can be run from any folder. It is the program the LMS runs on upload. As long as it is still beside pf-ai.js in the kit's starter folder, it also confirms the helper in your page is the one from this kit. If you cannot run commands, check the file against HOSTING-CONTRACT.md line by line.

Give the learner exactly one file, prototype.zip, and one short note in plain words with these parts, in this order:

1. **How to open it:** unzip prototype.zip and double-click index.html.
2. **What it does:** three or four lines, following the five stages.
3. **Real AI and sample mode:** without a key the page shows labelled samples. For real AI they paste their own Claude API key into the bar at the bottom of the page, never into this chat.
4. **What you checked yourself**, and in which way (sample mode or stand-in AI).
5. **What they still need to try by hand**, and how.
6. **Choices you made** where their plan left something open, including the skin.
7. **What to do next:** run remaining real-AI cases through the helper, complete human-review and baseline comparisons, enter honest verdicts, fix evidenced failures, and rerun affected checks. Keep final held-out scenarios separate from tuning; replace an exposed final holdout before making final quality claims. Copy/export the results for the capstone answers.
8. **Last line:** "When you are happy, upload prototype.zip in the LMS under Deploy when that section opens."

## 12. When the learner comes back

Stay in the same conversation. Change the prototype, keep what already works, check it again and hand back a new prototype.zip. Explain what changed in plain words. A new workflow, different fields or different controls are product changes: make them without asking technical questions.

**When a failure occurs**, first reproduce it and identify which layer failed. Approval, hard-constraint, allocation, expiry, acknowledgement, and retry defects require a code/configuration fix; never attempt to repair a safety boundary only by strengthening a prompt. Check data contracts and source context for factual failures. Change model instructions or supplied grounding for interpretation/explanation failures only after identifying the cause. Change one thing at a time when practical.

Record the failing evidence, cause, change, and rerun result. Run affected checks and the happy path; run the full relevant boundary suite after state, rule, or write changes. Use independent held-out evidence for final quality assessment rather than repeatedly tuning to it.

**When the learner pastes their results**, record them in the page (the `RECORDED` constant in the starter: the date, each case's actual result, verdict and note, and the improvement) so a visitor sees the author's results. Include mode, versions, repeats, and provenance. Record exactly what they supplied. All-passing results are possible; require observed evidence and clearly list unrun checks. Suggest additional challenge cases only when coverage is missing, and never fabricate a failure or an improvement.

**When the learner asks for more**, assess it against the current PRD and hosting limits. The approval card, trace, Stop/Reset, execution summary, and separate evaluation runner are already required core features. Do not add agents, live lookups, network-wide recovery, or unrelated dashboards merely because the starter suggests them. Keep the existing controls and evidence intact when implementing an authorised scope change.

If a request truly cannot work as a single web page (for example it needs a shared database, a live connection to another system, or scheduled jobs), do not refuse the project and do not quietly build something else. Say in a sentence or two what the request would need, build the closest version that works as a single page (for example with made-up data standing in for the other system), and tell the learner that a project needing its own server can be hosted elsewhere and given to faculty as a link in the LMS.

## 13. If the learner pastes a "fix request" from the LMS

The LMS checks the file on upload. If it refuses the file it gives the learner a short list of fixes to paste here. Make exactly those fixes, keep everything else as it is, and hand back a new prototype.zip.
