const SESSION_KEY = "fridge2dish_session_id";

const ROUTE_LABELS = {
  COOK_NOW: { text: "즉시조리", cls: "bg-success" },
  SUBSTITUTION: { text: "대체재", cls: "bg-warning text-dark" },
  SHOPPING_NEEDED: { text: "장보기", cls: "bg-info text-dark" },
};

if (window.marked) {
  marked.use({
    breaks: true,
    gfm: true,
  });
}

function getSessionId() {
  return localStorage.getItem(SESSION_KEY);
}

function setSessionId(id) {
  if (!id) return;
  localStorage.setItem(SESSION_KEY, id);
  renderSessionLabel(id);
}

function renderSessionLabel(id) {
  const label = document.getElementById("session-label");
  label.textContent = id ? `세션: ${id.slice(0, 8)}...` : "";
}

function resetSession() {
  localStorage.removeItem(SESSION_KEY);
  renderSessionLabel("");
  const container = document.getElementById("chat-container");
  container.innerHTML = `
    <div class="bubble-agent">
      <div class="bg-white border p-3">
        새 대화를 시작합니다.<br>냉장고에 있는 재료나 먹고 싶은 메뉴를 알려주세요.
      </div>
    </div>`;
}

async function loadFridge() {
  const list = document.getElementById("fridge-list");
  list.innerHTML = `
    <div class="text-center text-muted py-4">
      <div class="spinner-border spinner-border-sm" role="status"></div>
      <div class="mt-2 small">재고 로딩 중...</div>
    </div>`;

  try {
    const res = await fetch("/api/fridge/1");
    if (!res.ok) throw new Error(`fridge api failed: ${res.status}`);

    const data = await res.json();
    const items = data.fridge_items || [];
    if (items.length === 0) {
      list.innerHTML = `<p class="text-muted text-center small py-4 mb-0">등록된 재료가 없습니다.</p>`;
      return;
    }

    list.innerHTML = items.map(renderFridgeItem).join("");
  } catch (error) {
    list.innerHTML = `<p class="text-danger small text-center py-4 mb-0">재고를 불러오지 못했습니다.</p>`;
  }
}

function renderFridgeItem(item) {
  const days = item.days_until_expiry;
  const quantity = item.quantity != null ? `${formatQuantity(item.quantity)}${item.unit || ""}` : "";
  const expiryText = days == null ? "기한 없음" : days < 0 ? `D+${Math.abs(days)}` : `D-${days}`;
  const badge = freshnessBadge(item);

  return `
    <div class="fridge-item d-flex justify-content-between align-items-center gap-2 mb-2 p-3">
      <div>
        <div class="fw-semibold">${escapeHtml(item.ingredient_name)}</div>
        <div class="text-muted small">${escapeHtml(quantity)} ${escapeHtml(expiryText)}</div>
      </div>
      ${badge}
    </div>`;
}

function freshnessBadge(item) {
  const days = item.days_until_expiry;
  const score = item.freshness_score;

  if (score != null && score < 3) {
    return `<span class="badge bg-danger">신선도 낮음</span>`;
  }
  if (days != null && days <= 1) {
    return `<span class="badge bg-danger">임박</span>`;
  }
  if (days != null && days <= 3) {
    return `<span class="badge bg-warning text-dark">주의</span>`;
  }
  return `<span class="badge bg-success">신선</span>`;
}

async function sendMessage() {
  const input = document.getElementById("chat-input");
  const message = input.value.trim();
  if (!message) return;

  appendUserBubble(message);
  input.value = "";
  setSending(true);

  const thinkingId = appendThinkingBubble();

  try {
    const body = { message };
    const sessionId = getSessionId();
    if (sessionId) body.session_id = sessionId;

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || `chat api failed: ${res.status}`);
    }

    setSessionId(data.session_id);
    removeThinkingBubble(thinkingId);
    appendAgentBubble(
      data.response,
      data.route,
      data.image_url,
      data.image_source_url,
      data.image_alt,
    );
  } catch (error) {
    removeThinkingBubble(thinkingId);
    appendAgentBubble(`오류가 발생했습니다. 잠시 후 다시 시도해주세요.\n${error.message}`, null);
  } finally {
    setSending(false);
  }
}

function setSending(isSending) {
  const btn = document.getElementById("send-btn");
  btn.disabled = isSending;
  btn.innerHTML = isSending
    ? `<span class="spinner-border spinner-border-sm" role="status"></span>`
    : "전송";
}

function appendUserBubble(text) {
  const container = document.getElementById("chat-container");
  const div = document.createElement("div");
  div.className = "bubble-user";
  div.innerHTML = `<div class="text-white p-3">${escapeHtml(text)}</div>`;
  container.appendChild(div);
  scrollChatToBottom();
}

function appendThinkingBubble() {
  const container = document.getElementById("chat-container");
  const id = `thinking-${Date.now()}`;
  const div = document.createElement("div");
  div.id = id;
  div.className = "bubble-agent";
  div.innerHTML = `
    <div class="bg-white border p-3 text-muted">
      <span class="spinner-border spinner-border-sm me-2" role="status"></span>
      레시피를 분석하고 있어요...
    </div>`;
  container.appendChild(div);
  scrollChatToBottom();
  return id;
}

function removeThinkingBubble(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function appendAgentBubble(text, route, imageUrl = null, imageSourceUrl = null, imageAlt = null) {
  const container = document.getElementById("chat-container");
  const div = document.createElement("div");
  div.className = "bubble-agent";

  const routeHtml = route && ROUTE_LABELS[route]
    ? `<span class="badge ${ROUTE_LABELS[route].cls} mb-2">${ROUTE_LABELS[route].text}</span><br>`
    : "";

  div.innerHTML = `
    <div class="bg-white border p-3">
      ${routeHtml}<div class="agent-markdown">${renderMarkdown(text || "(응답 없음)")}</div>
      ${renderRecipeImage(imageUrl, imageSourceUrl, imageAlt)}
    </div>`;
  container.appendChild(div);
  scrollChatToBottom();
}

function scrollChatToBottom() {
  const container = document.getElementById("chat-container");
  container.scrollTop = container.scrollHeight;
}

function formatQuantity(quantity) {
  return Number.isInteger(quantity) ? String(quantity) : String(quantity).replace(/\.0$/, "");
}

function renderMarkdown(text) {
  if (!window.marked) {
    return escapeHtml(text).replace(/\n/g, "<br>");
  }
  return marked.parse(text);
}

function renderRecipeImage(imageUrl, sourceUrl, alt) {
  if (imageUrl) {
    const safeUrl = escapeHtml(imageUrl);
    const safeAlt = escapeHtml(alt || "추천 레시피 이미지");
    const sourceLink = sourceUrl
      ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer" class="small text-muted">이미지 출처</a>`
      : "";

    return `
      <div class="recipe-image mt-3">
        <img src="${safeUrl}" alt="${safeAlt}" loading="lazy" referrerpolicy="no-referrer"
          onerror="this.closest('.recipe-image').remove()">
        ${sourceLink}
      </div>`;
  }

  if (sourceUrl) {
    return `
      <div class="mt-3">
        <a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline-success">
          관련 이미지 보기
        </a>
      </div>`;
  }

  return "";
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

document.addEventListener("DOMContentLoaded", () => {
  loadFridge();
  renderSessionLabel(getSessionId());

  document.getElementById("chat-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  });
});
