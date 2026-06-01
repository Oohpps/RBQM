<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { commitUpload, fetchSession, fetchState, resetState, thresholdParams } from "./api";
import { thresholds as thresholdDefaults } from "./config";
import { translate } from "./i18n";
import type { DataRow, Locale, PatientMedicalRecord, PatientMedicalSubject, RbqmState, TabKey, Theme, ThresholdItem, UploadPreview, UploadRole } from "./types";
import DataTable from "./components/DataTable.vue";
import Sidebar from "./components/Sidebar.vue";
import Topbar from "./components/Topbar.vue";

const kriEnabled = ref(true);
const activeTab = ref<TabKey>("overview");
const state = ref<RbqmState | null>(null);
const locale = ref<Locale>((localStorage.getItem("rbqm.language") as Locale) || "zh");
const theme = ref<Theme>((localStorage.getItem("rbqm.theme") as Theme) || "light");
const sidebarCollapsed = ref(false);
const pendingFiles = ref<File[]>([]);
const pendingSourceRoles = ref<Record<string, UploadRole>>({});
const uploadPreview = ref<UploadPreview | null>(null);
const importingData = ref(false);
const sessionStorageKey = "rbqm.backendSessionId";

const thresholds = reactive<ThresholdItem[]>(
  thresholdDefaults.map((item) => ({
    ...item,
    label: { ...item.label },
    group: { ...item.group },
  })),
);

const params = computed(() => thresholdParams(kriEnabled.value, thresholds));
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

const dashboardPanel = ref<"efficacy" | "ae" | "sae" | "critical">("efficacy");
const selectedMedicalSubjectId = ref("");
const medicalSubjects = computed<PatientMedicalSubject[]>(() => state.value?.patient_medical_review?.subjects || []);
const medicalRecords = computed<PatientMedicalRecord[]>(() => state.value?.patient_medical_review?.records || []);
const blindedEfficacySiteRows = computed(() => state.value?.patient_medical_review?.site_summary || []);
const indicationOptions = [
  { value: "non_oncology_diabetes", label: "非肿瘤 - 糖尿病", configured: true },
  { value: "oncology_hcc", label: "肿瘤 - 肝癌", configured: false },
  { value: "oncology_lung", label: "肿瘤 - 肺癌", configured: false },
  { value: "non_oncology_hypertension", label: "非肿瘤 - 高血压", configured: false },
  { value: "non_oncology_copd", label: "非肿瘤 - 慢阻肺", configured: false },
] as const;
type Indication = typeof indicationOptions[number]["value"];
const selectedIndication = ref<Indication>("non_oncology_diabetes");
const selectedIndicationConfig = computed(() => indicationOptions.find((option) => option.value === selectedIndication.value)!);
const isConfiguredIndication = computed(() => selectedIndicationConfig.value.configured);
const efficacyModelOptions = [
  { value: "hba1c_weight", label: "综合疗效：HbA1c + 体重" },
  { value: "hba1c", label: "主要疗效：HbA1c" },
  { value: "weight", label: "辅助疗效：体重" },
] as const;
type EfficacyModel = typeof efficacyModelOptions[number]["value"];
const selectedEfficacyModel = ref<EfficacyModel>("hba1c_weight");
const usesHba1c = computed(() => selectedEfficacyModel.value !== "weight");
const usesWeight = computed(() => selectedEfficacyModel.value !== "hba1c");
const blindedRiskWeightInputs = reactive({ hba1c: 40, weight: 30, incomplete: 30 });
const appliedBlindedRiskWeights = reactive({ hba1c: 40, weight: 30, incomplete: 30 });
const blindedRiskWeightMessage = ref("当前使用默认权重。");
const blindedRiskWeightTotal = computed(() =>
  (usesHba1c.value ? appliedBlindedRiskWeights.hba1c : 0)
  + (usesWeight.value ? appliedBlindedRiskWeights.weight : 0)
  + appliedBlindedRiskWeights.incomplete,
);
const normalizedBlindedRiskWeights = computed(() => {
  const total = blindedRiskWeightTotal.value || 1;
  return {
    hba1c: usesHba1c.value ? appliedBlindedRiskWeights.hba1c / total : 0,
    weight: usesWeight.value ? appliedBlindedRiskWeights.weight / total : 0,
    incomplete: appliedBlindedRiskWeights.incomplete / total,
  };
});
const blindedRiskFormula = computed(() => {
  const parts = [];
  if (usesHba1c.value) parts.push("HbA1c异常评分 × 权重");
  if (usesWeight.value) parts.push("体重异常评分 × 权重");
  parts.push("数据不完整评分 × 权重");
  return `中心风险评分 = ${parts.join(" + ")}`;
});
function applyBlindedRiskWeights(): void {
  const values = [
    usesHba1c.value ? Number(blindedRiskWeightInputs.hba1c) : 0,
    usesWeight.value ? Number(blindedRiskWeightInputs.weight) : 0,
    Number(blindedRiskWeightInputs.incomplete),
  ];
  if (values.some((value) => !Number.isFinite(value) || value < 0)) {
    blindedRiskWeightMessage.value = "请输入大于或等于 0 的有效数字。";
    return;
  }
  if (values.reduce((sum, value) => sum + value, 0) <= 0) {
    blindedRiskWeightMessage.value = "当前显示的权重合计必须大于 0。";
    return;
  }
  [appliedBlindedRiskWeights.hba1c, appliedBlindedRiskWeights.weight, appliedBlindedRiskWeights.incomplete] = values;
  blindedRiskWeightMessage.value = "已按新权重重新计算中心风险评分。";
}
const dynamicBlindedEfficacySiteRows = computed(() =>
  blindedEfficacySiteRows.value
    .map((source) => {
      const row = { ...source };
      const subjectCount = Number(row["受试者数"] || 0);
      const evaluableCount = usesHba1c.value && usesWeight.value
        ? subjectCount * (1 - Number(row["配对数据不完整率（%）"] || 0) / 100)
        : Number(row[usesHba1c.value ? "HbA1c可评估人数" : "体重可评估人数"] || 0);
      const incompleteScore = subjectCount ? Math.min(100, Math.max(0, (1 - evaluableCount / subjectCount) * 100)) : 0;
      const score = (
        (usesHba1c.value ? Number(row["HbA1c异常评分"] || 0) * normalizedBlindedRiskWeights.value.hba1c : 0)
        + (usesWeight.value ? Number(row["体重异常评分"] || 0) * normalizedBlindedRiskWeights.value.weight : 0)
        + incompleteScore * normalizedBlindedRiskWeights.value.incomplete
      );
      const roundedScore = Number(score.toFixed(1));
      row["盲态疗效异常风险评分"] = roundedScore;
      row["数据不完整评分"] = Number(incompleteScore.toFixed(1));
      row["所选指标数据不完整率（%）"] = Number(incompleteScore.toFixed(2));
      row["风险等级"] = Number(row["受试者数"] || 0) < 3 ? "观察" : roundedScore >= 70 ? "高" : roundedScore >= 40 ? "中" : "低";
      const reasons = [];
      if (subjectCount < 3) reasons.push("样本量不足");
      if (usesHba1c.value && Number(row["HbA1c异常评分"] || 0) >= 50) reasons.push("HbA1c下降比例偏离项目整体");
      if (usesWeight.value && Number(row["体重异常评分"] || 0) >= 50) reasons.push("体重下降值偏离项目整体");
      if (incompleteScore >= 20) reasons.push("所选指标随访数据不完整");
      row["风险原因"] = reasons.length ? reasons.join("；") : "未见明显异常";
      return row;
    })
    .sort((a, b) => Number(b["盲态疗效异常风险评分"] || 0) - Number(a["盲态疗效异常风险评分"] || 0) || String(a["中心"]).localeCompare(String(b["中心"]))),
);
const blindedEfficacyProjectRows = computed(() =>
  (state.value?.patient_medical_review?.project_summary || [])
    .filter((row) => (
      (usesHba1c.value || !String(row["指标"] || "").includes("HbA1c"))
      && (usesWeight.value || !String(row["指标"] || "").includes("体重"))
    ))
    .map((row) =>
      row["指标"] === "高风险中心数"
        ? { ...row, 数值: dynamicBlindedEfficacySiteRows.value.filter((item) => item["风险等级"] === "高").length }
        : row,
    ),
);
const blindedEfficacyChartRows = computed(() => dynamicBlindedEfficacySiteRows.value.slice(0, 15));
const screenFailureRows = computed(() => state.value?.patient_medical_review?.screen_failure_summary || []);
const selectedBlindedSite = ref("");
const selectedBlindedSitePatients = computed(() =>
  (state.value?.patient_medical_review?.subject_summary || []).filter((row) => String(row["中心"] || "") === selectedBlindedSite.value),
);
const maxBlindedHba1cDrop = computed(() => Math.max(...blindedEfficacyChartRows.value.map((row) => Math.abs(Number(row["HbA1c平均下降比例（%）"] || 0))), 1));
const maxBlindedWeightDrop = computed(() => Math.max(...blindedEfficacyChartRows.value.map((row) => Math.abs(Number(row["体重平均下降值（kg）"] || 0))), 1));
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

function blindedRiskClass(row: DataRow): string {
  const level = String(row["风险等级"] || "");
  if (level === "高") return "high";
  if (level === "中") return "medium";
  if (level === "观察") return "watch";
  return "low";
}

function patientInfluenceClass(row: DataRow): string {
  const level = String(row["影响等级"] || "");
  if (level === "高") return "high";
  if (level === "中") return "medium";
  return "low";
}

function selectBlindedSite(row: DataRow): void {
  selectedBlindedSite.value = String(row["中心"] || "");
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

watch(medicalSubjects, (items) => {
  if (!items.length) {
    selectedMedicalSubjectId.value = "";
    return;
  }
  if (!items.some((item) => item.subject_id === selectedMedicalSubjectId.value)) {
    selectedMedicalSubjectId.value = items[0].subject_id;
  }
});

watch(dynamicBlindedEfficacySiteRows, (items) => {
  if (!items.length) {
    selectedBlindedSite.value = "";
    return;
  }
  if (!items.some((item) => String(item["中心"] || "") === selectedBlindedSite.value)) {
    selectedBlindedSite.value = String(items[0]["中心"] || "");
  }
});

watch(selectedEfficacyModel, () => {
  blindedRiskWeightMessage.value = "已切换疗效指标组合，中心风险评分已自动更新。";
});

watch(selectedIndication, () => {
  selectedEfficacyModel.value = "hba1c_weight";
  selectedBlindedSite.value = "";
  blindedRiskWeightMessage.value = isConfiguredIndication.value
    ? "已切换项目适应症，请选择疗效指标组合。"
    : "当前适应症尚未接入疗效指标解析规则。";
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

function cancelUpload(): void {
  if (importingData.value) return;
  uploadPreview.value = null;
  pendingFiles.value = [];
  pendingSourceRoles.value = {};
}

function exportPackage(): void {
  window.location.href = `/api/export?${params.value.toString()}`;
}

async function loadState(): Promise<void> {
  try {
    state.value = await fetchState(params.value);
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

watch(theme, (nextTheme) => {
  document.body.dataset.theme = nextTheme;
}, { immediate: true });

watch(locale, (nextLocale) => {
  document.documentElement.lang = nextLocale === "zh" ? "zh-CN" : "en";
}, { immediate: true });

watch(sidebarCollapsed, (collapsed) => {
  document.body.classList.toggle("sidebar-collapsed", collapsed);
});

onMounted(() => {
  initializeSessionState();
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
        :t="t"
        @change-tab="activateTab"
        @change-locale="setLocale"
        @change-theme="setTheme"
      />

      <section class="workspace overview-mode">
        <section class="content">
          <section class="tab-page" :class="{ active: activeTab === 'import' }">
            <h1>{{ t("pages.import") }}</h1>

            <section class="project-risk-thresholds">
              <h2>项目风险阈值</h2>
              <div class="source-note">数据源：Form Excel（临床研究数据）</div>
              <div class="data-card efficacy-model-card">
                <div class="card-title">疗效指标配置</div>
                <div class="efficacy-model-body">
                  <p class="medical-subtitle">先选择项目适应症，再选择参与中心风险评分的疗效指标组合。当前已接入糖尿病项目的 HbA1c 和体重，其他适应症可按项目方案继续扩展。</p>
                  <div class="efficacy-model-fields">
                    <label class="efficacy-model-select">
                      <span><b>01</b>项目适应症</span>
                      <select v-model="selectedIndication">
                        <option v-for="option in indicationOptions" :key="option.value" :value="option.value">
                          {{ option.label }}
                        </option>
                      </select>
                    </label>
                    <label class="efficacy-model-select">
                      <span><b>02</b>疗效指标组合</span>
                      <select v-model="selectedEfficacyModel" :disabled="!isConfiguredIndication">
                        <option v-if="!isConfiguredIndication" value="hba1c_weight">请先配置该适应症的疗效指标</option>
                        <option v-for="option in isConfiguredIndication ? efficacyModelOptions : []" :key="option.value" :value="option.value">
                          {{ option.label }}
                        </option>
                      </select>
                    </label>
                  </div>
                </div>
              </div>
              <div v-if="!isConfiguredIndication" class="data-card">
                <div class="mapping-empty">{{ selectedIndicationConfig.label }} 尚未接入疗效指标解析规则。建议根据项目方案配置主要终点、辅助终点、变化方向、单位和中心异常评分权重。</div>
              </div>
              <div v-else-if="!hasClinicalData" class="data-card">
                <div class="mapping-empty">请先导入Form Excel/临床研究数据，导入后展示盲态疗效风险阈值和中心筛败率。</div>
              </div>
              <template v-else>
                <div class="data-card">
                  <div class="card-title">盲态中心疗效异常风险</div>
                  <p class="medical-subtitle">仅按中心汇总已选择疗效指标的相对基线变化，不展示试验组、对照组或剂量组。风险评分用于识别偏离项目整体或数据不完整的中心，不代表疗效优劣。</p>
                  <div class="metric-grid blinded-summary-grid">
                    <div v-for="row in blindedEfficacyProjectRows" :key="String(row['指标'])" class="metric-card">
                      <div class="metric-label">{{ row["指标"] }}</div>
                      <div class="metric-value">{{ row["数值"] }}</div>
                    </div>
                  </div>
                  <div class="blinded-chart-grid">
                    <div class="blinded-chart-panel">
                      <div class="chart-section-title">中心风险评分 Top 15</div>
                      <div class="center-chart blinded-risk-chart">
                        <div
                          v-for="row in blindedEfficacyChartRows"
                          :key="String(row['中心'])"
                          class="center-bar-row clickable-chart-row"
                          :class="{ selected: selectedBlindedSite === String(row['中心']) }"
                          role="button"
                          tabindex="0"
                          @click="selectBlindedSite(row)"
                          @keydown.enter="selectBlindedSite(row)"
                        >
                          <div class="center-bar-label">{{ row["中心"] }}</div>
                          <div class="center-bar-track">
                            <div class="center-bar-fill risk-score-fill" :class="blindedRiskClass(row)" :style="{ width: `${Math.max(2, Number(row['盲态疗效异常风险评分'] || 0))}%` }"></div>
                          </div>
                          <div class="center-bar-value">{{ row["盲态疗效异常风险评分"] }} · {{ row["风险等级"] }}</div>
                        </div>
                      </div>
                      <div class="risk-formula-panel">
                        <div class="risk-formula-title">动态计算方法</div>
                        <code>{{ blindedRiskFormula }}</code>
                        <p>填写当前显示的权重并点击“确定计算”。系统会按合计值自动归一化，并更新 Top 15 中心和风险等级。</p>
                        <label v-if="usesHba1c" class="risk-weight-control">
                          <span>HbA1c异常</span>
                          <input v-model.number="blindedRiskWeightInputs.hba1c" type="number" min="0" step="1" />
                          <strong>应用 {{ Math.round(normalizedBlindedRiskWeights.hba1c * 100) }}%</strong>
                        </label>
                        <label v-if="usesWeight" class="risk-weight-control">
                          <span>体重异常</span>
                          <input v-model.number="blindedRiskWeightInputs.weight" type="number" min="0" step="1" />
                          <strong>应用 {{ Math.round(normalizedBlindedRiskWeights.weight * 100) }}%</strong>
                        </label>
                        <label class="risk-weight-control">
                          <span>数据不完整</span>
                          <input v-model.number="blindedRiskWeightInputs.incomplete" type="number" min="0" step="1" />
                          <strong>应用 {{ Math.round(normalizedBlindedRiskWeights.incomplete * 100) }}%</strong>
                        </label>
                        <div class="risk-weight-actions">
                          <button type="button" class="risk-weight-apply" @click="applyBlindedRiskWeights">确定计算</button>
                          <span>{{ blindedRiskWeightMessage }}</span>
                        </div>
                      </div>
                    </div>
                    <div class="blinded-chart-panel">
                      <div class="chart-section-title">中心疗效变化 Top 15</div>
                      <div class="center-chart blinded-efficacy-chart">
                        <div
                          v-for="row in blindedEfficacyChartRows"
                          :key="String(row['中心'])"
                          class="blinded-efficacy-row clickable-chart-row"
                          :class="{ selected: selectedBlindedSite === String(row['中心']) }"
                          role="button"
                          tabindex="0"
                          @click="selectBlindedSite(row)"
                          @keydown.enter="selectBlindedSite(row)"
                        >
                          <div class="center-bar-label">{{ row["中心"] }}</div>
                          <div class="efficacy-bars">
                            <div v-if="usesHba1c" class="efficacy-bar-line">
                              <span>HbA1c</span>
                              <div class="center-bar-track"><div class="center-bar-fill hba1c-fill" :style="{ width: `${Math.max(2, (Math.abs(Number(row['HbA1c平均下降比例（%）'] || 0)) / maxBlindedHba1cDrop) * 100)}%` }"></div></div>
                              <strong>{{ row["HbA1c平均下降比例（%）"] }}%</strong>
                            </div>
                            <div v-if="usesWeight" class="efficacy-bar-line">
                              <span>体重</span>
                              <div class="center-bar-track"><div class="center-bar-fill weight-fill" :style="{ width: `${Math.max(2, (Math.abs(Number(row['体重平均下降值（kg）'] || 0)) / maxBlindedWeightDrop) * 100)}%` }"></div></div>
                              <strong>{{ row["体重平均下降值（kg）"] }}kg</strong>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-if="selectedBlindedSite" class="blinded-patient-panel">
                    <div class="chart-section-title">中心 {{ selectedBlindedSite }} / 患者疗效影响明细</div>
                    <p class="medical-subtitle">高亮患者对该中心盲态疗效异常影响较大。</p>
                    <div class="table-wrap blinded-patient-table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>受试者</th>
                            <th v-if="usesHba1c">HbA1c下降比例</th>
                            <th v-if="usesWeight">体重下降值</th>
                            <th>影响评分</th>
                            <th>影响等级</th>
                            <th>影响原因</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr
                            v-for="row in selectedBlindedSitePatients"
                            :key="String(row['受试者'])"
                            class="influential-patient-row"
                            :class="patientInfluenceClass(row)"
                          >
                            <td>{{ row["受试者"] }}</td>
                            <td v-if="usesHba1c" class="number">{{ row["HbA1c下降比例（%）"] ?? "-" }}%</td>
                            <td v-if="usesWeight" class="number">{{ row["体重下降值（kg）"] ?? "-" }}kg</td>
                            <td class="number">{{ row["患者影响评分"] }}</td>
                            <td>{{ row["影响等级"] }}</td>
                            <td>{{ row["影响原因"] }}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <div class="table-wrap">
                    <DataTable :rows="dynamicBlindedEfficacySiteRows" :limit="30" :empty-text="t('empty')" />
                  </div>
                </div>

                <div class="data-card">
                  <div class="card-title">中心筛败率</div>
                  <p class="medical-subtitle">筛选失败患者不纳入盲态疗效分析。筛败率单独用于识别入排标准执行、招募人群匹配度和筛选流程异常。</p>
                  <div class="table-wrap">
                    <DataTable :rows="screenFailureRows" :limit="30" :empty-text="t('empty')" />
                  </div>
                </div>
              </template>
            </section>
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
