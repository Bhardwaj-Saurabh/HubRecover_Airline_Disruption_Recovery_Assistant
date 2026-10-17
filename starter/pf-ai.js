/* PFAI-HELPER-START v1. Product Faculty connection helper. Include this block unchanged. */
(function () {
  'use strict';
  if (window.PFAI && window.PFAI.version) return;
var PF_CORE = (function () {
  'use strict';
  // One request shape for every prototype. The hosted page and the helper inside a prototype both use this code,
  // so what works in a coding agent's preview works the same way once it is hosted.
  var DEFAULTS = { provider: 'anthropic', endpoint: 'https://api.anthropic.com', model: 'claude-opus-5-5', effort: 'low', maxTokens: 16000, timeoutMs: 120000 };
  var LIMITS = { files: 8, fileChars: 8 * 1024 * 1024, totalChars: 14 * 1024 * 1024, messages: 40, textChars: 200000, systemChars: 40000 };
  var IMAGE = /^image\/(png|jpeg|gif|webp)$/;
  var TEXTUAL = /^(text\/[\w.+-]+|application\/(json|xml|csv))$/;
  var WORDS = {
    'not-connected': 'AI is not connected. Connect a key to run this for real.',
    'unsupported-key': 'This page works with a Claude API key (it starts with sk-ant-). Keys from other services are not supported yet.',
    'invalid-key': 'That key was not accepted. Check it and connect again.',
    'no-access': 'This key is not allowed to use the AI model this page needs.',
    'no-credit': 'This key has no credit left. Add credit to the account, or connect a different key.',
    'rate-limited': 'Too many requests for this key right now. Wait a moment and try again.',
    'overloaded': 'The AI service is busy. Try again in a moment.',
    'too-large': 'That is too much to send in one go. Use a smaller file or less text.',
    'unsupported-file': 'The AI cannot read that kind of file. Use a PNG, JPEG, GIF or WebP picture, a PDF, or a text file.',
    'refused': 'The AI declined this request.',
    'too-long': 'The answer was cut off before it finished. Ask for something shorter.',
    'timeout': 'The AI took too long to answer. Try again.',
    'network': 'The AI service could not be reached. Check your connection and try again.',
    'bad-request': 'The AI service did not accept this request.',
    'bad-reply': 'The AI answered in a form this page could not use. Try again.',
    'busy': 'Still working on the previous request. Wait for it to finish.',
    'unavailable': 'The AI service had a problem. Try again in a moment.'
  };

  function fail(code, detail) {
    var error = new Error(WORDS[code] || WORDS['bad-request']);
    error.name = 'PFAIError'; error.code = code;
    if (detail) error.detail = String(detail).slice(0, 500);
    return error;
  }
  function describe(error) {
    if (error && error.name === 'PFAIError') return { code: error.code, message: error.message, detail: error.detail || '' };
    return { code: 'unavailable', message: WORDS.unavailable, detail: error && error.message ? String(error.message).slice(0, 300) : '' };
  }
  function revive(shape) { var error = fail(shape && shape.code); if (shape && shape.message) error.message = shape.message; if (shape && shape.detail) error.detail = shape.detail; return error; }

  function keyKind(key) {
    var value = String(key || '').trim();
    if (/^sk-ant-[\w-]{10,}$/.test(value)) return 'anthropic';
    return value ? 'other' : 'empty';
  }

  /** A request as a prototype may send it, checked and tidied. Throws a PFAIError for anything else. */
  function normalize(input) {
    if (!input || typeof input !== 'object' || Array.isArray(input)) throw fail('bad-request', 'The request must be an object.');
    var messages = [];
    if (Array.isArray(input.messages)) {
      if (input.messages.length > LIMITS.messages) throw fail('too-large', 'Too many messages.');
      input.messages.forEach(function (item) {
        if (!item || (item.role !== 'user' && item.role !== 'assistant') || typeof item.content !== 'string') throw fail('bad-request', 'Each message needs a role of user or assistant and text content.');
        if (item.content.length > LIMITS.textChars) throw fail('too-large', 'A message is too long.');
        messages.push({ role: item.role, content: item.content });
      });
    }
    if (typeof input.prompt === 'string' && input.prompt.trim()) {
      if (input.prompt.length > LIMITS.textChars) throw fail('too-large', 'The prompt is too long.');
      messages.push({ role: 'user', content: input.prompt });
    }
    if (!messages.length || messages[0].role !== 'user' || messages[messages.length - 1].role !== 'user') throw fail('bad-request', 'Send a prompt, or messages that start and end with the user.');
    var system = typeof input.system === 'string' ? input.system : '';
    if (system.length > LIMITS.systemChars) throw fail('too-large', 'The instructions are too long.');
    var files = []; var total = 0;
    (Array.isArray(input.files) ? input.files : []).forEach(function (file) {
      if (!file || typeof file.data !== 'string' || typeof file.type !== 'string') throw fail('bad-request', 'Each file needs a type and base64 data.');
      var type = file.type.toLowerCase().split(';')[0].trim();
      if (type === 'image/jpg') type = 'image/jpeg';
      if (!IMAGE.test(type) && type !== 'application/pdf' && !TEXTUAL.test(type)) throw fail('unsupported-file', type);
      var data = file.data.replace(/^data:[^,]*,/, '').replace(/\s+/g, '');
      if (!/^[A-Za-z0-9+/]*={0,2}$/.test(data.slice(0, 2000)) || !data.length) throw fail('bad-request', 'A file is not valid base64.');
      if (data.length > LIMITS.fileChars) throw fail('too-large', 'A file is too large.');
      total += data.length;
      files.push({ name: String(file.name || 'file').slice(0, 120), type: type, data: data });
    });
    if (files.length > LIMITS.files) throw fail('too-large', 'Too many files.');
    if (total > LIMITS.totalChars) throw fail('too-large', 'The files are too large together.');
    var schema = input.schema && typeof input.schema === 'object' && !Array.isArray(input.schema) ? input.schema : null;
    if (schema && JSON.stringify(schema).length > 20000) throw fail('too-large', 'The schema is too large.');
    var maxTokens = Number(input.maxTokens);
    return { system: system, messages: messages, files: files, json: input.json === true || Boolean(schema), schema: schema, maxTokens: maxTokens > 0 && isFinite(maxTokens) ? Math.floor(maxTokens) : 0 };
  }

  function decodeText(base64) {
    var binary = atob(base64); var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return new TextDecoder('utf-8').decode(bytes);
  }

  function anthropicBody(config, request, options) {
    var parts = request.files.map(function (file) {
      if (file.type === 'application/pdf') return { type: 'document', source: { type: 'base64', media_type: 'application/pdf', data: file.data } };
      if (IMAGE.test(file.type)) return { type: 'image', source: { type: 'base64', media_type: file.type, data: file.data } };
      return { type: 'text', text: 'File: ' + file.name + '\n\n' + decodeText(file.data).slice(0, LIMITS.textChars) };
    });
    var last = request.messages.length - 1;
    var messages = request.messages.map(function (item, index) {
      // Files go before the words that refer to them, in the latest user turn.
      if (index === last && parts.length) return { role: 'user', content: parts.concat([{ type: 'text', text: item.content }]) };
      return { role: item.role, content: item.content };
    });
    var system = request.system;
    if (request.json && !request.schema) system = (system ? system + '\n\n' : '') + 'Reply with one valid JSON value only. No code fences and no commentary.';
    var body = { model: config.model, max_tokens: Math.min(request.maxTokens || config.maxTokens, config.maxTokens), messages: messages };
    if (system) body.system = system;
    var output = {};
    if (config.effort && options.effort) output.effort = config.effort;
    if (request.schema) output.format = { type: 'json_schema', schema: request.schema };
    if (Object.keys(output).length) body.output_config = output;
    if (options.fallbacks) body.fallbacks = 'default';
    return body;
  }

  async function send(config, key, path, method, body, beta) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, config.timeoutMs);
    var headers = { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'anthropic-dangerous-direct-browser-access': 'true' };
    if (body) headers['content-type'] = 'application/json';
    if (beta) headers['anthropic-beta'] = beta;
    var response;
    try {
      response = await fetch(config.endpoint.replace(/\/+$/, '') + path, { method: method, headers: headers, body: body ? JSON.stringify(body) : undefined, signal: controller.signal, credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer' });
    } catch (cause) {
      throw fail(controller.signal.aborted ? 'timeout' : 'network', cause && cause.message);
    } finally { clearTimeout(timer); }
    var data = null; var text = '';
    try { text = await response.text(); data = text ? JSON.parse(text) : null; } catch (ignore) { data = null; }
    if (response.ok && data) return data;
    var message = (data && data.error && data.error.message) || text.slice(0, 300) || ('HTTP ' + response.status);
    var kind = (data && data.error && data.error.type) || '';
    if (response.status === 401 || kind === 'authentication_error') throw fail('invalid-key', message);
    if (/credit balance|billing/i.test(message)) throw fail('no-credit', message);
    if (response.status === 403 || kind === 'permission_error') throw fail('no-access', message);
    if (response.status === 404 && /model/i.test(message)) throw fail('no-access', message);
    if (response.status === 413 || kind === 'request_too_large') throw fail('too-large', message);
    if (response.status === 429 || kind === 'rate_limit_error') throw fail('rate-limited', message);
    if (response.status === 529 || kind === 'overloaded_error') throw fail('overloaded', message);
    if (response.status >= 500) throw fail('unavailable', message);
    throw fail('bad-request', message);
  }

  /** Confirms the key is real without spending anything. */
  async function checkKey(config, key) {
    var kind = keyKind(key);
    if (kind === 'empty') throw fail('not-connected');
    if (kind !== 'anthropic') throw fail('unsupported-key');
    await send(config, String(key).trim(), '/v1/models?limit=1', 'GET', null, '');
    return { provider: 'anthropic' };
  }

  async function generate(config, key, input) {
    if (!key) throw fail('not-connected');
    var request = normalize(input);
    var options = { effort: true, fallbacks: true };
    var data;
    for (var attempt = 0; attempt < 3; attempt += 1) {
      try {
        data = await send(config, String(key).trim(), '/v1/messages', 'POST', anthropicBody(config, request, options), options.fallbacks ? 'server-side-fallback-2026-07-01' : '');
        break;
      } catch (error) {
        // An optional extra the account or model does not take must never be the reason a prototype cannot run.
        var detail = (error && error.detail) || '';
        if (error.code === 'bad-request' && options.fallbacks && /fallback|anthropic-beta|beta header|unexpected.*beta/i.test(detail)) { options.fallbacks = false; continue; }
        if (error.code === 'bad-request' && options.effort && /effort|output_config/i.test(detail) && !/format|schema/i.test(detail)) { options.effort = false; continue; }
        throw error;
      }
    }
    if (!data) throw fail('bad-request', 'No response.');
    if (data.stop_reason === 'refusal') throw fail('refused', data.stop_details && data.stop_details.explanation);
    var text = (Array.isArray(data.content) ? data.content : []).filter(function (block) { return block && block.type === 'text' && typeof block.text === 'string'; }).map(function (block) { return block.text; }).join('');
    if (!text.trim()) throw fail(data.stop_reason === 'max_tokens' ? 'too-long' : 'unavailable', 'The reply had no text.');
    return { text: text, truncated: data.stop_reason === 'max_tokens' };
  }

  /** The JSON value in a reply, tolerant of code fences and a sentence around it. Throws when there is none. */
  function parseJson(text) {
    var source = String(text || '').trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
    try { return JSON.parse(source); } catch (ignore) { /* look inside */ }
    var open = source.search(/[[{]/);
    var close = Math.max(source.lastIndexOf('}'), source.lastIndexOf(']'));
    if (open >= 0 && close > open) { try { return JSON.parse(source.slice(open, close + 1)); } catch (ignore2) { /* fall through */ } }
    throw fail('bad-reply', 'The AI did not reply with JSON.');
  }

  return { DEFAULTS: DEFAULTS, LIMITS: LIMITS, WORDS: WORDS, fail: fail, describe: describe, revive: revive, keyKind: keyKind, normalize: normalize, checkKey: checkKey, generate: generate, parseJson: parseJson };
})();
  // --- Browser storage is not available on the hosted page. Keep it in memory for the visit instead of crashing.
  function memoryStore() {
    var items = {};
    return {
      getItem: function (key) { return Object.prototype.hasOwnProperty.call(items, key) ? items[key] : null; },
      setItem: function (key, value) { items[key] = String(value); },
      removeItem: function (key) { delete items[key]; },
      clear: function () { items = {}; },
      key: function (index) { var keys = Object.keys(items); return index < keys.length ? keys[index] : null; },
      get length() { return Object.keys(items).length; }
    };
  }
  ['localStorage', 'sessionStorage'].forEach(function (name) {
    try { var store = window[name]; store.setItem('__pfai', '1'); store.removeItem('__pfai'); }
    catch (blocked) { try { Object.defineProperty(window, name, { value: memoryStore(), configurable: true }); } catch (ignore) { /* nothing more to do */ } }
  });

  var state = { mode: 'starting', connected: false, provider: null };
  var listeners = [];
  var key = '';            // standalone preview only; never written anywhere
  var port = null;         // hosted page only
  var bar = null;          // standalone preview only. Declared before anything can paint it, so there is only ever one.
  var room = null;         // empty space at the end of the page, as tall as the bar, so the bar never covers content
  var waiting = {};
  var counter = 0;
  var config = PF_CORE.DEFAULTS;

  function announce() {
    var snapshot = { mode: state.mode, connected: state.connected, provider: state.provider };
    listeners.slice().forEach(function (listener) { try { listener(snapshot); } catch (ignore) { /* a listener must not break the helper */ } });
    paintBar();
  }

  // --- Hosted: the Product Faculty page around the prototype holds the visitor's key and makes the call.
  function ask(type, payload) {
    return new Promise(function (resolve, reject) {
      counter += 1; var id = 'r' + counter;
      waiting[id] = { resolve: resolve, reject: reject };
      // The page around the prototype always answers. Should it ever not, the request ends instead of hanging.
      setTimeout(function () { if (waiting[id]) { delete waiting[id]; reject(PF_CORE.fail('timeout')); } }, type === 'generate' ? config.timeoutMs + 20000 : 15000);
      port.postMessage({ id: id, type: type, request: payload });
    });
  }
  function onPortMessage(event) {
    var message = event.data || {};
    if (message.type === 'state') { state.connected = message.connected === true; state.provider = message.provider || null; announce(); return; }
    var pending = message.id && waiting[message.id];
    if (!pending) return;
    delete waiting[message.id];
    if (message.ok) pending.resolve(message.result); else pending.reject(PF_CORE.revive(message.error));
  }
  var ready = new Promise(function (resolve) {
    var settled = false;
    function settle(mode) {
      if (settled) return; settled = true;
      state.mode = mode; announce(); resolve({ mode: mode, connected: state.connected });
    }
    if (window.parent === window) { settle('standalone'); return; }
    window.addEventListener('message', function (event) {
      var data = event.data;
      if (settled || event.source !== window.parent || !data || data.pfCapstone !== 1 || data.type !== 'welcome' || !event.ports || !event.ports[0]) return;
      port = event.ports[0]; port.onmessage = onPortMessage;
      state.connected = data.connected === true; state.provider = data.provider || null;
      settle('hosted');
    });
    try { window.parent.postMessage({ pfCapstone: 1, type: 'hello', version: 1 }, '*'); } catch (ignore) { /* not hosted */ }
    setTimeout(function () { settle('standalone'); }, 1500);
  });

  // --- Standalone preview: a small bar where the person trying the prototype connects their own key for this tab.
  function paintBar() {
    if (state.mode !== 'standalone' || !document.body) return;
    if (!bar) {
      bar = document.createElement('div');
      bar.setAttribute('data-pfai-bar', '');
      bar.style.cssText = 'position:fixed;left:12px;right:12px;bottom:12px;z-index:2147483000;display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 14px;border-radius:12px;background:#080739;color:#fff;font:14px/20px system-ui,sans-serif;box-shadow:0 6px 24px rgba(8,7,57,.28)';
      document.body.appendChild(bar);
      room = document.createElement('div');
      room.setAttribute('data-pfai-room', ''); room.setAttribute('aria-hidden', 'true');
      room.style.cssText = 'flex:none;width:100%;pointer-events:none';
      document.body.appendChild(room);
      // The bar grows when the window narrows and when a message appears in it. The room follows the bar itself.
      if (typeof ResizeObserver === 'function') new ResizeObserver(makeRoom).observe(bar);
      window.addEventListener('resize', makeRoom);
    }
    bar.textContent = '';
    var label = document.createElement('span'); label.style.cssText = 'flex:1 1 220px;min-width:0';
    var button = function (text, action) { var b = document.createElement('button'); b.type = 'button'; b.textContent = text; b.style.cssText = 'font:inherit;font-weight:600;padding:6px 14px;border-radius:999px;border:1px solid #FFAC40;background:#FFAC40;color:#080739;cursor:pointer'; b.addEventListener('click', action); return b; };
    if (state.connected) {
      label.textContent = 'AI connected for this tab. The key is kept in memory only.';
      bar.appendChild(label);
      bar.appendChild(button('Disconnect', function () { key = ''; state.connected = false; state.provider = null; announce(); }));
      makeRoom();
      return;
    }
    label.textContent = 'Sample mode. To run real AI, connect a Claude API key for this tab.';
    var input = document.createElement('input');
    input.type = 'password'; input.placeholder = 'sk-ant-…'; input.autocomplete = 'off'; input.spellcheck = false;
    input.setAttribute('aria-label', 'Claude API key');
    input.style.cssText = 'flex:1 1 200px;min-width:0;font:inherit;padding:6px 10px;border-radius:8px;border:1px solid #c9c9e0;background:#fff;color:#080739';
    var note = document.createElement('span'); note.style.cssText = 'flex:1 1 100%;color:#FFD9A0'; note.setAttribute('role', 'status');
    var go = button('Connect', function () {
      go.disabled = true; note.textContent = 'Checking the key…'; makeRoom();
      PF_CORE.checkKey(config, input.value).then(function (result) {
        key = input.value.trim(); state.connected = true; state.provider = result.provider; announce();
      }).catch(function (error) { go.disabled = false; note.textContent = PF_CORE.describe(error).message; makeRoom(); });
    });
    input.addEventListener('keydown', function (event) { if (event.key === 'Enter') go.click(); });
    bar.appendChild(label); bar.appendChild(input); bar.appendChild(go); bar.appendChild(note);
    makeRoom();
  }
  function makeRoom() { if (bar && room) room.style.height = (bar.offsetHeight + 24) + 'px'; }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', paintBar); else paintBar();

  // Some systems hand over a file with no type; the name's ending says what it is.
  var TYPES = { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', gif: 'image/gif', webp: 'image/webp', pdf: 'application/pdf', txt: 'text/plain', md: 'text/plain', csv: 'text/csv', json: 'application/json' };
  function typeOf(file) {
    if (file.type) return file.type;
    var ending = String(file.name || '').toLowerCase().split('.').pop();
    return TYPES[ending] || 'application/octet-stream';
  }
  function fileToPart(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onerror = function () { reject(PF_CORE.fail('bad-request', 'The file could not be read.')); };
      reader.onload = function () { resolve({ name: file.name || 'file', type: typeOf(file), data: String(reader.result).replace(/^data:[^,]*,/, '') }); };
      reader.readAsDataURL(file);
    });
  }
  /** A data: URL (for example a made-up example kept inside the page, or canvas.toDataURL()) as a file for generate(). */
  function partFromDataUrl(dataUrl, name) {
    // data:[type][;charset=…][;base64],content
    var match = /^data:([^;,]*)((?:;[^;,]*)*),([\s\S]*)$/.exec(String(dataUrl || ''));
    if (!match) throw PF_CORE.fail('bad-request', 'That is not a data: URL.');
    var data = /;base64$/i.test(match[2]) ? match[3] : btoa(unescape(encodeURIComponent(decodeURIComponent(match[3]))));
    return { name: name || 'example', type: match[1] || 'text/plain', data: data };
  }
  /** Plain text as a file for generate(). */
  function partFromText(text, name) {
    return { name: name || 'text.txt', type: 'text/plain', data: btoa(unescape(encodeURIComponent(String(text)))) };
  }

  window.PFAI = {
    version: 1,
    /** Resolves once the helper knows where it is running: { mode: 'hosted' | 'standalone', connected }. */
    ready: ready,
    /** True when a visitor has connected a key and real AI calls will run. Otherwise show your sample mode. */
    connected: function () { return state.connected; },
    /** Calls back at once with the state so far, and again each time it changes: { mode, connected, provider }.
     *  Until PFAI.ready has resolved, connected is false. Use this to switch between sample mode and live. */
    onChange: function (listener) { if (typeof listener === 'function') { listeners.push(listener); listener({ mode: state.mode, connected: state.connected, provider: state.provider }); } },
    /** Opens the place where a visitor connects their key: the bar at the bottom when the page is opened by
     *  itself, the "Connect your AI key" box of the Product Faculty page when hosted. Give the page a button for it. */
    connect: function () { return ready.then(function () { if (state.mode === 'hosted') return ask('connect', null).catch(function () { return null; }); paintBar(); var field = bar && bar.querySelector('input'); if (field) field.focus(); return null; }); },
    /**
     * One AI request. { system?, prompt? | messages?, files?: [{ name, type, data(base64) }], json?: true, schema?, maxTokens? }
     * Resolves to { text, json?, truncated }. Rejects with an error that has .code and a plain .message to show the user.
     */
    generate: function (request) {
      return ready.then(function () {
        var checked = PF_CORE.normalize(request);
        if (!state.connected) throw PF_CORE.fail('not-connected');
        return state.mode === 'hosted' ? ask('generate', checked) : PF_CORE.generate(config, key, checked);
      }).then(function (result) {
        var out = { text: result.text, truncated: result.truncated === true };
        if (request && (request.json === true || request.schema)) out.json = PF_CORE.parseJson(result.text);
        return out;
      });
    },
    /** Turns a File from an <input type="file"> into the { name, type, data } shape generate() takes. */
    fileToPart: fileToPart,
    partFromDataUrl: partFromDataUrl,
    partFromText: partFromText
  };
})();
/* PFAI-HELPER-END */
