const canvas = document.getElementById('board');
const ctx = canvas.getContext('2d');
const statusEl = document.getElementById('status');
const sessionEl = document.getElementById('session');
const aiEl = document.getElementById('ai');
let ws = null;
const strokes = new Map();
const aiCards = [];
const imageCache = new Map();
const pending = [];

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
  for (const stroke of strokes.values()) drawStroke(stroke);
  for (const card of aiCards) drawAiCard(card);
}

function resetBoard() {
  strokes.clear();
  aiCards.length = 0;
  aiEl.textContent = '';
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
    aiEl.textContent = `${payload.kind || 'text'}\n\n${payload.content || ''}`;
    aiCards.length = 0;
    aiCards.push({
      id: `${msg.timestamp || Date.now()}`,
      kind: payload.kind || 'text',
      content: payload.content || '',
      image_url: payload.metadata?.image_url || ''
    });
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
  if (!strokeIds.length) {
    resetBoard();
    return;
  }
  const message = {
    type: 'erase',
    session_id: sessionEl.value || 'demo',
    client_id: 'web-viewer',
    page_id: 'page-1',
    timestamp: Date.now(),
    version: 1,
    payload: { stroke_ids: strokeIds }
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
