const state = {
  dashboard: null,
  selectedProspectId: null,
};

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request failed");
  }
  return payload;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function badge(value, tone = "neutral") {
  return `<span class="badge badge-${tone}">${escapeHtml(value)}</span>`;
}

function routeOptions(selected) {
  const routes = ["", "ES_LOCAL", "ES_B2B", "US_HISPANIC"];
  return routes
    .map((route) => {
      const label = route || "Auto";
      const isSelected = route === (selected || "") ? "selected" : "";
      return `<option value="${route}" ${isSelected}>${label}</option>`;
    })
    .join("");
}

function scoreTone(score) {
  if (score == null) return "neutral";
  if (score >= 80) return "good";
  if (score >= 65) return "warn";
  return "bad";
}

function statusTone(status) {
  if (["proposal_ready", "draft_ready", "success"].includes(status)) return "good";
  if (["researching", "running", "queued"].includes(status)) return "warn";
  if (["error"].includes(status)) return "bad";
  return "neutral";
}

function aacoreTone(status) {
  if (status === "enriched") return "good";
  if (status === "error") return "bad";
  return "neutral";
}

function renderSummary(summary) {
  const cards = [
    ["Prospects", summary.total_prospects],
    ["En cola", summary.queued],
    ["Propuestas listas", summary.proposal_ready],
    ["Recomendados", summary.recommended],
    ["Mensajes pendientes", summary.needs_reply],
    ["Telegram", summary.telegram_configured ? "OK" : "No config"],
  ];
  document.getElementById("summaryCards").innerHTML = cards
    .map(([label, value]) => `<article class="card"><span>${label}</span><strong>${escapeHtml(value)}</strong></article>`)
    .join("");
}

function renderProspects(prospects) {
  document.getElementById("prospectCount").textContent = `${prospects.length} registrados`;
  const tbody = document.getElementById("prospectsBody");
  if (!prospects.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-cell">Todavia no hay prospects.</td></tr>`;
    return;
  }

  tbody.innerHTML = prospects
    .map((prospect) => {
      const selected = prospect.id === state.selectedProspectId ? "selected-row" : "";
      const recommendation = prospect.recommended ? badge("Recomendado", "good") : "";
      return `
        <tr class="${selected}" data-prospect-id="${prospect.id}">
          <td>
            <div>${escapeHtml(prospect.company_name || prospect.website || prospect.id)}</div>
            ${recommendation ? `<div class="inline-tags">${recommendation}</div>` : ""}
          </td>
          <td>${badge(prospect.status || "-", statusTone(prospect.status))}</td>
          <td>${badge(prospect.route || "-", "neutral")}</td>
          <td>${badge(prospect.fit_score ?? "-", scoreTone(prospect.fit_score))}</td>
          <td>${badge(prospect.aacore_status || "-", aacoreTone(prospect.aacore_status))}</td>
          <td>${escapeHtml(prospect.country || "-")}</td>
          <td>${escapeHtml(prospect.updated_at || "-")}</td>
        </tr>
      `;
    })
    .join("");

  tbody.querySelectorAll("tr[data-prospect-id]").forEach((row) => {
    row.addEventListener("click", () => selectProspect(row.dataset.prospectId));
  });
}

function renderEvents(events) {
  const container = document.getElementById("eventsList");
  container.innerHTML = events.length
    ? events
        .map(
          (event) => `
        <article class="list-item">
          <div class="list-meta">
            ${badge(event.type, statusTone(event.level))}
            <span>${escapeHtml(event.created_at)}</span>
          </div>
          <p>${escapeHtml(event.message)}</p>
        </article>`
        )
        .join("")
    : `<div class="empty-state">Sin eventos todavia.</div>`;
}

function renderJobs(jobs) {
  const container = document.getElementById("jobsList");
  container.innerHTML = jobs.length
    ? jobs
        .map(
          (job) => `
        <article class="list-item">
          <div class="list-meta">
            ${badge(job.type, "neutral")}
            ${badge(job.status, statusTone(job.status))}
          </div>
          <p>${escapeHtml(job.summary || job.error || "En ejecucion")}</p>
        </article>`
        )
        .join("")
    : `<div class="empty-state">Sin jobs todavia.</div>`;
}

function renderMessages(messages) {
  const container = document.getElementById("messagesList");
  container.innerHTML = messages.length
    ? messages
        .map(
          (message) => `
        <article class="list-item">
          <div class="list-meta">
            ${badge(message.channel || "manual", "neutral")}
            ${badge(message.status, statusTone(message.status))}
          </div>
          <p>${escapeHtml(message.content)}</p>
          ${message.reply_draft ? `<pre class="code-block">${escapeHtml(message.reply_draft)}</pre>` : ""}
        </article>`
        )
        .join("")
    : `<div class="empty-state">Sin mensajes.</div>`;
}

function renderProspectDetail(detail) {
  const hint = document.getElementById("detailHint");
  const container = document.getElementById("detailContent");
  const { prospect, artifacts, events, messages } = detail;
  hint.textContent = prospect.company_name || prospect.website || prospect.id;

  const socials = Object.entries(prospect.socials || {})
    .map(([name, value]) => `<li><strong>${escapeHtml(name)}</strong>: <a href="${escapeHtml(value)}" target="_blank" rel="noreferrer">${escapeHtml(value)}</a></li>`)
    .join("");

  container.innerHTML = `
    <div class="detail-grid">
      <section>
        <h3>Ficha</h3>
        <ul class="meta-list">
          <li><strong>Estado</strong>: ${badge(prospect.status || "-", statusTone(prospect.status))}</li>
          <li><strong>Ruta</strong>: ${badge(prospect.route || "-", "neutral")}</li>
          <li><strong>Ruta forzada</strong>: ${escapeHtml(prospect.route_override || "-")}</li>
          <li><strong>Fit</strong>: ${badge(prospect.fit_score ?? "-", scoreTone(prospect.fit_score))}</li>
          <li><strong>Fit raw</strong>: ${escapeHtml(prospect.fit_score_raw ?? prospect.fit_score ?? "-")}</li>
          <li><strong>Modo decision</strong>: ${escapeHtml(prospect.decision_mode || "automatic")}</li>
          <li><strong>Recomendacion</strong>: ${prospect.recommended ? badge("Activa", "good") : badge("No", "neutral")}</li>
          <li><strong>Angulo estrategico</strong>: ${escapeHtml(prospect.strategic_angle_label || "-")}</li>
          <li><strong>Idioma</strong>: ${escapeHtml(prospect.language || "-")}</li>
          <li><strong>Moneda</strong>: ${escapeHtml(prospect.currency || "-")}</li>
          <li><strong>Website</strong>: ${prospect.website ? `<a href="${escapeHtml(prospect.website)}" target="_blank" rel="noreferrer">${escapeHtml(prospect.website)}</a>` : "-"}</li>
          <li><strong>Sector</strong>: ${escapeHtml(prospect.sector || "-")}</li>
          <li><strong>Notas</strong>: ${escapeHtml(prospect.notes || "-")}</li>
          <li><strong>Nota recomendacion</strong>: ${escapeHtml(prospect.recommendation_note || "-")}</li>
        </ul>
        ${socials ? `<h4>Redes</h4><ul class="meta-list">${socials}</ul>` : ""}
      </section>
      <section>
        <h3>Decision manual</h3>
        <form id="overrideForm">
          <input type="hidden" name="prospect_id" value="${escapeHtml(prospect.id)}" />
          <label class="checkbox-row">
            <span>Marcar como recomendacion</span>
            <input type="checkbox" name="recommended" ${prospect.recommended ? "checked" : ""} />
            <small>Si esta activo, el prospecto puede desbloquear propuesta aunque el fit bruto sea bajo.</small>
          </label>
          <label>
            Forzar ruta
            <select name="route_override">
              ${routeOptions(prospect.route_override)}
            </select>
          </label>
          <label>
            Nota recomendacion
            <textarea name="recommendation_note" rows="3" placeholder="Motivo interno de la excepcion">${escapeHtml(prospect.recommendation_note || "")}</textarea>
          </label>
          <label class="checkbox-row">
            <span>Reencolar ahora</span>
            <input type="checkbox" name="requeue" checked />
            <small>Vuelve a pasar por el worker con estas decisiones aplicadas.</small>
          </label>
          <button type="submit">Guardar decision manual</button>
        </form>
        <p id="overrideStatus" class="subtle"></p>

        <h3 class="section-gap">Registrar mensaje entrante</h3>
        <form id="messageForm">
          <input type="hidden" name="prospect_id" value="${escapeHtml(prospect.id)}" />
          <label>
            Canal
            <select name="channel">
              <option value="telegram">Telegram</option>
              <option value="email">Email</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="manual">Manual</option>
            </select>
          </label>
          <label>
            Contenido
            <textarea name="content" rows="5" placeholder="Pega aqui el mensaje entrante"></textarea>
          </label>
          <button type="submit">Crear borrador automatico</button>
        </form>
        <p id="messageStatus" class="subtle"></p>
      </section>
    </div>

    ${prospect.aacore_status === "enriched" ? `
    <section class="outreach-panel">
      <h3>Outreach listo</h3>
      <div class="outreach-meta">
        <div class="audit-score-block">
          <span class="audit-label">Auditoría web</span>
          <div class="audit-bar-wrap">
            <div class="audit-bar" style="width: ${(prospect.auditoria_score || 0) * 10}%"></div>
          </div>
          <span class="audit-score-num">${escapeHtml(prospect.auditoria_score ?? "-")}/10</span>
          ${prospect.prioridad ? badge(prospect.prioridad, prospect.prioridad === "alta" ? "good" : prospect.prioridad === "baja" ? "bad" : "warn") : ""}
        </div>
        ${prospect.contacto_email ? `
        <div class="contact-block">
          <span class="contact-email">${escapeHtml(prospect.contacto_email)}</span>
          <button class="copy-btn" data-copy="${escapeHtml(prospect.contacto_email)}">Copiar email</button>
        </div>` : ""}
      </div>
      ${prospect.auditoria_resumen ? `<p class="audit-resumen">${escapeHtml(prospect.auditoria_resumen)}</p>` : ""}
      ${prospect.email_frio ? `
      <div class="outreach-block">
        <div class="outreach-block-header">
          <span>Email frío</span>
          <button class="copy-btn" data-copy="${escapeHtml((prospect.asunto_email ? "Asunto: " + prospect.asunto_email + "\n\n" : "") + prospect.email_frio)}">Copiar todo</button>
        </div>
        ${prospect.asunto_email ? `<div class="outreach-subject">Asunto: ${escapeHtml(prospect.asunto_email)}</div>` : ""}
        <pre class="outreach-body">${escapeHtml(prospect.email_frio)}</pre>
      </div>` : ""}
      ${prospect.mensaje_linkedin ? `
      <div class="outreach-block">
        <div class="outreach-block-header">
          <span>LinkedIn</span>
          <button class="copy-btn" data-copy="${escapeHtml(prospect.mensaje_linkedin)}">Copiar</button>
        </div>
        <pre class="outreach-body">${escapeHtml(prospect.mensaje_linkedin)}</pre>
      </div>` : ""}
    </section>` : ""}

    <section class="artifact-section">
      <h3>Artefactos</h3>
      ${artifacts.length ? artifacts.map((artifact) => `
        <details class="artifact-item">
          <summary>${escapeHtml(artifact.name)}</summary>
          <pre class="code-block">${escapeHtml(artifact.content)}</pre>
        </details>
      `).join("") : `<div class="empty-state">Todavia no hay artefactos generados.</div>`}
    </section>

    <section class="detail-grid">
      <section>
        <h3>Eventos del prospecto</h3>
        <div class="stack-list">
          ${events.length ? events.map((event) => `<article class="list-item"><div class="list-meta">${badge(event.type, statusTone(event.level))}<span>${escapeHtml(event.created_at)}</span></div><p>${escapeHtml(event.message)}</p></article>`).join("") : `<div class="empty-state">Sin eventos.</div>`}
        </div>
      </section>
      <section>
        <h3>Mensajes del prospecto</h3>
        <div class="stack-list">
          ${messages.length ? messages.map((message) => `<article class="list-item"><div class="list-meta">${badge(message.channel || 'manual', 'neutral')}${badge(message.status, statusTone(message.status))}</div><p>${escapeHtml(message.content)}</p>${message.reply_draft ? `<pre class="code-block">${escapeHtml(message.reply_draft)}</pre>` : ''}</article>`).join("") : `<div class="empty-state">Sin mensajes.</div>`}
        </div>
      </section>
    </section>
  `;

  const overrideForm = document.getElementById("overrideForm");
  overrideForm.addEventListener("submit", submitOverrideForm);
  const messageForm = document.getElementById("messageForm");
  messageForm.addEventListener("submit", submitMessageForm);

  container.querySelectorAll(".copy-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      navigator.clipboard.writeText(btn.dataset.copy || "").then(() => {
        const original = btn.textContent;
        btn.textContent = "✓ Copiado";
        setTimeout(() => { btn.textContent = original; }, 1500);
      });
    });
  });
}

async function loadDashboard({ preserveSelection = true } = {}) {
  const payload = await requestJson("/api/dashboard");
  state.dashboard = payload;
  if (!preserveSelection && payload.prospects.length) {
    state.selectedProspectId = payload.prospects[0].id;
  }
  renderSummary(payload.summary);
  renderProspects(payload.prospects);
  renderEvents(payload.events);
  renderJobs(payload.jobs);
  renderMessages(payload.messages);
  if (state.selectedProspectId) {
    await selectProspect(state.selectedProspectId, false);
  }
}

async function selectProspect(prospectId, rerenderTable = true) {
  state.selectedProspectId = prospectId;
  if (rerenderTable && state.dashboard) {
    renderProspects(state.dashboard.prospects);
  }
  const detail = await requestJson(`/api/prospects/${prospectId}`);
  renderProspectDetail(detail);
}

async function submitProspectForm(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const status = document.getElementById("formStatus");
  status.textContent = "Enviando a cola...";

  const data = new FormData(form);
  const payload = {
    company_name: data.get("company_name"),
    website: data.get("website"),
    country: data.get("country"),
    sector: data.get("sector"),
    notes: data.get("notes"),
    recommended: form.elements.recommended.checked,
    recommendation_note: data.get("recommendation_note"),
    route_override: data.get("route_override") || null,
    socials: {
      instagram: data.get("instagram"),
      linkedin: data.get("linkedin"),
      facebook: data.get("facebook"),
      youtube: data.get("youtube"),
    },
  };

  try {
    const response = await requestJson("/api/prospects", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    status.textContent = "Prospecto creado y enviado a cola.";
    form.reset();
    await loadDashboard({ preserveSelection: false });
    state.selectedProspectId = response.prospect.id;
    await selectProspect(response.prospect.id);
  } catch (error) {
    status.textContent = error.message;
  }
}

async function submitOverrideForm(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const status = document.getElementById("overrideStatus");
  const data = new FormData(form);
  status.textContent = "Guardando decision manual...";

  try {
    await requestJson(`/api/prospects/${data.get("prospect_id")}/update`, {
      method: "POST",
      body: JSON.stringify({
        recommended: form.elements.recommended.checked,
        recommendation_note: data.get("recommendation_note"),
        route_override: data.get("route_override") || null,
        requeue: form.elements.requeue.checked,
      }),
    });
    status.textContent = "Decision manual guardada.";
    await loadDashboard();
    await selectProspect(state.selectedProspectId, false);
  } catch (error) {
    status.textContent = error.message;
  }
}

async function submitMessageForm(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const status = document.getElementById("messageStatus");
  const data = new FormData(form);
  status.textContent = "Registrando mensaje...";
  try {
    await requestJson("/api/messages", {
      method: "POST",
      body: JSON.stringify({
        prospect_id: data.get("prospect_id"),
        channel: data.get("channel"),
        content: data.get("content"),
        direction: "inbound",
      }),
    });
    status.textContent = "Mensaje registrado. El worker preparara un borrador.";
    form.reset();
    await loadDashboard();
    await selectProspect(state.selectedProspectId, false);
  } catch (error) {
    status.textContent = error.message;
  }
}

async function runWorkerOnce() {
  const result = await requestJson("/api/worker/run-once", { method: "POST", body: JSON.stringify({}) });
  await loadDashboard();
  if (state.selectedProspectId) {
    await selectProspect(state.selectedProspectId, false);
  }
  return result;
}

document.getElementById("prospectForm").addEventListener("submit", submitProspectForm);
document.getElementById("refreshButton").addEventListener("click", () => loadDashboard());
document.getElementById("runWorkerButton").addEventListener("click", runWorkerOnce);

loadDashboard({ preserveSelection: false }).catch((error) => {
  document.getElementById("formStatus").textContent = error.message;
});

setInterval(() => {
  loadDashboard().catch(() => {});
}, 5000);
