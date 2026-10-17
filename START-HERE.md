# Start here

This is the build kit for **HubRecover — Airline Disruption Recovery Assistant**. The revised PRD contains all 36 workflow questions and the decisions needed to create the synthetic data and bounded recovery prototype. The airline-specific prototype and its evaluation have not been built or run yet.

PRD.md is the current product baseline. TEST-PLAN.md mirrors its cases and evaluation gates. ARCHITECTURE-ADK.md designs the requested Python/Google ADK backend. BUILD-INSTRUCTIONS.md explains the separate LMS browser implementation, DESIGN.md sets the appearance, and HOSTING-CONTRACT.md sets LMS packaging/browser restrictions. PRD-REVIEW.md records the historical review that informed the revision. manifest.json preserves the original LMS export provenance; its answer IDs and fingerprint are not a record of the later local edits.

## Requested ADK prototype

Read [ARCHITECTURE-ADK.md](ARCHITECTURE-ADK.md) for the selected backend architecture and implementation order. It uses ADK graph workflows, deterministic Python recovery rules, a web review interface, and durable synthetic booking/approval records. Sections 17–25 address all nine architecture-review findings; section 26 lists the implementation checks still required. This is a design, not a built application. The ADK prototype requires a local server or separate hosting and cannot be packaged into the LMS single-page ZIP. Both profiles follow the PRD's product rules and shared acceptance gates, with separate runtime evidence.

The instructions below and BUILD-PROMPT.txt describe the LMS browser deliverable only. Use the ADK architecture when building the requested backend prototype.

## What to do

1. Open a coding agent. Any agent that can read a ZIP and create files will do. This kit was tested with Claude Code.
2. Attach this ZIP (capstone-build-kit.zip) to a new conversation.
3. Paste the build prompt and send it. The prompt is the text you copied in the LMS with **Copy build prompt**. It is also in this ZIP as BUILD-PROMPT.txt.
4. The agent builds the prototype and gives you one file: **prototype.zip**. To try it, unzip the file and double-click index.html. It opens in your browser. Say what is wrong in your own words and ask the same agent to fix it.
5. When you are happy, keep the latest prototype.zip. You will upload it in the LMS when the Deploy section opens.
6. Go back to the LMS and choose **I've built it**. The next questions ask what really happened when you tested.

## What you will have at the end

- One file you can open by double-clicking, and upload in the LMS so it is live at your own address.
- Your recovery loop: scoped restriction, verified context, calculated options and evidence, Duty Manager review, required operational acknowledgements, final revalidation, mock passenger execution, and reconciliation.
- A refusal you can show: the case your agent must not handle, handed to a person on screen.
- An Evals view for 18 visible development case families and a separate 20-case held-out evaluation, with observed results and verdicts you choose yourself.
- Trace/results exports and any evidenced improvement recorded as before, change, and after; no invented improvement is required.

## After it works

Open the Evals view and run the development cases. Sample mode checks the deterministic engine and UI; real-AI cases need a key connected through the helper. Read the observed outcomes and choose verdicts honestly. All-passing results are possible, but each needs evidence; mark unrun checks explicitly. Fix observed failures and rerun affected cases. Keep final held-out cases outside prompt tuning, then run and record the final evaluation separately.

Complete the human review and matched manual/rules-only comparisons before claiming decision usefulness or time savings. Choose **Copy results** and export the trace. Update PRD sections 25–28 and the corresponding LMS answers with what actually happened, what changed, current limitations, and the verified demo description. Performance targets are not measured results.

## Good to know

- To run real AI in your prototype you connect your own Claude API key. When you open the prototype from your own files, a bar at the bottom of the page asks for it. Once the prototype is live on its Product Faculty address, the button is at the top of the page: **Connect your AI key**. The key stays in that browser tab only and is never saved.
- Never paste a key into the chat with the coding agent.
- Without a key, predefined scenarios run the deterministic engine with visibly labelled example explanations. Arbitrary edit text is not processed in sample mode.
- Use only made-up data. The agent creates it from your plan.
- If you download a later LMS kit, compare it with this revised PRD and preserve the accepted local requirements. Do not silently overwrite HubRecover's later decisions with an older export.

## What is in this ZIP

| File | For | What it is |
| --- | --- | --- |
| START-HERE.md | You | This page |
| BUILD-PROMPT.txt | You | The prompt to paste |
| PRD.md | You and the agent | Current 36-question requirements baseline, data contracts, controls, and acceptance gates |
| ARCHITECTURE-ADK.md | You and the agent | Selected ADK backend design, workflow diagrams, approval/transaction boundaries, evaluation, and build order |
| ARCHITECTURE-REVIEW.md | You and the agent | Historical architecture gap review and current design-closure status; runtime verification remains pending |
| diagrams/ | You and the agent | Editable Mermaid source and verified PNG/SVG previews of the architecture and recovery workflow |
| PRD-REVIEW.md | You and the agent | Historical expert review; current decisions are in PRD.md |
| TEST-PLAN.md | The agent | Mirrored demo inputs, 18 development test families, 20 held-out variants, and evaluation gates |
| BUILD-INSTRUCTIONS.md | The agent | How to build the separate LMS browser prototype |
| DESIGN.md | The agent | The look: colours, type and ready-made parts, so nobody chooses a font |
| HOSTING-CONTRACT.md | The agent | The rules the finished file must meet to upload |
| starter/ | The agent | Generic support-tool example to replace, the unchanged AI helper/upload check, and output metadata titled HubRecover |
| manifest.json | Product Faculty | Original export versions, IDs, and fingerprint; preserved provenance, not the revised local requirements |
