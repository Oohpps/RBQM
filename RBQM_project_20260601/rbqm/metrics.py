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


def distinct_subject_rate(subject_counts: pd.Series, subject_sets: dict[str, set[str]], sites: list[str]) -> pd.Series:
    values = []
    for site in sites:
        denominator = max(float(subject_counts.get(site, 0) or 0), 1.0)
        values.append(len(subject_sets.get(site, set())) / denominator)
    return pd.Series(values, index=sites, dtype="float64")


def add_subject_hits(subject_sets: dict[str, set[str]], frame: pd.DataFrame, mask: pd.Series) -> None:
    if frame.empty or "__site_id" not in frame or not mask.any():
        return
    subject_col = "__subject_id" if "__subject_id" in frame else find_col(frame, ["subject_id", "subject", "受试者编号", "受试者", "筛选号"])
    if subject_col:
        for site, subject in frame.loc[mask, ["__site_id", subject_col]].itertuples(index=False, name=None):
            site_text = str(site).strip()
            normalized_site = site_text.zfill(3) if site_text.isdigit() else site_text
            subject_sets.setdefault(normalized_site, set()).add(str(subject))
        return
    for row_index, site in frame.loc[mask, "__site_id"].items():
        site_text = str(site).strip()
        normalized_site = site_text.zfill(3) if site_text.isdigit() else site_text
        subject_sets.setdefault(normalized_site, set()).add(f"row-{row_index}")


def text_scan_mask(frame: pd.DataFrame, pattern: str) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype="bool")
    columns = [col for col in frame.columns if not col.startswith("__")]
    if not columns:
        return pd.Series(False, index=frame.index)
    mask = pd.Series(False, index=frame.index)
    for col in columns:
        mask = mask | frame[col].astype(str).str.lower().str.contains(pattern, regex=True, na=False)
    return mask


def text_contains(df: pd.DataFrame, columns: list[str | None], pattern: str) -> pd.Series:
    mask = pd.Series(False, index=df.index)
    for col in columns:
        if col and col in df.columns:
            mask = mask | df[col].astype(str).str.lower().str.contains(pattern, regex=True, na=False)
    return mask


def positive_result_mask(frame: pd.DataFrame, result_col: str | None) -> pd.Series:
    if not result_col or result_col not in frame:
        return pd.Series(False, index=frame.index)
    text = frame[result_col].astype(str).str.strip().str.lower()
    return (
        text.str.contains("\u9633\u6027", regex=False, na=False)
        | text.str.contains("positive", regex=False, na=False)
        | text.eq("+")
        | text.eq("pos")
    )


def hcg_positive_mask(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype="bool")
    source = frame.get("__source_name", pd.Series("", index=frame.index)).astype(str).str.lower()
    sheet = source.str.rsplit("::", n=1).str[-1]
    hcg_source = sheet.eq("lb_hcg") | sheet.str.contains("hcg", regex=False, na=False)
    if not hcg_source.any():
        test_col = find_col(frame, ["test", "test_name", "parameter", "lab_test", "检查项", "项目", "指标", "lbtest"])
        hcg_source = text_contains(frame, [test_col], r"hcg|β-hcg|bhcg|人绒毛膜促性腺激素") if test_col else pd.Series(False, index=frame.index)
    result_col = None
    for column in frame.columns:
        normalized = str(column).lower().replace("_", "")
        if normalized.endswith("hcgorres"):
            result_col = column
            break
    if result_col is None:
        result_col = find_col(frame, [
            "hcgorres", "检查结果", "test_result", "lab_result", "result", "结果", "检验结果",
            "orres", "lbstresc", "lbstresn",
        ])
    return hcg_source & positive_result_mask(frame, result_col)


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
        return values.gt(0).astype(float) * 100
    return (values / threshold * 100).replace([np.inf, -np.inf], 0).fillna(0).clip(0, 100)


def range_component_score(values: pd.Series, lower: float, upper: float) -> pd.Series:
    low_score = ((lower - values).clip(lower=0) / max(lower, 1) * 100)
    high_score = ((values - upper).clip(lower=0) / max(upper, 1) * 100)
    return (low_score + high_score).replace([np.inf, -np.inf], 0).fillna(0).clip(0, 100)


def baseline_mask(frame: pd.DataFrame) -> pd.Series:
    visit_col = find_col(frame, ["数据节", "data_section", "visit", "visit_name", "visit_folder", "访视", "访视名称", "周期", "timepoint", "assessment"])
    if not visit_col:
        return pd.Series(True, index=frame.index)
    mask = text_contains(frame, [visit_col], "baseline|screen|筛选|基线|v1|visit 1")
    return mask if mask.any() else pd.Series(True, index=frame.index)


def screening_hba1c_section_mask(frame: pd.DataFrame) -> pd.Series:
    section_col = find_col(
        frame,
        [
            "数据节",
            "数据节点",
            "数据阶段",
            "data_section",
            "visit",
            "visit_name",
            "visit_folder",
            "访视",
            "访视名称",
            "周期",
            "timepoint",
        ],
    )
    if not section_col:
        return pd.Series(False, index=frame.index)
    text = frame[section_col].astype(str).str.lower().str.replace(r"\s+", "", regex=True)
    chinese = text.str.contains(r"筛选期.*w[^0-9]*2.*d[^0-9]*1", regex=True, na=False)
    english = text.str.contains(r"screen(?:ing)?.*w[^0-9]*2.*d[^0-9]*1", regex=True, na=False)
    return chinese | english


def screening_weight_table_mask(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(False, index=frame.index)
    bmi_col = bmi_value_column(frame)
    if not bmi_col:
        return pd.Series(False, index=frame.index)
    if "__source_name" not in frame:
        source_mask = pd.Series(True, index=frame.index)
    else:
        source_text = frame["__source_name"].astype(str).str.lower()
        sheet_text = source_text.str.rsplit("::", n=1).str[-1]
        source_mask = (
            sheet_text.eq("vs_w")
            | sheet_text.str.contains("空腹体重|fasting weight|fasting_weight", regex=True, na=False)
            | (sheet_text.str.contains("weight", regex=False, na=False) & sheet_text.str.contains("fast", regex=False, na=False))
        )
    section_col = find_col(
        frame,
        [
            "数据节",
            "数据节点",
            "数据阶段",
            "data_section",
            "visit",
            "visit_name",
            "visit_folder",
            "访视",
            "访视名称",
            "周期",
            "timepoint",
            "assessment",
            "edc访视名称",
        ],
    )
    if not section_col:
        return pd.Series(False, index=frame.index)
    section_mask = text_contains(
        frame,
        [section_col],
        r"筛选期|screening|screen|baseline|w-?2|d-?1|scr",
    )
    return source_mask & section_mask & leading_number_series(frame[bmi_col]).notna()


def screening_hba1c_page_mask(frame: pd.DataFrame) -> pd.Series:
    section_mask = screening_hba1c_section_mask(frame)
    if not section_mask.any():
        return section_mask
    source_mask = text_contains(
        frame,
        ["__source_name"],
        r"lb_hba1c|糖化血红蛋白|hba1c|hb a1c|glycated",
    )
    test_col = find_col(
        frame,
        [
            "test",
            "test_name",
            "parameter",
            "lab_test",
            "analyte",
            "实验室指标名称",
            "检查项目",
            "检查项",
            "项目",
            "指标",
        ],
    )
    test_mask = text_contains(
        frame,
        [test_col],
        r"糖化血红蛋白|hba1c|hb a1c|glycated",
    )
    return section_mask & (source_mask | test_mask)


def hba1c_value_column(frame: pd.DataFrame) -> str | None:
    result_col = find_col(frame, ["result", "lab_result", "value", "aval", "结果", "数值"])
    source_is_hba1c = text_contains(
        frame,
        ["__source_name"],
        r"lb_hba1c|糖化血红蛋白|hba1c|hb a1c|glycated",
    ).any()
    if source_is_hba1c and result_col:
        return result_col

    candidate = find_col(
        frame,
        [
            "hba1c",
            "hb_a1c",
            "glycated_hemoglobin",
            "a1c",
            "糖化血红蛋白",
            "糖化血红蛋白值",
        ],
    )
    if candidate:
        candidate_name = str(candidate).lower()
        if not any(token in candidate_name for token in ("lbyn", "是否", "检查")):
            return candidate
    return result_col


def bmi_value_column(frame: pd.DataFrame) -> str | None:
    preferred_aliases = ["BMI(Derived)(BMI)", "bmi_derived_bmi", "derived_bmi"]
    normalized_columns = {str(col).strip().lower(): col for col in frame.columns}
    for alias in preferred_aliases:
        alias_norm = str(alias).strip().lower()
        if alias_norm in normalized_columns:
            return normalized_columns[alias_norm]
    snake_columns = {str(col).strip().lower().replace("_", ""): col for col in frame.columns}
    for alias in preferred_aliases:
        alias_norm = str(alias).strip().lower().replace("_", "")
        if alias_norm in snake_columns:
            return snake_columns[alias_norm]
    preferred = find_col(frame, preferred_aliases)
    if preferred:
        return preferred
    fallback = find_col(frame, ["bmi", "body_mass_index", "体重指数", "身体质量指数"])
    if fallback and not any(token in str(fallback).lower() for token in ("bmiu", "单位", "unit")):
        return fallback
    return None


def subject_level_series(frame: pd.DataFrame, value_col: str, sites: list[str], mask: pd.Series | None = None) -> pd.Series:
    if frame.empty or "__site_id" not in frame or value_col not in frame:
        return pd.Series(dtype="float64")
    work = frame.loc[mask] if mask is not None else frame
    if work.empty:
        return pd.Series(dtype="float64")
    values = numeric_series(work[value_col])
    subject_col = "__subject_id" if "__subject_id" in work else find_col(work, ["subject_id", "subject", "受试者编号", "受试者", "筛选号"])
    if subject_col:
        temp = pd.DataFrame({"site": work["__site_id"], "subject": work[subject_col].astype(str), "value": values})
        temp = temp.dropna(subset=["value"])
        if temp.empty:
            return pd.Series(dtype="float64")
        return temp.groupby(["site", "subject"])["value"].first().groupby("site").mean().reindex(sites)
    return values.groupby(work["__site_id"]).mean().reindex(sites)


def compute_mm_metrics(metrics: pd.DataFrame, tables: dict[str, pd.DataFrame], sites: list[str]) -> None:
    subjects = tables.get("subjects", pd.DataFrame())
    if not subjects.empty and "__site_id" in subjects:
        age_col = find_col(subjects, ["年龄(Derived)(AGE)", "age_derived_age", "derived_age", "age_years", "受试者年龄", "age_at_screening", "screening_age", "年龄", "age"])
        sex_col = find_col(subjects, ["sex", "gender", "性别"])
        if age_col:
            metrics["avg_age_years"] = subject_level_series(subjects, age_col, sites).fillna(0)
        if sex_col:
            male_mask = text_contains(subjects, [sex_col], r"^m$|male|男|男性")
            subject_col = "__subject_id" if "__subject_id" in subjects else find_col(subjects, ["subject_id", "subject", "受试者编号", "受试者", "筛选号"])
            if subject_col:
                total = subjects.groupby("__site_id")[subject_col].nunique().reindex(sites).fillna(0)
                male = subjects.loc[male_mask].groupby("__site_id")[subject_col].nunique().reindex(sites).fillna(0)
                metrics["male_rate"] = [safe_div(male.loc[site], max(total.loc[site], 1)) for site in sites]
            else:
                metrics["male_rate"] = male_mask.groupby(subjects["__site_id"]).mean().reindex(sites).fillna(0)

    hba1c_parts: list[pd.Series] = []
    bmi_values_by_site: dict[str, list[float]] = {site: [] for site in sites}
    for domain in tables:
        frame = tables.get(domain, pd.DataFrame())
        if frame.empty or "__site_id" not in frame:
            continue
        hba1c_col = hba1c_value_column(frame)
        bmi_col = bmi_value_column(frame)
        test_col = find_col(frame, ["test", "test_name", "parameter", "lab_test", "analyte", "检查项", "项目", "指标"])
        result_col = find_col(frame, ["result", "lab_result", "value", "aval", "结果", "数值"])
        hba1c_mask = screening_hba1c_page_mask(frame)
        if hba1c_col and hba1c_mask.any():
            hba1c_work = frame.copy()
            hba1c_work["__hba1c_numeric"] = leading_number_series(hba1c_work[hba1c_col])
            hba1c_parts.append(subject_level_series(hba1c_work, "__hba1c_numeric", sites, hba1c_mask))
        elif test_col and result_col:
            result_mask = hba1c_mask & text_contains(frame, [test_col], "hba1c|hb a1c|hb_a1c|a1c|glycated|糖化血红蛋白|糖化")
            if result_mask.any():
                hba1c_work = frame.copy()
                hba1c_work["__hba1c_numeric"] = leading_number_series(hba1c_work[result_col])
                hba1c_parts.append(subject_level_series(hba1c_work, "__hba1c_numeric", sites, result_mask))

        bmi_mask = screening_weight_table_mask(frame)
        if bmi_col and bmi_mask.any():
            values = leading_number_series(frame.loc[bmi_mask, bmi_col])
            for site, value in zip(frame.loc[bmi_mask, "__site_id"].astype(str), values):
                if pd.notna(value):
                    bmi_values_by_site.setdefault(site, []).append(float(value))

    if hba1c_parts:
        metrics["baseline_hba1c_avg"] = pd.concat(hba1c_parts, axis=1).mean(axis=1).reindex(sites).fillna(0)
    metrics["baseline_bmi_avg"] = [
        float(pd.Series(bmi_values_by_site.get(site, []), dtype="float64").mean())
        if bmi_values_by_site.get(site)
        else 0.0
        for site in sites
    ]
    metrics["bmi_under_24_rate"] = [safe_div(sum(value < 24 for value in bmi_values_by_site.get(site, [])), max(len(bmi_values_by_site.get(site, [])), 1)) for site in sites]
    metrics["bmi_30_35_rate"] = [safe_div(sum(30 <= value < 35 for value in bmi_values_by_site.get(site, [])), max(len(bmi_values_by_site.get(site, [])), 1)) for site in sites]
    metrics["bmi_over_35_count"] = [sum(value > 35 for value in bmi_values_by_site.get(site, [])) for site in sites]


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


def compute_efficacy_completeness_metrics(metrics: pd.DataFrame, tables: dict[str, pd.DataFrame], sites: list[str]) -> None:
    subject_counts = metrics["subjects"]
    hba1c_subjects: dict[str, set[str]] = {}
    weight_subjects: dict[str, set[str]] = {}

    for domain in ("visits", "labs"):
        frame = tables.get(domain, pd.DataFrame())
        if frame.empty or "__site_id" not in frame:
            continue
        source = frame.get("__source_name", pd.Series("", index=frame.index)).astype(str).str.lower()
        hba1c_col = find_col(frame, ["hba1c", "hb_a1c", "glycated_hemoglobin", "a1c", "糖化血红蛋白", "糖化"])
        weight_col = find_col(frame, ["weight", "body_weight", "wt", "体重", "体质量"])
        test_col = find_col(frame, ["test", "test_name", "parameter", "lab_test", "analyte", "检查项", "项目", "指标"])
        result_col = find_col(frame, ["result", "lab_result", "value", "aval", "结果", "数值"])

        hba1c_missing = source.str.contains("hba1c|糖化血红蛋白|糖化", regex=True, na=False) & source.str.contains("缺失|missing", regex=True, na=False)
        weight_missing = source.str.contains("weight|体重|体质量", regex=True, na=False) & source.str.contains("缺失|missing", regex=True, na=False)
        if hba1c_col:
            hba1c_missing = hba1c_missing | frame[hba1c_col].isna() | frame[hba1c_col].astype(str).str.strip().isin(["", "nan", "None"])
        if weight_col:
            weight_missing = weight_missing | frame[weight_col].isna() | frame[weight_col].astype(str).str.strip().isin(["", "nan", "None"])
        if test_col and result_col:
            hba1c_row = text_contains(frame, [test_col], "hba1c|hb a1c|hb_a1c|a1c|glycated|糖化血红蛋白|糖化")
            weight_row = text_contains(frame, [test_col], "weight|body weight|体重|体质量")
            result_missing = frame[result_col].isna() | frame[result_col].astype(str).str.strip().isin(["", "nan", "None"])
            hba1c_missing = hba1c_missing | (hba1c_row & result_missing)
            weight_missing = weight_missing | (weight_row & result_missing)

        add_subject_hits(hba1c_subjects, frame, hba1c_missing)
        add_subject_hits(weight_subjects, frame, weight_missing)

    metrics["hba1c_missing_rate"] = distinct_subject_rate(subject_counts, hba1c_subjects, sites)
    metrics["weight_missing_rate"] = distinct_subject_rate(subject_counts, weight_subjects, sites)


def _find_pre_w44_early_terminations(subjects: pd.DataFrame, visits: pd.DataFrame, sites: list[str]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    if subjects.empty or "__site_id" not in subjects:
        return result

    status_col = find_col(subjects, ["subject_status", "受试者状态", "status", "状态"])
    subject_col = "__subject_id" if "__subject_id" in subjects else find_col(subjects, ["subject_id", "subject", "受试者编号", "受试者", "筛选号"])
    if not status_col or not subject_col:
        return result

    # 状态为提前退出/研究结束/完成/终止
    early_status_mask = text_contains(subjects, [status_col], r"early terminat|withdraw|discontinu|dropout|提前退出|提前终止|退出研究|终止研究|脱落|研究结束|completed|结束")
    early_frame = subjects.loc[early_status_mask]
    if early_frame.empty:
        return result

    early_subject_ids = set(early_frame[subject_col].dropna().astype(str).str.strip())

    # 从visits找有W44记录的受试者
    w44_subject_ids: set[str] = set()
    if not visits.empty and "__site_id" in visits:
        visit_col = find_col(visits, ["visit", "visit_name", "visit_folder", "访视", "访视名称", "周期", "timepoint", "assessment", "edc访视名称"])
        if visit_col:
            w44_mask = text_contains(visits, [visit_col], r"w44|week44|visit44|v44|w-44|第44")
            subject_col_v = "__subject_id" if "__subject_id" in visits else find_col(visits, ["subject_id", "subject", "受试者编号", "受试者", "筛选号"])
            if subject_col_v:
                w44_subject_ids = set(visits.loc[w44_mask, subject_col_v].dropna().astype(str).str.strip())

    # 排除有W44记录的受试者
    pre_w44_ids = early_subject_ids - w44_subject_ids
    if not pre_w44_ids:
        return result

    for _, row in early_frame.iterrows():
        sid = str(row[subject_col]).strip()
        site = str(row.get("__site_id", "")).strip()
        if sid in pre_w44_ids and site:
            result.setdefault(site, set()).add(sid)

    return result


def compute_subject_event_metrics(metrics: pd.DataFrame, tables: dict[str, pd.DataFrame], sites: list[str]) -> None:
    subject_counts = metrics["subjects"]
    concomitant_subjects: dict[str, set[str]] = {}
    early_subjects: dict[str, set[str]] = {}
    pregnancy_subjects: dict[str, set[str]] = {}

    for domain in ("subjects", "visits", "ae", "deviations", "dosing"):
        frame = tables.get(domain, pd.DataFrame())
        if frame.empty or "__site_id" not in frame:
            continue
        concomitant_mask = text_scan_mask(frame, "concomitant|rescue|remedial|伴发|补救|提前终止治疗|接受补救治疗")
        add_subject_hits(concomitant_subjects, frame, concomitant_mask)

    # W44前提前退出
    subjects = tables.get("subjects", pd.DataFrame())
    visits = tables.get("visits", pd.DataFrame())
    early_subjects = _find_pre_w44_early_terminations(subjects, visits, sites)

    # 妊娠：只从 LB_HCG 找检查结果为阳性的受试者
    for domain in ("labs", "visits"):
        frame = tables.get(domain, pd.DataFrame())
        if frame.empty or "__site_id" not in frame:
            continue
        positive_mask = hcg_positive_mask(frame)
        add_subject_hits(pregnancy_subjects, frame, positive_mask)

    metrics["concomitant_event_rate"] = distinct_subject_rate(subject_counts, concomitant_subjects, sites)
    metrics["early_termination_rate"] = distinct_subject_rate(subject_counts, early_subjects, sites)
    metrics["pregnancy_rate"] = distinct_subject_rate(subject_counts, pregnancy_subjects, sites)


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
    consistency_mask = text_contains(work, ["__source_name", type_col, text_col], "pk|ada|anti-drug|抗药|一致|比对|recon|reconciliation|discrepancy")
    metrics["data_consistency_issue_days"] = age_days.where(consistency_mask & open_mask).groupby(work["__site_id"]).mean().reindex(sites).fillna(0).clip(lower=0)


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


def is_screen_failure_status(value: object) -> bool:
    text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    return any(token in text for token in ("筛选失败", "筛败", "screen fail", "screening fail"))


def exclude_screen_failure_subjects(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    failed_subjects: set[str] = set()
    status_aliases = ["subject_status", "受试者状态", "status", "状态"]
    for frame in tables.values():
        if frame.empty or "__subject_id" not in frame:
            continue
        status_col = find_col(frame, status_aliases)
        if not status_col:
            continue
        failed_mask = frame[status_col].map(is_screen_failure_status)
        failed_subjects.update(
            frame.loc[failed_mask, "__subject_id"].dropna().astype(str).str.strip().tolist()
        )

    filtered: dict[str, pd.DataFrame] = {}
    for domain, frame in tables.items():
        if frame.empty:
            filtered[domain] = frame.copy()
            continue
        keep_mask = pd.Series(True, index=frame.index)
        if "__subject_id" in frame:
            subject_ids = frame["__subject_id"].fillna("").astype(str).str.strip()
            keep_mask &= ~subject_ids.isin(failed_subjects)
        status_col = find_col(frame, status_aliases)
        if status_col:
            keep_mask &= ~frame[status_col].map(is_screen_failure_status)
        filtered[domain] = frame.loc[keep_mask].copy()
    return filtered


def compute_metrics(
    tables: dict[str, pd.DataFrame],
    thresholds: Thresholds,
    sites: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sites = sites if sites is not None else available_sites(tables)
    metrics = pd.DataFrame(index=sites)
    metrics.index.name = "site_id"
    metrics["subjects"] = count_subjects(tables.get("subjects", pd.DataFrame()), sites)
    metrics["data_points"] = data_point_counts(tables, sites)
    for metric_name in KRI_METRIC_KEYS:
        metrics[metric_name] = 0.0

    compute_mm_metrics(metrics, tables, sites)
    compute_visit_metrics(metrics, tables.get("visits", pd.DataFrame()), thresholds, sites)
    compute_lab_metrics(metrics, tables.get("labs", pd.DataFrame()), sites)
    compute_efficacy_completeness_metrics(metrics, tables, sites)
    compute_subject_event_metrics(metrics, tables, sites)
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
        "Efficacy Completeness": {
            "weight": 0.20,
            "metrics": [
                ("hba1c_missing_rate", thresholds.hba1c_missing_rate),
                ("weight_missing_rate", thresholds.weight_missing_rate),
            ],
        },
        "Subject Retention": {
            "weight": 0.15,
            "metrics": [("early_termination_rate", thresholds.early_termination_rate)],
        },
        "Safety Reporting": {
            "weight": 0.15,
            "metrics": [
                ("concomitant_event_rate", thresholds.concomitant_event_rate),
                ("pregnancy_rate", thresholds.pregnancy_rate),
            ],
        },
        "Data Consistency": {
            "weight": 0.15,
            "metrics": [("data_consistency_issue_days", thresholds.data_consistency_issue_days)],
        },
        "MM Baseline Balance": {
            "weight": 0.15,
            "metrics": [
                ("avg_age_years", thresholds.avg_age_years),
                ("male_rate", thresholds.male_rate),
                ("baseline_hba1c_avg", thresholds.baseline_hba1c_avg),
                ("baseline_bmi_avg", thresholds.baseline_bmi_avg),
                ("bmi_under_24_rate", thresholds.bmi_under_24_rate),
                ("bmi_30_35_rate", thresholds.bmi_30_35_rate),
                ("bmi_over_35_count", thresholds.bmi_over_35_count),
            ],
        },
    }
    active_components: list[tuple[str, float]] = []
    for label, definition in component_defs.items():
        scores = []
        for metric_name, threshold in definition["metrics"]:
            if metric_name not in enabled_metrics:
                continue
            if metric_name == "baseline_hba1c_avg":
                scores.append(range_component_score(metrics[metric_name], 8.0, 8.5))
            else:
                scores.append(metric_component_score(metrics[metric_name], threshold))
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
        ("平均年龄偏高", "avg_age_years", thresholds.avg_age_years, "MM基线人口学"),
        ("男性参与者比例偏高", "male_rate", thresholds.male_rate, "MM基线人口学"),
        ("基线BMI平均值偏高", "baseline_bmi_avg", thresholds.baseline_bmi_avg, "MM基线BMI"),
        ("BMI<24比例偏高", "bmi_under_24_rate", thresholds.bmi_under_24_rate, "MM基线BMI"),
        ("BMI 30-35比例偏高", "bmi_30_35_rate", thresholds.bmi_30_35_rate, "MM基线BMI"),
        ("BMI>35病例数不为0", "bmi_over_35_count", thresholds.bmi_over_35_count, "MM基线BMI"),
        ("EDC访视录入延迟", "edc_visit_entry_delay_days", thresholds.edc_visit_entry_delay_days, "录入及时性"),
        ("页面缺失天数（全部）偏长", "page_missing_days_all", thresholds.page_missing_days_all, "页面质量"),
        ("页面缺失天数（不含对接LAB）偏长", "page_missing_days_without_lab", thresholds.page_missing_days_without_lab, "页面质量"),
        ("未SDV（页面）天数偏长", "page_sdv_pending_rate", thresholds.page_sdv_pending_rate, "页面质量"),
        ("未SDV（logline）天数偏长", "logline_sdv_pending_rate", thresholds.logline_sdv_pending_rate, "页面质量"),
        ("人工质疑重发率偏高", "manual_query_reissue_rate", thresholds.manual_query_reissue_rate, "Query返工"),
        ("未关闭质疑天数偏长", "avg_open_query_age_days", thresholds.avg_open_query_age_days, "Query账龄"),
        ("HbA1c数据缺失比例偏高", "hba1c_missing_rate", thresholds.hba1c_missing_rate, "疗效数据完整性"),
        ("体重数据缺失比例偏高", "weight_missing_rate", thresholds.weight_missing_rate, "疗效数据完整性"),
        ("伴发事件受试者比例偏高", "concomitant_event_rate", thresholds.concomitant_event_rate, "伴发事件"),
        ("W44前提前退出比例偏高", "early_termination_rate", thresholds.early_termination_rate, "受试者留存"),
        ("妊娠受试者比例偏高", "pregnancy_rate", thresholds.pregnancy_rate, "安全性事件"),
        ("数据一致性问题未解决天数偏长", "data_consistency_issue_days", thresholds.data_consistency_issue_days, "数据一致性"),
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
        if "baseline_hba1c_avg" in enabled_metrics:
            value = float(row.get("baseline_hba1c_avg", 0) or 0)
            if value and (value < 8.0 or value > thresholds.baseline_hba1c_avg):
                rows.append({
                    "signal_id": f"{row['site_id']}-baseline_hba1c_avg",
                    "site_id": row["site_id"],
                    "category": "MM基线疗效特征",
                    "signal": "基线HbA1c平均值不在8-8.5%",
                    "metric": METRIC_VALUE_LABELS.get("baseline_hba1c_avg", "基线HbA1c平均值"),
                    "value": round(value, 3),
                    "threshold": "8-8.5",
                    "severity": "中",
                    "risk_score": row["risk_score"],
                    "recommended_action": recommended_action("基线HbA1c平均值不在8-8.5%"),
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
        "平均年龄偏高": "按中心复核入组人群年龄分布，确认是否偏离方案人群和项目基线预期。",
        "男性参与者比例偏高": "复核中心性别分布，确认招募人群是否存在结构性偏倚。",
        "基线HbA1c平均值不在8-8.5%": "复核中心基线HbA1c分布，确认入组人群与方案设定及统计假设是否一致。",
        "基线BMI平均值偏高": "复核中心BMI分布，确认是否存在基线特征偏移。",
        "BMI<24比例偏高": "复核低BMI受试者入组情况，确认入排标准和人群匹配度。",
        "BMI 30-35比例偏高": "复核高BMI受试者集中中心，确认是否影响人群均衡。",
        "BMI>35病例数不为0": "核查BMI>35病例，确认是否违反入排标准或需医学评估。",
        "HbA1c数据缺失比例偏高": "按访视和中心复核HbA1c缺失原因，优先补齐关键疗效访视或记录不可采集原因。",
        "体重数据缺失比例偏高": "核查体重数据缺失集中访视，推动中心补录或确认未采集原因。",
        "伴发事件受试者比例偏高": "复核提前终止治疗、补救治疗或伴发事件记录，确认是否影响主要分析和受试者保护。",
        "W44前提前退出比例偏高": "按中心梳理提前退出原因，评估依从性、随访和中心执行风险。",
        "妊娠受试者比例偏高": "立即复核妊娠相关报告、随访和安全性升级流程，确认是否需要项目级CAPA。",
        "数据一致性问题未解决天数偏长": "推动EDC与PK/ADA等外部数据比对问题关闭，明确责任方和预计解决时间。",
    }
    return actions.get(signal_name, "复核该信号并记录行动计划。")
