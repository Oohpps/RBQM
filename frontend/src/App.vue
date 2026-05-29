<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { commitUpload, fetchConfig, fetchSession, fetchState, resetState, saveConfig as saveConfigApi, thresholdParams } from "./api";
import { thresholds as thresholdDefaults } from "./config";
import { translate } from "./i18n";
import type { DataRow, Locale, PatientMedicalRecord, PatientMedicalSubject, RbqmState, TabKey, Theme, ThresholdItem, UploadPreview, UploadRole } from "./types";
import DataTable from "./components/DataTable.vue";
import IconSvg from "./components/IconSvg.vue";
import Sidebar from "./components/Sidebar.vue";
import ThresholdPanel from "./components/ThresholdPanel.vue";
import Topbar from "./components/Topbar.vue";

const kriEnabled = ref(true);
const activeTab = ref<TabKey>("overview");
const state = ref<RbqmState | null>(null);
const locale = ref<Locale>((localStorage.getItem("rbqm.language") as Locale) || "zh");
const theme = ref<Theme>((localStorage.getItem("rbqm.theme") as Theme) || "light");
const sidebarCollapsed = ref(false);
const settingsRefreshTimer = ref<number | null>(null);
const pendingFiles = ref<File[]>([]);
const pendingSourceRoles = ref<Record<string, UploadRole>>({});
const uploadPreview = ref<UploadPreview | null>(null);
const importingData = ref(false);
const workspaceRef = ref<HTMLElement | null>(null);
const resizeHandleRef = ref<HTMLElement | null>(null);
const savingConfig = ref(false);
const thresholdRailWidth = {
  default: 352,
  min: 280,
  max: 560,
  storageKey: "rbqm.thresholdRailWidth",
};
const sessionStorageKey = "rbqm.backendSessionId";

const thresholds = reactive<ThresholdItem[]>(
  thresholdDefaults.map((item) => ({
    ...item,
    label: { ...item.label },
    group: { ...item.group },
  })),
);

const params = computed(() => thresholdParams(kriEnabled.value, thresholds));
const hasImportedData = computed(() => Boolean((state.value?.raw_summary || []).length || (state.value?.domain_summary || []).length));
const dataHint = computed(() => (hasImportedData.value ? t("hint.uploaded") : t("hint.empty")));
const importStatusText = computed(() => (locale.value === "zh" ? "正在导入数据，请稍候..." : "Importing data, please wait..."));
const rawSourceNames = computed(() => (state.value?.raw_summary || []).map((row) => Object.values(row).join(" ").toLowerCase()).join(" "));
const hasProgressReport = computed(() =>
  Boolean(state.value?.data_sources?.progress_report) || /progress|进展报告|進展報告|è¿|ç¼ºå¤±|æœªsdv|summary/.test(rawSourceNames.value),
);
const hasClinicalData = computed(() =>
  Boolean(state.value?.data_sources?.clinical_data) || /formexcel|form excel|form_excel|临床研究数据|臨床研究數據|lb_hba1c|vs_w|::ae|::dm/.test(rawSourceNames.value),
);
const subjectStatusRows = computed(() => state.value?.subject_status_summary || []);
const maxSubjectStatusCount = computed(() => Math.max(...subjectStatusRows.value.map((row) => Number(row["受试者数"] || 0)), 1));
const siteStatusRows = computed(() => {
  const source = state.value?.subject_status_by_site || [];
  const sites = new Map<string, Record<string, string | number | string[]>>();
  source.forEach((row) => {
    const site = String(row["中心"] || "");
    const status = String(row["受试者状态"] || "未知");
    const count = Number(row["受试者数"] || 0);
    if (!sites.has(site)) sites.set(site, { 中心: site, 总数: 0 });
    const item = sites.get(site)!;
    item[status] = Number(item[status] || 0) + count;
    item["总数"] = Number(item["总数"] || 0) + count;
  });
  return Array.from(sites.values()).sort((a, b) => String(a["中心"]).localeCompare(String(b["中心"])));
});
const siteStatusNames = computed(() => {
  const names = Array.from(new Set((state.value?.subject_status_by_site || []).map((row) => String(row["受试者状态"] || "未知"))));
  const ordered = ["筛选中", "筛选失败", "已入组", "治疗结束", "提前退出"];
  const known = ordered.filter((status) => names.includes(status));
  const extra = names.filter((name) => !known.includes(name)).sort();
  return [...known, ...extra];
});
const siteStatusColors: Record<string, string> = {
  筛选中: "#F59E0B",
  筛选失败: "#9CA3AF",
  已入组: "#2563EB",
  治疗结束: "#14B8A6",
  提前退出: "#DC2626",
};
const fallbackStatusColors = ["#7C3AED", "#DB2777", "#0EA5E9", "#84CC16"];
const selectedSiteStatus = ref<{ site: string; status: string; count: number } | null>(null);
const maxSiteSubjectTotal = computed(() => Math.max(...siteStatusRows.value.map((row) => Number(row["总数"] || 0)), 1));

function colorForStatus(status: string, index: number): string {
  return siteStatusColors[status] || fallbackStatusColors[index % fallbackStatusColors.length];
}

function selectSiteStatus(row: Record<string, string | number | string[]>, status: string): void {
  selectedSiteStatus.value = {
    site: String(row["中心"] || ""),
    status,
    count: Number(row[status] || 0),
  };
}

function valueRange(records: PatientMedicalRecord[], fallbackMin: number, fallbackMax: number): { min: number; max: number } {
  const values = records.map((row) => Number(row.value)).filter((value) => Number.isFinite(value));
  if (!values.length) return { min: fallbackMin, max: fallbackMax };
  const min = Math.min(...values, fallbackMin);
  const max = Math.max(...values, fallbackMax);
  const pad = Math.max((max - min) * 0.12, 0.5);
  return { min: Math.max(0, min - pad), max: max + pad };
}

function linePoints(records: PatientMedicalRecord[], width: number, height: number, fallbackMin: number, fallbackMax: number): string {
  if (!records.length) return "";
  const range = valueRange(records, fallbackMin, fallbackMax);
  return records
    .map((row, index) => {
      const x = records.length === 1 ? width / 2 : 28 + (index / (records.length - 1)) * (width - 56);
      const y = 18 + ((range.max - Number(row.value)) / Math.max(range.max - range.min, 1)) * (height - 42);
      return `${x},${y}`;
    })
    .join(" ");
}

function pointX(index: number, total: number, width: number): number {
  return total === 1 ? width / 2 : 28 + (index / (total - 1)) * (width - 56);
}

function pointY(row: PatientMedicalRecord, records: PatientMedicalRecord[], height: number, fallbackMin: number, fallbackMax: number): number {
  const range = valueRange(records, fallbackMin, fallbackMax);
  return 18 + ((range.max - Number(row.value)) / Math.max(range.max - range.min, 1)) * (height - 68);
}

function changeFromBaseline(records: PatientMedicalRecord[], index: number): number {
  if (!records.length) return 0;
  return Number((Number(records[index]?.value || 0) - Number(records[0]?.value || 0)).toFixed(2));
}

function shortVisitLabel(row: PatientMedicalRecord): string {
  const text = row.visit || row.date || "-";
  const week = text.match(/W-?\d+/i)?.[0];
  if (week) return week.toUpperCase();
  if (text.includes("筛选")) return "筛选";
  if (text.includes("治疗结束")) return "EOT";
  if (text.includes("提前")) return "退出";
  return text.length > 6 ? text.slice(0, 6) : text;
}

function deltaScale(records: PatientMedicalRecord[]): number {
  const deltas = records.map((_, index) => Math.abs(changeFromBaseline(records, index)));
  return Math.max(...deltas, 1);
}

function deltaBarWidth(records: PatientMedicalRecord[], index: number): number {
  return Math.max(2, Math.abs(changeFromBaseline(records, index)) / deltaScale(records) * 48);
}

function deltaBarLeft(records: PatientMedicalRecord[], index: number): number {
  const width = deltaBarWidth(records, index);
  return changeFromBaseline(records, index) < 0 ? 50 - width : 50;
}

const activeDrilldownKey = ref("");
const dashboardPanel = ref<"efficacy" | "ae" | "sae" | "critical">("efficacy");
const enabledMetricKeys = computed(() => new Set(kriEnabled.value ? thresholds.filter((item) => item.enabled).map((item) => item.key) : []));
const kriDrilldowns = computed(() => (state.value?.kri_drilldowns || []).filter((item) => enabledMetricKeys.value.has(item.key)));
const activeDrilldown = computed(() => kriDrilldowns.value.find((item) => item.key === activeDrilldownKey.value) || kriDrilldowns.value[0] || null);
const maxDrilldownValue = computed(() => Math.max(...(activeDrilldown.value?.center_rows || []).map((row) => Number(row["超阈值条数"] || 0)), 1));
const selectedMedicalSubjectId = ref("");
const medicalSubjects = computed<PatientMedicalSubject[]>(() => state.value?.patient_medical_review?.subjects || []);
const medicalRecords = computed<PatientMedicalRecord[]>(() => state.value?.patient_medical_review?.records || []);
const selectedMedicalSubject = computed(() => medicalSubjects.value.find((item) => item.subject_id === selectedMedicalSubjectId.value) || medicalSubjects.value[0] || null);
const selectedMedicalRecords = computed(() => {
  const subject = selectedMedicalSubject.value?.subject_id;
  if (!subject) return [];
  return medicalRecords.value.filter((row) => row.subject_id === subject).sort((a, b) => (a.day || 0) - (b.day || 0) || a.visit.localeCompare(b.visit));
});
const selectedHba1cRecords = computed(() => selectedMedicalRecords.value.filter((row) => row.metric === "hba1c"));
const selectedWeightRecords = computed(() => selectedMedicalRecords.value.filter((row) => row.metric === "weight"));
const combinedTrendRecords = computed(() => {
  const maxLength = Math.max(selectedHba1cRecords.value.length, selectedWeightRecords.value.length);
  return Array.from({ length: maxLength }, (_, index) => ({
    index,
    label: shortVisitLabel(selectedHba1cRecords.value[index] || selectedWeightRecords.value[index]),
    hba1c: selectedHba1cRecords.value[index],
    weight: selectedWeightRecords.value[index],
  }));
});
const medicalTimelineRecords = computed(() => {
  const visits = new Map<string, Record<string, string | number>>();
  selectedMedicalRecords.value.forEach((row) => {
    const key = `${row.date || row.visit}-${row.visit}`;
    if (!visits.has(key)) visits.set(key, { 日期: row.date || "-", 访视: row.visit || "-", HbA1c: "", 体重: "" });
    visits.get(key)![row.metric === "hba1c" ? "HbA1c" : "体重"] = `${row.value}${row.unit || ""}`;
  });
  return Array.from(visits.values());
});
const aeReview = computed(() => state.value?.ae_event_review || null);
const criticalQueryReview = computed(() => state.value?.critical_query_review || null);

function rowValue(row: DataRow, keys: string[]): string | number | boolean | string[] | null {
  for (const key of keys) {
    if (Object.prototype.hasOwnProperty.call(row, key)) return row[key];
  }
  return null;
}

function normalizeMetricRows(rows: DataRow[] = []): { label: string; value: number }[] {
  return rows.map((row) => ({
    label: String(rowValue(row, ["指标", "鎸囨爣"]) || "-"),
    value: Number(rowValue(row, ["数值", "鏁板€?"]) || 0),
  }));
}

function normalizeCountRows(rows: DataRow[] = [], labelKeys: string[], countKeys: string[] = ["事件数", "浜嬩欢鏁?"]): { label: string; count: number }[] {
  return rows.map((row) => ({
    label: String(rowValue(row, labelKeys) || "-"),
    count: Number(rowValue(row, countKeys) || 0),
  }));
}

const aeOverviewRows = computed(() => normalizeMetricRows(aeReview.value?.overview || []));
const aeSiteRows = computed(() => normalizeCountRows(aeReview.value?.by_site || [], ["中心", "涓績"]));
const saeSiteRows = computed(() => normalizeCountRows(aeReview.value?.sae_by_site || [], ["中心", "涓績"]));
const criticalOverviewRows = computed(() => normalizeMetricRows(criticalQueryReview.value?.overview || []));
const criticalSiteRows = computed(() => normalizeCountRows(criticalQueryReview.value?.by_site || [], ["中心", "涓績"], ["质疑创建数", "璐ㄧ枒鍒涘缓鏁?"]));
const maxAeSiteCount = computed(() => Math.max(...aeSiteRows.value.map((row) => row.count), 1));
const maxSaeSiteCount = computed(() => Math.max(...saeSiteRows.value.map((row) => row.count), 1));
const maxCriticalSiteCount = computed(() => Math.max(...criticalSiteRows.value.map((row) => row.count), 1));

watch(kriDrilldowns, (items) => {
  if (!items.length) {
    activeDrilldownKey.value = "";
    return;
  }
  if (!items.some((item) => item.key === activeDrilldownKey.value)) {
    activeDrilldownKey.value = items[0].key;
  }
});

watch(medicalSubjects, (items) => {
  if (!items.length) {
    selectedMedicalSubjectId.value = "";
    return;
  }
  if (!items.some((item) => item.subject_id === selectedMedicalSubjectId.value)) {
    selectedMedicalSubjectId.value = items[0].subject_id;
  }
});

function t(key: string, values: Record<string, string | number> = {}): string {
  return translate(locale.value, key, values);
}

function setLocale(nextLocale: Locale): void {
  locale.value = nextLocale;
  localStorage.setItem("rbqm.language", nextLocale);
}

function setTheme(nextTheme: Theme): void {
  theme.value = nextTheme;
  localStorage.setItem("rbqm.theme", nextTheme);
}

function activateTab(tab: TabKey): void {
  activeTab.value = tab;
}

function setKriEnabled(enabled: boolean): void {
  kriEnabled.value = enabled;
  scheduleRefresh();
}

function cancelUpload(): void {
  if (importingData.value) return;
  uploadPreview.value = null;
  pendingFiles.value = [];
  pendingSourceRoles.value = {};
}

function exportPackage(): void {
  window.location.href = `/api/export?${params.value.toString()}`;
}

function applyConfig(config: { kri_enabled: boolean; enabled_metrics: string[]; thresholds: Record<string, number> }): void {
  kriEnabled.value = config.kri_enabled;
  const enabled = new Set(config.enabled_metrics);
  thresholds.forEach((item) => {
    if (Object.prototype.hasOwnProperty.call(config.thresholds, item.key)) {
      item.value = Number(config.thresholds[item.key]);
    }
    item.enabled = enabled.has(item.key);
  });
}

async function loadConfig(): Promise<void> {
  try {
    const config = await fetchConfig();
    if (config.active) applyConfig(config.active);
  } catch (error) {
    console.error(error);
    alert(t("alert.configLoad"));
  }
}

async function saveConfig(): Promise<void> {
  if (savingConfig.value) return;
  savingConfig.value = true;
  try {
    const saved = await saveConfigApi(kriEnabled.value, thresholds);
    if (saved.active) applyConfig(saved.active);
    await loadState();
    alert(t("alert.configSave", { version: saved.active.version }));
  } catch (error) {
    console.error(error);
    alert(error instanceof Error ? error.message : t("alert.configSaveFailed"));
  } finally {
    savingConfig.value = false;
  }
}

function scheduleRefresh(): void {
  if (settingsRefreshTimer.value !== null) window.clearTimeout(settingsRefreshTimer.value);
  settingsRefreshTimer.value = window.setTimeout(() => {
    loadState();
  }, 240);
}

async function loadState(): Promise<void> {
  try {
    state.value = await fetchState(params.value);
    if (!activeDrilldownKey.value && state.value.kri_drilldowns.length) activeDrilldownKey.value = state.value.kri_drilldowns[0].key;
  } catch (error) {
    console.error(error);
    alert(t("alert.load"));
  }
}

async function initializeSessionState(): Promise<void> {
  try {
    const session = await fetchSession();
    const previousSession = localStorage.getItem(sessionStorageKey);
    if (previousSession !== session.session_id) {
      state.value = await resetState(params.value);
      localStorage.setItem(sessionStorageKey, session.session_id);
      activeDrilldownKey.value = "";
      return;
    }
  } catch (error) {
    console.warn("Unable to initialize clean RBQM session", error);
  }
  await loadState();
}

async function onFilesSelected(files: File[], role: UploadRole): Promise<void> {
  if (!files.length || importingData.value) return;
  importingData.value = true;
  const existing = new Map(pendingFiles.value.map((file) => [file.name, file]));
  files.forEach((file) => {
    existing.set(file.name, file);
    pendingSourceRoles.value[file.name] = role;
  });
  pendingFiles.value = Array.from(existing.values());
  try {
    state.value = await commitUpload(pendingFiles.value, { sources: {} }, params.value, pendingSourceRoles.value);
    uploadPreview.value = null;
    pendingFiles.value = [];
    pendingSourceRoles.value = {};
    if (state.value.kri_drilldowns.length) activeDrilldownKey.value = state.value.kri_drilldowns[0].key;
  } catch (error) {
    alert(error instanceof Error ? error.message : t("alert.preview"));
  } finally {
    importingData.value = false;
  }
}

function onUploadImported(nextState: RbqmState): void {
  state.value = nextState;
  uploadPreview.value = null;
  pendingFiles.value = [];
  pendingSourceRoles.value = {};
}

function clampThresholdRailWidth(width: number): number {
  return Math.min(thresholdRailWidth.max, Math.max(thresholdRailWidth.min, Math.round(width)));
}

function setThresholdRailWidth(width: number, persist = true): void {
  const workspace = workspaceRef.value;
  const handle = resizeHandleRef.value;
  if (!workspace) return;
  const nextWidth = clampThresholdRailWidth(width);
  workspace.style.setProperty("--threshold-rail-width", `${nextWidth}px`);
  if (handle) {
    handle.setAttribute("aria-valuemin", String(thresholdRailWidth.min));
    handle.setAttribute("aria-valuemax", String(thresholdRailWidth.max));
    handle.setAttribute("aria-valuenow", String(nextWidth));
  }
  if (persist) localStorage.setItem(thresholdRailWidth.storageKey, String(nextWidth));
}

function initThresholdRailResize(): void {
  const workspace = workspaceRef.value;
  const handle = resizeHandleRef.value;
  if (!workspace || !handle) return;
  const savedWidth = Number(localStorage.getItem(thresholdRailWidth.storageKey));
  setThresholdRailWidth(Number.isFinite(savedWidth) && savedWidth > 0 ? savedWidth : thresholdRailWidth.default, false);

  const widthFromPointer = (clientX: number) => clientX - workspace.getBoundingClientRect().left;
  const stopResize = () => document.body.classList.remove("threshold-resizing");

  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    handle.setPointerCapture(event.pointerId);
    document.body.classList.add("threshold-resizing");
  });
  handle.addEventListener("pointermove", (event) => {
    if (document.body.classList.contains("threshold-resizing")) setThresholdRailWidth(widthFromPointer(event.clientX));
  });
  handle.addEventListener("pointerup", stopResize);
  handle.addEventListener("pointercancel", stopResize);
  handle.addEventListener("dblclick", () => setThresholdRailWidth(thresholdRailWidth.default));
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

watch(theme, (nextTheme) => {
  document.body.dataset.theme = nextTheme;
}, { immediate: true });

watch(locale, (nextLocale) => {
  document.documentElement.lang = nextLocale === "zh" ? "zh-CN" : "en";
}, { immediate: true });

watch(sidebarCollapsed, (collapsed) => {
  document.body.classList.toggle("sidebar-collapsed", collapsed);
});

onMounted(async () => {
  await nextTick();
  initThresholdRailResize();
  await loadConfig();
  initializeSessionState();
});

onBeforeUnmount(() => {
  if (settingsRefreshTimer.value !== null) window.clearTimeout(settingsRefreshTimer.value);
});
</script>

<template>
  <div class="app-shell" :aria-busy="importingData">
    <Sidebar
      :active-tab="activeTab"
      :t="t"
      :importing="importingData"
      @toggle-sidebar="sidebarCollapsed = !sidebarCollapsed"
      @navigate="activateTab"
      @files-selected="onFilesSelected"
    />

    <main class="main">
      <Topbar
        :active-tab="activeTab"
        :locale="locale"
        :theme="theme"
        :saving-config="savingConfig"
        :t="t"
        @change-tab="activateTab"
        @change-locale="setLocale"
        @change-theme="setTheme"
        @save-config="saveConfig"
      />

      <section ref="workspaceRef" class="workspace" :class="{ 'overview-mode': activeTab !== 'import' }">
        <aside v-if="activeTab === 'import'" class="threshold-rail">
          <ThresholdPanel
            :kri-enabled="kriEnabled"
            :thresholds="thresholds"
            :locale="locale"
            :t="t"
            @update-kri-enabled="setKriEnabled"
            @threshold-changed="scheduleRefresh"
          />
        </aside>
        <div
          v-if="activeTab === 'import'"
          ref="resizeHandleRef"
          class="threshold-resize-handle"
          role="separator"
          aria-label="调整KRI阈值设置列宽"
          aria-orientation="vertical"
          tabindex="0"
        ></div>

        <section class="content">
          <section class="tab-page" :class="{ active: activeTab === 'import' }">
            <h1>{{ t("pages.import") }}</h1>
            <div class="source-note">数据源：进展报告</div>
            <div v-if="!hasProgressReport" class="data-card">
              <div class="mapping-empty">请先导入进展报告，导入后展示风险阈值图表和明细列表。</div>
            </div>
            <template v-else>
            <div class="info-banner">
              <IconSvg name="info" />
              <span>{{ dataHint }} 选择左侧上传入口后会自动导入；点击下方指标查看中心图和明细列表。</span>
            </div>

            <section class="drilldown-panel">
              <div v-if="kriDrilldowns.length" class="drilldown-tabs">
                <button
                  v-for="item in kriDrilldowns"
                  :key="item.key"
                  type="button"
                  class="drilldown-tab"
                  :class="{ active: activeDrilldown?.key === item.key }"
                  @click="activeDrilldownKey = item.key"
                >
                  {{ item.label }}
                </button>
              </div>
              <div v-else class="data-card">
                <div class="mapping-empty">KRI阈值评分已关闭或暂无启用指标</div>
              </div>

              <div v-if="activeDrilldown" class="drilldown-grid">
                <div class="data-card drilldown-chart-card">
                  <div class="card-title">{{ activeDrilldown.label }} / 各中心</div>
                  <div class="center-chart">
                    <div class="threshold-note">按阈值 {{ activeDrilldown.threshold }}{{ activeDrilldown.unit }}统计超阈值总条数</div>
                    <div v-for="row in activeDrilldown.center_rows.slice(0, 30)" :key="String(row['中心'])" class="center-bar-row">
                      <div class="center-bar-label">{{ row["中心"] }}</div>
                      <div class="center-bar-track">
                        <div
                          class="center-bar-fill"
                          :class="{ over: Number(row['超阈值条数'] || 0) > 0 }"
                          :style="{ width: `${Math.max(2, (Number(row['超阈值条数'] || 0) / maxDrilldownValue) * 100)}%` }"
                        ></div>
                      </div>
                      <div class="center-bar-value">{{ row["超阈值条数"] }}</div>
                    </div>
                  </div>
                </div>

                <div class="data-card">
                  <div class="card-title">中心汇总</div>
                  <div class="table-wrap drilldown-table-wrap">
                    <DataTable :rows="activeDrilldown.center_rows" :limit="30" :empty-text="t('empty')" />
                  </div>
                </div>
              </div>

              <div v-if="activeDrilldown" class="data-card">
                <div class="card-title">{{ activeDrilldown.label }} / 明细列表</div>
                <div class="table-wrap">
                  <DataTable :rows="activeDrilldown.details" :limit="100" :empty-text="t('empty')" />
                </div>
              </div>
            </section>
            </template>
          </section>

          <section class="tab-page" :class="{ active: activeTab === 'overview' }">
            <h1>{{ t("pages.overview") }}</h1>
            <div class="source-note">数据源：进展报告</div>
            <div v-if="!hasProgressReport" class="data-card">
              <div class="mapping-empty">请先导入进展报告，导入后展示研究概览和受试者状态明细。</div>
            </div>
            <template v-else>
            <div class="metric-grid">
              <div v-for="(value, label) in state?.overview || {}" :key="label" class="metric-card">
                <div class="metric-label">{{ label }}</div>
                <div class="metric-value">{{ value }}</div>
              </div>
            </div>

            <div class="overview-grid">
              <div class="data-card status-chart-card">
                <div class="card-title">受试者状态分布</div>
                <div class="status-chart">
                  <div v-if="!subjectStatusRows.length" class="mapping-empty">{{ t("empty") }}</div>
                  <div v-for="row in subjectStatusRows" :key="String(row['受试者状态'])" class="status-bar-row">
                    <div class="status-bar-label">{{ row["受试者状态"] }}</div>
                    <div class="status-bar-track">
                      <div class="status-bar-fill" :style="{ width: `${(Number(row['受试者数'] || 0) / maxSubjectStatusCount) * 100}%` }"></div>
                    </div>
                    <div class="status-bar-value">{{ row["受试者数"] }} <span>{{ row["占比"] }}%</span></div>
                  </div>
                </div>
              </div>

              <div class="data-card">
                <div class="card-title">受试者状态明细</div>
                <div class="table-wrap overview-table-wrap">
                  <DataTable :rows="subjectStatusRows" :empty-text="t('empty')" />
                </div>
              </div>
            </div>

            <div class="data-card site-stack-card">
              <div class="site-stack-legend">
                <span v-for="(status, index) in siteStatusNames" :key="status">
                  <i :style="{ background: colorForStatus(status, index) }"></i>{{ status }}
                </span>
              </div>
              <div class="site-stack-chart">
                <div v-if="!siteStatusRows.length" class="mapping-empty">{{ t("empty") }}</div>
                <div v-for="row in siteStatusRows" :key="String(row['中心'])" class="site-stack-row">
                  <div class="site-stack-total">{{ row["总数"] }}</div>
                  <div class="site-stack-track">
                    <div
                      v-for="(status, index) in siteStatusNames"
                      :key="status"
                      class="site-stack-segment"
                      :title="`${status}: ${Number(row[status] || 0)}`"
                      role="button"
                      tabindex="0"
                      @click="selectSiteStatus(row, status)"
                      @keydown.enter="selectSiteStatus(row, status)"
                      :style="{
                        height: `${(Number(row[status] || 0) / maxSiteSubjectTotal) * 100}%`,
                        background: colorForStatus(status, index),
                      }"
                    ></div>
                  </div>
                  <div class="site-stack-label">{{ row["中心"] }}</div>
                </div>
              </div>
              <div v-if="selectedSiteStatus" class="site-stack-selection">
                中心 {{ selectedSiteStatus.site }} / {{ selectedSiteStatus.status }}：{{ selectedSiteStatus.count }}
              </div>
              <div class="site-stack-title">各中心受试者状态明细</div>
            </div>
            </template>
          </section>
          <section class="tab-page" :class="{ active: activeTab === 'kri' }">
            <h1>{{ t("pages.kri") }}</h1>
            <div class="source-note">数据源：Form Excel（临床研究数据）</div>
            <div v-if="!hasClinicalData" class="data-card">
              <div class="mapping-empty">请先导入Form Excel/临床研究数据，导入后展示患者疗效、AE/SAE和关键数据点质疑看板。</div>
            </div>
            <template v-else>
            <div class="dashboard-tabs">
              <button type="button" :class="{ active: dashboardPanel === 'efficacy' }" @click="dashboardPanel = 'efficacy'">患者疗效趋势</button>
              <button type="button" :class="{ active: dashboardPanel === 'ae' }" @click="dashboardPanel = 'ae'">AE事件汇总统计</button>
              <button type="button" :class="{ active: dashboardPanel === 'sae' }" @click="dashboardPanel = 'sae'">SAE事件分析</button>
              <button type="button" :class="{ active: dashboardPanel === 'critical' }" @click="dashboardPanel = 'critical'">关键数据点质疑明细</button>
            </div>
            <section v-if="dashboardPanel === 'efficacy'" class="medical-review-panel">
              <div class="data-card medical-selector-card">
                <div>
                  <div class="card-title">患者疗效趋势</div>
                  <p class="medical-subtitle">盲态展示每位受试者的糖化血红蛋白与体重随访变化，用于快速发现代谢控制和体重波动信号。</p>
                </div>
                <label class="patient-select-label">
                  受试者
                  <select v-model="selectedMedicalSubjectId" class="patient-select">
                    <option v-for="subject in medicalSubjects" :key="subject.subject_id" :value="subject.subject_id">
                      {{ subject.subject_id }} · {{ subject.site_id }} · {{ subject.subject_status || "状态未知" }}
                    </option>
                  </select>
                </label>
              </div>

              <div v-if="selectedMedicalSubject" class="medical-summary-grid">
                <div class="medical-kpi">
                  <span>中心</span>
                  <strong>{{ selectedMedicalSubject.site_id || "-" }}</strong>
                </div>
                <div class="medical-kpi">
                  <span>受试者状态</span>
                  <strong>{{ selectedMedicalSubject.subject_status || "-" }}</strong>
                </div>
                <div class="medical-kpi">
                  <span>HbA1c记录</span>
                  <strong>{{ selectedMedicalSubject.hba1c_count }}</strong>
                </div>
                <div class="medical-kpi">
                  <span>体重记录</span>
                  <strong>{{ selectedMedicalSubject.weight_count }}</strong>
                </div>
              </div>

              <div v-if="selectedMedicalSubject" class="medical-chart-grid">
                <div class="data-card medical-chart-card">
                  <div class="card-title">HbA1c 趋势</div>
                  <svg class="medical-line-chart" viewBox="0 0 360 250" role="img" aria-label="HbA1c趋势图">
                    <line x1="28" y1="154" x2="332" y2="154" class="medical-ref-line" />
                    <text x="294" y="148" class="medical-axis-note">7.0%</text>
                    <polyline :points="linePoints(selectedHba1cRecords, 360, 250, 6, 10)" class="hba1c-line" />
                    <g v-for="(row, index) in selectedHba1cRecords" :key="`${row.date}-${row.visit}`">
                      <circle :cx="pointX(index, selectedHba1cRecords.length, 360)" :cy="pointY(row, selectedHba1cRecords, 250, 6, 10)" r="5" class="hba1c-point" />
                      <text :x="pointX(index, selectedHba1cRecords.length, 360)" :y="pointY(row, selectedHba1cRecords, 250, 6, 10) - 10" class="medical-point-label">{{ row.value }}</text>
                      <text
                        :x="pointX(index, selectedHba1cRecords.length, 360)"
                        y="222"
                        class="medical-visit-label angled"
                        :transform="`rotate(-34 ${pointX(index, selectedHba1cRecords.length, 360)} 222)`"
                      >{{ shortVisitLabel(row) }}</text>
                    </g>
                  </svg>
                </div>

                <div class="data-card medical-chart-card">
                  <div class="card-title">体重趋势</div>
                  <svg class="medical-line-chart" viewBox="0 0 360 250" role="img" aria-label="体重趋势图">
                    <polyline :points="linePoints(selectedWeightRecords, 360, 250, 55, 95)" class="weight-line" />
                    <g v-for="(row, index) in selectedWeightRecords" :key="`${row.date}-${row.visit}`">
                      <circle :cx="pointX(index, selectedWeightRecords.length, 360)" :cy="pointY(row, selectedWeightRecords, 250, 55, 95)" r="5" class="weight-point" />
                      <text :x="pointX(index, selectedWeightRecords.length, 360)" :y="pointY(row, selectedWeightRecords, 250, 55, 95) - 10" class="medical-point-label">{{ row.value }}</text>
                      <text
                        :x="pointX(index, selectedWeightRecords.length, 360)"
                        y="222"
                        class="medical-visit-label angled"
                        :transform="`rotate(-34 ${pointX(index, selectedWeightRecords.length, 360)} 222)`"
                      >{{ shortVisitLabel(row) }}</text>
                    </g>
                  </svg>
                </div>

                <div class="data-card medical-chart-card">
                  <div class="card-title">体重较基线变化</div>
                  <div class="delta-chart">
                    <div class="delta-zero-label">0 kg</div>
                    <div v-for="(row, index) in selectedWeightRecords" :key="`${row.date}-${row.visit}`" class="delta-row">
                      <div class="delta-label">{{ shortVisitLabel(row) }}</div>
                      <div class="delta-track">
                        <i class="delta-zero"></i>
                        <div
                          class="delta-bar"
                          :class="{ negative: changeFromBaseline(selectedWeightRecords, index) < 0 }"
                          :style="{ left: `${deltaBarLeft(selectedWeightRecords, index)}%`, width: `${deltaBarWidth(selectedWeightRecords, index)}%` }"
                        ></div>
                      </div>
                      <div class="delta-value">{{ changeFromBaseline(selectedWeightRecords, index) }} kg</div>
                    </div>
                  </div>
                </div>

                <div class="data-card medical-chart-card">
                  <div class="card-title">HbA1c 与体重双趋势</div>
                  <div class="dual-trend-legend">
                    <span><i class="hba1c-dot"></i>HbA1c</span>
                    <span><i class="weight-dot"></i>体重</span>
                  </div>
                  <svg class="medical-dual-chart" viewBox="0 0 360 250" role="img" aria-label="HbA1c与体重双趋势图">
                    <polyline :points="linePoints(selectedHba1cRecords, 360, 250, 6, 10)" class="hba1c-line" />
                    <polyline :points="linePoints(selectedWeightRecords, 360, 250, 55, 95)" class="weight-line" />
                    <g v-for="row in combinedTrendRecords" :key="row.index">
                      <circle
                        v-if="row.hba1c"
                        :cx="pointX(row.index, combinedTrendRecords.length, 360)"
                        :cy="pointY(row.hba1c, selectedHba1cRecords, 250, 6, 10)"
                        r="4.5"
                        class="hba1c-point"
                      />
                      <circle
                        v-if="row.weight"
                        :cx="pointX(row.index, combinedTrendRecords.length, 360)"
                        :cy="pointY(row.weight, selectedWeightRecords, 250, 55, 95)"
                        r="4.5"
                        class="weight-point"
                      />
                      <text
                        :x="pointX(row.index, combinedTrendRecords.length, 360)"
                        y="224"
                        class="medical-visit-label angled"
                        :transform="`rotate(-34 ${pointX(row.index, combinedTrendRecords.length, 360)} 224)`"
                      >{{ row.label }}</text>
                    </g>
                  </svg>
                </div>
              </div>

              <div v-else class="data-card">
                <div class="mapping-empty">暂无可展示的患者级 HbA1c / 体重数据</div>
              </div>

              <div class="data-card">
                <div class="card-title">患者随访明细</div>
                <div class="table-wrap">
                  <DataTable :rows="medicalTimelineRecords" :limit="20" :empty-text="t('empty')" />
                </div>
              </div>
            </section>

            <section v-else-if="dashboardPanel === 'ae'" class="medical-review-panel">
              <div class="metric-grid">
                <div v-for="row in aeOverviewRows" :key="row.label" class="metric-card">
                  <div class="metric-label">{{ row.label }}</div>
                  <div class="metric-value">{{ row.value }}</div>
                </div>
              </div>
              <div v-if="!aeOverviewRows.length" class="data-card">
                <div class="mapping-empty">已导入Form Excel后，将在这里展示AE事件汇总统计。</div>
              </div>
              <div class="medical-chart-grid">
                <div class="data-card medical-chart-card">
                  <div class="card-title">各中心AE事件数</div>
                  <div class="center-chart">
                    <div v-for="row in aeSiteRows" :key="row.label" class="center-bar-row">
                      <div class="center-bar-label">{{ row.label }}</div>
                      <div class="center-bar-track">
                        <div class="center-bar-fill" :style="{ width: `${Math.max(2, (row.count / maxAeSiteCount) * 100)}%` }"></div>
                      </div>
                      <div class="center-bar-value">{{ row.count }}</div>
                    </div>
                  </div>
                </div>
                <div class="data-card">
                  <div class="card-title">AE编码分类（SOC）</div>
                  <div class="table-wrap">
                    <DataTable :rows="aeReview?.by_soc || []" :limit="12" :empty-text="t('empty')" />
                  </div>
                </div>
                <div class="data-card">
                  <div class="card-title">AE首选语（PT）</div>
                  <div class="table-wrap">
                    <DataTable :rows="aeReview?.by_pt || []" :limit="12" :empty-text="t('empty')" />
                  </div>
                </div>
                <div class="data-card">
                  <div class="card-title">中心 × SOC 汇总</div>
                  <div class="table-wrap">
                    <DataTable :rows="aeReview?.by_site_soc || []" :limit="16" :empty-text="t('empty')" />
                  </div>
                </div>
                <div class="data-card">
                  <div class="card-title">严重程度 / 相关性 / 转归</div>
                  <div class="table-wrap">
                    <DataTable :rows="[...(aeReview?.by_grade || []), ...(aeReview?.by_relation || []), ...(aeReview?.by_outcome || [])]" :limit="24" :empty-text="t('empty')" />
                  </div>
                </div>
              </div>
              <div class="data-card">
                <div class="card-title">AE事件明细</div>
                <div class="table-wrap">
                  <DataTable :rows="aeReview?.ae_details || []" :limit="80" :empty-text="t('empty')" />
                </div>
              </div>
            </section>

            <section v-else-if="dashboardPanel === 'sae'" class="medical-review-panel">
              <div class="medical-chart-grid">
                <div class="data-card medical-chart-card">
                  <div class="card-title">各中心SAE事件数</div>
                  <div class="center-chart">
                    <div v-for="row in saeSiteRows" :key="row.label" class="center-bar-row">
                      <div class="center-bar-label">{{ row.label }}</div>
                      <div class="center-bar-track">
                        <div class="center-bar-fill over" :style="{ width: `${Math.max(2, (row.count / maxSaeSiteCount) * 100)}%` }"></div>
                      </div>
                      <div class="center-bar-value">{{ row.count }}</div>
                    </div>
                  </div>
                </div>
                <div class="data-card">
                  <div class="card-title">SAE编码分类（SOC）</div>
                  <div class="table-wrap">
                    <DataTable :rows="aeReview?.sae_by_soc || []" :limit="12" :empty-text="t('empty')" />
                  </div>
                </div>
                <div class="data-card">
                  <div class="card-title">SAE首选语（PT）</div>
                  <div class="table-wrap">
                    <DataTable :rows="aeReview?.sae_by_pt || []" :limit="12" :empty-text="t('empty')" />
                  </div>
                </div>
                <div class="data-card">
                  <div class="card-title">SAE原因 / 转归</div>
                  <div class="table-wrap">
                    <DataTable :rows="[...(aeReview?.sae_by_reason || []), ...(aeReview?.sae_by_outcome || [])]" :limit="16" :empty-text="t('empty')" />
                  </div>
                </div>
              </div>
              <div class="data-card">
                <div class="card-title">SAE事件明细</div>
                <div class="table-wrap">
                  <DataTable :rows="aeReview?.sae_details || []" :limit="80" :empty-text="t('empty')" />
                </div>
              </div>
            </section>

            <section v-else class="medical-review-panel">
              <div class="metric-grid">
                <div v-for="row in criticalOverviewRows" :key="row.label" class="metric-card">
                  <div class="metric-label">{{ row.label }}</div>
                  <div class="metric-value">{{ row.value }}</div>
                </div>
              </div>
              <div v-if="!criticalOverviewRows.length" class="data-card">
                <div class="mapping-empty">请导入质疑明细报告和关键数据点文件后，展示关键数据点质疑明细。</div>
              </div>
              <div class="medical-chart-grid">
                <div class="data-card medical-chart-card">
                  <div class="card-title">各中心关键数据点Query创建数</div>
                  <div class="center-chart">
                    <div v-for="row in criticalSiteRows" :key="row.label" class="center-bar-row">
                      <div class="center-bar-label">{{ row.label }}</div>
                      <div class="center-bar-track">
                        <div class="center-bar-fill" :style="{ width: `${Math.max(2, (row.count / maxCriticalSiteCount) * 100)}%` }"></div>
                      </div>
                      <div class="center-bar-value">{{ row.count }}</div>
                    </div>
                  </div>
                </div>
                <div class="data-card">
                  <div class="card-title">各中心未关闭关键数据点Query</div>
                  <div class="table-wrap">
                    <DataTable :rows="criticalQueryReview?.open_by_site || []" :limit="30" :empty-text="t('empty')" />
                  </div>
                </div>
              </div>
              <div class="data-card">
                <div class="card-title">关键数据点质疑明细</div>
                <div class="table-wrap">
                  <DataTable :rows="criticalQueryReview?.details || []" :limit="100" :empty-text="t('empty')" />
                </div>
              </div>
              <div class="data-card">
                <div class="card-title">未关闭关键数据点质疑明细</div>
                <div class="table-wrap">
                  <DataTable :rows="criticalQueryReview?.open_details || []" :limit="100" :empty-text="t('empty')" />
                </div>
              </div>
            </section>
            </template>
          </section>
          <section class="tab-page fill-table-page" :class="{ active: activeTab === 'ranking' }">
            <h1>{{ t("pages.ranking") }}</h1>
            <div class="data-card">
              <div class="table-wrap">
                <DataTable
                  :rows="state?.metrics || []"
                  :preferred-columns="['中心', '受试者数', '风险评分', '风险等级', '缺失率', '延迟录入率']"
                  :limit="30"
                  :empty-text="t('empty')"
                />
              </div>
            </div>
          </section>

          <section class="tab-page fill-table-page" :class="{ active: activeTab === 'details' }">
            <h1>{{ t("pages.details") }}</h1>
            <div class="data-card">
              <div class="table-wrap">
                <DataTable :rows="state?.signals || []" :limit="30" :empty-text="t('empty')" />
              </div>
            </div>
            <button class="export-button" type="button" @click="exportPackage">
              {{ t("actions.export") }}
            </button>
          </section>

          <section class="tab-page fill-table-page" :class="{ active: activeTab === 'actions' }">
            <h1>{{ t("pages.actions") }}</h1>
            <div class="data-card">
              <div class="table-wrap">
                <DataTable :rows="state?.action_log || []" :limit="30" :empty-text="t('empty')" />
              </div>
            </div>
            <button class="export-button" type="button" @click="exportPackage">
              {{ t("actions.export") }}
            </button>
          </section>
        </section>
      </section>
    </main>

    <div v-if="importingData" class="import-loading-overlay" role="status" aria-live="assertive">
      <div class="import-loading-panel">
        <div class="import-loading-spinner" aria-hidden="true"></div>
        <div>
          <strong>{{ importStatusText }}</strong>
          <span>{{ locale === "zh" ? "正在解析文件并刷新页面数据" : "Parsing files and refreshing dashboards" }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
