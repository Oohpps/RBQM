const icons = {
  grid: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect></svg>',
  lab: '<svg viewBox="0 0 24 24"><path d="M10 2v7.5L5.5 18a3 3 0 0 0 2.6 4h7.8a3 3 0 0 0 2.6-4L14 9.5V2"></path><path d="M8 2h8"></path><path d="M7 16h10"></path></svg>',
  sliders: '<svg viewBox="0 0 24 24"><path d="M4 7h7"></path><path d="M15 7h5"></path><path d="M13 5v4"></path><path d="M4 12h3"></path><path d="M11 12h9"></path><path d="M9 10v4"></path><path d="M4 17h10"></path><path d="M18 17h2"></path><path d="M16 15v4"></path></svg>',
  pin: '<svg viewBox="0 0 24 24"><path d="M12 21s7-5.4 7-12a7 7 0 1 0-14 0c0 6.6 7 12 7 12z"></path><circle cx="12" cy="9" r="2.5"></circle></svg>',
  chart: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"></rect><path d="M8 17v-5"></path><path d="M12 17V8"></path><path d="M16 17v-3"></path></svg>',
  upload: '<svg viewBox="0 0 24 24"><path d="M12 16V4"></path><path d="m7 9 5-5 5 5"></path><path d="M5 20h14"></path></svg>',
  info: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"></circle><path d="M12 11v5"></path><path d="M12 8h.01"></path></svg>',
  chevron: '<svg viewBox="0 0 24 24"><path d="m6 15 6-6 6 6"></path></svg>',
  bell: '<svg viewBox="0 0 24 24"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>',
  more: '<svg viewBox="0 0 24 24"><circle cx="12" cy="5" r="1.5"></circle><circle cx="12" cy="12" r="1.5"></circle><circle cx="12" cy="19" r="1.5"></circle></svg>',
  collapseLeft: '<svg viewBox="0 0 24 24"><path d="m15 18-6-6 6-6"></path></svg>',
};

const thresholds = [
  { key: "dlt_rate", label: { zh: "DLT发生率", en: "DLT Rate" }, group: { zh: "剂量安全", en: "Dose Safety" }, min: 0.01, max: 1, step: 0.01, value: 0.1, decimals: 2 },
  { key: "grade3_ae_rate", label: { zh: "≥3级AE发生率", en: "Grade ≥3 AE Rate" }, group: { zh: "剂量安全", en: "Dose Safety" }, min: 0.01, max: 2, step: 0.01, value: 0.2, decimals: 2 },
  { key: "safety_issues_per_subject", label: { zh: "SAE随访/报告缺口", en: "SAE Follow-up Gap" }, group: { zh: "安全复核", en: "Safety Review" }, min: 0.01, max: 1, step: 0.01, value: 0.15, decimals: 2 },
  { key: "dose_modification_rate", label: { zh: "毒性相关剂量调整率", en: "Toxicity Dose Modification" }, group: { zh: "给药管理", en: "Dosing" }, min: 0.01, max: 2, step: 0.01, value: 0.2, decimals: 2 },
  { key: "eligibility_deviation_rate", label: { zh: "入排标准偏离率", en: "Eligibility Deviation" }, group: { zh: "方案依从", en: "Protocol" }, min: 0.01, max: 1, step: 0.01, value: 0.1, decimals: 2 },
  { key: "pk_window_deviation_rate", label: { zh: "PK/PD采样窗偏离率", en: "PK/PD Window Deviation" }, group: { zh: "PK/PD", en: "PK/PD" }, min: 0.01, max: 1, step: 0.01, value: 0.15, decimals: 2 },
  { key: "tumor_assessment_issue_rate", label: { zh: "肿瘤评估缺失/延迟率", en: "Tumor Assessment Issue" }, group: { zh: "疗效评估", en: "Response" }, min: 0.01, max: 1, step: 0.01, value: 0.2, decimals: 2 },
  { key: "missing_rate", label: { zh: "关键数据缺失率", en: "Critical Data Missing" }, group: { zh: "数据质量", en: "Data Quality" }, min: 0.01, max: 0.3, step: 0.01, value: 0.1, decimals: 2 },
  { key: "late_entry_rate", label: { zh: "EDC延迟/未完成率", en: "Late / Incomplete EDC" }, group: { zh: "数据质量", en: "Data Quality" }, min: 0.01, max: 0.6, step: 0.01, value: 0.2, decimals: 2 },
  { key: "avg_entry_delay_days", label: { zh: "平均录入延迟（天）", en: "Avg Entry Delay Days" }, group: { zh: "数据质量", en: "Data Quality" }, min: 1, max: 30, step: 1, value: 7, decimals: 2 },
  { key: "open_queries_per_subject", label: { zh: "每受试者未关闭Query数", en: "Open Queries / Subject" }, group: { zh: "Query", en: "Query" }, min: 0.1, max: 5, step: 0.1, value: 1.5, decimals: 2 },
  { key: "avg_open_query_age_days", label: { zh: "未关闭Query平均龄期（天）", en: "Avg Open Query Age" }, group: { zh: "Query", en: "Query" }, min: 1, max: 60, step: 1, value: 21, decimals: 2 },
  { key: "lab_issues_per_subject", label: { zh: "未复核异常实验室率", en: "Unreviewed Lab Issue Rate" }, group: { zh: "实验室", en: "Labs" }, min: 0.01, max: 1, step: 0.01, value: 0.2, decimals: 2 },
  { key: "major_deviations_per_subject", label: { zh: "重大方案偏离率", en: "Major Deviation Rate" }, group: { zh: "方案依从", en: "Protocol" }, min: 0.01, max: 1, step: 0.01, value: 0.1, decimals: 2 },
];

thresholds.forEach((item) => {
  item.enabled = true;
});

const scoreColumnsByMetric = {
  dlt_rate: ["剂量安全评分"],
  grade3_ae_rate: ["剂量安全评分"],
  safety_issues_per_subject: ["安全性复核评分"],
  dose_modification_rate: ["给药调整评分"],
  eligibility_deviation_rate: ["方案依从性评分"],
  pk_window_deviation_rate: ["PK/PD完整性评分"],
  tumor_assessment_issue_rate: ["肿瘤评估评分"],
  missing_rate: ["数据质量评分"],
  late_entry_rate: ["数据质量评分"],
  avg_entry_delay_days: ["数据质量评分"],
  open_queries_per_subject: ["数据质量评分"],
  avg_open_query_age_days: ["数据质量评分"],
  lab_issues_per_subject: ["实验室与偏离评分"],
  major_deviations_per_subject: ["方案依从性评分"],
};

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

const translations = {
  zh: {
    "nav.collapse": "收起菜单",
    "nav.dashboard": "看板",
    "nav.studies": "研究",
    "nav.thresholds": "风险阈值",
    "nav.sites": "中心",
    "nav.reports": "报告",
    "upload.title": "上传临床研究数据",
    "upload.button": "上传研究数据",
    "upload.note": "200MB per file • CSV, XLSX, XLS",
    "sample.toggle": "使用示例数据",
    "tabs.import": "数据接入",
    "tabs.overview": "研究概览",
    "tabs.kri": "KRI监测",
    "tabs.ranking": "中心风险",
    "tabs.details": "信号详情",
    "tabs.actions": "行动闭环",
    "actions.deploy": "部署",
    "actions.export": "导出RBQM审查包",
    "settings.title": "设置",
    "settings.language": "语言",
    "settings.theme": "主题",
    "threshold.title": "KRI阈值设置",
    "threshold.master": "启用KRI阈值评估",
    "threshold.enabled": "已启用 {count}/{total} 项指标",
    "threshold.disabled": "已关闭，风险评分与信号暂停计算",
    "pages.import": "数据导入",
    "pages.overview": "研究总览",
    "pages.kri": "KRI看板",
    "pages.ranking": "中心风险排序",
    "pages.details": "风险信号详情",
    "pages.actions": "行动跟踪",
    "cards.raw": "已上传的原始数据集",
    "cards.domain": "已识别的数据域",
    "cards.fields": "支持的常见数据域与字段",
    "cards.kri": "中心KRI概览",
    "hint.demo": "当前使用示例数据。可在侧边栏上传CSV/XLSX文件查看自己的研究数据。",
    "hint.uploaded": "当前使用已上传的临床研究数据。",
    "empty": "暂无数据",
    "alert.load": "RBQM数据加载失败，请确认FastAPI服务已启动。",
    "alert.upload": "上传失败，未识别到可用数据域。",
  },
  en: {
    "nav.collapse": "Collapse Menu",
    "nav.dashboard": "Dashboard",
    "nav.studies": "Studies",
    "nav.thresholds": "Risk Thresholds",
    "nav.sites": "Sites",
    "nav.reports": "Reports",
    "upload.title": "Upload Clinical Trial Data",
    "upload.button": "Upload Trial Data",
    "upload.note": "200MB per file • CSV, XLSX, XLS",
    "sample.toggle": "Use Demo Data",
    "tabs.import": "Data Import",
    "tabs.overview": "Study Overview",
    "tabs.kri": "KRI Dashboard",
    "tabs.ranking": "Site Ranking",
    "tabs.details": "Risk Details",
    "tabs.actions": "Action Tracking",
    "actions.deploy": "Deploy",
    "actions.export": "Export RBQM Package",
    "settings.title": "Settings",
    "settings.language": "Language",
    "settings.theme": "Theme",
    "threshold.title": "KRI Thresholds",
    "threshold.master": "Enable KRI Threshold Scoring",
    "threshold.enabled": "{count}/{total} indicators enabled",
    "threshold.disabled": "Disabled. Risk scoring and signals are paused.",
    "pages.import": "Data Import",
    "pages.overview": "Study Overview",
    "pages.kri": "KRI Dashboard",
    "pages.ranking": "Site Risk Ranking",
    "pages.details": "Risk Signal Details",
    "pages.actions": "Action Tracking",
    "cards.raw": "Uploaded Raw Datasets",
    "cards.domain": "Recognized Data Domains",
    "cards.fields": "Supported Common Domains and Fields",
    "cards.kri": "Site KRI Overview",
    "hint.demo": "Demo data is currently in use. Upload CSV/XLSX files from the sidebar to analyze your study data.",
    "hint.uploaded": "Uploaded clinical study data is currently in use.",
    "empty": "No data",
    "alert.load": "RBQM data failed to load. Please confirm the FastAPI service is running.",
    "alert.upload": "Upload failed. No usable data domain was recognized.",
  },
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

async function uploadFiles(files) {
  if (!files.length) return;
  const formData = new FormData();
  Array.from(files).forEach((file) => formData.append("files", file));
  const res = await fetch(`/api/upload?${thresholdParams().toString()}`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    alert(payload.detail || t("alert.upload"));
    return;
  }
  currentState = await res.json();
  document.getElementById("sampleToggle").checked = false;
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
    uploadFiles(event.target.files);
  });

  const sampleToggle = document.getElementById("sampleToggle");
  if (sampleToggle) sampleToggle.addEventListener("change", (event) => {
    if (event.target.checked) resetDemo();
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
