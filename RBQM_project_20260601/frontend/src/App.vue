<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { commitUpload, fetchKriCatalog, fetchSession, fetchState, resetState, thresholdParams } from "./api";
import { thresholds as thresholdDefaults } from "./config";
import { translate } from "./i18n";
import type { DataRow, KriDrilldown, Locale, PatientMedicalRecord, PatientMedicalSubject, RbqmState, TabKey, Theme, ThresholdItem, UploadPreview, UploadRole } from "./types";
import DataTable from "./components/DataTable.vue";
import AppSelect from "./components/AppSelect.vue";
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
let panelObserver: MutationObserver | null = null;
let fullscreenPanel: HTMLElement | null = null;
const selectedAgeCenter = ref("");
const selectedSexCenter = ref("");
const selectedSexRiskGroup = ref<"over" | "within">("over");
const selectedHba1cCenter = ref("");
const selectedEtimeCenter = ref("");

const thresholds = reactive<ThresholdItem[]>(
  thresholdDefaults.map((item) => ({
    ...item,
    label: { ...item.label },
    group: { ...item.group },
  })),
);

function applyThresholdCatalog(items: ThresholdItem[]): void {
  thresholds.splice(
    0,
    thresholds.length,
    ...items.map((item) => ({
      ...item,
      label: { ...item.label },
      group: { ...item.group },
    })),
  );
}

const params = computed(() => thresholdParams(kriEnabled.value, thresholds));
const departmentOrder = ["MM", "ST", "PM", "DM"];
const departmentNames: Record<string, string> = {
  MM: "MM",
  ST: "ST",
  PM: "PM",
  DM: "DM",
};
const selectedDepartment = ref("MM");
const selectedMetricByDepartment = reactive<Record<string, string>>({});
const thresholdByKey = computed(() => new Map(thresholds.map((item) => [item.key, item])));

function isDefined<T>(value: T | null | undefined): value is T {
  return value !== null && value !== undefined;
}

const departmentRiskGroups = computed(() =>
  departmentOrder.map((department) => {
    const items = (state.value?.kri_drilldowns || [])
      .filter((item) => thresholdByKey.value.get(item.key)?.department === department || item.department === department)
      .map((item) => {
        const overRows = item.center_rows.filter((row) => Number(row["超阈值条数"] || 0) > 0);
        const values = item.center_rows.map((row) => Number(row["当前值"] || 0)).filter((value) => Number.isFinite(value));
        return {
          ...item,
          overRows,
          centerCount: item.center_rows.length,
          overCenterCount: overRows.length,
          maxValue: values.length ? Math.max(...values) : 0,
        };
      });
    return {
      department,
      label: departmentNames[department],
      items,
      metricCount: department === "MM"
        ? items.filter((item) => !mmBmiMetricKeys.includes(item.key)).length + (items.some((item) => mmBmiMetricKeys.includes(item.key)) ? 1 : 0)
        : items.length,
      overMetricCount: department === "MM"
        ? items.filter((item) => !mmBmiMetricKeys.includes(item.key) && item.overCenterCount > 0).length
          + (items.some((item) => mmBmiMetricKeys.includes(item.key) && item.overCenterCount > 0) ? 1 : 0)
        : items.filter((item) => item.overCenterCount > 0).length,
      overCenterCount: Array.from(new Set(items.flatMap((item) => item.overRows.map((row) => String(row["中心"] || ""))))).filter(Boolean).length,
    };
  }),
);
const activeDepartmentRiskGroup = computed(() =>
  departmentRiskGroups.value.find((group) => group.department === selectedDepartment.value) || departmentRiskGroups.value[0],
);
const mmBmiMetricKeys = ["baseline_bmi_avg", "bmi_under_24_rate", "bmi_30_35_rate", "bmi_over_35_count"];
const activeDepartmentQtlOptions = computed(() => {
  const group = activeDepartmentRiskGroup.value;
  const options: { value: string; label: string }[] = [];
  group.items.forEach((item) => {
    if (group.department === "MM" && mmBmiMetricKeys.includes(item.key)) {
      if (!options.some((option) => option.value === "mm_bmi")) options.push({ value: "mm_bmi", label: "BMI" });
      return;
    }
    const label = item.key === "avg_age_years"
      ? "年龄"
      : item.key === "male_rate"
        ? "受试者性别比例"
        : item.label;
    options.push({ value: item.key, label });
  });
  return options;
});
const activeDepartmentSelectedMetrics = computed(() => {
  const group = activeDepartmentRiskGroup.value;
  const selectedKey = selectedMetricByDepartment[group.department] || "";
  if (selectedKey === "mm_bmi") return group.items.filter((item) => mmBmiMetricKeys.includes(item.key));
  const metric = group.items.find((item) => item.key === selectedKey);
  return metric ? [metric] : [];
});
const activeDepartmentMetricGroups = computed(() => {
  const metrics = activeDepartmentSelectedMetrics.value;
  if (selectedMetricByDepartment[activeDepartmentRiskGroup.value.department] !== "mm_bmi") {
    return metrics.map((metric) => ({ key: metric.key, title: metric.label, metrics: [metric] }));
  }
  const byKey = new Map(metrics.map((metric) => [metric.key, metric]));
  const bmiMetrics = [
    byKey.get("baseline_bmi_avg"),
    byKey.get("bmi_under_24_rate"),
    byKey.get("bmi_30_35_rate"),
    byKey.get("bmi_over_35_count"),
  ].filter(isDefined);
  return bmiMetrics.length ? [{ key: "bmi", title: "BMI", metrics: bmiMetrics }] : [];
});
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
const hba1cBayesianPrediction = computed(() => state.value?.patient_medical_review?.bayesian_hba1c_prediction || null);
const hba1cBayesianSummaryRows = computed(() => hba1cBayesianPrediction.value?.summary || []);
const hba1cBayesianProbabilityRows = computed(() => hba1cBayesianPrediction.value?.probabilities || []);
const hba1cBayesianCenterRows = computed(() => hba1cBayesianPrediction.value?.center_rows || []);
const hba1cBayesianBenchmarks = computed(() => hba1cBayesianPrediction.value?.drug_benchmarks || []);
const hba1cPredictedDropPoints = computed(() => {
  const row = hba1cBayesianSummaryRows.value.find((item) => String(item["指标"] || "").includes("贝叶斯预测：HbA1c下降值"));
  return Number(row?.["数值"] || 0);
});
const hba1cBenchmarkMax = computed(() =>
  Math.max(
    hba1cPredictedDropPoints.value,
    ...hba1cBayesianBenchmarks.value.map((row) => Number(row["典型HbA1c下降（百分点）"] || 0)),
    1,
  ),
);
const hba1cPosterior = computed(() => hba1cBayesianPrediction.value?.posterior || {});
const hba1cPosteriorMean = computed(() => Number(hba1cPosterior.value.points_mean || hba1cPredictedDropPoints.value || 0));
const hba1cPosteriorSd = computed(() => Math.max(Number(hba1cPosterior.value.points_sd || 0.1), 0.01));
const hba1cObservedPointSd = computed(() => Math.max(Number(hba1cPosterior.value.points_observed_sd || 1), 0.01));
const hba1cPosteriorLow = computed(() => Number(hba1cPosterior.value.points_ci_low || (hba1cPosteriorMean.value - 1.96 * hba1cPosteriorSd.value)));
const hba1cPosteriorHigh = computed(() => Number(hba1cPosterior.value.points_ci_high || (hba1cPosteriorMean.value + 1.96 * hba1cPosteriorSd.value)));
const hba1cPosteriorDomain = computed(() => {
  const min = Math.min(0, hba1cPosteriorLow.value - 0.2);
  const max = Math.max(hba1cBenchmarkMax.value + 0.2, hba1cPosteriorHigh.value + 0.2, 2);
  return { min, max };
});
function hba1cPosteriorX(value: number): number {
  const domain = hba1cPosteriorDomain.value;
  return 40 + ((value - domain.min) / Math.max(domain.max - domain.min, 0.01)) * 520;
}
function drugClassColor(value: unknown): string {
  const text = String(value || "");
  if (text.includes("GLP-1")) return "#7c3aed";
  if (text.includes("SGLT2")) return "#0f9f8f";
  if (text.includes("DPP-4")) return "#2563eb";
  if (text.includes("磺脲")) return "#f79009";
  if (text.includes("TZD")) return "#d92d20";
  if (text.includes("二甲双胍")) return "#475467";
  return "#64748b";
}
const hba1cBenchmarkRows = computed(() =>
  [...hba1cBayesianBenchmarks.value]
    .sort((a, b) => Number(b["典型HbA1c下降（百分点）"] || 0) - Number(a["典型HbA1c下降（百分点）"] || 0)),
);
const hba1cFunnelRows = computed(() =>
  hba1cBayesianCenterRows.value
    .map((row) => ({
      site: String(row["中心"] || ""),
      n: Number(row["可评估人数"] || 0),
      value: Number(row["平均下降值（百分点）"] || 0),
      pct: Number(row["平均下降比例（%）"] || 0),
    }))
    .filter((row) => row.site && row.n > 0 && Number.isFinite(row.value)),
);
const hba1cFunnelMaxN = computed(() => Math.max(...hba1cFunnelRows.value.map((row) => row.n), 1));
function hba1cFunnelLimit(n: number, z: number, direction: 1 | -1): number {
  return hba1cPosteriorMean.value + direction * z * hba1cObservedPointSd.value / Math.sqrt(Math.max(n, 1));
}
const hba1cFunnelYDomain = computed(() => {
  const values = hba1cFunnelRows.value.flatMap((row) => [
    row.value,
    hba1cFunnelLimit(row.n, 2.58, 1),
    hba1cFunnelLimit(row.n, 2.58, -1),
  ]);
  const min = Math.min(...values, hba1cPosteriorMean.value) - 0.25;
  const max = Math.max(...values, hba1cPosteriorMean.value) + 0.25;
  return { min, max };
});
function hba1cFunnelX(n: number): number {
  return 56 + (n / Math.max(hba1cFunnelMaxN.value, 1)) * 494;
}
function hba1cFunnelY(value: number): number {
  const domain = hba1cFunnelYDomain.value;
  return 32 + ((domain.max - value) / Math.max(domain.max - domain.min, 0.01)) * 238;
}
function hba1cFunnelCurve(z: number, direction: 1 | -1): string {
  const maxN = Math.max(hba1cFunnelMaxN.value, 1);
  return Array.from({ length: 60 }, (_, index) => {
    const n = 1 + (index / 59) * (maxN - 1);
    return `${hba1cFunnelX(n).toFixed(1)},${hba1cFunnelY(hba1cFunnelLimit(n, z, direction)).toFixed(1)}`;
  }).join(" ");
}
function hba1cFunnelClass(row: { n: number; value: number }): string {
  const upper99 = hba1cFunnelLimit(row.n, 2.58, 1);
  const lower99 = hba1cFunnelLimit(row.n, 2.58, -1);
  const upper95 = hba1cFunnelLimit(row.n, 1.96, 1);
  const lower95 = hba1cFunnelLimit(row.n, 1.96, -1);
  if (row.value > upper99 || row.value < lower99) return "extreme";
  if (row.value > upper95 || row.value < lower95) return "outside";
  return "inside";
}
function hba1cPosteriorDensity(value: number): number {
  const sd = hba1cPosteriorSd.value;
  const z = (value - hba1cPosteriorMean.value) / sd;
  return Math.exp(-0.5 * z * z);
}
const hba1cPosteriorPoints = computed(() => {
  const domain = hba1cPosteriorDomain.value;
  const points = Array.from({ length: 80 }, (_, index) => {
    const value = domain.min + (index / 79) * (domain.max - domain.min);
    const x = hba1cPosteriorX(value);
    const y = 178 - hba1cPosteriorDensity(value) * 112;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return points.join(" ");
});
const hba1cPosteriorAreaPoints = computed(() => `40,178 ${hba1cPosteriorPoints.value} 560,178`);
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
const screenFailureDetailRows = computed(() => state.value?.patient_medical_review?.screen_failure_details || []);
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

function updateKriEnabled(enabled: boolean): void {
  kriEnabled.value = enabled;
  void loadState();
}

function onThresholdChanged(): void {
  void loadState();
}

function departmentMetricRows(item: KriDrilldown): DataRow[] {
  return item.center_rows
    .map((row) => ({
      中心: row["中心"],
      当前值: row["当前值"],
      阈值: row["阈值"],
      超阈值条数: row["超阈值条数"],
      __distance: thresholdDistance(Number(row["当前值"] || 0), row["阈值"]),
    }))
    .sort((a, b) => Number(a.__distance) - Number(b.__distance) || String(a["中心"]).localeCompare(String(b["中心"]), undefined, { numeric: true }))
    .map(({ __distance, ...row }) => row);
}

function ageDetailRows(item: KriDrilldown): DataRow[] {
  if (!selectedAgeCenter.value) return [];
  return item.details
    .filter((row) => String(row["中心"] || "") === selectedAgeCenter.value)
    .sort((a, b) => String(a["受试者编号"] || "").localeCompare(String(b["受试者编号"] || ""), undefined, { numeric: true }))
    .map((row) => ({
      受试者编号: row["受试者编号"] || row["受试者"] || "",
      年龄: row["年龄"],
    }));
}

function ageDetailValue(row: DataRow): number {
  return Number(row["年龄"]);
}

function formatAgeDetail(row: DataRow): string {
  const value = ageDetailValue(row);
  if (!Number.isFinite(value)) return "";
  return `${Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1)}岁`;
}

function isAgeDetailOverThreshold(row: DataRow, item: KriDrilldown): boolean {
  const value = ageDetailValue(row);
  const threshold = Number(item.threshold);
  return Number.isFinite(value) && Number.isFinite(threshold) && value > threshold;
}

function sexCenterSummary(item: KriDrilldown): { male: number; female: number; total: number; malePct: number; femalePct: number } {
  if (!selectedSexCenter.value) return { male: 0, female: 0, total: 0, malePct: 0, femalePct: 0 };
  const rows = item.details.filter((row) => String(row["中心"] || "") === selectedSexCenter.value);
  const male = rows.filter((row) => /^(m|male|男|男性)$/i.test(String(row["性别"] || "").trim())).length;
  const female = rows.filter((row) => /^(f|female|女|女性)$/i.test(String(row["性别"] || "").trim())).length;
  const total = male + female;
  return {
    male,
    female,
    total,
    malePct: total ? male / total : 0,
    femalePct: total ? female / total : 0,
  };
}

function sexRiskSummary(item: KriDrilldown): { over: number; within: number; total: number; overPct: number; withinPct: number } {
  const threshold = Number(item.threshold);
  const limit = Number.isFinite(threshold) ? threshold : 0.6;
  const rows = departmentChartRows(item).filter((row) => row.site);
  const over = rows.filter((row) => row.value > limit).length;
  const within = rows.length - over;
  const total = rows.length;
  return {
    over,
    within,
    total,
    overPct: total ? over / total : 0,
    withinPct: total ? within / total : 0,
  };
}

function sexRiskCenters(item: KriDrilldown) {
  const threshold = Number(item.threshold);
  const limit = Number.isFinite(threshold) ? threshold : 0.6;
  return departmentChartRows(item)
    .filter((row) => selectedSexRiskGroup.value === "over" ? row.value > limit : row.value <= limit)
    .sort((a, b) => b.value - a.value || a.site.localeCompare(b.site, undefined, { numeric: true }));
}

function donutLabelPosition(startPct: number, segmentPct: number): { x: number; y: number } {
  const angle = (-90 + (startPct + segmentPct / 2) * 3.6) * Math.PI / 180;
  return {
    x: 60 + Math.cos(angle) * 42,
    y: 60 + Math.sin(angle) * 42,
  };
}

function selectSexRiskGroup(group: "over" | "within"): void {
  selectedSexRiskGroup.value = group;
  selectedSexCenter.value = "";
}

function selectAgeCenter(site: string): void {
  selectedAgeCenter.value = site;
}

function selectSexCenter(site: string): void {
  selectedSexCenter.value = site;
}

function thresholdDistance(value: number, threshold: DataRow[string]): number {
  const text = String(threshold ?? "").trim();
  const range = text.match(/(-?\d+(?:\.\d+)?)\s*[-–~至]\s*(-?\d+(?:\.\d+)?)/);
  if (range) {
    const lower = Number(range[1]);
    const upper = Number(range[2]);
    if (value < lower) return lower - value;
    if (value > upper) return value - upper;
    return Math.min(value - lower, upper - value);
  }
  const numericThreshold = Number(text);
  return Number.isFinite(numericThreshold) ? Math.abs(value - numericThreshold) : Number.POSITIVE_INFINITY;
}

function departmentChartRows(item: KriDrilldown) {
  const rows = item.center_rows
    .map((row) => ({
      site: String(row["中心"] || ""),
      value: Number(row["当前值"] || 0),
      threshold: row["阈值"],
      count: Number(row["超阈值条数"] || 0),
      status: String(row["状态"] || ""),
    }));
  const merged = new Map<string, (typeof rows)[number]>();
  for (const row of rows) {
    if (!row.site) continue;
    const existing = merged.get(row.site);
    if (!existing) {
      merged.set(row.site, { ...row });
      continue;
    }
    existing.count = Math.max(existing.count, row.count);
    if (row.value > existing.value) existing.value = row.value;
    existing.status = existing.count > 0 ? "有超阈值记录" : "未超阈值";
  }
  return Array.from(merged.values())
    .sort((a, b) => b.count - a.count || b.value - a.value || a.site.localeCompare(b.site));
}

function departmentChartMax(item: KriDrilldown): number {
  return Math.max(
    ...departmentChartRows(item).map((row) => Math.abs(row.value)),
    Number.isFinite(Number(item.threshold)) ? Number(item.threshold) : 0,
    1,
  );
}

function ageChartMax(item: KriDrilldown): number {
  return Math.max(65, departmentChartMax(item) * 1.08);
}

function ageChartRows(item: KriDrilldown) {
  const rowsBySite = new Map<string, ReturnType<typeof departmentChartRows>[number]>();
  for (const row of departmentChartRows(item)) {
    if (!row.site || !Number.isFinite(row.value) || row.value <= 0) continue;
    const existing = rowsBySite.get(row.site);
    if (!existing || row.value > existing.value) rowsBySite.set(row.site, row);
  }
  return Array.from(rowsBySite.values()).sort((a, b) => a.site.localeCompare(b.site, undefined, { numeric: true }));
}

function ageChartWidth(item: KriDrilldown): number {
  return Math.max(560, ageChartRows(item).length * 36 + 68);
}

function agePointX(index: number): number {
  return 38 + index * 36;
}

function agePointY(value: number, item: KriDrilldown): number {
  return 24 + ((ageChartMax(item) - value) / ageChartMax(item)) * 190;
}

function ageLinePoints(item: KriDrilldown): string {
  return ageChartRows(item)
    .map((row, index) => `${agePointX(index)},${agePointY(row.value, item)}`)
    .join(" ");
}

function isTopAgeThresholdCenter(item: KriDrilldown, site: string): boolean {
  const threshold = Number(item.threshold);
  const target = Number.isFinite(threshold) ? threshold : 50;
  return ageChartRows(item)
    .filter((row) => row.value > 0)
    .sort((a, b) => Math.abs(a.value - target) - Math.abs(b.value - target) || a.site.localeCompare(b.site, undefined, { numeric: true }))
    .slice(0, 10)
    .some((row) => row.site === site);
}

function ratioPercent(value: number): number {
  return Math.max(0, Math.min(100, value * 100));
}

function sexProjectSummary(item: KriDrilldown): { male: number; female: number; total: number; malePct: number; femalePct: number } {
  const detailRows = item.details || [];
  const male = detailRows.filter((row) => String(row["性别"] || "").includes("男")).length;
  const female = detailRows.filter((row) => String(row["性别"] || "").includes("女")).length;
  const total = male + female;
  if (total > 0) {
    return {
      male,
      female,
      total,
      malePct: male / total,
      femalePct: female / total,
    };
  }
  const centerRows = departmentChartRows(item);
  const fallbackMale = centerRows.reduce((sum, row) => sum + row.value, 0);
  const fallbackTotal = centerRows.length || 1;
  return {
    male: 0,
    female: 0,
    total: 0,
    malePct: fallbackMale / fallbackTotal,
    femalePct: 1 - fallbackMale / fallbackTotal,
  };
}

function hba1cChartRows(item: KriDrilldown) {
  return departmentChartRows(item).sort((a, b) => {
    const aDistance = hba1cRangeDistance(a.value);
    const bDistance = hba1cRangeDistance(b.value);
    return bDistance - aDistance || a.site.localeCompare(b.site, undefined, { numeric: true });
  });
}

function hba1cRadarRows(item: KriDrilldown) {
  return departmentChartRows(item)
    .filter((row) => row.value > 0)
    .sort((a, b) => a.site.localeCompare(b.site, undefined, { numeric: true }));
}

function hba1cRangeDistance(value: number): number {
  if (value <= 0) return 0;
  if (value < 8) return 8 - value;
  if (value > 8.5) return value - 8.5;
  return 0;
}

function hba1cOffsetPct(value: number): number {
  const distance = hba1cRangeDistance(value);
  return Math.min(50, Math.max(4, distance / 2 * 50));
}

function hba1cRadarMax(item: KriDrilldown): number {
  const values = hba1cRadarRows(item).map((row) => row.value);
  const max = values.length ? Math.max(...values) : 8.5;
  return Math.ceil(max * 2) / 2;
}

function hba1cRadarRadius(value: number, item: KriDrilldown): number {
  const min = 8.0;
  const max = hba1cRadarMax(item);
  return Math.max(4, ((value - min) / Math.max(max - min, 0.5)) * 200);
}

function hba1cRadarRings(item: KriDrilldown): number[] {
  const max = hba1cRadarMax(item);
  const rings: number[] = [];
  for (let v = 8.0; v <= max; v += 0.5) rings.push(v);
  return rings;
}

function hba1cRadarPoint(item: KriDrilldown, row: { site: string; value: number }, index: number): { x: number; y: number } {
  const rows = hba1cRadarRows(item);
  const angle = -Math.PI / 2 + (Math.PI * 2 * index) / Math.max(rows.length, 1);
  const radius = hba1cRadarRadius(row.value, item);
  return {
    x: 220 + Math.cos(angle) * radius,
    y: 220 + Math.sin(angle) * radius,
  };
}

function hba1cRadarPolygon(item: KriDrilldown): string {
  return hba1cRadarRows(item)
    .map((row, index) => {
      const point = hba1cRadarPoint(item, row, index);
      return `${point.x.toFixed(1)},${point.y.toFixed(1)}`;
    })
    .join(" ");
}

function hba1cRingRadius(value: number, item: KriDrilldown): number {
  return hba1cRadarRadius(value, item);
}

function hba1cSelectedCenter(item: KriDrilldown): string {
  const rows = hba1cRadarRows(item);
  if (selectedHba1cCenter.value && rows.some((row) => row.site === selectedHba1cCenter.value)) return selectedHba1cCenter.value;
  return rows[0]?.site || "";
}

function selectHba1cCenter(site: string): void {
  selectedHba1cCenter.value = site;
}

function hba1cSelectedSummary(item: KriDrilldown): { site: string; value: number; status: string; count: number } {
  const site = hba1cSelectedCenter(item);
  const row = departmentChartRows(item).find((entry) => entry.site === site);
  const count = item.details.filter((detail) => String(detail["中心"] || "") === site).length;
  return {
    site,
    value: row?.value || 0,
    status: row && hba1cRangeDistance(row.value) > 0 ? "超出8-8.5%" : "处于8-8.5%",
    count,
  };
}

function hba1cSelectedDetailRows(item: KriDrilldown): DataRow[] {
  const site = hba1cSelectedCenter(item);
  if (!site) return [];
  return item.details
    .filter((row) => String(row["中心"] || "") === site)
    .sort((a, b) => String(a["受试者编号"] || "").localeCompare(String(b["受试者编号"] || ""), undefined, { numeric: true }))
    .map((row) => {
      const val = Number(row["HbA1c"] || 0);
      const avg = Number(row["中心均值"] || 0);
      const diff = val - avg;
      return {
        受试者编号: row["受试者编号"],
        访视: row["访视"],
        HbA1c: `${val.toFixed(1)}%`,
        与均值差: `${diff >= 0 ? "+" : ""}${diff.toFixed(2)}%`,
      };
    });
}


function bmiSourceSummary(item: KriDrilldown): { loaded: boolean; subjectCount: number; centerCount: number; projectAverage: number } {
  const rows = item.details || [];
  const values = rows.map((row) => Number(row["BMI"] || 0)).filter((value) => Number.isFinite(value) && value > 0);
  return {
    loaded: values.length > 0,
    subjectCount: values.length,
    centerCount: new Set(rows.map((row) => String(row["中心"] || "")).filter(Boolean)).size,
    projectAverage: values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0,
  };
}

function bmiMetricRows(item: KriDrilldown) {
  return departmentChartRows(item).sort((a, b) => b.count - a.count || b.value - a.value || a.site.localeCompare(b.site, undefined, { numeric: true }));
}

function bmiThresholdText(item: KriDrilldown): string {
  if (item.key === "baseline_bmi_avg") return "中心基线BMI均值 <29";
  if (item.key === "bmi_under_24_rate") return "中心BMI<24比例 <3%";
  if (item.key === "bmi_30_35_rate") return "中心BMI 30-35比例 <15%";
  if (item.key === "bmi_over_35_count") return "中心BMI>35例数 =0";
  return "";
}

function bmiOverCenters(item: KriDrilldown): Set<string> {
  return new Set(
    bmiMetricRows(item)
      .filter((row) => {
        if (item.key === "baseline_bmi_avg") return row.value >= 29;
        if (item.key === "bmi_under_24_rate") return row.value >= 0.03;
        if (item.key === "bmi_30_35_rate") return row.value >= 0.15;
        if (item.key === "bmi_over_35_count") return row.value > 0;
        return false;
      })
      .map((row) => row.site),
  );
}

function bmiDetailRows(item: KriDrilldown): DataRow[] {
  const overCenters = bmiOverCenters(item);
  return (item.details || [])
    .filter((row) => {
      const site = String(row["中心"] || "");
      const bmi = Number(row["BMI"] || 0);
      if (!overCenters.has(site) || !Number.isFinite(bmi) || bmi <= 0) return false;
      if (item.key === "baseline_bmi_avg") return true;
      if (item.key === "bmi_under_24_rate") return bmi < 24;
      if (item.key === "bmi_30_35_rate") return bmi >= 30 && bmi < 35;
      if (item.key === "bmi_over_35_count") return bmi > 35;
      return false;
    })
    .sort((a, b) =>
      String(a["中心"] || "").localeCompare(String(b["中心"] || ""), undefined, { numeric: true })
      || Number(b["BMI"] || 0) - Number(a["BMI"] || 0)
      || String(a["受试者编号"] || "").localeCompare(String(b["受试者编号"] || ""), undefined, { numeric: true }),
    )
    .map((row) => ({
      中心: row["中心"],
      受试者编号: row["受试者编号"],
      BMI: Number(row["BMI"] || 0).toFixed(2),
    }));
}

function etimePct(value: number): string {
  return Math.min(100, Math.max(0, value * 100)).toFixed(1) + "%";
}

function etimeProjectSummary(item: KriDrilldown): { total: number; exitCount: number; rate: string } {
  const backendTotal = Number(item.project_subjects || 0);
  const backendExit = Number(item.project_events || 0);
  if (backendTotal > 0) {
    return { total: backendTotal, exitCount: backendExit, rate: (backendExit / backendTotal * 100).toFixed(1) };
  }
  const rows = departmentChartRows(item);
  let totalSubjects = 0;
  let exitSubjects = 0;
  for (const row of rows) {
    const count = Number(row.count) || 0;
    if (count > 0) exitSubjects += count;
    totalSubjects += Math.round(Number(row.value) > 0 ? count / row.value : 0);
  }
  if (totalSubjects === 0 && rows.length > 0) {
    const rates = rows.map((r) => r.value);
    const avg = rates.reduce((a, b) => a + b, 0) / rates.length;
    return { total: 0, exitCount: 0, rate: (avg * 100).toFixed(1) };
  }
  return { total: totalSubjects, exitCount: exitSubjects, rate: (totalSubjects > 0 ? (exitSubjects / totalSubjects * 100) : 0).toFixed(1) };
}

function selectEtimeCenter(site: string): void {
  selectedEtimeCenter.value = selectedEtimeCenter.value === site ? "" : site;
}

function etimeDetailRows(item: KriDrilldown): DataRow[] {
  if (!selectedEtimeCenter.value) return [];
  return item.details
    .filter((row) => String(row["中心"] || "") === selectedEtimeCenter.value)
    .sort((a, b) => String(a["受试者编号"] || "").localeCompare(String(b["受试者编号"] || ""), undefined, { numeric: true }))
    .map((row) => ({
      "受试者编号": row["受试者编号"] || "",
      "受试者状态": row["受试者状态"] || row["状态"] || "",
    }));
}

function pregProjectRate(item: KriDrilldown): string {
  const denominator = pregProjectSubjectCount(item);
  const positives = pregPositiveCount(item);
  const rate = denominator > 0 ? positives / denominator : 0;
  return (rate * 100).toFixed(2) + "%";
}

function pregProjectSubjectCount(item: KriDrilldown): number {
  return Number(item.project_subjects || 0);
}

function pregPositiveCount(item: KriDrilldown): number {
  return new Set((item.details || []).map((row) => String(row["受试者编号"] || "")).filter(Boolean)).size;
}

function pregCenterCount(item: KriDrilldown): number {
  return new Set((item.details || []).map((row) => String(row["中心"] || "")).filter(Boolean)).size;
}

function pregBarWidth(value: number): string {
  return Math.max(3, Math.min(100, value / 0.10 * 100)) + "%";
}

function selectDepartment(department: string): void {
  selectedDepartment.value = department;
  selectedAgeCenter.value = "";
  selectedSexCenter.value = "";
  selectedSexRiskGroup.value = "over";
  selectedHba1cCenter.value = "";
  selectedEtimeCenter.value = "";
}

function selectDepartmentMetric(department: string, value: string): void {
  selectedMetricByDepartment[department] = value;
  selectedAgeCenter.value = "";
  selectedSexCenter.value = "";
  selectedSexRiskGroup.value = "over";
  selectedHba1cCenter.value = "";
}

function closeFullscreenPanel(): void {
  fullscreenPanel?.classList.remove("panel-fullscreen");
  fullscreenPanel?.querySelector<HTMLButtonElement>(".panel-fullscreen-button")?.setAttribute("aria-label", "全屏放大");
  document.body.classList.remove("panel-fullscreen-open");
  fullscreenPanel = null;
}

function toggleFullscreenPanel(panel: HTMLElement): void {
  if (fullscreenPanel === panel) {
    closeFullscreenPanel();
    return;
  }
  closeFullscreenPanel();
  fullscreenPanel = panel;
  panel.classList.add("panel-fullscreen");
  panel.querySelector<HTMLButtonElement>(".panel-fullscreen-button")?.setAttribute("aria-label", "退出全屏");
  document.body.classList.add("panel-fullscreen-open");
}

function enhanceFullscreenPanels(root: ParentNode = document): void {
  const selector = ".department-metric-card, .data-card, .blinded-chart-panel, .blinded-patient-panel";
  root.querySelectorAll<HTMLElement>(selector).forEach((panel) => {
    if (panel.dataset.fullscreenReady === "true") return;
    panel.dataset.fullscreenReady = "true";
    panel.classList.add("fullscreen-capable-panel");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "panel-fullscreen-button";
    button.setAttribute("aria-label", "全屏放大");
    button.title = "全屏放大";
    button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"></path></svg>';
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleFullscreenPanel(panel);
      button.title = panel.classList.contains("panel-fullscreen") ? "退出全屏" : "全屏放大";
    });
    panel.appendChild(button);
  });
}

function onFullscreenKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") closeFullscreenPanel();
}

async function initializeSessionState(): Promise<void> {
  try {
    const catalog = await fetchKriCatalog();
    kriEnabled.value = catalog.kri_enabled;
    applyThresholdCatalog(catalog.metrics);
  } catch (error) {
    console.warn("Unable to load KRI catalog; using frontend defaults", error);
  }
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
  enhanceFullscreenPanels();
  panelObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node instanceof HTMLElement) {
          if (node.matches(".department-metric-card, .data-card, .blinded-chart-panel, .blinded-patient-panel")) {
            enhanceFullscreenPanels(node.parentNode || document);
          } else {
            enhanceFullscreenPanels(node);
          }
        }
      });
    });
  });
  panelObserver.observe(document.querySelector(".content") || document.body, { childList: true, subtree: true });
  document.addEventListener("keydown", onFullscreenKeydown);
});

onBeforeUnmount(() => {
  panelObserver?.disconnect();
  document.removeEventListener("keydown", onFullscreenKeydown);
  closeFullscreenPanel();
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
              <h2>各部门QTL一览</h2>
              <div
                v-if="selectedDepartment === 'DM' ? !hasProgressReport : !hasClinicalData"
                class="source-note"
              >
                {{ selectedDepartment === "DM" ? "请导入进展报告" : "请导入项目数据" }}
              </div>
              <div class="department-nav" role="tablist" aria-label="职能部门">
                <button
                  v-for="group in departmentRiskGroups"
                  :key="group.department"
                  type="button"
                  :class="{ active: selectedDepartment === group.department }"
                  @click="selectDepartment(group.department)"
                >
                  <span>{{ group.label }}</span>
                  <strong>{{ group.overMetricCount }}/{{ group.metricCount }}</strong>
                </button>
              </div>
              <section class="department-risk-section">
                <div class="department-risk-toolbar">
                  <div class="department-risk-header">
                    <div>
                      <div class="department-code">{{ activeDepartmentRiskGroup.label }}</div>
                      <div class="department-caption">按已确定阈值展示整体和中心情况</div>
                    </div>
                  </div>
                  <div v-if="activeDepartmentRiskGroup.items.length" class="department-qtl-panel">
                    <label class="department-qtl-select">
                      <span>选择该部门QTL</span>
                      <AppSelect
                        :model-value="selectedMetricByDepartment[activeDepartmentRiskGroup.department] || ''"
                        :options="activeDepartmentQtlOptions"
                        aria-label="选择该部门QTL"
                        @update:model-value="selectDepartmentMetric(activeDepartmentRiskGroup.department, $event)"
                      />
                    </label>
                  </div>
                </div>
                <div v-if="!activeDepartmentRiskGroup.items.length" class="mapping-empty department-empty">
                  该职能部门的图片指标尚未接入可计算数据字段。
                </div>
                <div class="department-risk-right">
                  <article
                    v-for="metricGroup in activeDepartmentMetricGroups"
                    :key="metricGroup.key"
                    class="department-metric-card"
                  >
                    <template v-for="metric in metricGroup.metrics" :key="metric.key">
                      <div v-if="metricGroup.metrics.length > 1" class="department-submetric-title">
                        {{ metric.label }}
                      </div>

                      <div v-if="metric.key === 'avg_age_years'" class="department-center-chart age-center-chart">
                        <div class="age-chart-legend">
                          <span>各中心入组患者平均年龄</span>
                        </div>
                        <div class="age-line-chart-wrap">
                          <svg
                            class="age-line-chart"
                            :style="{ width: `${ageChartWidth(metric)}px` }"
                            :viewBox="`0 0 ${ageChartWidth(metric)} 280`"
                            role="img"
                            aria-label="各中心平均年龄折线图"
                          >
                            <line
                              x1="36"
                              :x2="ageChartWidth(metric) - 24"
                              :y1="agePointY(Number(metric.threshold) || 50, metric)"
                              :y2="agePointY(Number(metric.threshold) || 50, metric)"
                              class="age-reference-line"
                            />
                            <polyline :points="ageLinePoints(metric)" class="age-line" />
                            <g
                              v-for="(row, index) in ageChartRows(metric)"
                              :key="row.site"
                              class="age-center-point"
                              role="button"
                              tabindex="0"
                              @click="selectAgeCenter(row.site)"
                              @keydown.enter="selectAgeCenter(row.site)"
                            >
                              <circle
                                :cx="agePointX(index)"
                                :cy="agePointY(row.value, metric)"
                                r="5"
                                class="age-point"
                                :class="{ alert: isTopAgeThresholdCenter(metric, row.site), selected: selectedAgeCenter === row.site }"
                              />
                              <text
                                :x="agePointX(index)"
                                :y="agePointY(row.value, metric) - 10"
                                class="age-value-label"
                              >{{ row.value.toFixed(1) }}</text>
                              <text
                                :x="agePointX(index)"
                                y="252"
                                class="age-site-label"
                                :class="{ selected: selectedAgeCenter === row.site }"
                                :transform="`rotate(-35 ${agePointX(index)} 252)`"
                              >{{ row.site }}</text>
                            </g>
                          </svg>
                        </div>
                        <div class="age-threshold-legend age-threshold-legend-bottom">
                          <i aria-hidden="true"></i>
                          <span>年龄阈值50岁</span>
                        </div>
                        <div v-if="selectedAgeCenter" class="age-center-details">
                          <div class="age-center-details-title">中心 {{ selectedAgeCenter }} / 受试者年龄明细</div>
                          <div v-if="ageDetailRows(metric).length" class="age-detail-grid">
                            <div
                              v-for="row in ageDetailRows(metric)"
                              :key="String(row['受试者编号'])"
                              class="age-detail-chip"
                              :class="{ alert: isAgeDetailOverThreshold(row, metric) }"
                            >
                              <span>{{ row["受试者编号"] }}</span>
                              <strong>{{ formatAgeDetail(row) }}</strong>
                            </div>
                          </div>
                          <div v-else class="mapping-empty">
                            {{ t("empty") }}
                          </div>
                        </div>
                      </div>

                      <template v-else-if="metric.key === 'male_rate'">
                        <div class="department-center-chart sex-ratio-chart">
                          <div class="sex-project-summary">
                          <div>
                            <div class="sex-summary-title">项目整体性别比例</div>
                            <div class="sex-summary-subtitle">
                              男性 {{ sexProjectSummary(metric).male }}人 / 女性 {{ sexProjectSummary(metric).female }}人
                            </div>
                          </div>
                          <div
                            class="department-metric-status sex-summary-status"
                            :class="{ alert: metric.overCenterCount > 0 }"
                          >
                            {{ metric.overCenterCount > 0 ? "存在超阈值中心" : "未超阈值" }}
                          </div>
                          <strong>男性阈值：60%</strong>
                          <div class="sex-project-track">
                            <div class="sex-ratio-male" :style="{ width: `${ratioPercent(sexProjectSummary(metric).malePct)}%` }">
                              <span>{{ ratioPercent(sexProjectSummary(metric).malePct).toFixed(1) }}%</span>
                            </div>
                            <div class="sex-ratio-female" :style="{ width: `${ratioPercent(sexProjectSummary(metric).femalePct)}%` }">
                              <span>{{ ratioPercent(sexProjectSummary(metric).femalePct).toFixed(1) }}%</span>
                            </div>
                            <div class="sex-threshold-guide" aria-label="男性比例60%警戒线">
                              <span>60%</span>
                            </div>
                          </div>
                          <div class="sex-color-legend" aria-label="性别颜色图例">
                            <span><i class="male-legend"></i>男性</span>
                            <span><i class="female-legend"></i>女性</span>
                          </div>
                        </div>
                          <div class="sex-risk-overview">
                            <div class="sex-risk-donut-wrap">
                              <svg class="sex-risk-donut" viewBox="0 0 120 120" role="img" aria-label="中心男性比例超阈值分布">
                                <circle class="sex-risk-donut-base" cx="60" cy="60" r="42" pathLength="100"></circle>
                                <circle
                                  v-if="sexRiskSummary(metric).over"
                                  class="sex-risk-donut-segment over"
                                  :class="{ selected: selectedSexRiskGroup === 'over' }"
                                  cx="60"
                                  cy="60"
                                  r="42"
                                  pathLength="100"
                                  :stroke-dasharray="`${ratioPercent(sexRiskSummary(metric).overPct)} ${100 - ratioPercent(sexRiskSummary(metric).overPct)}`"
                                  transform="rotate(-90 60 60)"
                                  role="button"
                                  tabindex="0"
                                  @click="selectSexRiskGroup('over')"
                                  @keydown.enter="selectSexRiskGroup('over')"
                                ></circle>
                                <circle
                                  v-if="sexRiskSummary(metric).within"
                                  class="sex-risk-donut-segment within"
                                  :class="{ selected: selectedSexRiskGroup === 'within' }"
                                  cx="60"
                                  cy="60"
                                  r="42"
                                  pathLength="100"
                                  :stroke-dasharray="`${ratioPercent(sexRiskSummary(metric).withinPct)} ${100 - ratioPercent(sexRiskSummary(metric).withinPct)}`"
                                  :stroke-dashoffset="-ratioPercent(sexRiskSummary(metric).overPct)"
                                  transform="rotate(-90 60 60)"
                                  role="button"
                                  tabindex="0"
                                  @click="selectSexRiskGroup('within')"
                                  @keydown.enter="selectSexRiskGroup('within')"
                                ></circle>
                                <text
                                  v-if="sexRiskSummary(metric).over"
                                  class="sex-risk-donut-label"
                                  :x="donutLabelPosition(0, ratioPercent(sexRiskSummary(metric).overPct)).x"
                                  :y="donutLabelPosition(0, ratioPercent(sexRiskSummary(metric).overPct)).y"
                                >{{ ratioPercent(sexRiskSummary(metric).overPct).toFixed(1) }}%</text>
                                <text
                                  v-if="sexRiskSummary(metric).within"
                                  class="sex-risk-donut-label"
                                  :x="donutLabelPosition(ratioPercent(sexRiskSummary(metric).overPct), ratioPercent(sexRiskSummary(metric).withinPct)).x"
                                  :y="donutLabelPosition(ratioPercent(sexRiskSummary(metric).overPct), ratioPercent(sexRiskSummary(metric).withinPct)).y"
                                >{{ ratioPercent(sexRiskSummary(metric).withinPct).toFixed(1) }}%</text>
                              </svg>
                              <div class="sex-risk-donut-center">
                                <strong>{{ sexRiskSummary(metric).total }}</strong>
                                <span>全部中心</span>
                              </div>
                            </div>
                            <div class="sex-risk-side">
                              <div class="sex-risk-summary-list">
                                <button
                                  type="button"
                                  class="sex-risk-summary-item over"
                                  :class="{ selected: selectedSexRiskGroup === 'over' }"
                                  @click="selectSexRiskGroup('over')"
                                >
                                  <i></i>
                                  <span>超阈值中心</span>
                                </button>
                                <button
                                  type="button"
                                  class="sex-risk-summary-item within"
                                  :class="{ selected: selectedSexRiskGroup === 'within' }"
                                  @click="selectSexRiskGroup('within')"
                                >
                                  <i></i>
                                  <span>未超阈值中心</span>
                                </button>
                              </div>
                              <div class="sex-risk-center-panel">
                                <div class="sex-risk-center-title">
                                  {{ selectedSexRiskGroup === "over" ? "超阈值中心" : "未超阈值中心" }}
                                  <span>点击中心查看男女数量</span>
                                </div>
                                <div v-if="sexRiskCenters(metric).length" class="sex-risk-center-grid">
                                  <button
                                    v-for="row in sexRiskCenters(metric)"
                                    :key="row.site"
                                    type="button"
                                    class="sex-risk-center-button"
                                    :class="{ alert: selectedSexRiskGroup === 'over', selected: selectedSexCenter === row.site }"
                                    @click="selectSexCenter(row.site)"
                                  >
                                    <strong>{{ row.site }}</strong>
                                    <span>男性 {{ ratioPercent(row.value).toFixed(1) }}%</span>
                                  </button>
                                </div>
                                <div v-else class="mapping-empty">该分类暂无中心</div>
                              </div>
                            </div>
                          </div>
                        </div>
                        <section v-if="selectedSexCenter" class="sex-center-details sex-subject-detail-panel">
                          <div class="age-center-details-title">中心 {{ selectedSexCenter }} / 性别人数汇总</div>
                          <div class="sex-center-brief-summary">
                            <div class="male">
                              <span><i class="male-legend"></i>男性</span>
                              <strong>{{ sexCenterSummary(metric).male }}人</strong>
                            </div>
                            <div class="female">
                              <span><i class="female-legend"></i>女性</span>
                              <strong>{{ sexCenterSummary(metric).female }}人</strong>
                            </div>
                          </div>
                        </section>
                      </template>

                      <template v-else-if="metric.key === 'baseline_hba1c_avg'">
                        <div class="department-center-chart hba1c-radar-panel">
                          <div class="hba1c-radar-stage">
                            <svg class="hba1c-radar" viewBox="0 0 440 440" role="img" aria-label="各中心基线HbA1c平均值雷达图">
                              <circle v-for="ring in hba1cRadarRings(metric)" :key="ring" cx="220" cy="220" :r="hba1cRingRadius(ring, metric)" class="hba1c-ring" :class="{ 'pretarget-ring': ring === 8.0, 'target-ring': ring === 8.5, 'warn-ring': ring > 8.5 && ring < hba1cRadarMax(metric), 'outer-ring': ring === hba1cRadarMax(metric) }" />
                              <text v-for="ring in hba1cRadarRings(metric)" :key="'l'+ring" x="225" :y="220 - hba1cRingRadius(ring, metric) + 4" class="hba1c-ring-label" :class="{ target: ring === 8.5 }">{{ ring.toFixed(1) }}</text>
                              <polygon v-if="hba1cRadarRows(metric).length > 2" :points="hba1cRadarPolygon(metric)" class="hba1c-radar-polygon" />
                              <g v-for="(row, index) in hba1cRadarRows(metric)" :key="row.site">
                                <line
                                  x1="220"
                                  y1="220"
                                  :x2="hba1cRadarPoint(metric, row, index).x"
                                  :y2="hba1cRadarPoint(metric, row, index).y"
                                  class="hba1c-axis"
                                />
                                <g class="hba1c-dot-hit" role="button" tabindex="0" @click="selectHba1cCenter(row.site)" @keydown.enter.prevent="selectHba1cCenter(row.site)">
                                  <title>中心 {{ row.site }}：{{ row.value.toFixed(2) }}%</title>
                                  <circle
                                    :cx="hba1cRadarPoint(metric, row, index).x"
                                    :cy="hba1cRadarPoint(metric, row, index).y"
                                    r="6"
                                    class="hba1c-radar-dot"
                                    :class="{ selected: hba1cSelectedCenter(metric) === row.site, alert: hba1cRangeDistance(row.value) > 0 }"
                                  />
                                </g>
                                <text
                                  v-if="hba1cSelectedCenter(metric) === row.site"
                                  :x="hba1cRadarPoint(metric, row, index).x"
                                  :y="hba1cRadarPoint(metric, row, index).y - 10"
                                  class="hba1c-site-label"
                                >{{ row.site }}</text>
                              </g>
                            </svg>
                            <div class="hba1c-radar-legend">
                              <span><i class="pretarget"></i>8.0</span>
                              <span><i class="target"></i>8.5 (目标上限)</span>
                              <span><i class="warn"></i>9.0</span>
                            </div>
                          </div>
                          <aside class="hba1c-radar-detail">
                            <div class="hba1c-detail-title">中心 {{ hba1cSelectedSummary(metric).site || "-" }}</div>
                            <div class="hba1c-detail-kpis">
                              <div>
                                <span>基线平均HbA1c</span>
                                <strong>{{ hba1cSelectedSummary(metric).value ? `${hba1cSelectedSummary(metric).value.toFixed(2)}%` : "-" }}</strong>
                              </div>
                              <div>
                                <span>筛选期记录</span>
                                <strong>{{ hba1cSelectedSummary(metric).count }}条</strong>
                              </div>
                              <div>
                                <span>区间判断</span>
                                <strong :class="{ alert: hba1cRangeDistance(hba1cSelectedSummary(metric).value) > 0 }">{{ hba1cSelectedSummary(metric).status }}</strong>
                              </div>
                            </div>
                            <DataTable
                              :rows="hba1cSelectedDetailRows(metric)"
                              :preferred-columns="['受试者编号', 'HbA1c', '与均值差']"
                              :limit="12"
                              :empty-text="t('empty')"
                            />
                          </aside>
                        </div>
                      </template>

                      <div v-else-if="mmBmiMetricKeys.includes(metric.key)" class="department-center-chart bmi-chart">
                        <div class="bmi-simple-panel" :class="{ alert: bmiDetailRows(metric).length > 0 }">
                          <div class="bmi-simple-head">
                            <div>
                              <strong>{{ metric.label }}</strong>
                              <span>{{ bmiThresholdText(metric) }}</span>
                            </div>
                            <em>{{ bmiDetailRows(metric).length > 0 ? "存在超阈值数据" : "没有超阈值数据" }}</em>
                          </div>
                          <DataTable
                            v-if="bmiDetailRows(metric).length"
                            :rows="bmiDetailRows(metric)"
                            :preferred-columns="['中心', '受试者编号', 'BMI']"
                            :limit="200"
                            :empty-text="t('empty')"
                          />
                        </div>

                      </div>

                      <!-- PM: W44前提前退出 - 百分比堆积柱状图 -->
                      <div v-else-if="metric.key === 'early_termination_rate'" class="department-center-chart etime-chart">
                        <div class="etime-title">W44 前提前退出受试者比例（阈值 &lt;10%）</div>
                        <div class="etime-project-summary">
                          <div class="etime-project-kpi">
                            <span class="etime-project-label">项目整体退出率</span>
                            <strong class="etime-project-rate" :class="{ over: Number(etimeProjectSummary(metric).rate) >= 10 }">{{ etimeProjectSummary(metric).rate }}%</strong>
                          </div>
                          <div class="etime-project-detail">
                            W44前提前退出人数 {{ etimeProjectSummary(metric).exitCount }} 人 / 总人数 {{ etimeProjectSummary(metric).total }} 人（不含筛败）
                          </div>
                        </div>
                        <div class="etime-stack-body">
                          <div
                            v-for="row in departmentChartRows(metric)"
                            :key="row.site"
                            class="etime-stack-col"
                            :class="{ over: row.value >= 0.10, selected: selectedEtimeCenter === row.site }"
                            role="button"
                            tabindex="0"
                            @click="selectEtimeCenter(row.site)"
                            @keydown.enter.prevent="selectEtimeCenter(row.site)"
                          >
                            <div class="etime-stack-bar">
                              <div class="etime-stack-exit" :style="{ height: etimePct(row.value) }">
                                <span v-if="row.value >= 0.005" class="etime-stack-label">{{ (row.value * 100).toFixed(1) }}%</span>
                              </div>
                              <div class="etime-stack-remain" :style="{ height: etimePct(1 - row.value) }"></div>
                            </div>
                            <div class="etime-stack-site">{{ row.site }}</div>
                          </div>
                        </div>
                        <div class="etime-stack-legend">
                          <span><i class="etime-legend-exit"></i>W44前退出</span>
                          <span><i class="etime-legend-remain"></i>在组受试者</span>
                        </div>
                      </div>
                      <section v-if="metric.key === 'early_termination_rate' && selectedEtimeCenter" class="etime-detail-panel">
                        <div class="etime-detail-title">中心 {{ selectedEtimeCenter }} - W44前提前退出受试者明细</div>
                        <DataTable
                          :rows="etimeDetailRows(metric)"
                          :preferred-columns="['受试者编号', '受试者状态']"
                          :limit="200"
                          :empty-text="t('empty')"
                        />
                      </section>

                      <!-- PM: 妊娠受试者 - 阳性患者列表 -->
                      <div v-if="metric.key === 'pregnancy_rate'" class="department-center-chart preg-chart">
                        <div class="preg-title">妊娠受试者（数据来源：LB_HCG 检查结果为阳性）</div>
                        <div class="preg-summary">
                          <div class="preg-summary-kpi">
                            <span class="preg-summary-label">项目妊娠比例</span>
                            <strong class="preg-summary-rate" :class="{ over: Number(pregProjectRate(metric).replace('%', '')) >= 2 }">{{ pregProjectRate(metric) }}</strong>
                          </div>
                          <div class="preg-summary-note">
                            阈值 2% · 阳性患者 {{ pregPositiveCount(metric) }} 名 / 项目患者 {{ pregProjectSubjectCount(metric) }} 名 · 涉及中心 {{ pregCenterCount(metric) }} 个
                          </div>
                        </div>
                        <div v-if="metric.details && metric.details.length" class="preg-detail-table">
                          <DataTable
                            :rows="metric.details"
                            :preferred-columns="['受试者编号', '中心', '数据节', '采样日期', '检查结果']"
                            :limit="200"
                            :empty-text="t('empty')"
                          />
                        </div>
                        <div v-else class="preg-empty">未发现妊娠阳性记录</div>
                      </div>

                      <div v-if="!['avg_age_years', 'male_rate', 'baseline_hba1c_avg', 'baseline_bmi_avg', 'bmi_under_24_rate', 'bmi_30_35_rate', 'bmi_over_35_count', 'early_termination_rate', 'pregnancy_rate'].includes(metric.key)" class="department-center-chart">
                        <div v-for="row in departmentChartRows(metric)" :key="row.site" class="department-center-row">
                          <div class="department-center-label">{{ row.site }}</div>
                          <div class="department-center-track">
                            <div
                              class="department-center-fill"
                              :class="{ alert: row.count > 0 }"
                              :style="{ width: `${Math.max(3, Math.min(100, Math.abs(row.value) / departmentChartMax(metric) * 100))}%` }"
                            ></div>
                          </div>
                          <div class="department-center-value">
                            {{ metric.unit === "比例" ? `${ratioPercent(row.value).toFixed(1)}%` : row.value }}
                          </div>
                        </div>
                      </div>

                      <div v-if="!['avg_age_years', 'male_rate', 'baseline_hba1c_avg', 'baseline_bmi_avg', 'bmi_under_24_rate', 'bmi_30_35_rate', 'bmi_over_35_count', 'early_termination_rate', 'pregnancy_rate'].includes(metric.key)" class="table-wrap department-table">
                        <DataTable
                          :rows="departmentMetricRows(metric)"
                          :preferred-columns="['中心', '当前值', '阈值', '超阈值条数']"
                          :limit="30"
                          :empty-text="t('empty')"
                          :clickable-rows="metric.key === 'avg_age_years'"
                          @row-click="metric.key === 'avg_age_years' && selectAgeCenter(String($event['中心'] || ''))"
                        />
                      </div>
                    </template>
                  </article>
                  <div v-if="!activeDepartmentMetricGroups.length" class="mapping-empty department-empty">
                    请先在右侧下拉列表选择一个QTL。
                  </div>
                </div>
              </section>
            </section>
          </section>

          <section class="tab-page" :class="{ active: activeTab === 'efficacy' }">
            <h1>{{ t("pages.efficacy") }}</h1>
            <div class="source-note">数据源：Form Excel（临床研究数据）</div>
              <div class="data-card efficacy-model-card">
                <div class="card-title">疗效指标配置</div>
                <div class="efficacy-model-body">
                  <p class="medical-subtitle">先选择项目适应症，再选择参与中心风险评分的疗效指标组合。当前已接入糖尿病项目的 HbA1c 和体重，其他适应症可按项目方案继续扩展。</p>
                  <div class="efficacy-model-fields">
                    <label class="efficacy-model-select">
                      <span><b>01</b>项目适应症</span>
                      <AppSelect
                        v-model="selectedIndication"
                        :options="[...indicationOptions]"
                        aria-label="项目适应症"
                      />
                    </label>
                    <label class="efficacy-model-select">
                      <span><b>02</b>疗效指标组合</span>
                      <AppSelect
                        v-model="selectedEfficacyModel"
                        :options="isConfiguredIndication ? [...efficacyModelOptions] : []"
                        :disabled="!isConfiguredIndication"
                        placeholder="请先配置该适应症的疗效指标"
                        aria-label="疗效指标组合"
                      />
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
                </div>

              </template>
          </section>

          <section class="tab-page" :class="{ active: activeTab === 'risk_forecast' }">
            <h1>{{ t("pages.riskForecast") }}</h1>
            <div class="source-note">数据源：Form Excel（HbA1c随访数据）</div>
            <div v-if="!hasClinicalData" class="data-card">
              <div class="mapping-empty">请先导入Form Excel/临床研究数据，导入后展示HbA1c贝叶斯疗效预测和潜在药物参照对比。</div>
            </div>
            <div v-else class="data-card bayes-hba1c-card">
              <div class="card-title">贝叶斯HbA1c疗效预测</div>
              <p class="medical-subtitle">基于每位受试者最早与最新HbA1c配对值，预测项目整体HbA1c下降值和下降比例；该模块不按治疗组、剂量组或对照组拆分，仅用于盲态RBQM风险预估。</p>
              <div v-if="!hba1cBayesianPrediction?.available" class="mapping-empty">{{ hba1cBayesianPrediction?.message || "暂无可用于预测的HbA1c配对随访数据。" }}</div>
              <template v-else>
                <div class="bayes-hba1c-grid">
                  <div class="bayes-hba1c-panel">
                    <div class="chart-section-title">后验预测结果</div>
                    <div class="bayes-posterior-chart">
                      <svg viewBox="0 0 600 230" role="img" aria-label="HbA1c贝叶斯后验分布图">
                        <line x1="40" y1="178" x2="560" y2="178" class="posterior-axis" />
                        <rect
                          :x="hba1cPosteriorX(hba1cPosteriorLow)"
                          y="50"
                          :width="Math.max(0, hba1cPosteriorX(hba1cPosteriorHigh) - hba1cPosteriorX(hba1cPosteriorLow))"
                          height="128"
                          class="posterior-ci-band"
                        />
                        <polyline :points="hba1cPosteriorAreaPoints" class="posterior-area" />
                        <polyline :points="hba1cPosteriorPoints" class="posterior-line" />
                        <line
                          :x1="hba1cPosteriorX(hba1cPosteriorMean)"
                          y1="44"
                          :x2="hba1cPosteriorX(hba1cPosteriorMean)"
                          y2="178"
                          class="posterior-mean-line"
                        />
                        <text :x="hba1cPosteriorX(hba1cPosteriorMean) + 8" y="48" class="posterior-label">后验均值 {{ hba1cPosteriorMean.toFixed(2) }}</text>
                        <text :x="hba1cPosteriorX(hba1cPosteriorLow)" y="202" class="posterior-tick">{{ hba1cPosteriorLow.toFixed(2) }}</text>
                        <text :x="hba1cPosteriorX(hba1cPosteriorHigh)" y="202" class="posterior-tick">{{ hba1cPosteriorHigh.toFixed(2) }}</text>
                        <text x="40" y="222" class="posterior-axis-title">HbA1c下降值（百分点）</text>
                        <g v-for="row in hba1cBayesianBenchmarks" :key="`posterior-${String(row['类别'])}`">
                          <line
                            :x1="hba1cPosteriorX(Number(row['典型HbA1c下降（百分点）'] || 0))"
                            y1="164"
                            :x2="hba1cPosteriorX(Number(row['典型HbA1c下降（百分点）'] || 0))"
                            y2="178"
                            class="posterior-benchmark-line"
                          />
                        </g>
                      </svg>
                      <div class="posterior-legend">
                        <span><i class="mean"></i>后验均值</span>
                        <span><i class="ci"></i>95%可信区间</span>
                        <span><i class="bench"></i>公开药物参照点</span>
                      </div>
                    </div>
                    <div class="bayes-summary-grid">
                      <div v-for="row in hba1cBayesianSummaryRows" :key="String(row['指标'])" class="bayes-summary-item">
                        <span>{{ row["指标"] }}</span>
                        <strong>{{ row["数值"] }}</strong>
                      </div>
                    </div>
                  </div>
                  <div class="bayes-hba1c-panel">
                    <div class="chart-section-title">与公开发售降糖药的潜在对比</div>
                    <div class="drug-forest-chart">
                      <div class="drug-forest-header">
                        <span>药物/剂量</span>
                        <span>公开模型估计A1c降幅</span>
                        <span>后验概率</span>
                      </div>
                      <div
                        v-for="row in hba1cBenchmarkRows"
                        :key="String(row['药物'] || row['类别'])"
                        class="drug-forest-row"
                      >
                        <div class="drug-forest-label">
                          <strong>{{ row["药物"] || row["类别"] }}</strong>
                          <span :style="{ color: drugClassColor(row['药物类别']) }">{{ row["药物类别"] || "公开药物" }}</span>
                        </div>
                        <div class="drug-forest-axis">
                          <div class="drug-forest-ci" :style="{ left: `${(hba1cPosteriorLow / hba1cBenchmarkMax) * 100}%`, width: `${Math.max(1, ((hba1cPosteriorHigh - hba1cPosteriorLow) / hba1cBenchmarkMax) * 100)}%` }"></div>
                          <div class="drug-forest-mean" :style="{ left: `${Math.min(100, (hba1cPredictedDropPoints / hba1cBenchmarkMax) * 100)}%` }"></div>
                          <div
                            class="drug-forest-dot"
                            :style="{ left: `${Math.min(100, (Number(row['典型HbA1c下降（百分点）'] || 0) / hba1cBenchmarkMax) * 100)}%`, background: drugClassColor(row['药物类别']) }"
                          ></div>
                        </div>
                        <div class="drug-forest-prob">
                          {{ hba1cBayesianProbabilityRows.find((item) => String(item['参照']) === String(row['类别']))?.["达到或超过概率（%）"] ?? "-" }}%
                        </div>
                      </div>
                    </div>
                    <div class="drug-benchmark-legend forest">
                      <span><i></i>圆点：公开药物/剂量典型A1c降幅</span>
                      <strong>蓝线/浅带：本项目贝叶斯后验均值与95%可信区间</strong>
                    </div>
                  </div>
                </div>
                <div class="bayes-hba1c-panel bayes-wide-panel">
                  <div class="chart-section-title">风险预估说明</div>
                  <div class="bayes-explain-box compact">
                    <p>该对比仅作为公开疗效范围的背景参照，不构成直接头对头比较，也不代表治疗组结论。</p>
                    <p>RBQM中更适合用于判断：项目整体疗效变化是否异常、中心间是否存在明显偏离、后续是否需要重点核查数据完整性或访视质量。</p>
                  </div>
                </div>
                <div class="bayes-hba1c-panel bayes-wide-panel">
                  <div class="chart-section-title">中心贝叶斯漏斗图</div>
                  <div class="bayes-funnel-chart">
                    <svg viewBox="0 0 600 330" role="img" aria-label="中心贝叶斯漏斗图">
                      <line x1="56" y1="270" x2="550" y2="270" class="funnel-axis" />
                      <line x1="56" y1="32" x2="56" y2="270" class="funnel-axis" />
                      <line
                        x1="56"
                        :y1="hba1cFunnelY(hba1cPosteriorMean)"
                        x2="550"
                        :y2="hba1cFunnelY(hba1cPosteriorMean)"
                        class="funnel-center-line"
                      />
                      <polyline :points="hba1cFunnelCurve(1.96, 1)" class="funnel-limit limit-95" />
                      <polyline :points="hba1cFunnelCurve(1.96, -1)" class="funnel-limit limit-95" />
                      <polyline :points="hba1cFunnelCurve(2.58, 1)" class="funnel-limit limit-99" />
                      <polyline :points="hba1cFunnelCurve(2.58, -1)" class="funnel-limit limit-99" />
                      <g v-for="row in hba1cFunnelRows" :key="`funnel-${row.site}`">
                        <circle
                          :cx="hba1cFunnelX(row.n)"
                          :cy="hba1cFunnelY(row.value)"
                          r="6"
                          class="funnel-point"
                          :class="hba1cFunnelClass(row)"
                        />
                        <text
                          v-if="hba1cFunnelClass(row) !== 'inside'"
                          :x="hba1cFunnelX(row.n) + 8"
                          :y="hba1cFunnelY(row.value) - 8"
                          class="funnel-site-label"
                        >{{ row.site }}</text>
                      </g>
                      <text x="300" y="316" class="posterior-axis-title">中心可评估人数</text>
                      <text x="14" y="28" class="posterior-axis-title">HbA1c平均下降值</text>
                      <text x="462" :y="hba1cFunnelY(hba1cPosteriorMean) - 8" class="funnel-mean-label">项目后验均值</text>
                    </svg>
                    <div class="posterior-legend">
                      <span><i class="mean"></i>项目后验均值</span>
                      <span><i class="ci"></i>95%控制界限</span>
                      <span><i class="bench"></i>99%控制界限</span>
                      <span><i class="funnel-alert"></i>界限外中心</span>
                    </div>
                  </div>
                </div>
                <p class="medical-subtitle bayes-note">{{ hba1cBayesianPrediction?.note }}</p>
              </template>
            </div>
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
                  <AppSelect
                    v-model="selectedMedicalSubjectId"
                    :options="medicalSubjects.map((subject) => ({
                      value: subject.subject_id,
                      label: `${subject.subject_id} · ${subject.site_id} · ${subject.subject_status || '状态未知'}`,
                    }))"
                    aria-label="选择受试者"
                  />
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
            <div class="report-export-grid">
              <div class="data-card">
                <div class="card-title">各中心筛败率</div>
                <p class="medical-subtitle">筛败率单独用于报告导出，不参与风险阈值判定。</p>
                <div class="table-wrap">
                  <DataTable :rows="screenFailureRows" :limit="30" :empty-text="t('empty')" />
                </div>
              </div>
              <div class="data-card">
                <div class="card-title">筛败患者明细</div>
                <p class="medical-subtitle">导出审查包时会生成“筛败患者明细”sheet。</p>
                <div class="table-wrap">
                  <DataTable :rows="screenFailureDetailRows" :limit="80" :empty-text="t('empty')" />
                </div>
              </div>
            </div>
            <div class="data-card">
              <div class="card-title">行动跟踪</div>
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
