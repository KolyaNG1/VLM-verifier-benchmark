const state = { snapshot: null, selectedId: null };
const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;" })[c]);
const labels = { queued:"в очереди", generating:"генерируется", awaiting_review:"ожидает проверки", approved:"одобрено", failed:"ошибка", manual_required:"нужна ручная разметка" };

function inlineMarkdown(value) {
  const protectedParts = [];
  const hold = (html) => `\u0000${protectedParts.push(html) - 1}\u0000`;
  let text = escapeHtml(value);
  text = text.replace(/`([^`\n]+)`/g, (_, code) => hold(`<code>${code}</code>`));
  text = text.replace(/\[([^\]]+)]\((https?:\/\/[^\s)]+)\)/g, (_, label, url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`);
  text = text.replace(/&lt;u&gt;([\s\S]*?)&lt;\/u&gt;/gi, "<u>$1</u>");
  text = text.replace(/&lt;mark&gt;([\s\S]*?)&lt;\/mark&gt;/gi, "<mark>$1</mark>");
  text = text.replace(/==(.+?)==/g, "<mark>$1</mark>");
  text = text.replace(/\+\+(.+?)\+\+/g, "<u>$1</u>");
  text = text.replace(/\*\*(.+?)\*\*|__(.+?)__/g, (_, boldA, boldB) => `<strong>${boldA || boldB}</strong>`);
  text = text.replace(/~~(.+?)~~/g, "<del>$1</del>");
  text = text.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)|(^|[^_])_([^_\n]+)_(?!_)/g, (_, beforeA, italicA, beforeB, italicB) => `${beforeA || beforeB || ""}<em>${italicA || italicB}</em>`);
  return text.replace(/\u0000(\d+)\u0000/g, (_, index) => protectedParts[Number(index)]);
}

function renderMarkdown(value) {
  const lines = String(value ?? "").replace(/\r\n?/g, "\n").split("\n");
  const html = []; let paragraph = []; let listType = null; let codeLines = null;
  const closeParagraph = () => { if (paragraph.length) { html.push(`<p>${inlineMarkdown(paragraph.join(" "))}</p>`); paragraph = []; } };
  const closeList = () => { if (listType) { html.push(`</${listType}>`); listType = null; } };
  for (const line of lines) {
    if (line.startsWith("```")) { closeParagraph(); closeList(); if (codeLines === null) { codeLines = []; } else { html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`); codeLines = null; } continue; }
    if (codeLines !== null) { codeLines.push(line); continue; }
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/); const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
    if (heading) { closeParagraph(); closeList(); html.push(`<h${heading[1].length}>${inlineMarkdown(heading[2])}</h${heading[1].length}>`); continue; }
    if (/^\s*(---+|\*\*\*+)\s*$/.test(line)) { closeParagraph(); closeList(); html.push("<hr>"); continue; }
    if (line.startsWith(">")) { closeParagraph(); closeList(); html.push(`<blockquote>${inlineMarkdown(line.replace(/^>\s?/, ""))}</blockquote>`); continue; }
    if (ordered || unordered) { closeParagraph(); const desired = ordered ? "ol" : "ul"; if (listType !== desired) { closeList(); html.push(`<${desired}>`); listType = desired; } html.push(`<li>${inlineMarkdown((ordered || unordered)[1])}</li>`); continue; }
    if (!line.trim()) { closeParagraph(); closeList(); continue; }
    closeList(); paragraph.push(line.trim());
  }
  if (codeLines !== null) html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
  closeParagraph(); closeList(); return html.join("") || "<p class=\"muted\">Нет текста.</p>";
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("annotation-viewer-theme", theme);
  $("#theme-toggle").textContent = theme === "dark" ? "Светлая тема" : "Тёмная тема";
}

async function api(url, options) { const response = await fetch(url, options); const body = await response.json().catch(() => ({})); if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`); return body; }
function metric(label, value) { return `<div class="metric"><b>${escapeHtml(value || 0)}</b><span>${escapeHtml(label)}</span></div>`; }
function itemMatches(item, needle) { return !needle || `${item.image_path} ${item.status} ${labels[item.status] || ""}`.toLowerCase().includes(needle); }

function renderSummary() { const c = state.snapshot.counts || {}; $("#summary").innerHTML = [metric("всего", state.snapshot.items.length), metric("в очереди", c.queued), metric("на проверке", c.awaiting_review), metric("одобрено", c.approved), metric("ошибки", c.failed), metric("в работе", c.generating)].join(""); }
function renderQueue() {
  const needle = $("#filter").value.trim().toLowerCase(); const queue = $("#queue"); queue.innerHTML = "";
  const order = { manual_required:0, awaiting_review:1, generating:2, queued:3, failed:4, approved:5 };
  const items = state.snapshot.items.filter((item) => itemMatches(item, needle)).sort((a,b) => (order[a.status] - order[b.status]) || a.image_path.localeCompare(b.image_path));
  for (const item of items) { const fragment = $("#item-template").content.cloneNode(true); const button = fragment.querySelector("button"); button.querySelector("strong").textContent = item.image_path; button.querySelector("span").innerHTML = `<span class="status-${escapeHtml(item.status)}">${escapeHtml(labels[item.status] || item.status)}</span> · попытка ${item.attempts}`; if (item.id === state.selectedId) button.classList.add("active"); button.onclick = () => showDetail(item.id); queue.append(fragment); }
}

async function submitReview(id, decision) {
  const comment = $("#comment")?.value || "";
  const annotation = $("#annotation")?.value || "";
  if (decision === "reject" && !comment.trim()) { $("#review-error").textContent = "Для отклонения напишите, что нужно исправить."; return; }
  if ((decision === "approve" || decision === "manual") && !annotation.trim()) { $("#review-error").textContent = "Введите непустое описание перед сохранением."; return; }
  try { await api(`/api/items/${encodeURIComponent(id)}/review`, { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ decision, comment, annotation }) }); await refresh(); await showDetail(id); } catch (error) { $("#review-error").textContent = error.message || String(error); }
}

async function showDetail(id) {
  state.selectedId = id; renderQueue();
  const item = await api(`/api/items/${encodeURIComponent(id)}`); const status = labels[item.status] || item.status;
  const editable = item.final_annotation || item.candidate_text || "";
  const rejectButton = item.status === "awaiting_review" ? `<button class="reject" id="reject">Отклонить и переделать</button>` : "";
  const approveButton = item.status === "awaiting_review" ? `<button class="approve" id="approve">Одобрить отредактированный ответ</button>` : "";
  const retryButton = item.status === "failed" ? `<button class="retry" id="retry">Вернуть к модели в очередь</button>` : "";
  const review = `<section><h3>Итоговое описание</h3><label>Редактор описания <textarea id="annotation" placeholder="Здесь можно полностью разметить картинку вручную или отредактировать ответ модели.">${escapeHtml(editable)}</textarea></label><label>Комментарий для журнала / следующей попытки <textarea id="comment" placeholder="При отклонении обязательно: что нужно исправить?"></textarea></label><p id="review-error" class="error"></p><div class="actions">${approveButton}${rejectButton}<button class="approve" id="manual">Сохранить вручную</button>${retryButton}</div></section>`;
  $("#detail").innerHTML = `<h2>${escapeHtml(item.image_path)}</h2><p class="metadata">Статус: <span class="status-${escapeHtml(item.status)}">${escapeHtml(status)}</span> · попытка ${item.attempts}</p><figure class="figure"><img src="/api/image/${encodeURIComponent(item.id)}" alt="Научная иллюстрация"><figcaption>${escapeHtml(item.image_path)}</figcaption></figure><h3>Последний ответ модели</h3><div class="candidate markdown">${renderMarkdown(item.candidate_text || "Ответа модели ещё нет.")}</div>${item.review_comment ? `<p class="metadata">Последний комментарий: ${escapeHtml(item.review_comment)}</p>` : ""}${review}`;
  $("#approve")?.addEventListener("click", () => submitReview(id, "approve")); $("#reject")?.addEventListener("click", () => submitReview(id, "reject")); $("#retry")?.addEventListener("click", () => submitReview(id, "retry"));
  $("#manual")?.addEventListener("click", () => submitReview(id, "manual"));
  const editor = $("#annotation"); const preview = document.createElement("div"); preview.id = "annotation-preview"; preview.className = "markdown markdown-preview"; preview.innerHTML = renderMarkdown(editor.value); editor.parentElement.append(preview); editor.addEventListener("input", () => { preview.innerHTML = renderMarkdown(editor.value); });
}

async function refresh() { state.snapshot = await api("/api/state"); renderSummary(); renderQueue(); if (!state.selectedId) { const first = state.snapshot.items.find((item) => item.status === "awaiting_review") || state.snapshot.items[0]; if (first) await showDetail(first.id); } }
function showError(error) { $("#detail").innerHTML = `<p class="error">Ошибка просмотра: ${escapeHtml(error.message || error)}</p>`; }
const storedTheme = localStorage.getItem("annotation-viewer-theme"); applyTheme(storedTheme || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"));
$("#theme-toggle").addEventListener("click", () => applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));
$("#filter").addEventListener("input", renderQueue); refresh().catch(showError); setInterval(() => refresh().catch(showError), 1200);
