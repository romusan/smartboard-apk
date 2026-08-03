const canvas = document.getElementById('board');
const ctx = canvas.getContext('2d');
const statusEl = document.getElementById('status');
const sessionEl = document.getElementById('session');
const aiEl = document.getElementById('ai');
const simulationPanel = document.getElementById('simulationPanel');
const mechanismSimulation = document.getElementById('mechanismSimulation');
const simulationCounter = document.getElementById('simulationCounter');
const simulationUrls = [];
let simulationIndex = -1;
function showSimulation(index) {
  if (!simulationUrls.length) return;
  simulationIndex = Math.max(0, Math.min(index, simulationUrls.length - 1));
  mechanismSimulation.src = `${simulationUrls[simulationIndex]}?view=${Date.now()}`;
  simulationCounter.textContent = `Simulación ${simulationIndex + 1} de ${simulationUrls.length}`;
  simulationPanel.hidden = false;
}
document.getElementById('previousSimulation').onclick = () => showSimulation(simulationIndex - 1);
document.getElementById('nextSimulation').onclick = () => showSimulation(simulationIndex + 1);
document.getElementById('closeSimulation').onclick = () => {
  simulationPanel.hidden = true;
  mechanismSimulation.src = 'about:blank';
};
let ws = null;
const strokes = new Map();
const aiCards = [];
const imageCache = new Map();
const pending = [];
let documentState = null;
let currentPage = 0;

function resize() {
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.floor(rect.width * devicePixelRatio);
  canvas.height = Math.floor(rect.height * devicePixelRatio);
  render();
}
addEventListener('resize', resize);
setTimeout(resize, 0);

function render() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawDocumentBackground();
  for (const stroke of strokes.values()) drawStroke(stroke);
  for (const card of aiCards) drawAiCard(card);
}

function resetBoard() {
  strokes.clear();
  aiCards.length = 0;
  aiEl.textContent = '';
  simulationPanel.hidden = true;
  mechanismSimulation.src = 'about:blank';
  render();
}

function drawDocumentBackground() {
  const page = documentState?.pages?.[currentPage];
  if (!page?.image_url) return;
  const image = imageCache.get(page.image_url);
  if (!image) {
    const next = new Image();
    next.onload = render;
    next.src = page.image_url;
    imageCache.set(page.image_url, next);
    return;
  }
  if (!image.complete) return;
  const ratio = Math.min(canvas.width / image.naturalWidth, canvas.height / image.naturalHeight);
  const width = image.naturalWidth * ratio;
  const height = image.naturalHeight * ratio;
  const x = (canvas.width - width) / 2;
  const y = (canvas.height - height) / 2;
  ctx.save();
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(image, x, y, width, height);
  ctx.strokeStyle = '#cbd5e1';
  ctx.lineWidth = 2 * devicePixelRatio;
  ctx.strokeRect(x, y, width, height);
  ctx.restore();
}

function updatePageInfo() {
  const pageInfo = document.getElementById('pageInfo');
  if (!documentState?.pages?.length) {
    pageInfo.textContent = 'Sin documento';
    return;
  }
  pageInfo.textContent = `${documentState.filename || 'PDF'} · página ${currentPage + 1}/${documentState.pages.length}`;
}

function setDocument(document, pageIndex = 0) {
  documentState = document;
  currentPage = Math.max(0, Math.min(pageIndex, (documentState?.pages?.length || 1) - 1));
  updatePageInfo();
  render();
}

function drawStroke(stroke) {
  if (!stroke.points || stroke.points.length < 2) return;
  ctx.save();
  ctx.strokeStyle = stroke.color || '#111';
  ctx.lineWidth = (stroke.width || 4) * devicePixelRatio;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.beginPath();
  stroke.points.forEach((p, i) => {
    const x = p.x * canvas.width;
    const y = p.y * canvas.height;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.restore();
}

function drawWrappedText(text, x, y, maxWidth, lineHeight, maxLines) {
  const words = String(text || '').replace(/\s+/g, ' ').trim().split(' ');
  let line = '';
  let lines = 0;
  for (const word of words) {
    const testLine = line ? `${line} ${word}` : word;
    if (ctx.measureText(testLine).width > maxWidth && line) {
      ctx.fillText(line, x, y);
      y += lineHeight;
      lines += 1;
      line = word;
      if (lines >= maxLines - 1) break;
    } else {
      line = testLine;
    }
  }
  if (line && lines < maxLines) ctx.fillText(line, x, y);
}

function drawAiCard(card) {
  if (card.kind === 'image' && card.image_url) {
    drawImageCard(card);
    return;
  }
  const margin = 18 * devicePixelRatio;
  const width = Math.min(canvas.width * 0.42, 460 * devicePixelRatio);
  const x = canvas.width - width - margin;
  const y = margin;
  const padding = 14 * devicePixelRatio;
  const lineHeight = 18 * devicePixelRatio;
  const height = Math.min(canvas.height * 0.48, 280 * devicePixelRatio);
  ctx.save();
  ctx.fillStyle = '#fffbeb';
  ctx.strokeStyle = '#f59e0b';
  ctx.lineWidth = 2 * devicePixelRatio;
  if (ctx.roundRect) {
    ctx.beginPath();
    ctx.roundRect(x, y, width, height, 16 * devicePixelRatio);
    ctx.fill();
    ctx.stroke();
  } else {
    ctx.fillRect(x, y, width, height);
    ctx.strokeRect(x, y, width, height);
  }
  ctx.fillStyle = '#78350f';
  ctx.font = `${16 * devicePixelRatio}px system-ui, sans-serif`;
  ctx.fillText('Respuesta IA supervisada', x + padding, y + padding + lineHeight);
  ctx.fillStyle = '#111827';
  ctx.font = `${13 * devicePixelRatio}px system-ui, sans-serif`;
  drawWrappedText(card.content, x + padding, y + padding + lineHeight * 2.3, width - padding * 2, lineHeight, 11);
  ctx.restore();
}

function drawImageCard(card) {
  const image = imageCache.get(card.image_url);
  if (!image) {
    const next = new Image();
    next.onload = render;
    next.src = card.image_url;
    imageCache.set(card.image_url, next);
    return;
  }
  if (!image.complete) return;
  const margin = 18 * devicePixelRatio;
  const maxWidth = canvas.width * 0.55;
  const maxHeight = canvas.height * 0.58;
  const ratio = Math.min(maxWidth / image.naturalWidth, maxHeight / image.naturalHeight);
  const width = image.naturalWidth * ratio;
  const height = image.naturalHeight * ratio;
  const x = canvas.width - width - margin;
  const y = margin;
  ctx.save();
  ctx.shadowColor = 'rgba(15, 23, 42, 0.22)';
  ctx.shadowBlur = 18 * devicePixelRatio;
  ctx.shadowOffsetY = 6 * devicePixelRatio;
  ctx.drawImage(image, x, y, width, height);
  ctx.restore();
}

function applyMessage(msg) {
  const payload = msg.payload || {};
  if (msg.type === 'sync_state') {
    resetBoard();
    for (const item of payload.history || []) applyMessage(item);
    render();
    return;
  }
  if (msg.type === 'object_update' && payload.action === 'document_set') {
    setDocument(payload.document, payload.document?.current_page || 0);
    return;
  }
  if (msg.type === 'page_select' && Number.isInteger(payload.page_index)) {
    currentPage = Math.max(0, Math.min(payload.page_index, (documentState?.pages?.length || 1) - 1));
    updatePageInfo();
    render();
    return;
  }
  if (['stroke_start', 'stroke_update', 'stroke_end'].includes(msg.type)) {
    const stroke = payload.stroke || { id: msg.stroke_id, page_id: msg.page_id, points: [] };
    const current = strokes.get(stroke.id) || stroke;
    Object.assign(current, stroke);
    strokes.set(current.id, current);
    render();
  }
  if (msg.type === 'erase' && payload.stroke_ids) {
    payload.stroke_ids.forEach(id => strokes.delete(id));
    render();
  }
  if (msg.type === 'ai_response') {
    const html3d = payload.metadata?.html_3d_url ? `\n\nVista 3D: ${location.origin}${payload.metadata.html_3d_url}` : '';
    aiEl.textContent = `${payload.kind || 'text'}\n\n${payload.content || ''}${html3d}`;
    const simulationUrl = payload.metadata?.simulation_url;
    if (simulationUrl) {
      if (!simulationUrls.includes(simulationUrl)) simulationUrls.push(simulationUrl);
      showSimulation(simulationUrls.length - 1);
    }
    aiCards.push({
      id: `${msg.timestamp || Date.now()}`,
      kind: payload.kind || 'text',
      content: payload.content || '',
      image_url: payload.metadata?.image_url || ''
    });
    render();
  }
  if (
    msg.type === 'command' &&
    ['clear_ai_cards', 'clear_ai_card', 'clear_ai', 'delete_ai_cards'].includes(payload.action)
  ) {
    aiCards.length = 0;
    aiEl.textContent = '';
    render();
  }
  if (
    msg.type === 'command' &&
    ['clear_board', 'delete_board', 'reset_board'].includes(payload.action)
  ) {
    strokes.clear();
    aiCards.length = 0;
    aiEl.textContent = '';
    render();
  }
}

async function refreshHistory() {
  const sessionId = encodeURIComponent(sessionEl.value || 'demo');
  statusEl.textContent = 'Actualizando...';
  const response = await fetch(`/sessions/${sessionId}`);
  const data = await response.json();
  resetBoard();
  for (const item of data.messages || []) applyMessage(item);
  render();
  statusEl.textContent = ws?.readyState === WebSocket.OPEN ? 'Conectado' : 'Desconectado';
}

function clearBoardRemote() {
  const strokeIds = [...strokes.keys()];
  const eraseMessage = {
    type: 'erase',
    session_id: sessionEl.value || 'demo',
    client_id: 'web-viewer',
    page_id: 'page-1',
    timestamp: Date.now(),
    version: 1,
    payload: { stroke_ids: strokeIds }
  };
  const clearCardsMessage = {
    type: 'command',
    session_id: sessionEl.value || 'demo',
    client_id: 'web-viewer',
    page_id: 'page-1',
    timestamp: Date.now() + 1,
    version: 1,
    payload: { action: 'clear_ai_cards' }
  };
  const clearBoardMessage = {
    type: 'command',
    session_id: sessionEl.value || 'demo',
    client_id: 'web-viewer',
    page_id: 'page-1',
    timestamp: Date.now() + 2,
    version: 1,
    payload: { action: 'clear_board' }
  };
  [eraseMessage, clearCardsMessage, clearBoardMessage].forEach(message => {
    applyMessage(message);
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(message));
    else pending.push(message);
  });
}

function sendPageSelect(pageIndex) {
  if (!documentState?.pages?.length) return;
  currentPage = Math.max(0, Math.min(pageIndex, documentState.pages.length - 1));
  const page = documentState.pages[currentPage];
  const message = {
    type: 'page_select',
    session_id: sessionEl.value || 'demo',
    client_id: 'web-viewer',
    page_id: page.page_id || 'page-1',
    timestamp: Date.now(),
    version: 1,
    payload: { page_index: currentPage, page_id: page.page_id, document_id: documentState.id }
  };
  applyMessage(message);
  if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(message));
  else pending.push(message);
}

function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws/${encodeURIComponent(sessionEl.value || 'demo')}`);
  ws.onopen = () => { statusEl.textContent = 'Conectado'; while (pending.length) ws.send(JSON.stringify(pending.shift())); };
  ws.onclose = () => { statusEl.textContent = 'Reconectando...'; setTimeout(connect, 1200); };
  ws.onerror = () => statusEl.textContent = 'Error de conexión';
  ws.onmessage = event => applyMessage(JSON.parse(event.data));
}

document.getElementById('connect').onclick = connect;
document.getElementById('refresh').onclick = refreshHistory;
document.getElementById('clear').onclick = clearBoardRemote;
document.getElementById('prevPage').onclick = () => sendPageSelect(currentPage - 1);
document.getElementById('nextPage').onclick = () => sendPageSelect(currentPage + 1);
document.getElementById('pdfFile').onchange = async event => {
  const file = event.target.files?.[0];
  if (!file) return;
  statusEl.textContent = 'Subiendo PDF...';
  const params = new URLSearchParams({ session_id: sessionEl.value || 'demo', filename: file.name });
  const response = await fetch(`/documents/upload?${params}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/pdf' },
    body: file
  });
  if (!response.ok) {
    statusEl.textContent = `Error PDF: ${await response.text()}`;
    return;
  }
  const payload = await response.json();
  setDocument(payload.document, payload.document?.current_page || 0);
  statusEl.textContent = ws?.readyState === WebSocket.OPEN ? 'Conectado' : 'Desconectado';
};
document.getElementById('exportPng').onclick = () => {
  const a = document.createElement('a');
  a.href = canvas.toDataURL('image/png');
  a.download = `smartboard-${sessionEl.value || 'demo'}.png`;
  a.click();
};
document.getElementById('ask').onclick = async () => {
  const response = await fetch('/ai/query', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action: 'explain', session_id: sessionEl.value || 'demo', page_id: 'page-1', strokes: [...strokes.values()], png_base64: canvas.toDataURL('image/png').split(',')[1], recognized_text: '', page_context: document.getElementById('context').value })
  });
  aiEl.textContent = JSON.stringify(await response.json(), null, 2);
};
connect();
