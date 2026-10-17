# Hosting contract, version 1

These are the rules a finished prototype must meet so the learner can upload it in the Product Faculty LMS and have it go live with no further step. The LMS checks them on upload.

**Scope: LMS browser profile only.** ARCHITECTURE-ADK.md defines a separately run Python/Google ADK backend; that application cannot run in this locked frame or be submitted as this single-page ZIP. This contract's packaging, PFAI, network, and visit-only persistence restrictions apply to the browser deliverable, not to the separately hosted backend.

For this kit, the product is **HubRecover**. This contract governs packaging and browser capabilities; PRD.md governs the recovery workflow and policy. Authority feeds, operational adapters, retrieval, acknowledgements, bookings, and messaging are local simulations. Azure/Teams integration, production identity, and durable audit storage are outside the browser demonstration. An upload PASS does not establish product correctness, safety, AI quality, or business value.

starter/check-upload.mjs is the program the LMS runs. Run it before you hand the file back. It checks what a program can check: the layout, sizes and types of the files, that nothing is loaded from other websites, that no AI service is called directly, that no key is inside, and that the helper is present, whole and (while the check sits beside pf-ai.js in the kit's starter folder) unchanged. It cannot judge whether sample mode is clearly labelled, whether the page really sends its AI work through the helper, or whether the data is made up. It prints a note only in the plainest cases, such as a page with no PFAI.generate call at all. All three are yours to get right.

## The file

- One file named **prototype.zip**. A single index.html file is also accepted.
- **index.html** at the top level of the ZIP. It is the page that opens.
- **capstone.json** at the top level: `{ "contract": 1, "title": "HubRecover", "kit": "2026.10.5" }`. `title` is shown in the Product Faculty bar above the prototype, beside the learner's name. Keep your own heading inside the page as well. `contract` is the version of these rules. `kit` says which build kit was used. Leave both as they are in starter/capstone.json.
- Other files only if the page needs them, in ordinary folders such as assets/.
- At most 200 files. At most 12 MB for the ZIP, 10 MB for one file, 25 MB unpacked.
- File types: html, css, js, mjs, json, txt, md, csv, tsv, xml, svg, png, jpg, jpeg, gif, webp, avif, ico, bmp, pdf, woff, woff2, ttf, otf, mp3, wav, ogg, mp4, webm, xlsx, docx.

## The page

1. It runs from index.html in a browser with **no server and no build step**. Source files that need compiling (TypeScript, JSX, and so on) are refused.
2. It loads **nothing from other websites**. No scripts, styles, fonts, images or data from a CDN or any other address. Everything it uses is inside the ZIP and referenced with relative paths.
3. It contains the **Product Faculty helper**, whole and unchanged: the block between `PFAI-HELPER-START` and `PFAI-HELPER-END`, inside index.html as in the starter. The same block as assets/pf-ai.js, loaded before your own script, is also accepted.
4. Every AI call goes through `PFAI.generate(...)`. The page never calls an AI service directly.
5. It contains **no API key, password or other secret**. Visitors connect their own key through the helper.
6. It shows a clearly labelled **sample mode** when no key is connected.
7. It uses made-up data only.

## How the hosted page behaves

The LMS serves the prototype inside a locked frame on a Product Faculty page. Exactly:

- The frame is `<iframe sandbox="allow-scripts allow-forms allow-modals allow-downloads" allow="clipboard-write">`. The page inside it has no origin of its own.
- Its files are served with this content policy, where FILES is the address the files are served from:

```
default-src 'none'; script-src FILES 'unsafe-inline' 'unsafe-eval' blob:; style-src FILES 'unsafe-inline'; img-src FILES data: blob:; font-src FILES data:; media-src FILES data: blob:; connect-src FILES data: blob:; worker-src blob:; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'
```

What that means in practice:

| Works | Does not work |
| --- | --- |
| Scripts and styles inside the page or in its own files | Anything loaded from another website |
| Images from its own files, from `data:` and `blob:` addresses, and canvas | Frames, embedded PDFs and other embedded viewers |
| Downloads made in the page (a Blob behind a download link) | Links to other websites and pop-up windows |
| `alert`, `confirm` and `prompt` | Form submissions to a server (handle forms in JavaScript) |
| Copying text with `navigator.clipboard.writeText` after a click | Reading the clipboard, camera, microphone, location |
| Workers made from a Blob | `document.cookie` (reading or writing it throws an error) and IndexedDB |
| `localStorage` and `sessionStorage`, kept in memory for the visit by the helper | Anything kept after the visitor leaves |

Two more rules follow from this:

- Do not read your own files with `fetch()`. It fails when index.html is opened straight from a folder. Put data inside the page, and show images with `<img>`.
- The visitor's key is held by the Product Faculty page around the prototype. Your page asks for AI work through the helper and receives the result. It never receives the key, and it must never ask for one.
- Keep the PRD's logical fixtures embedded for runtime use. Export traces/results through downloads; page reload loses working state, and importing an old trace cannot grant execution authority. Reference sources must be inspectable as local excerpts rather than require external links or live lookups from the hosted page.

## The helper

`PFAI.generate({ system, prompt, messages, files, json, schema, maxTokens })`

- `prompt`: text. Or `messages`: up to 40 of `{ role: 'user' | 'assistant', content: 'text' }`, starting and ending with the user.
- `files`: up to 8 of `{ name, type, data }` with base64 data. PNG, JPEG, GIF, WebP, PDF, or text. About 6 MB each and about 10 MB together.
- `schema`: a JSON Schema for the reply. Or `json: true` for free-form JSON.
- It resolves to `{ text, json, truncated }`. It rejects with an error whose `message` can be shown to the person as it is and whose `code` is one of: not-connected, invalid-key, no-credit, no-access, rate-limited, overloaded, too-large, unsupported-file, too-long, refused, timeout, network, busy, bad-request, bad-reply, unavailable.

| | |
| --- | --- |
| `PFAI.ready` | A promise. It resolves to `{ mode, connected }` once the helper knows where it is running: `'hosted'` or `'standalone'`. |
| `PFAI.connected()` | True when a key is connected. Always false before `PFAI.ready` has resolved. |
| `PFAI.onChange(fn)` | Calls `fn({ mode, connected, provider })` at once, and again on every change. |
| `PFAI.connect()` | Opens the place where a person connects a key: the helper's own bar at the bottom of the page when standalone, the Connect your AI key box of the Product Faculty page when hosted. |
| `PFAI.fileToPart(file)` | A promise for the `{ name, type, data }` of a file the person chose. |
| `PFAI.partFromDataUrl(dataUrl, name)` | The same shape from a `data:` address. |
| `PFAI.partFromText(text, name)` | The same shape from text. |

## How the hosted page talks to the helper

You never need this to build a prototype. It is here in case you want to imitate the hosted page in a test.

1. On load the helper posts `{ pfCapstone: 1, type: 'hello', version: 1 }` to the parent window.
2. The host answers with `{ pfCapstone: 1, type: 'welcome', connected, provider }` and transfers one MessagePort. With no answer within 1.5 seconds the helper runs standalone and shows its own bar.
3. Over the port the helper sends `{ id, type: 'generate', request }` or `{ id, type: 'connect' }`. The host answers `{ id, ok: true, result: { text, truncated } }` or `{ id, ok: false, error: { code, message } }`.
4. The host sends `{ type: 'state', connected, provider }` whenever a key is connected or removed.

## What the LMS corrects by itself

These do not cause a refusal: one folder wrapped around the page, a build folder named dist, build or out, hidden and system files, a missing capstone.json, and a single HTML file uploaded instead of a ZIP.
