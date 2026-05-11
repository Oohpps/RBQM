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
  { key: "dlt_rate", label: "DLT发生率", min: 0.01, max: 1, step: 0.01, value: 0.1, decimals: 2 },
  { key: "grade3_ae_rate", label: "≥3级AE发生率", min: 0.01, max: 2, step: 0.01, value: 0.2, decimals: 2 },
  { key: "safety_issues_per_subject", label: "SAE随访/报告缺口", min: 0.01, max: 1, step: 0.01, value: 0.15, decimals: 2 },
  { key: "dose_modification_rate", label: "毒性相关剂量调整率", min: 0.01, max: 2, step: 0.01, value: 0.2, decimals: 2 },
  { key: "eligibility_deviation_rate", label: "入排标准偏离率", min: 0.01, max: 1, step: 0.01, value: 0.1, decimals: 2 },
  { key: "pk_window_deviation_rate", label: "PK/PD采样窗偏离率", min: 0.01, max: 1, step: 0.01, value: 0.15, decimals: 2 },
  { key: "tumor_assessment_issue_rate", label: "肿瘤评估缺失/延迟率", min: 0.01, max: 1, step: 0.01, value: 0.2, decimals: 2 },
  { key: "missing_rate", label: "关键数据缺失率", min: 0.01, max: 0.3, step: 0.01, value: 0.1, decimals: 2 },
  { key: "late_entry_rate", label: "EDC延迟/未完成率", min: 0.01, max: 0.6, step: 0.01, value: 0.2, decimals: 2 },
  { key: "avg_entry_delay_days", label: "平均录入延迟（天）", min: 1, max: 30, step: 1, value: 7, decimals: 2 },
  { key: "open_queries_per_subject", label: "每受试者未关闭Query数", min: 0.1, max: 5, step: 0.1, value: 1.5, decimals: 2 },
  { key: "avg_open_query_age_days", label: "未关闭Query平均龄期（天）", min: 1, max: 60, step: 1, value: 21, decimals: 2 },
  { key: "lab_issues_per_subject", label: "未复核异常实验室率", min: 0.01, max: 1, step: 0.01, value: 0.2, decimals: 2 },
  { key: "major_deviations_per_subject", label: "重大方案偏离率", min: 0.01, max: 1, step: 0.01, value: 0.1, decimals: 2 },
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

function mountIcons() {
  document.querySelectorAll("[data-icon]").forEach((node) => {
    const icon = icons[node.dataset.icon];
    if (icon) node.innerHTML = icon;
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
      <div class="threshold-master-title">启用KRI阈值评估</div>
      <div class="threshold-master-note">${kriEnabled ? `已启用 ${enabledCount}/${thresholds.length} 项指标` : "已关闭，风险评分与信号暂停计算"}</div>
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
          <span>${item.label}</span>
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
    alert(payload.detail || "上传失败，未识别到可用数据域。");
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
    ? "当前使用示例数据。可在侧边栏上传CSV/XLSX文件查看自己的研究数据。"
    : "当前使用已上传的临床研究数据。";
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
    table.innerHTML = '<tbody><tr><td>暂无数据</td></tr></tbody>';
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
}

mountIcons();
renderThresholds();
bindEvents();
loadState().catch((error) => {
  console.error(error);
  alert("RBQM数据加载失败，请确认FastAPI服务已启动。");
});
