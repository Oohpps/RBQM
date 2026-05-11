from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO
import re
from typing import Any

import numpy as np
import pandas as pd

TODAY = pd.Timestamp(date.today())

KRI_METRIC_KEYS = (
    "missing_rate",
    "late_entry_rate",
    "avg_entry_delay_days",
    "open_queries_per_subject",
    "avg_open_query_age_days",
    "safety_issues_per_subject",
    "dlt_rate",
    "grade3_ae_rate",
    "dose_modification_rate",
    "eligibility_deviation_rate",
    "pk_window_deviation_rate",
    "tumor_assessment_issue_rate",
    "lab_issues_per_subject",
    "major_deviations_per_subject",
)


@dataclass(frozen=True)
class Thresholds:
    missing_rate: float
    late_entry_rate: float
    avg_entry_delay_days: float
    open_queries_per_subject: float
    avg_open_query_age_days: float
    safety_issues_per_subject: float
    dlt_rate: float
    grade3_ae_rate: float
    dose_modification_rate: float
    eligibility_deviation_rate: float
    pk_window_deviation_rate: float
    tumor_assessment_issue_rate: float
    lab_issues_per_subject: float
    major_deviations_per_subject: float
    kri_enabled: bool = True
    enabled_metrics: tuple[str, ...] = KRI_METRIC_KEYS


DOMAIN_LABELS = {
    "subjects": "受试者 / 入组",
    "visits": "访视 / EDC表单",
    "queries": "Query / 数据核查",
    "ae": "AE / SAE",
    "dosing": "给药 / 剂量调整",
    "pk": "PK / PD采样",
    "tumor": "肿瘤评估",
    "labs": "实验室",
    "deviations": "方案偏离",
}

METRIC_LABELS = {
    "site_id": "中心",
    "subjects": "受试者数",
    "missing_rate": "缺失率",
    "late_entry_rate": "延迟录入率",
    "avg_entry_delay_days": "平均录入延迟（天）",
    "open_queries": "未关闭Query数",
    "open_queries_per_subject": "每受试者未关闭Query数",
    "avg_open_query_age_days": "未关闭Query平均账期（天）",
    "safety_issues": "安全性问题数",
    "safety_issues_per_subject": "每受试者安全性问题数",
    "dlt_events": "DLT事件数",
    "dlt_rate": "DLT发生率",
    "grade3_ae_events": "≥3级AE事件数",
    "grade3_ae_rate": "≥3级AE发生率",
    "dose_modifications": "毒性相关剂量调整数",
    "dose_modification_rate": "毒性相关剂量调整率",
    "eligibility_deviations": "入排标准偏离数",
    "eligibility_deviation_rate": "入排标准偏离率",
    "pk_window_deviations": "PK/PD采样窗偏离数",
    "pk_window_deviation_rate": "PK/PD采样窗偏离率",
    "tumor_assessment_issues": "肿瘤评估缺失/延迟数",
    "tumor_assessment_issue_rate": "肿瘤评估缺失/延迟率",
    "lab_issues": "未复核异常实验室数",
    "lab_issues_per_subject": "每受试者未复核异常实验室数",
    "major_deviations": "重大偏离数",
    "major_deviations_per_subject": "每受试者重大偏离数",
    "Completeness_component": "完整性评分",
    "Timeliness_component": "及时性评分",
    "Query Burden_component": "Query负荷评分",
    "Safety Review_component": "安全性复核评分",
    "Dose Safety_component": "剂量安全评分",
    "Dose Administration_component": "给药调整评分",
    "PK Integrity_component": "PK/PD完整性评分",
    "Tumor Assessment_component": "肿瘤评估评分",
    "Protocol Compliance_component": "方案依从性评分",
    "Data Quality_component": "数据质量评分",
    "Labs and PD_component": "实验室与偏离评分",
    "risk_score": "风险评分",
    "risk_level": "风险等级",
}

SIGNAL_LABELS = {
    "signal_id": "信号编号",
    "site_id": "中心",
    "category": "类别",
    "signal": "风险信号",
    "metric": "指标",
    "value": "当前值",
    "threshold": "阈值",
    "severity": "严重度",
    "risk_score": "风险评分",
    "recommended_action": "建议动作",
}

ACTION_LOG_LABELS = {
    "signal_id": "信号编号",
    "site_id": "中心",
    "signal": "风险信号",
    "severity": "严重度",
    "owner": "责任人",
    "action": "行动",
    "due_date": "截止日期",
    "status": "状态",
    "resolution_comment": "关闭说明",
}

COMPONENT_LABELS = {
    "Completeness_component": "完整性",
    "Timeliness_component": "及时性",
    "Query Burden_component": "Query负荷",
    "Safety Review_component": "安全性",
    "Dose Safety_component": "剂量安全",
    "Dose Administration_component": "给药调整",
    "PK Integrity_component": "PK/PD完整性",
    "Tumor Assessment_component": "肿瘤评估",
    "Protocol Compliance_component": "方案依从性",
    "Labs and PD_component": "实验室与偏离",
}

METRIC_VALUE_LABELS = {
    "missing_rate": "缺失率",
    "late_entry_rate": "延迟录入率",
    "avg_entry_delay_days": "平均录入延迟（天）",
    "open_queries_per_subject": "每受试者未关闭Query数",
    "avg_open_query_age_days": "未关闭Query平均账期（天）",
    "safety_issues_per_subject": "每受试者安全性问题数",
    "dlt_rate": "DLT发生率",
    "grade3_ae_rate": "≥3级AE发生率",
    "dose_modification_rate": "毒性相关剂量调整率",
    "eligibility_deviation_rate": "入排标准偏离率",
    "pk_window_deviation_rate": "PK/PD采样窗偏离率",
    "tumor_assessment_issue_rate": "肿瘤评估缺失/延迟率",
    "lab_issues_per_subject": "每受试者未复核异常实验室数",
    "major_deviations_per_subject": "每受试者重大偏离数",
}

SITE_ALIASES = [
    "site_id", "site", "site_no", "site_number", "center", "center_id", "centre", "institution",
    "中心", "中心编号", "研究中心", "机构编号",
]
SUBJECT_ALIASES = [
    "subject_id", "subject", "subjid", "usubjid", "participant_id", "patient_id", "patient", "screening_number",
    "受试者", "受试者编号", "受试者id", "患者", "患者编号", "患者id", "入组编号", "随机号",
]

def snake_case(value: Any) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^\w]+", "_", text, flags=re.UNICODE)
    return text.strip("_") or "column"


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    clean = df.copy()
    seen: dict[str, int] = {}
    new_cols: list[str] = []
    for col in clean.columns:
        base = snake_case(col)
        count = seen.get(base, 0)
        new_cols.append(base if count == 0 else f"{base}_{count + 1}")
        seen[base] = count + 1
    clean.columns = new_cols
    return clean


def find_col(df: pd.DataFrame, aliases: list[str]) -> str | None:
    if df.empty:
        return None
    columns = set(df.columns)
    for alias in aliases:
        norm = snake_case(alias)
        if norm in columns:
            return norm
    for col in df.columns:
        compact_col = str(col).replace("_", "")
        for alias in aliases:
            norm = snake_case(alias)
            compact_norm = norm.replace("_", "")
            if (
                col == norm
                or str(col).endswith(f"_{norm}")
                or norm in str(col)
                or compact_col == compact_norm
                or compact_col.endswith(compact_norm)
                or compact_norm in compact_col
            ):
                return col
    return None


def numeric_series(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype="float64")
    return pd.to_numeric(series, errors="coerce")


def datetime_series(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(series, errors="coerce")


def truthy_series(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype="bool")
    text = series.astype(str).str.strip().str.lower()
    return text.isin(["y", "yes", "true", "1", "serious", "sae", "major", "critical", "是", "有", "严重", "重大"])


def grade_series(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype="float64")
    text = series.astype(str).str.extract(r"(\d+(?:\.\d+)?)", expand=False)
    return pd.to_numeric(text, errors="coerce")


def safe_div(numerator: float | int, denominator: float | int) -> float:
    denominator = float(denominator or 0)
    if denominator == 0:
        return 0.0
    return float(numerator) / denominator


def infer_domain(name: str) -> str | None:
    value = snake_case(name)
    if any(token in value for token in ["query", "queries", "qry", "查询", "质疑", "问题"]):
        return "queries"
    if any(token in value for token in ["dose", "dosing", "exposure", "ex", "drug_administration", "给药", "剂量", "暴露"]):
        return "dosing"
    if any(token in value for token in ["pk", "pharmacokinetic", "pharmacodynamic", "pd_sample", "sample", "采样", "药代", "药效"]):
        return "pk"
    if any(token in value for token in ["tumor", "tumour", "recist", "response", "lesion", "assessment", "肿瘤", "疗效", "病灶", "评估"]):
        return "tumor"
    if any(token in value for token in ["deviation", "protocol_deviation", "pd", "dv", "偏离", "违背"]):
        return "deviations"
    if any(token in value for token in ["lab", "laboratory", "hematology", "chemistry", "lb", "实验室", "化验", "检验"]):
        return "labs"
    if any(token in value for token in ["sae", "adverse", "ae", "不良事件", "不良反应"]):
        return "ae"
    if any(token in value for token in ["visit", "form", "edc", "crf", "访视", "表单", "随访"]):
        return "visits"
    if any(token in value for token in ["subject", "enroll", "random", "participant", "patient", "adsl", "dm", "受试者", "患者", "入组", "随机"]):
        return "subjects"
    return None

def read_uploaded_files(uploaded_files: list[Any]) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    domain_tables: dict[str, list[pd.DataFrame]] = {domain: [] for domain in DOMAIN_LABELS}
    raw_tables: dict[str, pd.DataFrame] = {}

    for uploaded in uploaded_files:
        filename = uploaded.name
        suffix = filename.rsplit(".", 1)[-1].lower()
        if suffix == "csv":
            df = pd.read_csv(uploaded)
            raw_tables[filename] = df
            domain = infer_domain(filename)
            if domain:
                domain_tables[domain].append(standardize_columns(df))
            continue

        sheets = pd.read_excel(uploaded, sheet_name=None)
        for sheet_name, df in sheets.items():
            label = f"{filename}::{sheet_name}"
            raw_tables[label] = df
            domain = infer_domain(sheet_name) or infer_domain(filename)
            if domain:
                domain_tables[domain].append(standardize_columns(df))

    combined: dict[str, pd.DataFrame] = {}
    for domain, parts in domain_tables.items():
        if parts:
            combined[domain] = pd.concat(parts, ignore_index=True, sort=False)
    return combined, raw_tables


def generate_demo_data(seed: int = 20260510) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    sites = [f"S{i:03d}" for i in range(1, 13)]
    countries = ["China", "United States", "Poland", "Brazil"]
    risk_factor = {site: rng.uniform(0.4, 1.8) for site in sites}
    risk_factor["S003"] = 2.4
    risk_factor["S008"] = 2.1
    risk_factor["S011"] = 1.9

    subject_rows: list[dict[str, Any]] = []
    start_date = pd.Timestamp("2025-10-01")
    for idx, site in enumerate(sites):
        count = int(rng.integers(22, 58))
        for sub in range(1, count + 1):
            enrolled_date = start_date + pd.Timedelta(days=int(rng.integers(0, 180)))
            subject_rows.append(
                {
                    "subject_id": f"{site}-{sub:03d}",
                    "site_id": site,
                    "country": countries[idx % len(countries)],
                    "status": rng.choice(["Active", "Completed", "Early Terminated"], p=[0.55, 0.35, 0.10]),
                    "enrolled_date": enrolled_date,
                    "randomized_date": enrolled_date + pd.Timedelta(days=int(rng.integers(0, 10))),
                }
            )
    subjects = pd.DataFrame(subject_rows)

    visits = []
    for row in subjects.itertuples(index=False):
        factor = risk_factor[row.site_id]
        for visit_no in range(1, 6):
            visit_date = pd.Timestamp(row.randomized_date) + pd.Timedelta(days=28 * (visit_no - 1))
            delay = max(0, int(rng.normal(2.5 * factor, 3.5)))
            completion_probability = max(0.72, 0.98 - 0.045 * factor)
            completed = rng.random() < completion_probability
            endpoint_missing = rng.random() < min(0.28, 0.035 * factor)
            visits.append(
                {
                    "subject_id": row.subject_id,
                    "site_id": row.site_id,
                    "visit": f"V{visit_no}",
                    "visit_date": visit_date,
                    "data_entry_date": visit_date + pd.Timedelta(days=delay) if completed else pd.NaT,
                    "form_status": "Complete" if completed else "Incomplete",
                    "primary_endpoint": np.nan if endpoint_missing else rng.normal(52, 12),
                    "egfr": np.nan if rng.random() < 0.02 * factor else rng.normal(82, 18),
                }
            )
    visits_df = pd.DataFrame(visits)

    query_rows = []
    for row in subjects.itertuples(index=False):
        factor = risk_factor[row.site_id]
        query_count = int(rng.poisson(0.45 * factor))
        for query_no in range(query_count):
            opened = TODAY - pd.Timedelta(days=int(rng.integers(2, 60)))
            is_closed = rng.random() < max(0.30, 0.80 - 0.14 * factor)
            closed = opened + pd.Timedelta(days=int(rng.integers(1, 24))) if is_closed else pd.NaT
            age_days = (closed - opened).days if is_closed else (TODAY - opened).days
            query_rows.append(
                {
                    "subject_id": row.subject_id,
                    "site_id": row.site_id,
                    "form": rng.choice(["AE", "Labs", "Visit", "Exposure", "Eligibility"]),
                    "field": rng.choice(["Date", "Result", "Outcome", "Endpoint", "Dose"]),
                    "query_status": "Closed" if is_closed else "Open",
                    "opened_date": opened,
                    "closed_date": closed,
                    "age_days": age_days,
                }
            )
    queries = pd.DataFrame(query_rows)

    ae_rows = []
    for row in subjects.itertuples(index=False):
        factor = risk_factor[row.site_id]
        ae_count = int(rng.poisson(0.30 + 0.16 * factor))
        for _ in range(ae_count):
            serious = rng.random() < 0.09
            missing_followup = serious and rng.random() < min(0.45, 0.08 * factor)
            ae_rows.append(
                {
                    "subject_id": row.subject_id,
                    "site_id": row.site_id,
                    "ae_term": rng.choice(["Headache", "Nausea", "ALT increased", "Fatigue", "Dizziness"]),
                    "serious": "Yes" if serious else "No",
                    "severity": np.nan if missing_followup else rng.choice(["Mild", "Moderate", "Severe"], p=[0.55, 0.35, 0.10]),
                    "outcome": np.nan if missing_followup else rng.choice(["Recovered", "Recovering", "Ongoing"]),
                    "start_date": TODAY - pd.Timedelta(days=int(rng.integers(5, 160))),
                }
            )
    ae = pd.DataFrame(ae_rows)

    lab_rows = []
    tests = {
        "ALT": (0, 40, 24, 18),
        "AST": (0, 40, 22, 16),
        "HGB": (120, 175, 142, 16),
        "eGFR": (60, 140, 86, 22),
    }
    for row in subjects.itertuples(index=False):
        factor = risk_factor[row.site_id]
        for test, (lln, uln, mean, sd) in tests.items():
            for visit_no in range(1, 4):
                result = rng.normal(mean, sd)
                if rng.random() < 0.025 * factor:
                    result = uln + abs(rng.normal(18, 12))
                out_of_range = result < lln or result > uln
                reviewed = not (out_of_range and rng.random() < min(0.60, 0.12 * factor))
                lab_rows.append(
                    {
                        "subject_id": row.subject_id,
                        "site_id": row.site_id,
                        "visit": f"V{visit_no}",
                        "test": test,
                        "result": round(float(result), 1),
                        "lln": lln,
                        "uln": uln,
                        "reviewed": "Yes" if reviewed else "No",
                        "collection_date": TODAY - pd.Timedelta(days=int(rng.integers(1, 180))),
                    }
                )
    labs = pd.DataFrame(lab_rows)

    deviation_rows = []
    for row in subjects.itertuples(index=False):
        factor = risk_factor[row.site_id]
        deviation_count = int(rng.poisson(0.12 * factor))
        for _ in range(deviation_count):
            deviation_rows.append(
                {
                    "subject_id": row.subject_id,
                    "site_id": row.site_id,
                    "deviation_type": rng.choice(["Visit Window", "Eligibility", "IP Compliance", "Procedure Missed"]),
                    "severity": rng.choice(["Minor", "Major", "Critical"], p=[0.62, 0.30, 0.08]),
                    "status": rng.choice(["Open", "Closed"], p=[0.42, 0.58]),
                    "deviation_date": TODAY - pd.Timedelta(days=int(rng.integers(3, 150))),
                }
            )
    deviations = pd.DataFrame(deviation_rows)

    dosing_rows = []
    for row in subjects.itertuples(index=False):
        factor = risk_factor[row.site_id]
        for cycle in range(1, 4):
            toxicity_modification = rng.random() < min(0.35, 0.035 * factor)
            dosing_rows.append(
                {
                    "subject_id": row.subject_id,
                    "site_id": row.site_id,
                    "cycle": cycle,
                    "dose_level": rng.choice(["DL1", "DL2", "DL3", "DL4"]),
                    "dose_modified": "Yes" if toxicity_modification else "No",
                    "modification_reason": "Toxicity" if toxicity_modification else "",
                    "administration_date": TODAY - pd.Timedelta(days=int(rng.integers(5, 120))),
                }
            )
    dosing = pd.DataFrame(dosing_rows)

    pk_rows = []
    for row in subjects.itertuples(index=False):
        factor = risk_factor[row.site_id]
        for timepoint in ["C1D1 pre-dose", "C1D1 2h", "C1D8"]:
            scheduled = TODAY - pd.Timedelta(days=int(rng.integers(5, 90)))
            deviated = rng.random() < min(0.32, 0.04 * factor)
            pk_rows.append(
                {
                    "subject_id": row.subject_id,
                    "site_id": row.site_id,
                    "timepoint": timepoint,
                    "scheduled_sample_time": scheduled,
                    "actual_sample_time": scheduled + pd.Timedelta(hours=int(rng.integers(0, 8) if deviated else rng.integers(0, 2))),
                    "window_deviation": "Yes" if deviated else "No",
                }
            )
    pk = pd.DataFrame(pk_rows)

    tumor_rows = []
    for row in subjects.itertuples(index=False):
        factor = risk_factor[row.site_id]
        for assessment_no in range(1, 3):
            scheduled = pd.Timestamp(row.randomized_date) + pd.Timedelta(days=56 * assessment_no)
            issue = rng.random() < min(0.30, 0.035 * factor)
            tumor_rows.append(
                {
                    "subject_id": row.subject_id,
                    "site_id": row.site_id,
                    "assessment": f"RECIST-{assessment_no}",
                    "scheduled_assessment_date": scheduled,
                    "actual_assessment_date": scheduled + pd.Timedelta(days=int(rng.integers(0, 25))) if not issue else pd.NaT,
                    "response": np.nan if issue else rng.choice(["CR", "PR", "SD", "PD"], p=[0.02, 0.18, 0.56, 0.24]),
                }
            )
    tumor = pd.DataFrame(tumor_rows)

    return {
        "subjects": standardize_columns(subjects),
        "visits": standardize_columns(visits_df),
        "queries": standardize_columns(queries),
        "ae": standardize_columns(ae),
        "dosing": standardize_columns(dosing),
        "pk": standardize_columns(pk),
        "tumor": standardize_columns(tumor),
        "labs": standardize_columns(labs),
        "deviations": standardize_columns(deviations),
    }


def enrich_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    enriched: dict[str, pd.DataFrame] = {}
    subject_to_site: dict[str, str] = {}

    subjects = tables.get("subjects", pd.DataFrame()).copy()
    if not subjects.empty:
        subject_col = find_col(subjects, SUBJECT_ALIASES)
        site_col = find_col(subjects, SITE_ALIASES)
        if subject_col:
            subjects["__subject_id"] = subjects[subject_col].astype(str)
        if site_col:
            subjects["__site_id"] = subjects[site_col].astype(str)
        elif "__subject_id" in subjects:
            subjects["__site_id"] = "Unknown"
        if "__subject_id" in subjects and "__site_id" in subjects:
            subject_to_site = dict(zip(subjects["__subject_id"], subjects["__site_id"]))
        enriched["subjects"] = subjects

    for domain, source in tables.items():
        if domain == "subjects":
            continue
        df = source.copy()
        subject_col = find_col(df, SUBJECT_ALIASES)
        site_col = find_col(df, SITE_ALIASES)
        if subject_col:
            df["__subject_id"] = df[subject_col].astype(str)
        if site_col:
            df["__site_id"] = df[site_col].astype(str)
        elif "__subject_id" in df and subject_to_site:
            df["__site_id"] = df["__subject_id"].map(subject_to_site).fillna("Unknown")
        else:
            df["__site_id"] = "Unknown"
        enriched[domain] = df
    return enriched


def available_sites(tables: dict[str, pd.DataFrame]) -> list[str]:
    sites: set[str] = set()
    for df in tables.values():
        if "__site_id" in df:
            sites.update(df["__site_id"].dropna().astype(str).unique().tolist())
    return sorted(sites) or ["Unknown"]


def count_subjects(subjects: pd.DataFrame, sites: list[str]) -> pd.Series:
    if subjects.empty or "__site_id" not in subjects:
        return pd.Series(0, index=sites, dtype="float64")
    if "__subject_id" in subjects:
        counts = subjects.groupby("__site_id")["__subject_id"].nunique()
    else:
        counts = subjects.groupby("__site_id").size()
    return counts.reindex(sites).fillna(0).astype(float)


def domain_missingness(df: pd.DataFrame) -> pd.Series:
    if df.empty or "__site_id" not in df:
        return pd.Series(dtype="float64")
    candidate_cols = [col for col in df.columns if not col.startswith("__")]
    if not candidate_cols:
        return pd.Series(dtype="float64")
    return df.groupby("__site_id")[candidate_cols].apply(lambda part: float(part.isna().mean().mean()))


def active_kri_metrics(thresholds: Thresholds) -> set[str]:
    if not thresholds.kri_enabled:
        return set()
    return {metric for metric in thresholds.enabled_metrics if metric in KRI_METRIC_KEYS}


def metric_component_score(values: pd.Series, threshold: float) -> pd.Series:
    if threshold <= 0:
        return pd.Series(0.0, index=values.index)
    return (values / threshold * 100).replace([np.inf, -np.inf], 0).fillna(0).clip(0, 100)


def compute_metrics(tables: dict[str, pd.DataFrame], thresholds: Thresholds) -> tuple[pd.DataFrame, pd.DataFrame]:
    sites = available_sites(tables)
    metrics = pd.DataFrame(index=sites)
    metrics.index.name = "site_id"
    metrics["subjects"] = count_subjects(tables.get("subjects", pd.DataFrame()), sites)

    missing_parts = []
    for df in tables.values():
        part = domain_missingness(df)
        if not part.empty:
            missing_parts.append(part.rename("missing_rate"))
    metrics["missing_rate"] = pd.concat(missing_parts, axis=1).mean(axis=1).reindex(sites).fillna(0) if missing_parts else 0.0

    visits = tables.get("visits", pd.DataFrame())
    metrics["late_entry_rate"] = 0.0
    metrics["avg_entry_delay_days"] = 0.0
    if not visits.empty and "__site_id" in visits:
        visit_date_col = find_col(visits, ["visit_date", "visit_dt", "assessment_date", "event_date", "访视日期", "检查日期", "事件日期"])
        entry_date_col = find_col(visits, ["data_entry_date", "entry_date", "entered_date", "form_entry_date", "created_date", "录入日期", "数据录入日期", "表单录入日期"])
        status_col = find_col(visits, ["form_status", "status", "visit_status", "completion_status", "表单状态", "访视状态", "完成状态"])
        visit_work = visits.copy()
        late_mask = pd.Series(False, index=visit_work.index)
        delay_days = pd.Series(np.nan, index=visit_work.index, dtype="float64")
        if visit_date_col and entry_date_col:
            delay_days = (datetime_series(visit_work[entry_date_col]) - datetime_series(visit_work[visit_date_col])).dt.days
            late_mask = delay_days > thresholds.avg_entry_delay_days
        if status_col:
            status_text = visit_work[status_col].astype(str).str.lower()
            late_mask = late_mask | status_text.str.contains("incomplete|missing|overdue|not done|pending|未完成|未录入|缺失|待录入|待完成", regex=True, na=False)
        metrics["late_entry_rate"] = late_mask.groupby(visit_work["__site_id"]).mean().reindex(sites).fillna(0)
        metrics["avg_entry_delay_days"] = delay_days.groupby(visit_work["__site_id"]).mean().reindex(sites).fillna(0).clip(lower=0)

    queries = tables.get("queries", pd.DataFrame())
    metrics["open_queries"] = 0.0
    metrics["open_queries_per_subject"] = 0.0
    metrics["avg_open_query_age_days"] = 0.0
    if not queries.empty and "__site_id" in queries:
        status_col = find_col(queries, ["query_status", "status", "query_state", "state", "查询状态", "处理状态"])
        age_col = find_col(queries, ["age_days", "query_age", "open_days", "days_open", "账期", "开放天数"])
        opened_col = find_col(queries, ["opened_date", "open_date", "created_date", "query_open_date", "开启日期", "打开日期"])
        closed_col = find_col(queries, ["closed_date", "resolved_date", "answered_date", "关闭日期", "解决日期", "回复日期"])
        query_work = queries.copy()
        if status_col:
            status_text = query_work[status_col].astype(str).str.lower()
            open_mask = ~status_text.str.contains("closed|resolved|cancelled|canceled|已关闭|关闭|已解决|已回复|已处理", regex=True, na=False)
        elif closed_col:
            open_mask = datetime_series(query_work[closed_col]).isna()
        else:
            open_mask = pd.Series(True, index=query_work.index)
        age_days = numeric_series(query_work[age_col]) if age_col else ((TODAY - datetime_series(query_work[opened_col])).dt.days if opened_col else pd.Series(0, index=query_work.index, dtype="float64"))
        open_queries = open_mask.groupby(query_work["__site_id"]).sum().reindex(sites).fillna(0).astype(float)
        metrics["open_queries"] = open_queries
        metrics["open_queries_per_subject"] = [safe_div(open_queries.loc[site], max(metrics.loc[site, "subjects"], 1)) for site in sites]
        metrics["avg_open_query_age_days"] = age_days.where(open_mask).groupby(query_work["__site_id"]).mean().reindex(sites).fillna(0).clip(lower=0)

    ae = tables.get("ae", pd.DataFrame())
    metrics["safety_issues"] = 0.0
    metrics["safety_issues_per_subject"] = 0.0
    metrics["dlt_events"] = 0.0
    metrics["dlt_rate"] = 0.0
    metrics["grade3_ae_events"] = 0.0
    metrics["grade3_ae_rate"] = 0.0
    if not ae.empty and "__site_id" in ae:
        serious_col = find_col(ae, ["serious", "seriousness", "sae", "is_serious", "严重", "是否严重", "严重性"])
        severity_col = find_col(ae, ["severity", "ae_severity", "grade", "严重程度", "等级"])
        dlt_col = find_col(ae, ["dlt", "dose_limiting_toxicity", "dose_limiting", "limiting_toxicity", "剂量限制性毒性"])
        grade_col = find_col(ae, ["ctcae_grade", "toxicity_grade", "ae_grade", "grade", "severity", "分级", "等级", "严重程度"])
        outcome_col = find_col(ae, ["outcome", "ae_outcome", "结局", "结果"])
        start_col = find_col(ae, ["start_date", "ae_start_date", "onset_date", "开始日期", "起始日期", "发生日期"])
        serious = truthy_series(ae[serious_col]) if serious_col else pd.Series(False, index=ae.index)
        missing_followup = pd.Series(False, index=ae.index)
        for col in [severity_col, outcome_col, start_col]:
            if col:
                missing_followup = missing_followup | ae[col].isna()
        safety_issues = (serious & missing_followup).groupby(ae["__site_id"]).sum().reindex(sites).fillna(0).astype(float)
        metrics["safety_issues"] = safety_issues
        metrics["safety_issues_per_subject"] = [safe_div(safety_issues.loc[site], max(metrics.loc[site, "subjects"], 1)) for site in sites]
        dlt_mask = truthy_series(ae[dlt_col]) if dlt_col else pd.Series(False, index=ae.index)
        grade3_mask = grade_series(ae[grade_col]).ge(3).fillna(False) if grade_col else pd.Series(False, index=ae.index)
        dlt_events = dlt_mask.groupby(ae["__site_id"]).sum().reindex(sites).fillna(0).astype(float)
        grade3_events = grade3_mask.groupby(ae["__site_id"]).sum().reindex(sites).fillna(0).astype(float)
        metrics["dlt_events"] = dlt_events
        metrics["dlt_rate"] = [safe_div(dlt_events.loc[site], max(metrics.loc[site, "subjects"], 1)) for site in sites]
        metrics["grade3_ae_events"] = grade3_events
        metrics["grade3_ae_rate"] = [safe_div(grade3_events.loc[site], max(metrics.loc[site, "subjects"], 1)) for site in sites]

    dosing = tables.get("dosing", pd.DataFrame())
    metrics["dose_modifications"] = 0.0
    metrics["dose_modification_rate"] = 0.0
    if not dosing.empty and "__site_id" in dosing:
        modified_col = find_col(dosing, ["dose_modified", "dose_modification", "modified", "action", "dose_action", "status", "剂量调整", "给药调整"])
        reason_col = find_col(dosing, ["modification_reason", "reason", "dose_change_reason", "toxicity_reason", "原因"])
        if modified_col:
            modified_text = dosing[modified_col].astype(str).str.lower()
            modified = truthy_series(dosing[modified_col]) | modified_text.str.contains("reduce|hold|interrupt|delay|discontinue|modified|reduced|withheld|减量|暂停|延迟|停药|中断|调整", regex=True, na=False)
        else:
            modified = pd.Series(False, index=dosing.index)
        if reason_col:
            reason_text = dosing[reason_col].astype(str).str.lower()
            toxicity_related = reason_text.str.contains("toxicity|ae|adverse|dlt|不良|毒性|安全", regex=True, na=False)
        else:
            toxicity_related = modified
        dose_modifications = (modified & toxicity_related).groupby(dosing["__site_id"]).sum().reindex(sites).fillna(0).astype(float)
        metrics["dose_modifications"] = dose_modifications
        metrics["dose_modification_rate"] = [safe_div(dose_modifications.loc[site], max(metrics.loc[site, "subjects"], 1)) for site in sites]

    labs = tables.get("labs", pd.DataFrame())
    metrics["lab_issues"] = 0.0
    metrics["lab_issues_per_subject"] = 0.0
    if not labs.empty and "__site_id" in labs:
        result_col = find_col(labs, ["result", "lab_result", "value", "aval", "结果", "数值"])
        lln_col = find_col(labs, ["lln", "lower_limit", "lower_limit_normal", "lblln", "下限", "正常下限"])
        uln_col = find_col(labs, ["uln", "upper_limit", "upper_limit_normal", "lbuln", "上限", "正常上限"])
        reviewed_col = find_col(labs, ["reviewed", "medical_review", "clinically_reviewed", "review_status", "已复核", "复核状态", "审核状态"])
        if result_col and (lln_col or uln_col):
            result = numeric_series(labs[result_col])
            lower = numeric_series(labs[lln_col]) if lln_col else pd.Series(-np.inf, index=labs.index)
            upper = numeric_series(labs[uln_col]) if uln_col else pd.Series(np.inf, index=labs.index)
            out_of_range = (result < lower) | (result > upper)
            if reviewed_col:
                reviewed_text = labs[reviewed_col].astype(str).str.lower()
                unreviewed = reviewed_text.isin(["no", "n", "false", "0", "open", "pending", "not reviewed", "否", "未复核", "待复核", "未审核", "未审阅"])
            else:
                unreviewed = pd.Series(False, index=labs.index)
            lab_issues = (out_of_range & unreviewed).groupby(labs["__site_id"]).sum().reindex(sites).fillna(0).astype(float)
            metrics["lab_issues"] = lab_issues
            metrics["lab_issues_per_subject"] = [safe_div(lab_issues.loc[site], max(metrics.loc[site, "subjects"], 1)) for site in sites]

    pk = tables.get("pk", pd.DataFrame())
    metrics["pk_window_deviations"] = 0.0
    metrics["pk_window_deviation_rate"] = 0.0
    if not pk.empty and "__site_id" in pk:
        deviation_col = find_col(pk, ["window_deviation", "sample_deviation", "deviation", "out_of_window", "missed", "采样窗偏离", "窗偏离", "漏采"])
        status_col = find_col(pk, ["status", "sample_status", "collection_status", "状态"])
        scheduled_col = find_col(pk, ["scheduled_sample_time", "scheduled_time", "scheduled_date", "计划采样时间", "计划时间"])
        actual_col = find_col(pk, ["actual_sample_time", "actual_time", "collection_time", "actual_date", "实际采样时间", "实际时间"])
        issue_mask = pd.Series(False, index=pk.index)
        if deviation_col:
            issue_mask = issue_mask | truthy_series(pk[deviation_col])
        if status_col:
            status_text = pk[status_col].astype(str).str.lower()
            issue_mask = issue_mask | status_text.str.contains("missed|not done|out of window|deviation|未采|漏采|偏离|超窗", regex=True, na=False)
        if scheduled_col and actual_col:
            delay_hours = (datetime_series(pk[actual_col]) - datetime_series(pk[scheduled_col])).dt.total_seconds().abs() / 3600
            issue_mask = issue_mask | delay_hours.gt(4).fillna(False)
        pk_issues = issue_mask.groupby(pk["__site_id"]).sum().reindex(sites).fillna(0).astype(float)
        pk_counts = pk.groupby("__site_id").size().reindex(sites).fillna(0).astype(float)
        metrics["pk_window_deviations"] = pk_issues
        metrics["pk_window_deviation_rate"] = [safe_div(pk_issues.loc[site], max(pk_counts.loc[site], 1)) for site in sites]

    tumor = tables.get("tumor", pd.DataFrame())
    metrics["tumor_assessment_issues"] = 0.0
    metrics["tumor_assessment_issue_rate"] = 0.0
    if not tumor.empty and "__site_id" in tumor:
        response_col = find_col(tumor, ["response", "recist_response", "overall_response", "result", "疗效", "评估结果"])
        status_col = find_col(tumor, ["status", "assessment_status", "状态"])
        scheduled_col = find_col(tumor, ["scheduled_assessment_date", "scheduled_date", "planned_date", "计划评估日期", "计划日期"])
        actual_col = find_col(tumor, ["actual_assessment_date", "assessment_date", "actual_date", "评估日期", "实际日期"])
        issue_mask = pd.Series(False, index=tumor.index)
        if response_col:
            issue_mask = issue_mask | tumor[response_col].isna()
        if status_col:
            status_text = tumor[status_col].astype(str).str.lower()
            issue_mask = issue_mask | status_text.str.contains("missing|not done|delayed|pending|overdue|缺失|未做|延迟|待评估|超窗", regex=True, na=False)
        if scheduled_col and actual_col:
            delay_days = (datetime_series(tumor[actual_col]) - datetime_series(tumor[scheduled_col])).dt.days
            issue_mask = issue_mask | delay_days.gt(14).fillna(False) | datetime_series(tumor[actual_col]).isna()
        tumor_issues = issue_mask.groupby(tumor["__site_id"]).sum().reindex(sites).fillna(0).astype(float)
        tumor_counts = tumor.groupby("__site_id").size().reindex(sites).fillna(0).astype(float)
        metrics["tumor_assessment_issues"] = tumor_issues
        metrics["tumor_assessment_issue_rate"] = [safe_div(tumor_issues.loc[site], max(tumor_counts.loc[site], 1)) for site in sites]

    deviations = tables.get("deviations", pd.DataFrame())
    metrics["major_deviations"] = 0.0
    metrics["major_deviations_per_subject"] = 0.0
    metrics["eligibility_deviations"] = 0.0
    metrics["eligibility_deviation_rate"] = 0.0
    if not deviations.empty and "__site_id" in deviations:
        severity_col = find_col(deviations, ["severity", "classification", "deviation_severity", "grade", "严重程度", "分级"])
        type_col = find_col(deviations, ["deviation_type", "type", "category", "classification", "偏离类型", "类别"])
        if severity_col:
            major_mask = deviations[severity_col].astype(str).str.lower().str.contains("major|critical|important|重大|严重|关键", regex=True, na=False)
        else:
            major_mask = pd.Series(True, index=deviations.index)
        major_devs = major_mask.groupby(deviations["__site_id"]).sum().reindex(sites).fillna(0).astype(float)
        metrics["major_deviations"] = major_devs
        metrics["major_deviations_per_subject"] = [safe_div(major_devs.loc[site], max(metrics.loc[site, "subjects"], 1)) for site in sites]
        if type_col:
            eligibility_mask = deviations[type_col].astype(str).str.lower().str.contains("eligibility|inclusion|exclusion|入选|排除|入排|资格", regex=True, na=False)
        else:
            eligibility_mask = pd.Series(False, index=deviations.index)
        eligibility_devs = eligibility_mask.groupby(deviations["__site_id"]).sum().reindex(sites).fillna(0).astype(float)
        metrics["eligibility_deviations"] = eligibility_devs
        metrics["eligibility_deviation_rate"] = [safe_div(eligibility_devs.loc[site], max(metrics.loc[site, "subjects"], 1)) for site in sites]

    enabled_metrics = active_kri_metrics(thresholds)
    component_defs = {
        "Dose Safety": {
            "weight": 0.25,
            "metrics": [
                ("dlt_rate", thresholds.dlt_rate),
                ("grade3_ae_rate", thresholds.grade3_ae_rate),
            ],
        },
        "Safety Review": {
            "weight": 0.15,
            "metrics": [("safety_issues_per_subject", thresholds.safety_issues_per_subject)],
        },
        "Dose Administration": {
            "weight": 0.10,
            "metrics": [("dose_modification_rate", thresholds.dose_modification_rate)],
        },
        "PK Integrity": {
            "weight": 0.10,
            "metrics": [("pk_window_deviation_rate", thresholds.pk_window_deviation_rate)],
        },
        "Tumor Assessment": {
            "weight": 0.10,
            "metrics": [("tumor_assessment_issue_rate", thresholds.tumor_assessment_issue_rate)],
        },
        "Protocol Compliance": {
            "weight": 0.10,
            "metrics": [
                ("eligibility_deviation_rate", thresholds.eligibility_deviation_rate),
                ("major_deviations_per_subject", thresholds.major_deviations_per_subject),
            ],
        },
        "Data Quality": {
            "weight": 0.20,
            "metrics": [
                ("missing_rate", thresholds.missing_rate),
                ("late_entry_rate", thresholds.late_entry_rate),
                ("avg_entry_delay_days", thresholds.avg_entry_delay_days),
                ("open_queries_per_subject", thresholds.open_queries_per_subject),
                ("avg_open_query_age_days", thresholds.avg_open_query_age_days),
            ],
        },
        "Labs and PD": {
            "weight": 0.05,
            "metrics": [
                ("lab_issues_per_subject", thresholds.lab_issues_per_subject),
            ],
        },
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
    signals = build_signals(metrics, thresholds)
    return metrics, signals

def build_signals(metrics: pd.DataFrame, thresholds: Thresholds) -> pd.DataFrame:
    enabled_metrics = active_kri_metrics(thresholds)
    signal_defs = [
        ("DLT发生率过高", "dlt_rate", thresholds.dlt_rate, "剂量安全"),
        ("≥3级AE发生率过高", "grade3_ae_rate", thresholds.grade3_ae_rate, "剂量安全"),
        ("毒性相关剂量调整过多", "dose_modification_rate", thresholds.dose_modification_rate, "给药/剂量"),
        ("入排标准偏离", "eligibility_deviation_rate", thresholds.eligibility_deviation_rate, "方案依从性"),
        ("PK/PD采样窗偏离", "pk_window_deviation_rate", thresholds.pk_window_deviation_rate, "PK/PD"),
        ("肿瘤评估缺失或延迟", "tumor_assessment_issue_rate", thresholds.tumor_assessment_issue_rate, "疗效评估"),
        ("缺失数据", "missing_rate", thresholds.missing_rate, "完整性"),
        ("EDC录入延迟", "late_entry_rate", thresholds.late_entry_rate, "及时性"),
        ("录入延迟过长", "avg_entry_delay_days", thresholds.avg_entry_delay_days, "及时性"),
        ("未关闭Query负荷", "open_queries_per_subject", thresholds.open_queries_per_subject, "Query负荷"),
        ("长期未关闭Query", "avg_open_query_age_days", thresholds.avg_open_query_age_days, "Query负荷"),
        ("SAE随访缺口", "safety_issues_per_subject", thresholds.safety_issues_per_subject, "安全性"),
        ("未复核异常实验室", "lab_issues_per_subject", thresholds.lab_issues_per_subject, "实验室"),
        ("重大方案偏离", "major_deviations_per_subject", thresholds.major_deviations_per_subject, "方案偏离"),
    ]
    rows: list[dict[str, Any]] = []
    for _, row in metrics.iterrows():
        for signal_name, metric_name, threshold, category in signal_defs:
            if metric_name not in enabled_metrics:
                continue
            value = float(row.get(metric_name, 0) or 0)
            if value > threshold:
                ratio = value / threshold if threshold else 0
                rows.append({"signal_id": f"{row['site_id']}-{metric_name}", "site_id": row["site_id"], "category": category, "signal": signal_name, "metric": METRIC_VALUE_LABELS.get(metric_name, metric_name), "value": round(value, 3), "threshold": threshold, "severity": "高" if ratio >= 1.5 else "中", "risk_score": row["risk_score"], "recommended_action": recommended_action(signal_name)})
    if not rows:
        return pd.DataFrame()
    signals = pd.DataFrame(rows)
    signals["__severity_order"] = signals["severity"].map({"高": 0, "中": 1}).fillna(2)
    signals = signals.sort_values(["__severity_order", "risk_score"], ascending=[True, False]).drop(columns="__severity_order")
    return signals


def recommended_action(signal_name: str) -> str:
    actions = {
        "DLT发生率过高": "立即复核DLT判定、剂量递增会议资料和是否触发暂停或降阶规则。",
        "≥3级AE发生率过高": "核对CTCAE分级、相关性和医学复核，评估是否需要升级安全性讨论。",
        "毒性相关剂量调整过多": "复核给药记录、减量/暂停原因及同剂量组趋势。",
        "入排标准偏离": "确认入排标准执行、筛选资料和医学监查确认记录。",
        "PK/PD采样窗偏离": "复核采样计划、实际采样时间和样本可用性，评估对剂量决策的影响。",
        "肿瘤评估缺失或延迟": "确认RECIST评估窗口、影像上传和疗效评估结论是否及时完整。",
        "缺失数据": "确认关键字段缺失并要求中心或供应商制定纠正计划。",
        "EDC录入延迟": "请CRA/中心复核录入积压并明确完成时限。",
        "录入延迟过长": "确认录入延迟是否影响终点或安全性复核时效。",
        "未关闭Query负荷": "优先处理关键数据及超龄Query。",
        "长期未关闭Query": "在研究团队会议中升级尚未关闭的超龄Query。",
        "SAE随访缺口": "立即与安全性负责人核对SAE随访字段。",
        "未复核异常实验室": "确认异常实验室结果是否已完成医学复核。",
        "重大方案偏离": "评估该偏离对受试者安全和终点可靠性的影响。",
    }
    return actions.get(signal_name, "复核该信号并记录行动计划。")

def display_frame(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    return df.rename(columns=mapping).copy()


def export_localized_frame(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    return display_frame(df, mapping)


def make_excel_export(metrics: pd.DataFrame, signals: pd.DataFrame, action_log: pd.DataFrame, tables: dict[str, pd.DataFrame]) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export_localized_frame(metrics, METRIC_LABELS).to_excel(writer, sheet_name="中心风险排名", index=False)
        export_localized_frame(signals, SIGNAL_LABELS).to_excel(writer, sheet_name="风险信号", index=False)
        export_localized_frame(action_log, ACTION_LOG_LABELS).to_excel(writer, sheet_name="行动跟踪", index=False)
        summary = pd.DataFrame(
            [
                {"数据域": DOMAIN_LABELS.get(domain, domain), "行数": len(df), "列数": len(df.columns)}
                for domain, df in tables.items()
            ]
        )
        summary.to_excel(writer, sheet_name="数据摘要", index=False)
    return output.getvalue()
