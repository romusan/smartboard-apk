const canvas = document.getElementById('board');
const ctx = canvas.getContext('2d');
const statusEl = document.getElementById('status');
const sessionEl = document.getElementById('session');
const aiEl = document.getElementById('ai');
let ws = null;
const strokes = new Map();
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

function applyMessage(msg) {
  const payload = msg.payload || {};
  if (msg.type === 'sync_state') {
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
  if (msg.type === 'ai_response') aiEl.textContent = `${payload.kind || 'text'}\n\n${payload.content || ''}`;
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
