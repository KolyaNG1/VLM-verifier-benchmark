const state = { run: null, detail: null };
const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[c]);

async function json(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function metric(label, value) { return `<div class="metric"><b>${escapeHtml(value ?? "—")}</b><span>${escapeHtml(label)}</span></div>`; }

function showSummary(run) {
  const summary = run.summary || {};
  $("#run-summary").innerHTML = [
    metric("модель", run.config?.model), metric("состояние", run.status), metric("пар", summary.pairs),
    metric("завершено", summary.complete), metric("частично", summary.partial), metric("ошибок", summary.failed),
    metric("вызовов", summary.calls), metric("стоимость, USD", Number(summary.cost_usd || 0).toFixed(5)),
  ].join("");
}

function filteredSamples() {
  const text = $("#pair-filter").value.trim().toLowerCase();
  const status = $("#status-filter").value;
  return state.run.samples.filter((sample) => (!text || sample.pair_id.toLowerCase().includes(text)) && (!status || sample.status === status));
}

function renderList() {
  const list = $("#pair-list"); list.innerHTML = "";
  for (const sample of filteredSamples()) {
    const template = $("#pair-template").content.cloneNode(true);
    const button = template.querySelector("button");
    button.querySelector("strong").textContent = sample.pair_id;
    button.querySelector("span").textContent = `${sample.status} · F: ${sample.orig?.scores?.faithfulness ?? "—"} → ${sample.fail?.scores?.faithfulness ?? "—"}`;
    if (state.detail === sample.pair_directory) button.classList.add("active");
    button.onclick = () => loadDetail(sample.pair_directory);
    list.append(template);
  }
}

function scoreCards(side) {
  const scores = side?.result?.computed?.scores;
  if (!scores) return `<p class="muted">${escapeHtml(side?.result?.status || "нет результата")}</p>`;
  return `<div class="scores">${["faithfulness", "clarity", "compactness", "style", "overall"].map((name) => `<div class="score"><b>${escapeHtml(scores[name])}</b><span>${name}</span></div>`).join("")}</div>`;
}

function imageUrl(descriptor) {
  return `/asset?path=${encodeURIComponent(descriptor.project_relative_path || descriptor.path)}`;
}

function sideDetail(name, side) {
  const result = side?.result;
  const audit = result?.model_output?.audit;
  return `<section><h3>${name}</h3>${scoreCards(side)}
    <p class="muted">Рассуждение: ${result?.provider_reasoning ? "предоставлено" : "не предоставлено"}</p>
    ${audit ? `<details><summary>Аудит</summary><pre>${escapeHtml(JSON.stringify(audit, null, 2))}</pre></details>` : ""}
    <details><summary>Разобранный результат</summary><pre>${escapeHtml(JSON.stringify(result, null, 2))}</pre></details>
    <details><summary>Запрос без base64</summary><pre>${escapeHtml(JSON.stringify(side?.request, null, 2))}</pre></details>
    <details><summary>Сырой ответ</summary><pre>${escapeHtml(JSON.stringify(side?.raw_response, null, 2))}</pre></details>
  </section>`;
}

async function loadDetail(directory) {
  state.detail = directory; renderList();
  const detail = await json(`/api/runs/${encodeURIComponent(state.run.run.run_id)}/samples/${encodeURIComponent(directory)}`);
  const pair = detail.pair;
  const comparison = pair.comparison ? `<pre>${escapeHtml(JSON.stringify(pair.comparison, null, 2))}</pre>` : "<p class=\"muted\">Парное сравнение пока недоступно.</p>";
  $("#detail").innerHTML = `<h2>${escapeHtml(pair.pair_id)}</h2><p>${escapeHtml(pair.article.figure_id)} · ${escapeHtml(pair.article.pdf_id)}</p>
    <details open><summary>Caption и text_block</summary><p>${escapeHtml(pair.caption)}</p><pre>${escapeHtml(pair.text_block)}</pre></details>
    <div class="image-grid"><figure class="image-card"><img src="${imageUrl(pair.images.orig)}" alt="Оригинал"><figcaption>orig</figcaption></figure><figure class="image-card"><img src="${imageUrl(pair.images.fail)}" alt="Изменённая картинка"><figcaption>fail</figcaption></figure></div>
    <details><summary>Эталонная разметка после оценки</summary><pre>${escapeHtml(JSON.stringify(pair.gold, null, 2))}</pre></details>
    <details><summary>Сравнение orig против fail</summary>${comparison}</details>
    <div class="image-grid">${sideDetail("orig", detail.orig)}${sideDetail("fail", detail.fail)}</div>`;
}

async function loadRun(runId) {
  state.detail = null;
  state.run = await json(`/api/runs/${encodeURIComponent(runId)}`);
  showSummary(state.run.run); renderList();
  $("#detail").innerHTML = "<p class=\"muted\">Выберите пару слева.</p>";
}

async function init() {
  try {
    const runs = await json("/api/runs");
    const select = $("#run-select"); select.innerHTML = "";
    if (!runs.length) { select.innerHTML = "<option>Запусков пока нет</option>"; return; }
    for (const run of runs) {
      const option = document.createElement("option"); option.value = run.run_id; option.textContent = `${run.run_id} · ${run.status}`; select.append(option);
    }
    select.onchange = () => loadRun(select.value).catch(showError);
    $("#pair-filter").oninput = renderList; $("#status-filter").onchange = renderList;
    await loadRun(select.value);
  } catch (error) { showError(error); }
}

function showError(error) { $("#detail").innerHTML = `<p class="bad">Ошибка просмотра: ${escapeHtml(error.message || error)}</p>`; }
init();
