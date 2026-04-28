/* ── 상수 ── */
const SESSION_KEY = "fridge2dish_session_id";

const ROUTE_LABELS = {
  COOK_NOW:        { emoji: "🍳", text: "즉시조리",  cls: "route-cook" },
  SUBSTITUTION:    { emoji: "🔄", text: "대체재",    cls: "route-sub" },
  SHOPPING_NEEDED: { emoji: "🛒", text: "장보기",    cls: "route-shop" },
};

if (window.marked) {
  marked.use({ gfm: true });
}

/* ── 세션 ── */
function getSessionId() { return localStorage.getItem(SESSION_KEY); }
function setSessionId(id) {
  if (!id) return;
  localStorage.setItem(SESSION_KEY, id);
  renderSessionLabel(id);
}
function renderSessionLabel(id) {
  document.getElementById("session-label").textContent =
    id ? `세션: ${id.slice(0, 8)}…` : "";
}
function resetSession() {
  localStorage.removeItem(SESSION_KEY);
  renderSessionLabel("");
  document.getElementById("chat-container").innerHTML = `
    <div class="bubble-wrap agent">
      <div class="bubble agent">
        새 대화를 시작합니다. 🍳<br>냉장고에 있는 재료나 먹고 싶은 메뉴를 알려주세요.
      </div>
    </div>`;
}

/* ── 냉장고 ── */
async function loadFridge() {
  const list = document.getElementById("fridge-list");
  list.innerHTML = `
    <div class="text-center text-muted py-5">
      <div class="spinner-border spinner-border-sm" role="status"></div>
      <div class="mt-2 small">재고 로딩 중...</div>
    </div>`;
  try {
    const res = await fetch("/api/fridge/1");
    if (!res.ok) throw new Error(`${res.status}`);
    const data = await res.json();
    const items = data.fridge_items || [];
    list.innerHTML = items.length
      ? items.map(renderFridgeItem).join("")
      : `<p class="text-muted text-center small py-5 mb-0">등록된 재료가 없습니다.</p>`;
  } catch {
    list.innerHTML = `<p class="text-danger small text-center py-5 mb-0">재고를 불러오지 못했습니다.</p>`;
  }
}

function renderFridgeItem(item) {
  const qty = item.quantity != null
    ? `${fmtQty(item.quantity)}${item.unit || ""}` : "";
  const days = item.days_until_expiry;
  const expiryText = days == null ? "기한 없음"
    : days < 0 ? `D+${Math.abs(days)}`
    : `D-${days}`;
  return `
    <div class="fridge-item d-flex justify-content-between align-items-center gap-2 mb-2 p-3">
      <div>
        <div class="fw-semibold">${esc(item.ingredient_name)}</div>
        <div class="text-muted small">${esc(qty)} ${esc(expiryText)}</div>
      </div>
      ${freshnessBadge(item)}
    </div>`;
}

function freshnessBadge(item) {
  const days  = item.days_until_expiry;
  const score = item.freshness_score;
  if (score != null && score < 0.4)   return `<span class="badge bg-danger">신선도 낮음</span>`;
  if (days  != null && days  <= 1)    return `<span class="badge bg-danger">임박</span>`;
  if (days  != null && days  <= 3)    return `<span class="badge bg-warning text-dark">⚠️ 주의</span>`;
  return `<span class="badge bg-success">신선</span>`;
}

/* ── 채팅 ── */
async function sendMessage() {
  const input   = document.getElementById("chat-input");
  const message = input.value.trim();
  if (!message) return;

  appendUserBubble(message);
  input.value = "";
  setSending(true);
  const thinkingId = appendThinkingBubble();

  try {
    const body = { message };
    const sid  = getSessionId();
    if (sid) body.session_id = sid;

    const res  = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `${res.status}`);

    setSessionId(data.session_id);
    removeThinkingBubble(thinkingId);
    appendAgentBubble(data.response, data.route);
  } catch (err) {
    removeThinkingBubble(thinkingId);
    appendAgentBubble(`오류가 발생했습니다. 잠시 후 다시 시도해 주세요.\n${err.message}`, null);
  } finally {
    setSending(false);
  }
}

function setSending(on) {
  const btn = document.getElementById("send-btn");
  btn.disabled  = on;
  btn.innerHTML = on
    ? `<span class="spinner-border spinner-border-sm" role="status"></span>`
    : "전송";
}

function appendUserBubble(text) {
  const div = document.createElement("div");
  div.className = "bubble-wrap user";
  div.innerHTML = `<div class="bubble user">${esc(text)}</div>`;
  chat().appendChild(div);
  scrollBottom();
}

function appendThinkingBubble() {
  const id  = `thinking-${Date.now()}`;
  const div = document.createElement("div");
  div.id        = id;
  div.className = "bubble-wrap agent";
  div.innerHTML = `
    <div class="bubble agent text-muted">
      <span class="thinking-dot"></span><span class="thinking-dot"></span><span class="thinking-dot"></span>
      레시피를 분석하고 있어요…
    </div>`;
  chat().appendChild(div);
  scrollBottom();
  return id;
}

function removeThinkingBubble(id) {
  document.getElementById(id)?.remove();
}

function appendAgentBubble(text, route) {
  const label  = route && ROUTE_LABELS[route];
  const badge  = label
    ? `<span class="route-badge ${label.cls}">${label.emoji} ${label.text}</span>`
    : "";
  const div = document.createElement("div");
  div.className = "bubble-wrap agent";
  div.innerHTML = `
    ${badge}
    <div class="bubble agent">
      <div class="agent-md">${renderMd(text || "(응답 없음)")}</div>
    </div>`;
  chat().appendChild(div);
  scrollBottom();
}

/* ── 유틸 ── */
function chat()        { return document.getElementById("chat-container"); }
function scrollBottom(){ const c = chat(); c.scrollTop = c.scrollHeight; }
function fmtQty(q)    { return Number.isInteger(q) ? String(q) : String(q).replace(/\.0$/, ""); }
function renderMd(txt) {
  return window.marked ? marked.parse(txt) : esc(txt).replace(/\n/g, "<br>");
}
function esc(v) {
  return String(v ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

/* ── 초기화 ── */
document.addEventListener("DOMContentLoaded", () => {
  loadFridge();
  renderSessionLabel(getSessionId());
  document.getElementById("chat-input").addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
});
