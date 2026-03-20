/**
 * fics.js — Browser-side WebSocket client for the FICS terminal.
 *
 * Message protocol (JSON):
 *   Browser → Server:
 *     { type: "connect",    fics_user, fics_pass }
 *     { type: "command",    text }
 *     { type: "disconnect" }
 *
 *   Server → Browser:
 *     { type: "status",  state: "connecting"|"connected"|"disconnected"|"error", msg }
 *     { type: "data",    text }
 *     { type: "error",   msg }
 */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
let ws        = null;
let connected = false;
let cmdHistory = [];
let histIdx   = -1;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const terminal     = () => document.getElementById('fics-terminal');
const cmdInput     = () => document.getElementById('cmd-input');
const sendBtn      = () => document.getElementById('send-btn');
const connectBtn   = () => document.getElementById('connect-btn');
const disconnectBtn= () => document.getElementById('disconnect-btn');
const ficsCredsEl  = () => document.getElementById('fics-creds');
const statusDot    = () => document.getElementById('status-dot');
const statusText   = () => document.getElementById('status-text');

// ── Terminal rendering ────────────────────────────────────────────────────────
function appendText(text) {
  const el = terminal();
  // Convert ANSI-style bold/colour codes FICS sometimes sends; strip the rest
  text = text
    .replace(/\x1b\[[0-9;]*m/g, '')   // strip ANSI colour codes
    .replace(/\x00/g, '');             // strip null bytes

  const span = document.createElement('span');
  span.textContent = text;
  el.appendChild(span);

  // Auto-scroll only if already near the bottom
  const threshold = 60;
  if (el.scrollHeight - el.scrollTop - el.clientHeight < threshold) {
    el.scrollTop = el.scrollHeight;
  }
}

function appendLine(text, cls) {
  const el = terminal();
  const div = document.createElement('div');
  div.className = 'fics-line' + (cls ? ' ' + cls : '');
  div.textContent = text;
  el.appendChild(div);
  el.scrollTop = el.scrollHeight;
}

function clearTerminal() {
  terminal().innerHTML = '';
}

// ── Status UI ─────────────────────────────────────────────────────────────────
function setStatus(state, msg) {
  const dot  = statusDot();
  const text = statusText();
  dot.className  = 'fics-status-dot fics-dot-' + state;
  text.textContent = msg || state;
}

function setConnected(yes) {
  connected = yes;
  cmdInput().disabled  = !yes;
  sendBtn().disabled   = !yes;
  connectBtn().style.display    = yes ? 'none' : '';
  disconnectBtn().style.display = yes ? '' : 'none';
  ficsCredsEl().style.display   = yes ? 'none' : '';
  if (yes) cmdInput().focus();
}

// ── WebSocket ─────────────────────────────────────────────────────────────────
function connect() {
  if (ws) return;

  const user = document.getElementById('fics-user').value.trim() || 'guest';
  const pass = document.getElementById('fics-pass').value;

  clearTerminal();
  setStatus('connecting', 'Connecting…');
  appendLine('Connecting to FICS (' + user + ')…', 'fics-info');

  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(proto + '://' + location.host + '/ws/fics');

  ws.onopen = () => {
    ws.send(JSON.stringify({ type: 'connect', fics_user: user, fics_pass: pass }));
  };

  ws.onmessage = (evt) => {
    let msg;
    try { msg = JSON.parse(evt.data); } catch { return; }

    if (msg.type === 'data') {
      appendText(msg.text);
    } else if (msg.type === 'status') {
      setStatus(msg.state, msg.msg);
      if (msg.state === 'connected') setConnected(true);
      if (msg.state === 'disconnected' || msg.state === 'error') {
        setConnected(false);
        ws = null;
      }
    } else if (msg.type === 'error') {
      appendLine('Error: ' + msg.msg, 'fics-error');
      setStatus('error', msg.msg);
      setConnected(false);
      ws = null;
    }
  };

  ws.onerror = () => {
    appendLine('WebSocket error — check your connection.', 'fics-error');
    setStatus('error', 'WebSocket error');
    setConnected(false);
    ws = null;
  };

  ws.onclose = () => {
    if (connected) {
      appendLine('Connection closed.', 'fics-info');
    }
    setStatus('disconnected', 'Not connected');
    setConnected(false);
    ws = null;
  };
}

function disconnect() {
  if (ws) {
    ws.send(JSON.stringify({ type: 'disconnect' }));
    ws.close();
    ws = null;
  }
  setConnected(false);
  setStatus('disconnected', 'Not connected');
  appendLine('Disconnected.', 'fics-info');
}

// ── Command sending ───────────────────────────────────────────────────────────
function sendCmd() {
  const input = cmdInput();
  const text  = input.value;
  if (!text || !ws || !connected) return;

  // Echo the command locally
  appendLine('fics% ' + text, 'fics-echo');

  ws.send(JSON.stringify({ type: 'command', text }));

  // History
  if (text && (cmdHistory.length === 0 || cmdHistory[0] !== text)) {
    cmdHistory.unshift(text);
    if (cmdHistory.length > 100) cmdHistory.pop();
  }
  histIdx = -1;
  input.value = '';
}

function handleKey(e) {
  if (e.key === 'Enter') {
    sendCmd();
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    if (histIdx < cmdHistory.length - 1) {
      histIdx++;
      cmdInput().value = cmdHistory[histIdx];
    }
  } else if (e.key === 'ArrowDown') {
    e.preventDefault();
    if (histIdx > 0) {
      histIdx--;
      cmdInput().value = cmdHistory[histIdx];
    } else {
      histIdx = -1;
      cmdInput().value = '';
    }
  }
}
