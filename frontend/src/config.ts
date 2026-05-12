import type { ThresholdItem } from "./types";

export const icons: Record<string, string> = {
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

export const thresholds: ThresholdItem[] = [
  { key: "dlt_rate", label: { zh: "DLT发生率", en: "DLT Rate" }, group: { zh: "剂量安全", en: "Dose Safety" }, min: 0.01, max: 1, step: 0.01, value: 0.1, decimals: 2, enabled: true },
  { key: "grade3_ae_rate", label: { zh: ">=3级AE发生率", en: "Grade >=3 AE Rate" }, group: { zh: "剂量安全", en: "Dose Safety" }, min: 0.01, max: 2, step: 0.01, value: 0.2, decimals: 2, enabled: true },
  { key: "safety_issues_per_subject", label: { zh: "SAE随访/报告缺口", en: "SAE Follow-up Gap" }, group: { zh: "安全复核", en: "Safety Review" }, min: 0.01, max: 1, step: 0.01, value: 0.15, decimals: 2, enabled: true },
  { key: "dose_modification_rate", label: { zh: "毒性相关剂量调整率", en: "Toxicity Dose Modification" }, group: { zh: "给药管理", en: "Dosing" }, min: 0.01, max: 2, step: 0.01, value: 0.2, decimals: 2, enabled: true },
  { key: "eligibility_deviation_rate", label: { zh: "入排标准偏离率", en: "Eligibility Deviation" }, group: { zh: "方案依从", en: "Protocol" }, min: 0.01, max: 1, step: 0.01, value: 0.1, decimals: 2, enabled: true },
  { key: "pk_window_deviation_rate", label: { zh: "PK/PD采样窗偏离率", en: "PK/PD Window Deviation" }, group: { zh: "PK/PD", en: "PK/PD" }, min: 0.01, max: 1, step: 0.01, value: 0.15, decimals: 2, enabled: true },
  { key: "tumor_assessment_issue_rate", label: { zh: "肿瘤评估缺失/延迟率", en: "Tumor Assessment Issue" }, group: { zh: "疗效评估", en: "Response" }, min: 0.01, max: 1, step: 0.01, value: 0.2, decimals: 2, enabled: true },
  { key: "missing_rate", label: { zh: "关键数据缺失率", en: "Critical Data Missing" }, group: { zh: "数据质量", en: "Data Quality" }, min: 0.01, max: 0.3, step: 0.01, value: 0.1, decimals: 2, enabled: true },
  { key: "late_entry_rate", label: { zh: "EDC延迟/未完成率", en: "Late / Incomplete EDC" }, group: { zh: "数据质量", en: "Data Quality" }, min: 0.01, max: 0.6, step: 0.01, value: 0.2, decimals: 2, enabled: true },
  { key: "avg_entry_delay_days", label: { zh: "平均录入延迟（天）", en: "Avg Entry Delay Days" }, group: { zh: "数据质量", en: "Data Quality" }, min: 1, max: 30, step: 1, value: 7, decimals: 2, enabled: true },
  { key: "open_queries_per_subject", label: { zh: "每受试者未关闭Query数", en: "Open Queries / Subject" }, group: { zh: "Query", en: "Query" }, min: 0.1, max: 5, step: 0.1, value: 1.5, decimals: 2, enabled: true },
  { key: "avg_open_query_age_days", label: { zh: "未关闭Query平均账龄（天）", en: "Avg Open Query Age" }, group: { zh: "Query", en: "Query" }, min: 1, max: 60, step: 1, value: 21, decimals: 2, enabled: true },
  { key: "lab_issues_per_subject", label: { zh: "未复核异常实验室率", en: "Unreviewed Lab Issue Rate" }, group: { zh: "实验室", en: "Labs" }, min: 0.01, max: 1, step: 0.01, value: 0.2, decimals: 2, enabled: true },
  { key: "major_deviations_per_subject", label: { zh: "重大方案偏离率", en: "Major Deviation Rate" }, group: { zh: "方案依从", en: "Protocol" }, min: 0.01, max: 1, step: 0.01, value: 0.1, decimals: 2, enabled: true },
];

export const scoreColumnsByMetric: Record<string, string[]> = {
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
