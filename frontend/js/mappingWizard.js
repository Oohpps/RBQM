let pendingUploadFiles = [];
let mappingPreview = null;
let mappingSelections = {};
let mappingStep = 1;
let mappingDeps = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function bindMappingWizardEvents(deps) {
  mappingDeps = deps;
  const mappingBackButton = document.getElementById("mappingBackButton");
  if (mappingBackButton) mappingBackButton.addEventListener("click", () => {
    mappingStep = Math.max(1, mappingStep - 1);
    renderMappingWizard();
  });

  const mappingNextButton = document.getElementById("mappingNextButton");
  if (mappingNextButton) mappingNextButton.addEventListener("click", () => {
    mappingStep = Math.min(3, mappingStep + 1);
    renderMappingWizard();
  });

  const mappingCommitButton = document.getElementById("mappingCommitButton");
  if (mappingCommitButton) mappingCommitButton.addEventListener("click", () => {
    commitMappedUpload();
  });

  const mappingCancelButton = document.getElementById("mappingCancelButton");
  if (mappingCancelButton) mappingCancelButton.addEventListener("click", () => {
    closeMappingWizard();
  });
}

export async function uploadFiles(files, deps) {
  mappingDeps = deps;
  if (!files.length) return;
  pendingUploadFiles = Array.from(files);
  const formData = new FormData();
  pendingUploadFiles.forEach((file) => formData.append("files", file));
  const res = await fetch("/api/upload/preview", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    alert(payload.detail || mappingDeps.t("alert.preview"));
    return;
  }
  mappingPreview = await res.json();
  mappingSelections = {};
  mappingPreview.sources.forEach((source) => {
    mappingSelections[source.source_id] = { domain: source.guessed_domain || "", fields: {} };
    initializeFieldMapping(source.source_id);
  });
  mappingStep = 1;
  mappingDeps.activateTab("import");
  renderMappingWizard();
}

function normalizeName(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^\w]+/gu, "_")
    .replace(/^_+|_+$/g, "");
}

function domainSpec(domain) {
  return mappingPreview?.domains.find((item) => item.key === domain) || null;
}

function sourceSpec(sourceId) {
  return mappingPreview?.sources.find((item) => item.source_id === sourceId) || null;
}

function guessColumnForField(source, field) {
  const normalizedField = normalizeName(field);
  return source.columns.find((column) => normalizeName(column) === normalizedField)
    || source.columns.find((column) => normalizeName(column).includes(normalizedField))
    || "";
}

function initializeFieldMapping(sourceId) {
  const selection = mappingSelections[sourceId];
  const source = sourceSpec(sourceId);
  const spec = domainSpec(selection?.domain);
  if (!selection || !source || !spec) return;
  const previous = selection.fields || {};
  selection.fields = {};
  spec.fields.forEach((field) => {
    selection.fields[field] = previous[field] || guessColumnForField(source, field);
  });
}

function selectedSources() {
  if (!mappingPreview) return [];
  return mappingPreview.sources.filter((source) => mappingSelections[source.source_id]?.domain);
}

function mappingConfig() {
  const sources = {};
  selectedSources().forEach((source) => {
    const selection = mappingSelections[source.source_id];
    const fields = {};
    Object.entries(selection.fields || {}).forEach(([field, column]) => {
      if (column) fields[field] = column;
    });
    sources[source.source_id] = { domain: selection.domain, fields };
  });
  return { sources };
}

function mappingWarnings() {
  const warnings = [];
  selectedSources().forEach((source) => {
    const selection = mappingSelections[source.source_id];
    const spec = domainSpec(selection.domain);
    (spec?.required_fields || []).forEach((field) => {
      if (!selection.fields?.[field]) warnings.push(`${source.source_id}: ${mappingDeps.t("mapping.missing")} ${field}`);
    });
  });
  if (!selectedSources().length) warnings.push(mappingDeps.t("mapping.noSources"));
  return warnings;
}

function renderMappingWizard() {
  const root = document.getElementById("mappingWizard");
  const body = document.getElementById("mappingWizardBody");
  if (!root || !body || !mappingPreview) return;
  root.classList.remove("hidden");
  document.querySelectorAll(".wizard-step").forEach((step) => {
    step.classList.toggle("active", Number(step.dataset.stepLabel) === mappingStep);
  });
  if (mappingStep === 1) renderDomainStep(body);
  if (mappingStep === 2) renderFieldStep(body);
  if (mappingStep === 3) renderConfirmStep(body);
  document.getElementById("mappingBackButton").disabled = mappingStep === 1;
  document.getElementById("mappingNextButton").classList.toggle("hidden", mappingStep === 3);
  document.getElementById("mappingCommitButton").classList.toggle("hidden", mappingStep !== 3);
}

function renderDomainStep(body) {
  const domainOptions = [`<option value="">${mappingDeps.t("mapping.skip")}</option>`]
    .concat(mappingPreview.domains.map((domain) => `<option value="${escapeHtml(domain.key)}">${escapeHtml(domain.label)}</option>`))
    .join("");
  body.innerHTML = `
    <div class="mapping-table">
      ${mappingPreview.sources.map((source) => {
        return `
          <div class="mapping-row">
            <div>
              <div class="mapping-source">${escapeHtml(source.source_id)}</div>
              <div class="mapping-meta">${mappingDeps.t("mapping.rows")} ${source.rows} · ${mappingDeps.t("mapping.columns")} ${source.columns.length}</div>
              <div class="mapping-chips">${source.columns.slice(0, 8).map((column) => `<span>${escapeHtml(column)}</span>`).join("")}</div>
            </div>
            <label>
              <span>${mappingDeps.t("mapping.domain")}</span>
              <select data-domain-source="${escapeHtml(source.source_id)}">${domainOptions}</select>
            </label>
          </div>
        `;
      }).join("")}
    </div>
  `;
  body.querySelectorAll("[data-domain-source]").forEach((select) => {
    const sourceId = select.dataset.domainSource;
    select.value = mappingSelections[sourceId]?.domain || "";
    select.addEventListener("change", () => {
      mappingSelections[sourceId].domain = select.value;
      initializeFieldMapping(sourceId);
      renderMappingWizard();
    });
  });
}

function renderFieldStep(body) {
  const sources = selectedSources();
  if (!sources.length) {
    body.innerHTML = `<div class="mapping-empty">${mappingDeps.t("mapping.noSources")}</div>`;
    return;
  }
  body.innerHTML = sources.map((source) => {
    const selection = mappingSelections[source.source_id];
    const spec = domainSpec(selection.domain);
    const required = new Set(spec.required_fields || []);
    const columnOptions = [`<option value="">-</option>`]
      .concat(source.columns.map((column) => `<option value="${escapeHtml(column)}">${escapeHtml(column)}</option>`))
      .join("");
    return `
      <section class="field-map-card">
        <div class="mapping-source">${escapeHtml(source.source_id)} · ${escapeHtml(spec.label)}</div>
        <div class="field-map-grid">
          ${spec.fields.map((field) => `
            <label class="field-map-row">
              <span>
                <strong>${escapeHtml(field)}</strong>
                <small>${required.has(field) ? mappingDeps.t("mapping.required") : mappingDeps.t("mapping.optional")}</small>
              </span>
              <select data-field-source="${escapeHtml(source.source_id)}" data-field-name="${escapeHtml(field)}">${columnOptions}</select>
            </label>
          `).join("")}
        </div>
      </section>
    `;
  }).join("");
  body.querySelectorAll("[data-field-source]").forEach((select) => {
    const sourceId = select.dataset.fieldSource;
    const field = select.dataset.fieldName;
    select.value = mappingSelections[sourceId]?.fields?.[field] || "";
    select.addEventListener("change", () => {
      mappingSelections[sourceId].fields[field] = select.value;
    });
  });
}

function renderConfirmStep(body) {
  const warnings = mappingWarnings();
  const config = mappingConfig();
  body.innerHTML = `
    <div class="mapping-confirm ${warnings.length ? "has-warnings" : ""}">
      <div>${warnings.length ? warnings.map((item) => `<p>${escapeHtml(item)}</p>`).join("") : mappingDeps.t("mapping.ready")}</div>
      <div class="mapping-summary">
        ${Object.entries(config.sources).map(([sourceId, configItem]) => {
          const spec = domainSpec(configItem.domain);
          return `<div><strong>${escapeHtml(sourceId)}</strong><span>${escapeHtml(spec?.label || configItem.domain)} · ${Object.keys(configItem.fields).length} fields</span></div>`;
        }).join("")}
      </div>
    </div>
  `;
}

export function closeMappingWizard() {
  pendingUploadFiles = [];
  mappingPreview = null;
  mappingSelections = {};
  mappingStep = 1;
  const root = document.getElementById("mappingWizard");
  if (root) root.classList.add("hidden");
  const fileInput = document.getElementById("fileInput");
  if (fileInput) fileInput.value = "";
}

async function commitMappedUpload() {
  if (!pendingUploadFiles.length) return;
  const formData = new FormData();
  pendingUploadFiles.forEach((file) => formData.append("files", file));
  formData.append("mapping_config", JSON.stringify(mappingConfig()));
  const res = await fetch(`/api/upload/commit?${mappingDeps.thresholdParams().toString()}`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    alert(payload.detail || mappingDeps.t("alert.upload"));
    return;
  }
  const nextState = await res.json();
  document.getElementById("sampleToggle").checked = false;
  closeMappingWizard();
  mappingDeps.renderState(nextState);
}

