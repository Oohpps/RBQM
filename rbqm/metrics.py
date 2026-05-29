from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from .config import METRIC_VALUE_LABELS
from .models import KRI_METRIC_KEYS, Thresholds
from .utils import datetime_series, find_col, numeric_series, safe_div, truthy_series

TODAY = pd.Timestamp(date.today())


def available_sites(tables: dict[str, pd.DataFrame]) -> list[str]:
    sites: set[str] = set()
    for df in tables.values():
        if "__site_id" in df:
            sites.update(df["__site_id"].dropna().astype(str).unique().tolist())
    return sorted(sites)


def count_subjects(subjects: pd.DataFrame, sites: list[str]) -> pd.Series:
    if subjects.empty or "__site_id" not in subjects:
        return pd.Series(0, index=sites, dtype="float64")
    total_col = find_col(subjects, ["total", "count", "n", "合计", "受试者数"])
    if "__subject_id" in subjects and subjects["__subject_id"].notna().any():
        detail = subjects[subjects["__subject_id"].notna() & subjects["__subject_id"].astype(str).str.strip().ne("")]
        counts = detail.groupby("__site_id")["__subject_id"].nunique()
    elif total_col:
        counts = numeric_series(subjects[total_col]).groupby(subjects["__site_id"]).sum()
    else:
        counts = subjects.groupby("__site_id").size()
    return counts.reindex(sites).fillna(0).astype(float)


def data_point_counts(tables: dict[str, pd.DataFrame], sites: list[str]) -> pd.Series:
    counts = pd.Series(0.0, index=sites)
    for df in tables.values():
        if df.empty or "__site_id" not in df:
            continue
        data_cols = [col for col in df.columns if not col.startswith("__") and col not in {"site_id", "subject_id"}]
        if data_cols:
            part = df.groupby("__site_id")[data_cols].count().sum(axis=1).reindex(sites).fillna(0)
            counts = counts.add(part, fill_value=0)
    return counts.reindex(sites).fillna(0).astype(float)


def domain_missingness(df: pd.DataFrame) -> pd.Series:
    if df.empty or "__site_id" not in df:
        return pd.Series(dtype="float64")
    candidate_cols = [col for col in df.columns if not col.startswith("__")]
    if not candidate_cols:
        return pd.Series(dtype="float64")
    return df.groupby("__site_id")[candidate_cols].apply(lambda part: float(part.isna().mean().mean()))


def text_contains(df: pd.DataFrame, columns: list[str | None], pattern: str) -> pd.Series:
    mask = pd.Series(False, index=df.index)
    for col in columns:
        if col and col in df.columns:
            mask = mask | df[col].astype(str).str.lower().str.contains(pattern, regex=True, na=False)
    return mask


LAB_PAGE_PATTERN = "lab|laboratory|lb|central lab|local lab|实验室|检验|化验|对接lab|对接_lab|糖化|血红蛋白|血常规|尿常规|生化|血糖"


def mean_days_since_visit(work: pd.DataFrame, mask: pd.Series, visit_date_col: str | None, sites: list[str]) -> pd.Series:
    if not visit_date_col or not mask.any():
        return pd.Series(0.0, index=sites)
    days = (TODAY - datetime_series(work[visit_date_col])).dt.days
    return days.where(mask).groupby(work["__site_id"]).mean().reindex(sites).fillna(0).clip(lower=0)


def leading_number_series(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype="float64")
    numeric = numeric_series(series)
    if numeric.isna().all():
        numeric = pd.to_numeric(series.astype(str).str.extract(r"(\d+(?:\.\d+)?)", expand=False), errors="coerce")
    return numeric


def normalized_text_values(series: pd.Series | None) -> set[str]:
    if series is None:
        return set()
    return {
        str(value).strip().lower()
        for value in series.dropna().tolist()
        if str(value).strip()
    }


def active_kri_metrics(thresholds: Thresholds) -> set[str]:
    if not thresholds.kri_enabled:
        return set()
    return {metric for metric in thresholds.enabled_metrics if metric in KRI_METRIC_KEYS}


def metric_component_score(values: pd.Series, threshold: float) -> pd.Series:
    if threshold <= 0:
        return pd.Series(0.0, index=values.index)
    return (values / threshold * 100).replace([np.inf, -np.inf], 0).fillna(0).clip(0, 100)


def compute_visit_metrics(metrics: pd.DataFrame, visits: pd.DataFrame, thresholds: Thresholds, sites: list[str]) -> None:
    metrics["late_entry_rate"] = 0.0
    metrics["avg_entry_delay_days"] = 0.0
    if visits.empty or "__site_id" not in visits:
        return

    visit_date_col = find_col(visits, ["visit_date", "visit_dt", "assessment_date", "event_date", "访视日期", "检查日期", "事件日期", "irt_actual_visit_date", "irt实际访视时间", "开始日期"])
    entry_date_col = find_col(visits, ["data_entry_date", "entry_date", "entered_date", "form_entry_date", "created_date", "录入日期", "数据录入日期", "表单录入日期"])
    status_col = find_col(visits, ["form_status", "status", "visit_status", "completion_status", "表单状态", "访视状态", "完成状态", "受试者状态", "状态"])
    missing_col = find_col(visits, ["page_missing", "missing_page", "form_missing", "is_missing", "missing", "页面缺失", "表单缺失", "缺失页"])
    sdv_col = find_col(visits, ["sdv_status", "sdv", "source_data_verification", "source_data_verified", "verified", "sdv_complete", "sdv_completed", "页面sdv"])
    days_to_today_col = find_col(visits, ["days_to_today", "days_since_today", "days_from_today", "距今天数"])
    page_col = find_col(visits, ["form_name", "page_name", "data_page_name", "form", "page", "表单名称", "数据页名称", "访视名称"])
    work = visits.copy()

    late_mask = pd.Series(False, index=work.index)
    delay_days = pd.Series(np.nan, index=work.index, dtype="float64")
    if visit_date_col and entry_date_col:
        delay_days = (datetime_series(work[entry_date_col]) - datetime_series(work[visit_date_col])).dt.days
        late_mask = delay_days > thresholds.edc_visit_entry_delay_days
    if status_col:
        late_mask = late_mask | text_contains(work, [status_col], "incomplete|missing|overdue|not done|pending|未完成|未录入|缺失|待录入|待完成")
    metrics["late_entry_rate"] = late_mask.groupby(work["__site_id"]).mean().reindex(sites).fillna(0)
    metrics["avg_entry_delay_days"] = delay_days.groupby(work["__site_id"]).mean().reindex(sites).fillna(0).clip(lower=0)
    metrics["edc_visit_entry_delay_days"] = metrics["avg_entry_delay_days"]

    page_missing_mask = pd.Series(False, index=work.index)
    if missing_col:
        page_missing_mask = page_missing_mask | truthy_series(work[missing_col])
    if status_col:
        page_missing_mask = page_missing_mask | text_contains(work, [status_col], "missing|not done|not submitted|incomplete|缺失|未完成|未提交")
    source_missing_visit_mask = text_contains(work, ["__source_name"], "缺失访视")
    source_missing_mask = text_contains(work, ["__source_name"], "缺失页")
    if source_missing_mask.any():
        page_missing_mask = page_missing_mask | source_missing_mask
    if missing_col is None and status_col is None and not source_missing_mask.any():
        page_missing_mask = pd.Series(True, index=work.index)
    page_lab_mask = text_contains(work, [page_col], LAB_PAGE_PATTERN)
    missing_without_lab_source = text_contains(work, ["__source_name"], "缺失页.*不含.*lab")
    missing_all_source = source_missing_mask & ~missing_without_lab_source
    all_mask = missing_all_source if missing_all_source.any() else page_missing_mask
    without_lab_mask = missing_without_lab_source if missing_without_lab_source.any() else (page_missing_mask & ~page_lab_mask)
    metrics["page_missing_days_all"] = mean_days_since_visit(work, all_mask, visit_date_col, sites)
    metrics["page_missing_days_without_lab"] = mean_days_since_visit(work, without_lab_mask, visit_date_col, sites)
    if source_missing_visit_mask.any():
        irt_visit_date_col = find_col(work, ["irt_actual_visit_time", "irt_actual_visit_date", "irt实际访视时间", "visit_date", "visit_dt", "访视日期"])
        edc_delay_days = (TODAY - datetime_series(work[irt_visit_date_col])).dt.days if irt_visit_date_col else pd.Series(0, index=work.index, dtype="float64")
        metrics["avg_entry_delay_days"] = edc_delay_days.where(source_missing_visit_mask).groupby(work["__site_id"]).mean().reindex(sites).fillna(0).clip(lower=0)
        metrics["edc_visit_entry_delay_days"] = metrics["avg_entry_delay_days"]
        metrics["late_entry_rate"] = edc_delay_days.where(source_missing_visit_mask).gt(thresholds.edc_visit_entry_delay_days).groupby(work["__site_id"]).mean().reindex(sites).fillna(0)
    elif source_missing_mask.any():
        edc_delay_days = (TODAY - datetime_series(work[visit_date_col])).dt.days if visit_date_col else pd.Series(0, index=work.index, dtype="float64")
        metrics["avg_entry_delay_days"] = edc_delay_days.where(all_mask).groupby(work["__site_id"]).mean().reindex(sites).fillna(0).clip(lower=0)
        metrics["edc_visit_entry_delay_days"] = metrics["avg_entry_delay_days"]
        metrics["late_entry_rate"] = edc_delay_days.where(all_mask).gt(thresholds.edc_visit_entry_delay_days).groupby(work["__site_id"]).mean().reindex(sites).fillna(0)

    page_sdv_source = text_contains(work, ["__source_name"], "未sdv.*页面|页面sdv")
    logline_sdv_source = text_contains(work, ["__source_name"], "未sdv.*logline")
    if page_sdv_source.any():
        metrics["page_sdv_pending_rate"] = mean_days_since_visit(work, page_sdv_source, visit_date_col, sites)
    if logline_sdv_source.any() and days_to_today_col:
        logline_days = leading_number_series(work[days_to_today_col])
        metrics["logline_sdv_pending_rate"] = logline_days.where(logline_sdv_source).groupby(work["__site_id"]).mean().reindex(sites).fillna(0).clip(lower=0)

    if sdv_col and not page_sdv_source.any():
        sdv_text = work[sdv_col].astype(str).str.lower()
        sdv_done = truthy_series(work[sdv_col]) | sdv_text.str.contains("done|complete|completed|verified|sdv complete|yes|true|1|完成|已sdv|已核查|已验证", regex=True, na=False)
        sdv_pending = ~sdv_done | sdv_text.str.contains("pending|open|not done|not verified|no|false|0|待|未|未sdv", regex=True, na=False)
        sdv_applicable = work[sdv_col].notna() | page_sdv_source | logline_sdv_source
        page_sdv_applicable = page_sdv_source if page_sdv_source.any() else (sdv_applicable & ~logline_sdv_source)
        metrics["page_sdv_pending_rate"] = sdv_pending.where(page_sdv_applicable).groupby(work["__site_id"]).mean().reindex(sites).fillna(0)
    if sdv_col and logline_sdv_source.any() and not days_to_today_col:
        sdv_text = work[sdv_col].astype(str).str.lower()
        sdv_done = truthy_series(work[sdv_col]) | sdv_text.str.contains("done|complete|completed|verified|sdv complete|yes|true|1|完成|已sdv|已核查|已验证", regex=True, na=False)
        sdv_pending = ~sdv_done | sdv_text.str.contains("pending|open|not done|not verified|no|false|0|待|未|未sdv", regex=True, na=False)
        metrics["logline_sdv_pending_rate"] = sdv_pending.where(logline_sdv_source).groupby(work["__site_id"]).mean().reindex(sites).fillna(0)

    hba1c_col = find_col(visits, ["hba1c", "hb_a1c", "glycated_hemoglobin", "a1c", "糖化血红蛋白"])
    if hba1c_col:
        hba1c = numeric_series(work[hba1c_col])
        abnormal = hba1c.gt(7.0).fillna(False)
        metrics["vital_sign_abnormal_trend_rate"] = abnormal.groupby(work["__site_id"]).mean().reindex(sites).fillna(0)


def compute_lab_metrics(metrics: pd.DataFrame, labs: pd.DataFrame, sites: list[str]) -> None:
    if labs.empty or "__site_id" not in labs:
        return
    result_col = find_col(labs, ["result", "lab_result", "value", "aval", "结果", "数值"])
    test_col = find_col(labs, ["test", "test_name", "parameter", "lab_test", "analyte", "检查项", "项目", "指标"])
    if not result_col:
        return
    work = labs.copy()
    if test_col:
        hba1c_mask = text_contains(work, [test_col], "hba1c|hb a1c|hb_a1c|a1c|glycated|糖化血红蛋白")
    else:
        hba1c_mask = pd.Series(True, index=work.index) if result_col.lower() in {"hba1c", "hb_a1c", "a1c"} else pd.Series(False, index=work.index)
    if not hba1c_mask.any():
        return
    hba1c = numeric_series(work[result_col])
    abnormal = hba1c.gt(7.0).fillna(False) & hba1c_mask
    metrics["vital_sign_abnormal_trend_rate"] = abnormal.groupby(work["__site_id"]).mean().reindex(sites).fillna(0)


def compute_query_metrics(metrics: pd.DataFrame, queries: pd.DataFrame, critical_points: pd.DataFrame, sites: list[str]) -> None:
    metrics["open_queries"] = 0.0
    metrics["open_queries_per_subject"] = 0.0
    if queries.empty or "__site_id" not in queries:
        return

    status_col = find_col(queries, ["query_status", "status", "query_state", "state", "查询状态", "处理状态", "质疑状态"])
    age_col = find_col(queries, ["age_days", "query_age", "open_days", "days_open", "账龄", "开放天数", "打开天数", "打开天数回答天数", "打开天数_回答天数"])
    opened_col = find_col(queries, ["opened_date", "open_date", "created_date", "query_open_date", "打开日期", "创建日期", "质疑打开时间"])
    closed_col = find_col(queries, ["closed_date", "resolved_date", "answered_date", "关闭日期", "解决日期", "质疑回答日期"])
    critical_col = find_col(queries, ["critical", "critical_data_point", "is_critical", "key_data_point", "critical_flag", "关键数据点"])
    sae_col = find_col(queries, ["sae", "serious", "is_sae", "is_serious", "serious_adverse_event", "严重不良事件", "严重"])
    type_col = find_col(queries, ["query_type", "type", "source", "category", "form", "field", "类型", "来源", "表单", "字段"])
    text_col = find_col(queries, ["query_text", "query", "query_message", "message", "质疑文本", "质疑内容", "文本"])
    reissue_col = find_col(queries, ["reissued", "reopened", "status_change", "status_history", "reopen_count", "reissue_count", "重开次数"])
    work = queries.copy()

    if status_col:
        open_mask = ~text_contains(work, [status_col], "closed|resolved|cancelled|canceled|关闭|已解决|已回复|已处理")
    elif closed_col:
        open_mask = datetime_series(work[closed_col]).isna()
    else:
        open_mask = pd.Series(True, index=work.index)

    if age_col:
        age_days = leading_number_series(work[age_col])
    else:
        age_days = (TODAY - datetime_series(work[opened_col])).dt.days if opened_col else pd.Series(0, index=work.index, dtype="float64")
    open_queries = open_mask.groupby(work["__site_id"]).sum().reindex(sites).fillna(0).astype(float)
    metrics["open_queries"] = open_queries
    metrics["open_queries_per_subject"] = [safe_div(open_queries.loc[site], max(metrics.loc[site, "subjects"], 1)) for site in sites]
    metrics["avg_open_query_age_days"] = age_days.where(open_mask).groupby(work["__site_id"]).mean().reindex(sites).fillna(0).clip(lower=0)

    if not critical_points.empty:
        query_visit_col = find_col(work, ["visit_name", "visit", "visit_folder", "访视名称"])
        query_page_col = find_col(work, ["page_name", "data_page_name", "form_name", "form", "数据页名称", "表单名称"])
        query_field_col = find_col(work, ["field_name", "field", "item_name", "字段名称", "变量名"])
        critical_visit_col = find_col(critical_points, ["visit_name", "visit", "visit_folder", "访视名称"])
        critical_page_col = find_col(critical_points, ["page_name", "data_page_name", "form_name", "form", "数据页名称", "表单名称"])
        critical_field_col = find_col(critical_points, ["field_name", "field", "item_name", "字段名称", "变量名"])
        critical_visits = normalized_text_values(critical_points[critical_visit_col]) if critical_visit_col else set()
        critical_pages = normalized_text_values(critical_points[critical_page_col]) if critical_page_col else set()
        critical_fields = normalized_text_values(critical_points[critical_field_col]) if critical_field_col else set()
        critical_mask = pd.Series(False, index=work.index)
        if query_field_col and critical_fields:
            critical_mask = work[query_field_col].astype(str).str.strip().str.lower().isin(critical_fields)
        elif query_page_col and critical_pages:
            critical_mask = work[query_page_col].astype(str).str.strip().str.lower().isin(critical_pages)
        elif query_visit_col and critical_visits:
            critical_mask = work[query_visit_col].astype(str).str.strip().str.lower().isin(critical_visits)
    elif critical_col:
        critical_mask = truthy_series(work[critical_col]) | text_contains(work, [critical_col], "critical|key|yes|true|1|关键|重要")
    else:
        critical_mask = text_contains(work, [type_col], "critical|key|endpoint|primary|safety|ae|sae|eligibility")
    sae_query_mask = text_contains(work, [text_col], r"^\s*\[sae recon\]")
    manual_mask = text_contains(work, [type_col], r"\bdm\s*manual\b|dm_manual|人工质疑")
    reissued_mask = text_contains(work, [status_col, reissue_col], "reopen|re-open|reissue|responded.*open|open.*responded|返回|重开|重新")
    if reissue_col and pd.api.types.is_numeric_dtype(work[reissue_col]):
        reissued_mask = reissued_mask | numeric_series(work[reissue_col]).gt(0).fillna(False)

    manual_total = manual_mask.groupby(work["__site_id"]).sum().reindex(sites).fillna(0).astype(float)
    manual_reissued = (manual_mask & reissued_mask).groupby(work["__site_id"]).sum().reindex(sites).fillna(0).astype(float)
    critical_queries = critical_mask.groupby(work["__site_id"]).sum().reindex(sites).fillna(0).astype(float)

    metrics["manual_query_reissue_rate"] = [safe_div(manual_reissued.loc[site], max(manual_total.loc[site], 1)) for site in sites]
    metrics["critical_queries_created"] = critical_queries
    metrics["avg_critical_open_query_age_days"] = age_days.where(critical_mask & open_mask).groupby(work["__site_id"]).mean().reindex(sites).fillna(0).clip(lower=0)

    if opened_col and closed_col:
        close_days = (datetime_series(work[closed_col]) - datetime_series(work[opened_col])).dt.days.clip(lower=0)
        metrics["avg_discrepancy_close_days"] = close_days.where(sae_query_mask).groupby(work["__site_id"]).mean().reindex(sites).fillna(0)


def compute_ae_metrics(metrics: pd.DataFrame, ae: pd.DataFrame, sites: list[str]) -> None:
    if ae.empty or "__site_id" not in ae:
        return
    serious_col = find_col(ae, ["aeser", "是否是严重不良事件", "is_sae", "sae", "serious_adverse_event", "is_serious", "seriousness", "serious", "是否严重", "SAE"])
    if serious_col:
        sae_mask = truthy_series(ae[serious_col]) | ae[serious_col].astype(str).str.lower().str.contains("sae|serious|yes|true|1|严重", regex=True, na=False)
    else:
        ae_type_col = find_col(ae, ["ae_type", "event_type", "type", "category", "事件类型", "类型"])
        sae_mask = text_contains(ae, [ae_type_col], "sae|serious|严重")
    sae_events = sae_mask.groupby(ae["__site_id"]).sum().reindex(sites).fillna(0)
    metrics["ae_event_error_changes"] = sae_events.astype(float)


def compute_metrics(tables: dict[str, pd.DataFrame], thresholds: Thresholds) -> tuple[pd.DataFrame, pd.DataFrame]:
    sites = available_sites(tables)
    metrics = pd.DataFrame(index=sites)
    metrics.index.name = "site_id"
    metrics["subjects"] = count_subjects(tables.get("subjects", pd.DataFrame()), sites)
    metrics["data_points"] = data_point_counts(tables, sites)
    for metric_name in KRI_METRIC_KEYS:
        metrics[metric_name] = 0.0

    compute_visit_metrics(metrics, tables.get("visits", pd.DataFrame()), thresholds, sites)
    compute_lab_metrics(metrics, tables.get("labs", pd.DataFrame()), sites)
    compute_query_metrics(metrics, tables.get("queries", pd.DataFrame()), tables.get("critical_points", pd.DataFrame()), sites)
    compute_ae_metrics(metrics, tables.get("ae", pd.DataFrame()), sites)

    enabled_metrics = active_kri_metrics(thresholds)
    component_defs = {
        "EDC Timeliness": {"weight": 0.15, "metrics": [("edc_visit_entry_delay_days", thresholds.edc_visit_entry_delay_days)]},
        "Page Quality": {
            "weight": 0.10,
            "metrics": [
                ("page_missing_days_all", thresholds.page_missing_days_all),
                ("page_missing_days_without_lab", thresholds.page_missing_days_without_lab),
                ("page_sdv_pending_rate", thresholds.page_sdv_pending_rate),
                ("logline_sdv_pending_rate", thresholds.logline_sdv_pending_rate),
            ],
        },
        "Query Cycle Time": {"weight": 0.25, "metrics": [("avg_open_query_age_days", thresholds.avg_open_query_age_days)]},
        "Query Rework": {"weight": 0.20, "metrics": [("manual_query_reissue_rate", thresholds.manual_query_reissue_rate)]},
    }
    active_components: list[tuple[str, float]] = []
    for label, definition in component_defs.items():
        scores = [
            metric_component_score(metrics[metric_name], threshold)
            for metric_name, threshold in definition["metrics"]
            if metric_name in enabled_metrics
        ]
        if scores:
            metrics[f"{label}_component"] = pd.concat(scores, axis=1).max(axis=1).clip(0, 100)
            active_components.append((label, float(definition["weight"])))
        else:
            metrics[f"{label}_component"] = 0.0

    total_weight = sum(weight for _, weight in active_components)
    if total_weight:
        score = sum((weight / total_weight) * metrics[f"{label}_component"] for label, weight in active_components)
        metrics["risk_score"] = score.round(1)
    else:
        metrics["risk_score"] = 0.0
    metrics["risk_level"] = pd.cut(metrics["risk_score"], bins=[-0.1, 39.9, 69.9, 100.0], labels=["低", "中", "高"]).astype(str)
    metrics = metrics.reset_index().sort_values("risk_score", ascending=False)
    return metrics, build_signals(metrics, thresholds)


def build_signals(metrics: pd.DataFrame, thresholds: Thresholds) -> pd.DataFrame:
    enabled_metrics = active_kri_metrics(thresholds)
    signal_defs = [
        ("EDC访视录入延迟", "edc_visit_entry_delay_days", thresholds.edc_visit_entry_delay_days, "录入及时性"),
        ("页面缺失天数（全部）偏长", "page_missing_days_all", thresholds.page_missing_days_all, "页面质量"),
        ("页面缺失天数（不含对接LAB）偏长", "page_missing_days_without_lab", thresholds.page_missing_days_without_lab, "页面质量"),
        ("未SDV（页面）天数偏长", "page_sdv_pending_rate", thresholds.page_sdv_pending_rate, "页面质量"),
        ("未SDV（logline）天数偏长", "logline_sdv_pending_rate", thresholds.logline_sdv_pending_rate, "页面质量"),
        ("人工质疑重发率偏高", "manual_query_reissue_rate", thresholds.manual_query_reissue_rate, "Query返工"),
        ("未关闭质疑天数偏长", "avg_open_query_age_days", thresholds.avg_open_query_age_days, "Query账龄"),
    ]
    rows: list[dict[str, Any]] = []
    for _, row in metrics.iterrows():
        for signal_name, metric_name, threshold, category in signal_defs:
            if metric_name not in enabled_metrics:
                continue
            value = float(row.get(metric_name, 0) or 0)
            if value > threshold:
                ratio = value / threshold if threshold else 0
                rows.append({
                    "signal_id": f"{row['site_id']}-{metric_name}",
                    "site_id": row["site_id"],
                    "category": category,
                    "signal": signal_name,
                    "metric": METRIC_VALUE_LABELS.get(metric_name, metric_name),
                    "value": round(value, 3),
                    "threshold": threshold,
                    "severity": "高" if ratio >= 1.5 else "中",
                    "risk_score": row["risk_score"],
                    "recommended_action": recommended_action(signal_name),
                })
    if not rows:
        return pd.DataFrame()
    signals = pd.DataFrame(rows)
    signals["__severity_order"] = signals["severity"].map({"高": 0, "中": 1}).fillna(2)
    return signals.sort_values(["__severity_order", "risk_score"], ascending=[True, False]).drop(columns="__severity_order")


def recommended_action(signal_name: str) -> str:
    actions = {
        "EDC访视录入延迟": "与中心确认访视后录入积压，优先处理关键访视和关键终点表单。",
        "页面缺失天数（全部）偏长": "复核缺失页面集中在哪些访视或表单，并推动中心补录或确认不适用原因。",
        "页面缺失天数（不含对接LAB）偏长": "排除对接LAB页面后复核中心自身页面缺失积压，并推动中心补录或确认不适用原因。",
        "未SDV（页面）天数偏长": "按中心和访视梳理未SDV页面，优先完成关键数据和超期页面的源数据核查。",
        "未SDV（logline）天数偏长": "按中心和数据页梳理未SDV logline，优先处理关键表单和超期行记录。",
        "人工质疑重发率偏高": "抽查重发质疑，确认答复质量、DM判定一致性和培训需求。",
        "SAE质疑关闭周期偏长": "推动中心和DM团队优先关闭SAE相关质疑，确认责任人、优先级和完成时限。",
        "未关闭质疑天数偏长": "按未关闭天数排序处理质疑，先处理超期和影响分析的数据点。",
    }
    return actions.get(signal_name, "复核该信号并记录行动计划。")
