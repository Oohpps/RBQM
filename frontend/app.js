import { icons, scoreColumnsByMetric, thresholds } from './js/config.js';
import { translations } from './js/i18n.js';
import { bindMappingWizardEvents, closeMappingWizard, uploadFiles } from './js/mappingWizard.js';

let kriEnabled = true;
let currentState = null;
let refreshTimer = null;
let currentLanguage = localStorage.getItem("rbqm.language") || "zh";
let currentTheme = localStorage.getItem("rbqm.theme") || "light";
const thresholdRailWidth = {
  default: 352,
  min: 280,
  max: 560,
  storageKey: "rbqm.thresholdRailWidth",
};
function mountIcons() {
  document.querySelectorAll("[data-icon]").forEach((node) => {
    const icon = icons[node.dataset.icon];
    if (icon) node.innerHTML = icon;
  });
}

function t(key, values = {}) {
  let text = translations[currentLanguage]?.[key] || translations.zh[key] || key;
  Object.entries(values).forEach(([name, value]) => {
    text = text.replace(`{${name}}`, value);
  });
  return text;
}

function localized(value) {
  if (typeof value === "string") return value;
  return value[currentLanguage] || value.zh || "";
}

function applyLanguage() {
  document.documentElement.lang = currentLanguage === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-lang-option]").forEach((button) => {
    button.classList.toggle("active", button.dataset.langOption === currentLanguage);
  });
  renderThresholds();
  if (currentState) renderState(currentState);
}

function applyTheme() {
  document.body.dataset.theme = currentTheme;
  document.querySelectorAll("[data-theme-option]").forEach((button) => {
    button.classList.toggle("active", button.dataset.themeOption === currentTheme);
  });
}

function thresholdParams() {
  const params = new URLSearchParams();
  params.set("kri_enabled", kriEnabled ? "true" : "false");
  params.set("enabled_metrics", kriEnabled ? thresholds.filter((item) => item.enabled).map((item) => item.key).join(",") : "");
  thresholds.forEach((item) => params.set(item.key, item.value));
  return params;
}

function updateRangeFill(input, item) {
  const percent = ((Number(input.value) - item.min) / (item.max - item.min)) * 100;
  input.style.setProperty("--pct", `${percent}%`);
}

function renderThresholds() {
  const root = document.getElementById("thresholdControls");
  root.innerHTML = "";
  const enabledCount = kriEnabled ? thresholds.filter((item) => item.enabled).length : 0;
  const master = document.createElement("div");
  master.className = `threshold-master ${kriEnabled ? "" : "off"}`;
  master.innerHTML = `
    <div>
      <div class="threshold-master-title">${t("threshold.master")}</div>
      <div class="threshold-master-note">${kriEnabled ? t("threshold.enabled", { count: enabledCount, total: thresholds.length }) : t("threshold.disabled")}</div>
    </div>
    <label class="switch-control" title="启用或关闭全部KRI阈值">
      <input type="checkbox" ${kriEnabled ? "checked" : ""} />
      <span class="switch-track"></span>
    </label>
  `;
  root.appendChild(master);
  master.querySelector("input").addEventListener("change", (event) => {
    kriEnabled = event.target.checked;
    renderThresholds();
    scheduleRefresh();
  });

  thresholds.forEach((item) => {
    const active = kriEnabled && item.enabled;
    const block = document.createElement("div");
    block.className = `threshold-control ${active ? "" : "disabled"}`;
    block.innerHTML = `
      <div class="threshold-row">
        <div class="threshold-name">
          <span class="threshold-chip">${localized(item.group)}</span>
          <span class="threshold-label">${localized(item.label)}</span>
          <span class="threshold-value" id="value-${item.key}">${item.value.toFixed(item.decimals)}</span>
        </div>
        <label class="switch-control metric-switch" title="启用或关闭该KRI指标">
          <input type="checkbox" ${item.enabled ? "checked" : ""} ${kriEnabled ? "" : "disabled"} />
          <span class="switch-track"></span>
        </label>
      </div>
      <input id="slider-${item.key}" type="range" min="${item.min}" max="${item.max}" step="${item.step}" value="${item.value}" ${active ? "" : "disabled"} />
    `;
    root.appendChild(block);
    const metricToggle = block.querySelector(".metric-switch input");
    metricToggle.addEventListener("change", () => {
      item.enabled = metricToggle.checked;
      renderThresholds();
      scheduleRefresh();
    });
    const slider = block.querySelector('input[type="range"]');
    updateRangeFill(slider, item);
    slider.addEventListener("input", () => {
      item.value = Number(slider.value);
      document.getElementById(`value-${item.key}`).textContent = item.value.toFixed(item.decimals);
      updateRangeFill(slider, item);
      scheduleRefresh();
    });
  });
}

function scheduleRefresh() {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(loadState, 240);
}

async function loadState() {
  const res = await fetch(`/api/state?${thresholdParams().toString()}`);
  if (!res.ok) throw new Error("加载数据失败");
  currentState = await res.json();
  renderState(currentState);
}

async function resetDemo() {
  const res = await fetch(`/api/demo?${thresholdParams().toString()}`, { method: "POST" });
  if (!res.ok) throw new Error("切换示例数据失败");
  currentState = await res.json();
  renderState(currentState);
}

function renderState(state) {
  document.getElementById("dataHint").textContent = state.using_demo_data
    ? t("hint.demo")
    : t("hint.uploaded");
  document.getElementById("sampleToggle").checked = Boolean(state.using_demo_data);

  renderTable("domainTable", state.domain_summary, ["数据域", "行数", "列数", "已识别中心列", "已识别受试者列"]);
  renderFields(state.fields);
  renderOverview(state.overview);

  const rawCard = document.getElementById("rawUploadCard");
  rawCard.classList.toggle("hidden", !state.raw_summary.length);
  if (state.raw_summary.length) {
    renderTable("rawSummaryTable", state.raw_summary, ["数据集", "行数", "列数"]);
  }

  renderTable("metricsTable", state.metrics, null, 12);
  renderTable("rankingTable", state.metrics, ["中心", "受试者数", "风险评分", "风险等级", "缺失率", "延迟录入率"], 30);
  renderTable("signalsTable", state.signals, null, 30);
  renderTable("actionsTable", state.action_log, null, 30);
}

function visibleMetricRows(rows) {
  if (!rows.length) return rows;
  const disabledScoreColumns = new Set();
  thresholds
    .filter((item) => !kriEnabled || !item.enabled)
    .forEach((item) => {
      (scoreColumnsByMetric[item.key] || []).forEach((column) => disabledScoreColumns.add(column));
    });

  return rows.map((row) => {
    const next = { ...row };
    disabledScoreColumns.forEach((column) => delete next[column]);
    return next;
  });
}

function renderTable(id, rows, preferredColumns = null, limit = null) {
  const table = document.getElementById(id);
  const sourceRows = id === "metricsTable" ? visibleMetricRows(rows) : rows;
  const data = limit ? sourceRows.slice(0, limit) : sourceRows;
  if (!data.length) {
    table.innerHTML = `<tbody><tr><td>${t("empty")}</td></tr></tbody>`;
    return;
  }
  const columns = preferredColumns || Object.keys(data[0]);
  const head = `<thead><tr>${columns.map((col) => `<th class="${isNumericColumn(data, col) ? "number" : ""}">${col}</th>`).join("")}</tr></thead>`;
  const body = data
    .map((row) => `<tr>${columns.map((col) => cell(row[col], isNumericColumn(data, col))).join("")}</tr>`)
    .join("");
  table.innerHTML = `${head}<tbody>${body}</tbody>`;
}

function isNumericColumn(rows, column) {
  return rows.some((row) => typeof row[column] === "number");
}

function cell(value, numeric) {
  let display = value ?? "";
  if (typeof value === "number") {
    display = Math.abs(value) < 1 ? value.toFixed(3) : Number.isInteger(value) ? value : value.toFixed(2);
  }
  return `<td class="${numeric ? "number" : ""}">${display}</td>`;
}

function renderFields(fields) {
  const root = document.getElementById("fieldList");
  root.innerHTML = fields
    .map(
      (item) => `
        <div class="field-row">
          <span class="field-domain">${item.domain}：</span>
          <span>${item.fields.map((field) => `<span class="field-chip">${field}</span>`).join("")}</span>
        </div>
      `,
    )
    .join("");
}

function renderOverview(overview) {
  const root = document.getElementById("overviewCards");
  root.innerHTML = Object.entries(overview)
    .map(
      ([label, value]) => `
        <div class="metric-card">
          <div class="metric-label">${label}</div>
          <div class="metric-value">${value}</div>
        </div>
      `,
    )
    .join("");
}

function activateTab(tab) {
  document.querySelectorAll(".top-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tab);
  });
  document.querySelectorAll(".tab-page").forEach((page) => {
    page.classList.toggle("active", page.id === `tab-${tab}`);
  });
}

function clampThresholdRailWidth(width) {
  return Math.min(thresholdRailWidth.max, Math.max(thresholdRailWidth.min, Math.round(width)));
}

function setThresholdRailWidth(width, persist = true) {
  const workspace = document.querySelector(".workspace");
  const handle = document.getElementById("thresholdResizeHandle");
  if (!workspace) return;
  const nextWidth = clampThresholdRailWidth(width);
  workspace.style.setProperty("--threshold-rail-width", `${nextWidth}px`);
  if (handle) {
    handle.setAttribute("aria-valuemin", String(thresholdRailWidth.min));
    handle.setAttribute("aria-valuemax", String(thresholdRailWidth.max));
    handle.setAttribute("aria-valuenow", String(nextWidth));
  }
  if (persist) {
    localStorage.setItem(thresholdRailWidth.storageKey, String(nextWidth));
  }
}

function initThresholdRailResize() {
  const workspace = document.querySelector(".workspace");
  const handle = document.getElementById("thresholdResizeHandle");
  if (!workspace || !handle) return;

  const savedWidth = Number(localStorage.getItem(thresholdRailWidth.storageKey));
  setThresholdRailWidth(Number.isFinite(savedWidth) && savedWidth > 0 ? savedWidth : thresholdRailWidth.default, false);

  const widthFromPointer = (clientX) => {
    const rect = workspace.getBoundingClientRect();
    return clientX - rect.left;
  };

  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    document.body.classList.add("threshold-resizing");
  });

  handle.addEventListener("pointermove", (event) => {
    if (!document.body.classList.contains("threshold-resizing")) return;
    setThresholdRailWidth(widthFromPointer(event.clientX));
  });

  const stopResize = () => {
    document.body.classList.remove("threshold-resizing");
  };
  handle.addEventListener("pointerup", stopResize);
  handle.addEventListener("pointercancel", stopResize);

  handle.addEventListener("dblclick", () => {
    setThresholdRailWidth(thresholdRailWidth.default);
  });

  handle.addEventListener("keydown", (event) => {
    const current = Number(handle.getAttribute("aria-valuenow")) || thresholdRailWidth.default;
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      setThresholdRailWidth(current - 16);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      setThresholdRailWidth(current + 16);
    } else if (event.key === "Home") {
      event.preventDefault();
      setThresholdRailWidth(thresholdRailWidth.min);
    } else if (event.key === "End") {
      event.preventDefault();
      setThresholdRailWidth(thresholdRailWidth.max);
    }
  });
}

function bindEvents() {
  const sidebarToggle = document.getElementById("sidebarToggle");
  if (sidebarToggle) sidebarToggle.addEventListener("click", () => {
    const collapsed = document.body.classList.toggle("sidebar-collapsed");
    sidebarToggle.setAttribute("aria-label", collapsed ? "展开左侧菜单" : "收起左侧菜单");
  });

  document.querySelectorAll(".top-tab").forEach((button) => {
    button.addEventListener("click", () => activateTab(button.dataset.tab));
  });

  const fileInput = document.getElementById("fileInput");
  if (fileInput) fileInput.addEventListener("change", (event) => {
    uploadFiles(event.target.files, { thresholdParams, t, activateTab, renderState });
  });
  bindMappingWizardEvents({ thresholdParams, t, activateTab, renderState });

  const sampleToggle = document.getElementById("sampleToggle");
  if (sampleToggle) sampleToggle.addEventListener("change", (event) => {
    if (event.target.checked) {
      closeMappingWizard();
      resetDemo();
    }
  });

  const exportButton = document.getElementById("exportButton");
  if (exportButton) exportButton.addEventListener("click", () => {
    window.location.href = `/api/export?${thresholdParams().toString()}`;
  });

  const settingsButton = document.getElementById("settingsButton");
  const settingsMenu = document.getElementById("settingsMenu");
  if (settingsButton && settingsMenu) {
    settingsButton.addEventListener("click", (event) => {
      event.stopPropagation();
      const open = settingsMenu.classList.toggle("hidden");
      settingsButton.setAttribute("aria-expanded", String(!open));
    });
    settingsMenu.addEventListener("click", (event) => event.stopPropagation());
    document.addEventListener("click", () => {
      settingsMenu.classList.add("hidden");
      settingsButton.setAttribute("aria-expanded", "false");
    });
  }

  document.querySelectorAll("[data-lang-option]").forEach((button) => {
    button.addEventListener("click", () => {
      currentLanguage = button.dataset.langOption;
      localStorage.setItem("rbqm.language", currentLanguage);
      applyLanguage();
    });
  });

  document.querySelectorAll("[data-theme-option]").forEach((button) => {
    button.addEventListener("click", () => {
      currentTheme = button.dataset.themeOption;
      localStorage.setItem("rbqm.theme", currentTheme);
      applyTheme();
    });
  });
}

mountIcons();
applyTheme();
applyLanguage();
initThresholdRailResize();
bindEvents();
loadState().catch((error) => {
  console.error(error);
  alert(t("alert.load"));
});
