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
  { key: "edc_visit_entry_delay_days", label: { zh: "EDC访视录入延迟天数", en: "EDC Visit Entry Delay Days" }, group: { zh: "录入及时性", en: "Entry Timeliness" }, min: 0, max: 90, step: 1, value: 7, decimals: 0, enabled: true },
  { key: "page_missing_days_all", label: { zh: "页面缺失天数（全部）", en: "Page Missing Days (All)" }, group: { zh: "页面质量", en: "Page Quality" }, min: 1, max: 90, step: 1, value: 7, decimals: 0, enabled: true },
  { key: "page_missing_days_without_lab", label: { zh: "页面缺失天数（不含对接LAB）", en: "Page Missing Days (Excl. Linked Lab)" }, group: { zh: "页面质量", en: "Page Quality" }, min: 1, max: 90, step: 1, value: 7, decimals: 0, enabled: true },
  { key: "page_sdv_pending_rate", label: { zh: "未SDV（页面）", en: "Un-SDV (Page)" }, group: { zh: "页面质量", en: "Page Quality" }, min: 1, max: 90, step: 1, value: 7, decimals: 0, enabled: true },
  { key: "logline_sdv_pending_rate", label: { zh: "未SDV（logline）", en: "Un-SDV (Logline)" }, group: { zh: "页面质量", en: "Page Quality" }, min: 1, max: 90, step: 1, value: 7, decimals: 0, enabled: true },
  { key: "avg_open_query_age_days", label: { zh: "未关闭质疑天数", en: "Open Query Days" }, group: { zh: "Query账龄", en: "Query Age" }, min: 1, max: 90, step: 1, value: 21, decimals: 0, enabled: true },
  { key: "manual_query_reissue_rate", label: { zh: "人工质疑重发率", en: "Manual Query Reissue Rate" }, group: { zh: "Query返工", en: "Query Rework" }, min: 0.01, max: 1, step: 0.01, value: 0.1, decimals: 2, enabled: true },
];

export const scoreColumnsByMetric: Record<string, string[]> = {
  edc_visit_entry_delay_days: ["EDC及时性评分"],
  page_missing_days_all: ["页面质量评分"],
  page_missing_days_without_lab: ["页面质量评分"],
  page_sdv_pending_rate: ["页面质量评分"],
  logline_sdv_pending_rate: ["页面质量评分"],
  manual_query_reissue_rate: ["Query返工评分"],
  avg_open_query_age_days: ["Query周期评分"],
};
