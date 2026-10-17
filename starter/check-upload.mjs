// Product Faculty capstone prototype: the upload rules, in one place.
//
// The LMS runs this file when a learner uploads a prototype. The build kit
// ships the very same file as starter/check-upload.mjs, so a coding agent can
// run the identical check before handing the file back:
//
//     node check-upload.mjs prototype.zip
//
// Plain JavaScript on purpose: it has to run with nothing installed.
import { deflateRawSync, inflateRawSync } from 'node:zlib';

export const CONTRACT_VERSION = 1;
export const HELPER_MARKER = 'PFAI-HELPER-START';
export const HELPER_END_MARKER = 'PFAI-HELPER-END';

export const LIMITS = {
  uploadBytes: 12 * 1024 * 1024,
  expandedBytes: 25 * 1024 * 1024,
  fileBytes: 10 * 1024 * 1024,
  entries: 800,
  files: 200,
  pathLength: 180,
};

export const CONTENT_TYPES = {
  html: 'text/html; charset=utf-8', htm: 'text/html; charset=utf-8', css: 'text/css; charset=utf-8',
  js: 'text/javascript; charset=utf-8', mjs: 'text/javascript; charset=utf-8', json: 'application/json; charset=utf-8',
  map: 'application/json; charset=utf-8', txt: 'text/plain; charset=utf-8', md: 'text/markdown; charset=utf-8',
  csv: 'text/csv; charset=utf-8', tsv: 'text/tab-separated-values; charset=utf-8', xml: 'application/xml; charset=utf-8',
  svg: 'image/svg+xml', png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', gif: 'image/gif', webp: 'image/webp',
  avif: 'image/avif', ico: 'image/x-icon', bmp: 'image/bmp', pdf: 'application/pdf',
  woff: 'font/woff', woff2: 'font/woff2', ttf: 'font/ttf', otf: 'font/otf',
  mp3: 'audio/mpeg', wav: 'audio/wav', ogg: 'audio/ogg', mp4: 'video/mp4', webm: 'video/webm',
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
};
const TEXT_TYPES = new Set(['html', 'htm', 'css', 'js', 'mjs', 'json', 'txt', 'md', 'csv', 'tsv', 'xml', 'svg']);
const CODE_TYPES = new Set(['html', 'htm', 'css', 'js', 'mjs', 'svg']);
const SERVER_FILES = /\.(py|rb|php|go|java|cs|rs|ex|exs|pl|sh|bat|ps1|sql)$/i;
const UNBUILT_FILES = /\.(tsx?|jsx|vue|svelte|scss|sass|less)$/i;
const AI_HOSTS = /api\.(openai|anthropic)\.com|generativelanguage\.googleapis\.com|api\.(groq|mistral|cohere)\.(com|ai)|openrouter\.ai/i;
const DEV_FILES = /^(package(-lock)?\.json|yarn\.lock|pnpm-lock\.yaml|bun\.lockb?|tsconfig(\.[\w-]+)?\.json|vite\.config\.[cm]?[jt]s|webpack\.config\.[cm]?js|readme(\.md|\.txt)?|license(\.md|\.txt)?|makefile|dockerfile|procfile|requirements\.txt|check-upload\.mjs)$/i;
const BUILD_FOLDERS = ['dist', 'build', 'out'];

// ---------------------------------------------------------------- zip

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  return table;
})();

export function crc32(bytes) {
  let crc = 0xffffffff;
  for (let i = 0; i < bytes.length; i += 1) crc = CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

const asBuffer = (data) => (typeof data === 'string' ? Buffer.from(data, 'utf8') : Buffer.from(data.buffer, data.byteOffset, data.byteLength));

/** A plain ZIP (deflate, UTF-8 names). `files`: [{ name, data }] with data a string or bytes. */
export function writeZip(files, date = new Date()) {
  const time = ((date.getUTCHours() << 11) | (date.getUTCMinutes() << 5) | (date.getUTCSeconds() >> 1)) & 0xffff;
  const day = (((Math.max(1980, date.getUTCFullYear()) - 1980) << 9) | ((date.getUTCMonth() + 1) << 5) | date.getUTCDate()) & 0xffff;
  const parts = []; const central = []; let offset = 0;
  for (const file of files) {
    const name = Buffer.from(file.name, 'utf8');
    const raw = asBuffer(file.data);
    const packed = deflateRawSync(raw, { level: 9 });
    const stored = packed.length >= raw.length;
    const body = stored ? raw : packed;
    const crc = crc32(raw);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0); local.writeUInt16LE(20, 4); local.writeUInt16LE(0x0800, 6);
    local.writeUInt16LE(stored ? 0 : 8, 8); local.writeUInt16LE(time, 10); local.writeUInt16LE(day, 12);
    local.writeUInt32LE(crc, 14); local.writeUInt32LE(body.length, 18); local.writeUInt32LE(raw.length, 22);
    local.writeUInt16LE(name.length, 26); local.writeUInt16LE(0, 28);
    const entry = Buffer.alloc(46);
    entry.writeUInt32LE(0x02014b50, 0); entry.writeUInt16LE(20, 4); entry.writeUInt16LE(20, 6); entry.writeUInt16LE(0x0800, 8);
    entry.writeUInt16LE(stored ? 0 : 8, 10); entry.writeUInt16LE(time, 12); entry.writeUInt16LE(day, 14);
    entry.writeUInt32LE(crc, 16); entry.writeUInt32LE(body.length, 20); entry.writeUInt32LE(raw.length, 24);
    entry.writeUInt16LE(name.length, 28); entry.writeUInt32LE(offset, 42);
    parts.push(local, name, body); central.push(entry, name);
    offset += 30 + name.length + body.length;
  }
  const directory = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0); end.writeUInt16LE(files.length, 8); end.writeUInt16LE(files.length, 10);
  end.writeUInt32LE(directory.length, 12); end.writeUInt32LE(offset, 16);
  return Buffer.concat([...parts, directory, end]);
}

class ZipProblem extends Error {
  constructor(code, message) { super(message); this.code = code; }
}

/** Entries of a ZIP as [{ name, data }]. Throws ZipProblem for anything it will not open. */
export function readZip(bytes, limits = LIMITS) {
  const buffer = asBuffer(bytes);
  let end = -1;
  for (let i = buffer.length - 22; i >= Math.max(0, buffer.length - 22 - 65535); i -= 1) {
    if (buffer.readUInt32LE(i) === 0x06054b50) { end = i; break; }
  }
  if (end < 0) throw new ZipProblem('not-a-zip', 'The file is not a complete ZIP file. It may have been cut off while saving.');
  const count = buffer.readUInt16LE(end + 10);
  const size = buffer.readUInt32LE(end + 12);
  let cursor = buffer.readUInt32LE(end + 16);
  if (buffer.readUInt16LE(end + 4) !== 0 || count === 0xffff || size === 0xffffffff || cursor === 0xffffffff) {
    throw new ZipProblem('zip-too-large', 'The ZIP uses a format for very large archives. A prototype must be a small, ordinary ZIP.');
  }
  if (count > limits.entries) throw new ZipProblem('too-many-files', `The ZIP holds ${count} entries. A prototype may hold at most ${limits.files} files.`);
  if (cursor + size > end) throw new ZipProblem('not-a-zip', 'The ZIP file is damaged.');
  const entries = []; let declared = 0;
  for (let n = 0; n < count; n += 1) {
    if (cursor + 46 > buffer.length || buffer.readUInt32LE(cursor) !== 0x02014b50) throw new ZipProblem('not-a-zip', 'The ZIP file is damaged.');
    const madeBy = buffer.readUInt16LE(cursor + 4) >> 8;
    const flags = buffer.readUInt16LE(cursor + 8);
    const method = buffer.readUInt16LE(cursor + 10);
    const crc = buffer.readUInt32LE(cursor + 16);
    const packedSize = buffer.readUInt32LE(cursor + 20);
    const fullSize = buffer.readUInt32LE(cursor + 24);
    const nameLength = buffer.readUInt16LE(cursor + 28);
    const extraLength = buffer.readUInt16LE(cursor + 30);
    const commentLength = buffer.readUInt16LE(cursor + 32);
    const mode = buffer.readUInt32LE(cursor + 38) >>> 16;
    const localOffset = buffer.readUInt32LE(cursor + 42);
    const name = buffer.subarray(cursor + 46, cursor + 46 + nameLength).toString('utf8');
    cursor += 46 + nameLength + extraLength + commentLength;
    if (flags & 1) throw new ZipProblem('zip-encrypted', 'The ZIP is password protected. Upload it without a password.');
    if (madeBy === 3 && (mode & 0o170000) === 0o120000) throw new ZipProblem('zip-symlink', `The ZIP contains a shortcut (${name}) instead of a real file.`);
    if (name.endsWith('/') || name.endsWith('\\')) continue;
    if (packedSize === 0xffffffff || fullSize === 0xffffffff || localOffset === 0xffffffff) throw new ZipProblem('zip-too-large', 'The ZIP holds a file that is too large.');
    if (fullSize > limits.fileBytes) throw new ZipProblem('file-too-large', `${name} is ${megabytes(fullSize)}. One file may be at most ${megabytes(limits.fileBytes)}.`);
    declared += fullSize;
    if (declared > limits.expandedBytes) throw new ZipProblem('too-large', `The files add up to more than ${megabytes(limits.expandedBytes)} once unpacked.`);
    if (method !== 0 && method !== 8) throw new ZipProblem('zip-method', `${name} is packed in a way this check cannot open. Make an ordinary ZIP.`);
    if (localOffset + 30 > buffer.length || buffer.readUInt32LE(localOffset) !== 0x04034b50) throw new ZipProblem('not-a-zip', 'The ZIP file is damaged.');
    const start = localOffset + 30 + buffer.readUInt16LE(localOffset + 26) + buffer.readUInt16LE(localOffset + 28);
    if (start + packedSize > buffer.length) throw new ZipProblem('not-a-zip', 'The ZIP file is damaged.');
    const packed = buffer.subarray(start, start + packedSize);
    let data;
    try { data = method === 0 ? Buffer.from(packed) : inflateRawSync(packed, { maxOutputLength: Math.max(1, fullSize) }); }
    catch { throw new ZipProblem('not-a-zip', `${name} could not be unpacked. The ZIP file is damaged.`); }
    if (data.length !== fullSize || crc32(data) !== crc) throw new ZipProblem('not-a-zip', `${name} did not unpack correctly. The ZIP file is damaged.`);
    entries.push({ name, data });
  }
  return entries;
}

// ---------------------------------------------------------------- rules

const megabytes = (bytes) => `${(bytes / (1024 * 1024)).toFixed(bytes < 1024 * 1024 ? 2 : 1)} MB`;
const extension = (path) => { const dot = path.lastIndexOf('.'); return dot < 0 || dot < path.lastIndexOf('/') ? '' : path.slice(dot + 1).toLowerCase(); };
const basename = (path) => path.slice(path.lastIndexOf('/') + 1);

const SECRETS = [
  // "sk-" must start the word: an id such as task-2026-... or desk-... is not a key.
  [/(?<![A-Za-z0-9_-])sk-ant-[A-Za-z0-9_-]{20,}/, 'an Anthropic API key'],
  [/(?<![A-Za-z0-9_-])sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}/, 'an OpenAI API key'],
  [/AIza[0-9A-Za-z_-]{35}/, 'a Google API key'],
  [/AKIA[0-9A-Z]{16}/, 'an AWS access key'],
  [/gh[pousr]_[A-Za-z0-9]{36,}/, 'a GitHub token'],
  [/xox[baprs]-[A-Za-z0-9-]{20,}/, 'a Slack token'],
  [/-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----/, 'a private key'],
];

// Every version of the helper is far longer than this and carries these two names. A block that was cut short
// ("... rest of the helper unchanged ...") or emptied fails both tests.
const HELPER_MIN_LENGTH = 6000;
const squeeze = (text) => text.replace(/\s+/g, '');

/** The helper blocks in a text. `whole` is false for one that was cut short, emptied, or is only a mention of the markers. */
function helperBlocks(text) {
  const blocks = [];
  for (let from = 0; ;) {
    const first = text.indexOf(HELPER_MARKER, from);
    if (first < 0) return blocks;
    const close = text.indexOf(HELPER_END_MARKER, first);
    // The block starts at the last start marker before the end marker, so a comment that names the marker is not part of it.
    const start = close < 0 ? first : text.lastIndexOf(HELPER_MARKER, close);
    const end = close < 0 ? text.length : close + HELPER_END_MARKER.length;
    const body = text.slice(start, end);
    blocks.push({ start, end, body, whole: close >= 0 && body.length >= HELPER_MIN_LENGTH && body.includes('window.PFAI') && body.includes('pfCapstone') });
    from = end;
  }
}

/** The text of a file with the Product Faculty helper removed, so its own code is never judged as the learner's. */
function withoutHelper(text) {
  // Only a complete helper is set aside. Anything else between the markers is judged like the rest of the page.
  let out = ''; let at = 0;
  for (const block of helperBlocks(text)) { if (!block.whole) continue; out += text.slice(at, block.start); at = block.end; }
  return out + text.slice(at);
}

function externalLoads(path, text) {
  const found = new Set();
  const add = (url) => { try { found.add(new URL(url.startsWith('//') ? `https:${url}` : url).host); } catch { found.add(url.slice(0, 60)); } };
  const type = extension(path);
  if (type === 'html' || type === 'htm' || type === 'svg') {
    const tags = /<(script|link|img|source|audio|video|iframe|embed|object|track|image|use)\b[^>]*>/gi;
    for (const tag of text.match(tags) ?? []) {
      // A plain link the visitor may click is fine; a stylesheet, font, icon or preload is a load.
      if (/^<link\b/i.test(tag) && !/\brel\s*=\s*["']?[^"'>]*(stylesheet|icon|preload|modulepreload|prefetch|manifest|font)/i.test(tag)) continue;
      for (const match of tag.matchAll(/\b(?:src|href|data|poster|xlink:href)\s*=\s*["']?\s*((?:https?:)?\/\/[^"'\s>]+)/gi)) add(match[1]);
    }
  }
  for (const match of text.matchAll(/@import\s+(?:url\()?\s*["']?\s*((?:https?:)?\/\/[^"')\s;]+)/gi)) add(match[1]);
  for (const match of text.matchAll(/url\(\s*["']?\s*((?:https?:)?\/\/[^"')\s]+)/gi)) add(match[1]);
  for (const match of text.matchAll(/\b(?:fetch|importScripts|import)\s*\(\s*["'`]\s*(https?:\/\/[^"'`\s)]+)/gi)) add(match[1]);
  for (const match of text.matchAll(/\bfrom\s+["'](https?:\/\/[^"'\s]+)["']/gi)) add(match[1]);
  for (const match of text.matchAll(/new\s+(?:WebSocket|EventSource)\s*\(\s*["'`]\s*((?:wss?|https?):\/\/[^"'`\s)]+)/gi)) add(match[1].replace(/^ws/, 'http'));
  return [...found];
}

function problem(code, message, fix) { return { code, message, fix: fix ?? message }; }

/**
 * Checks one uploaded file against the prototype rules.
 * Returns { ok, files: [{ path, data, contentType }], title, contract, fixes, notes, problems, stats }.
 * `fixes` are harmless differences that were corrected; `problems` stop the upload.
 * `helper` is optional: the helper as it must appear (starter/pf-ai.js). When given, an edited helper is a problem.
 */
export function checkArtifact({ filename = '', bytes, helper: expectedHelper = '' }) {
  const buffer = asBuffer(bytes);
  const fixes = []; const notes = []; const problems = [];
  const fail = () => ({ ok: false, files: [], title: '', contract: CONTRACT_VERSION, fixes, notes, problems, stats: { files: 0, bytes: 0 } });
  if (!buffer.length) { problems.push(problem('empty', 'The file is empty.', 'Give me the finished prototype.zip again; the file I received was empty.')); return fail(); }
  if (buffer.length > LIMITS.uploadBytes) {
    problems.push(problem('too-large', `The file is ${megabytes(buffer.length)}. A prototype may be at most ${megabytes(LIMITS.uploadBytes)}.`, `Make prototype.zip smaller than ${megabytes(LIMITS.uploadBytes)}: shrink large images and leave out anything the page does not use.`));
    return fail();
  }

  let entries;
  const isZip = buffer.length >= 4 && buffer[0] === 0x50 && buffer[1] === 0x4b && (buffer[2] === 3 || buffer[2] === 5);
  if (isZip) {
    try { entries = readZip(buffer); }
    catch (error) {
      if (!(error instanceof ZipProblem)) throw error;
      problems.push(problem(error.code, error.message, `${error.message} Make a new, ordinary prototype.zip with index.html at the top level.`));
      return fail();
    }
  } else {
    const head = buffer.subarray(0, 2000).toString('utf8').replace(/^﻿/, '').trimStart().toLowerCase();
    const looksHtml = /^(<!doctype html|<html|<head|<body|<!--)/.test(head) || /\.html?$/i.test(filename);
    if (!looksHtml || buffer.includes(0)) {
      problems.push(problem('unsupported-file', 'This is not a prototype file. Upload the prototype.zip your coding agent made, or a single HTML file.', 'I need the prototype as prototype.zip with index.html at the top level (see HOSTING-CONTRACT.md).'));
      return fail();
    }
    entries = [{ name: 'index.html', data: buffer }];
    if (!/^index\.html?$/i.test(basename(filename))) fixes.push('A single HTML file was uploaded; it was used as index.html.');
  }

  // Names first: nothing is kept under a name that could land outside its own folder.
  let kept = [];
  for (const entry of entries) {
    const name = entry.name.replace(/\\/g, '/').replace(/^(\.\/)+/, '');
    const segments = name.split('/');
    if (name.startsWith('/') || /^[a-zA-Z]:/.test(name) || segments.includes('..') || segments.some((part) => !part) || /[\u0000-\u001f\u007f]/.test(name)) {
      problems.push(problem('unsafe-path', `The ZIP contains a file with an unsafe name (${entry.name.slice(0, 80)}).`, 'Rebuild prototype.zip so every file sits inside it with a simple relative name, for example index.html and assets/logo.png.'));
      continue;
    }
    if (segments.some((part) => part === '__MACOSX' || part === 'node_modules' || (part.startsWith('.') && part !== '.well-known')) || /^(thumbs\.db|desktop\.ini)$/i.test(basename(name))) continue;
    kept.push({ path: name, data: entry.data });
  }
  if (problems.length) return fail();
  if (kept.length < entries.length) fixes.push('Hidden and system files were left out.');

  // Where the page really starts: the top level, one wrapping folder, or a build folder.
  const hasIndex = (list, prefix = '') => list.some((file) => file.path.toLowerCase() === `${prefix}index.html` || file.path.toLowerCase() === `${prefix}index.htm`);
  if (!hasIndex(kept)) {
    const tops = new Set(kept.map((file) => file.path.split('/')[0]));
    const only = tops.size === 1 && kept.every((file) => file.path.includes('/')) ? [...tops][0] : null;
    const candidates = [only, ...BUILD_FOLDERS, ...(only ? BUILD_FOLDERS.map((folder) => `${only}/${folder}`) : [])].filter(Boolean);
    const root = candidates.find((folder) => hasIndex(kept, `${folder.toLowerCase()}/`));
    if (root) {
      const prefix = `${root}/`;
      kept = kept.filter((file) => file.path.toLowerCase().startsWith(prefix.toLowerCase())).map((file) => ({ ...file, path: file.path.slice(prefix.length) }));
      fixes.push(`The page was inside the folder “${root}”; that folder was opened and used as the top level.`);
    }
  }
  const entryFile = kept.find((file) => /^index\.html?$/i.test(file.path));
  if (!entryFile) {
    const serverLike = kept.some((file) => SERVER_FILES.test(file.path) || UNBUILT_FILES.test(file.path));
    problems.push(serverLike
      ? problem('needs-server', 'This looks like a project that needs a server or a build step. The upload takes a finished web page: one index.html, with anything else it needs beside it.', 'The LMS hosts static files only. Produce the static version described in HOSTING-CONTRACT.md: one self-contained index.html (plus an assets folder if needed), packed as prototype.zip.')
      : problem('no-index', 'There is no index.html at the top level of the file.', 'Put the page in a file named index.html at the top level of prototype.zip.'));
    return fail();
  }
  if (entryFile.path !== 'index.html') { fixes.push(`${entryFile.path} was renamed to index.html.`); entryFile.path = 'index.html'; }

  // What is left beside the page.
  const files = []; let total = 0; const seen = new Set(); const unbuilt = [];
  for (const file of kept) {
    const type = extension(file.path);
    if (DEV_FILES.test(basename(file.path))) { if (basename(file.path).toLowerCase() !== 'check-upload.mjs') notes.push(`${file.path} is not part of the page and was left out.`); continue; }
    if (file.path === 'capstone.json') { files.push({ ...file, contentType: CONTENT_TYPES.json }); continue; }
    if (SERVER_FILES.test(file.path)) {
      problems.push(problem('needs-server', `${file.path} is source code that a browser cannot run. The upload takes a finished web page.`, `Remove ${file.path}. The prototype must run from index.html in a browser with no server and no build step (see HOSTING-CONTRACT.md).`));
      continue;
    }
    if (UNBUILT_FILES.test(file.path)) { unbuilt.push(file.path); continue; }
    if (!CONTENT_TYPES[type]) {
      problems.push(problem('unsupported-type', `${file.path}: this type of file is not supported.`, `Remove ${file.path} or turn it into one of: ${Object.keys(CONTENT_TYPES).filter((key) => key !== 'htm' && key !== 'map').join(', ')}.`));
      continue;
    }
    if (file.path.length > LIMITS.pathLength) { problems.push(problem('unsafe-path', `A file name is too long (${file.path.slice(0, 60)}…).`, 'Use shorter file and folder names.')); continue; }
    const key = file.path.toLowerCase();
    if (seen.has(key)) { problems.push(problem('duplicate', `Two files are named ${file.path}.`, `Keep one file named ${file.path}.`)); continue; }
    seen.add(key);
    total += file.data.length;
    files.push({ ...file, contentType: CONTENT_TYPES[type] });
  }
  if (files.length > LIMITS.files) problems.push(problem('too-many-files', `The prototype holds ${files.length} files. The most allowed is ${LIMITS.files}.`, `Use fewer files (at most ${LIMITS.files}); put scripts and styles inside index.html.`));
  if (total > LIMITS.expandedBytes) problems.push(problem('too-large', `The files add up to ${megabytes(total)}. The most allowed is ${megabytes(LIMITS.expandedBytes)}.`, `Make the files smaller than ${megabytes(LIMITS.expandedBytes)} in total.`));

  // The page itself.
  const page = entryFile.data.toString('utf8');
  if (page.includes('�') && !entryFile.data.subarray(0, 4000).toString('latin1').toLowerCase().includes('<')) {
    problems.push(problem('bad-index', 'index.html is not a readable web page.', 'Save index.html as a UTF-8 text file containing the page.'));
  } else if (page.trim().length < 80 || !/<(html|body|div|main|script|section|h1)\b/i.test(page)) {
    problems.push(problem('bad-index', 'index.html is almost empty, so there is no page to show.', 'index.html must contain the whole working prototype page.'));
  }
  const needsBuild = /<script\b[^>]*\bsrc\s*=\s*["']?[^"'>\s]*\.(tsx?|jsx)\b/i.test(page) || /<script\b[^>]*\bsrc\s*=\s*["']\/?src\//i.test(page);
  if (needsBuild) {
    problems.push(problem('needs-build', 'index.html loads source files that need a build step before a browser can run them.', 'Build the project and give me the finished static output: one index.html that runs by itself in a browser (see HOSTING-CONTRACT.md).'));
  } else if (unbuilt.length) {
    // Source files beside a page that does not use them are just left out.
    notes.push(`${unbuilt.slice(0, 3).join(', ')}${unbuilt.length > 3 ? ' and others' : ''} ${unbuilt.length === 1 ? 'is' : 'are'} source code the page does not load, and ${unbuilt.length === 1 ? 'was' : 'were'} left out.`);
  }

  let helper = false; let cutHelper = false; let editedHelper = false; let asksAi = false; let saysSample = false;
  const outside = new Map(); let storage = false;
  const expected = squeeze(helperBlocks(String(expectedHelper || '')).find((block) => block.whole)?.body ?? '');
  for (const file of files) {
    const type = extension(file.path);
    if (!TEXT_TYPES.has(type)) continue;
    const text = file.data.toString('utf8');
    const blocks = helperBlocks(text);
    if (blocks.some((block) => block.whole)) helper = true; else if (blocks.length) cutHelper = true;
    if (expected && blocks.some((block) => block.whole && squeeze(block.body) !== expected)) editedHelper = true;
    const own = withoutHelper(text);
    if (/sample|demo|example/i.test(own)) saysSample = true;
    // One finding per file is enough: the same key often matches more than one pattern.
    const secret = SECRETS.find(([pattern]) => pattern.test(own));
    if (secret) problems.push(problem('secret', `${file.path} contains what looks like ${secret[1]}. A published prototype must never contain a key.`, `Remove the key from ${file.path}. Never put a key in the prototype: visitors connect their own key through the Product Faculty helper (PFAI).`));
    if (!CODE_TYPES.has(type)) continue;
    if (AI_HOSTS.test(own)) {
      problems.push(problem('direct-ai', `${file.path} calls an AI service directly. On the hosted page that call is blocked.`, `In ${file.path}, replace the direct AI service call with PFAI.generate(...) from the Product Faculty helper (starter/pf-ai.js, see BUILD-INSTRUCTIONS.md).`));
    }
    // An AI service called directly is reported once, above, not again as an outside website.
    for (const host of externalLoads(file.path, own)) if (!AI_HOSTS.test(host)) outside.set(host, file.path);
    if (/\bPFAI\s*\.\s*generate\s*\(/.test(own)) asksAi = true;
    if (/\b(localStorage|sessionStorage|indexedDB)\b|document\.cookie/.test(own)) storage = true;
  }
  if (outside.size) {
    const hosts = [...outside.keys()].slice(0, 6).join(', ');
    problems.push(problem('external', `The page loads files from other websites (${hosts}). The hosted page can only use files inside the upload.`, `Do not load anything from other websites (${hosts}). Copy those libraries, fonts and images into index.html or the assets folder and reference them with relative paths.`));
  }
  if (!helper) {
    // What is left of a cut-short helper still names the AI service. That is the helper's own code, not a direct call.
    if (cutHelper) for (let index = problems.length - 1; index >= 0; index -= 1) if (problems[index].code === 'direct-ai') problems.splice(index, 1);
    problems.push(cutHelper
      ? problem('broken-helper', 'The Product Faculty connection helper in this file is incomplete, so the hosted page could not run AI for a visitor.', 'The Product Faculty helper (the block between PFAI-HELPER-START and PFAI-HELPER-END) is incomplete. Replace it with the whole of starter/pf-ai.js from the build kit, unchanged and not shortened.')
      : problem('missing-helper', 'The Product Faculty connection helper is missing, so the hosted page could not run AI for a visitor.', 'Include the Product Faculty helper from starter/pf-ai.js unchanged (inline in index.html, or as assets/pf-ai.js loaded before your own script) and make every AI call through PFAI.generate(...).'));
  } else if (editedHelper) {
    problems.push(problem('changed-helper', 'The Product Faculty connection helper in this file is not the one from this build kit.', 'Put the Product Faculty helper back exactly as it is in starter/pf-ai.js. Do not edit, shorten or reformat the block between PFAI-HELPER-START and PFAI-HELPER-END; your own code goes outside it.'));
  } else {
    if (!asksAi) notes.push('This page never asks the AI for anything (there is no PFAI.generate call), so visitors will only ever see samples. If that is not what you meant, ask your coding agent to make its AI calls through PFAI.generate.');
    if (!saysSample) notes.push('Nothing on this page says when a result is a sample. Visitors without a key should be told clearly; ask your coding agent to label sample mode.');
  }
  if (storage) notes.push('The page uses browser storage. On the hosted page nothing is kept after the visitor leaves; the helper keeps it in memory for the visit.');

  // capstone.json: which version of the rules this file was made for.
  let title = (page.match(/<title[^>]*>([^<]{1,160})<\/title>/i)?.[1] ?? '').replace(/\s+/g, ' ').trim();
  const manifestFile = files.find((file) => file.path === 'capstone.json');
  let manifest = {};
  if (manifestFile) {
    try { manifest = JSON.parse(manifestFile.data.toString('utf8')); if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) throw new Error('shape'); }
    catch { manifest = {}; fixes.push('capstone.json could not be read; it was replaced with a standard one.'); }
    const version = Number(manifest.contract ?? CONTRACT_VERSION);
    if (version !== CONTRACT_VERSION) {
      problems.push(problem('unsupported-contract', `capstone.json says this prototype was made for version ${String(manifest.contract).slice(0, 12)} of the upload rules. This LMS accepts version ${CONTRACT_VERSION}.`, `Set "contract": ${CONTRACT_VERSION} in capstone.json and follow HOSTING-CONTRACT.md from the build kit.`));
    }
    if (typeof manifest.title === 'string' && manifest.title.trim()) title = manifest.title.replace(/\s+/g, ' ').trim().slice(0, 160);
  } else {
    fixes.push('capstone.json was missing; a standard one was added.');
  }
  const normalized = { contract: CONTRACT_VERSION, title: title || 'Capstone prototype', ...(typeof manifest.kit === 'string' ? { kit: manifest.kit.slice(0, 80) } : {}) };
  const output = files.filter((file) => file.path !== 'capstone.json');
  output.push({ path: 'capstone.json', data: Buffer.from(JSON.stringify(normalized, null, 2)), contentType: CONTENT_TYPES.json });
  output.sort((a, b) => (a.path === 'index.html' ? -1 : b.path === 'index.html' ? 1 : a.path.localeCompare(b.path)));

  // One problem per kind is enough to act on.
  const unique = []; const kinds = new Set();
  for (const item of problems) { const key = `${item.code}:${item.message}`; if (!kinds.has(key)) { kinds.add(key); unique.push(item); } }
  return {
    ok: unique.length === 0,
    files: unique.length ? [] : output,
    title: normalized.title,
    contract: CONTRACT_VERSION,
    fixes, notes,
    problems: unique,
    stats: { files: output.length, bytes: output.reduce((sum, file) => sum + file.data.length, 0) },
  };
}

/** What a learner pastes to their coding agent when an upload is refused. */
export function fixRequest(problems) {
  return [
    'The Product Faculty LMS did not accept the prototype file. Please fix the following and give me a new prototype.zip.',
    '',
    ...problems.map((item, index) => `${index + 1}. ${item.fix}`),
    '',
    'Keep everything else working as it is. Before you hand the file back, run "node starter/check-upload.mjs prototype.zip" from the build kit if you can run commands, and fix anything it reports. If you cannot run commands, follow HOSTING-CONTRACT.md exactly.',
  ].join('\n');
}

// ---------------------------------------------------------------- command line

async function main() {
  const { readFile } = await import('node:fs/promises');
  const target = process.argv[2];
  if (!target) { console.error('Usage: node check-upload.mjs prototype.zip'); process.exit(2); }
  let bytes;
  try { bytes = await readFile(target); } catch { console.error(`Could not read ${target}.`); process.exit(2); }
  // In the build kit the helper sits beside this file, so an edited helper is caught before the learner uploads.
  let helper = '';
  try { helper = await readFile(new URL('./pf-ai.js', import.meta.url), 'utf8'); } catch { helper = ''; }
  const result = checkArtifact({ filename: target, bytes, helper });
  for (const line of result.fixes) console.log(`fixed on upload: ${line}`);
  for (const line of result.notes) console.log(`note: ${line}`);
  if (result.ok) {
    console.log(`PASS: ${target} is ready to upload in the LMS (${result.stats.files} files, ${megabytes(result.stats.bytes)}). Title: ${result.title}`);
    return;
  }
  console.log(`NOT READY: fix the following in ${target} before you hand it back.`);
  result.problems.forEach((item, index) => console.log(`${index + 1}. ${item.message}\n   Fix: ${item.fix}`));
  process.exit(1);
}

// Runs only when this file is the command itself, never when the LMS imports it. Both paths are followed to
// the real file first: from a folder reached through a link (/tmp on a Mac) they would otherwise never match,
// and the command would print nothing.
const { fileURLToPath } = await import('node:url');
const { realpathSync } = await import('node:fs');
const real = (path) => { try { return realpathSync(path); } catch { return path; } };
if (process.argv[1] && real(process.argv[1]) === real(fileURLToPath(import.meta.url))) await main();
