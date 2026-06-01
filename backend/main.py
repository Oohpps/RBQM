from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from pydantic import BaseModel, Field
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from rbqm.config import (
    ACTION_LOG_LABELS,
    DOMAIN_FIELDS,
    DOMAIN_LABELS,
    METRIC_LABELS,
    SIGNAL_LABELS,
)
from rbqm.enrichment import enrich_tables
from rbqm.export import make_kri_detail_export
from rbqm.ingestion import normalize_source_roles, preview_uploaded_files, read_uploaded_files
from rbqm.metrics import compute_metrics, leading_number_series, text_contains
from rbqm.models import (
    KRI_METRIC_KEYS,
    Thresholds,
)
from rbqm.settings_store import KriConfigStore, threshold_values
from rbqm.utils import datetime_series, find_col, numeric_series, standardize_columns


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
CONFIG_STORE = KriConfigStore(ROOT / "data" / "config")

DEFAULT_THRESHOLDS = Thresholds(
    edc_visit_entry_delay_days=7.0,
    page_missing_days_all=7.0,
    page_missing_days_without_lab=7.0,
    avg_open_query_age_days=21.0,
    page_sdv_pending_rate=7.0,
    logline_sdv_pending_rate=7.0,
    manual_query_reissue_rate=0.10,
)


def parse_enabled_metrics(value: str | None) -> tuple[str, ...]:
    if value is None:
        return KRI_METRIC_KEYS
    return tuple(metric for metric in value.split(",") if metric in KRI_METRIC_KEYS)


def direct_query_default(value: Any) -> Any:
    if hasattr(value, "default"):
        return value.default
    return value


class KriConfigInput(BaseModel):
    kri_enabled: bool = True
    enabled_metrics: list[str] = Field(default_factory=lambda: list(KRI_METRIC_KEYS))
    thresholds: dict[str, float]
    saved_by: str | None = None
    change_reason: str | None = None

app = FastAPI(title="RBQM API")
APP_SESSION_ID = uuid4().hex

current_tables: dict[str, pd.DataFrame] = {}
current_raw_tables: dict[str, pd.DataFrame] = {}
current_source_roles: dict[str, str] = {}
using_demo_data = False


class MemoryUpload(BytesIO):
    def __init__(self, name: str, payload: bytes) -> None:
        super().__init__(payload)
        self.name = name


def clear_uploaded_state() -> None:
    global current_tables, current_raw_tables, current_source_roles, using_demo_data
    current_tables = {}
    current_raw_tables = {}
    current_source_roles = {}
    using_demo_data = False


def thresholds_from_query(
    kri_enabled: bool | None = Query(None),
    enabled_metrics: str | None = Query(None),
    edc_visit_entry_delay_days: float | None = Query(None, ge=0.0, le=90.0),
    page_missing_days_all: float | None = Query(None, ge=1.0, le=90.0),
    page_missing_days_without_lab: float | None = Query(None, ge=1.0, le=90.0),
    avg_open_query_age_days: float | None = Query(None, ge=1.0, le=90.0),
    page_sdv_pending_rate: float | None = Query(None, ge=1.0, le=90.0),
    logline_sdv_pending_rate: float | None = Query(None, ge=1.0, le=90.0),
    manual_query_reissue_rate: float | None = Query(None, ge=0.01, le=1.00),
) -> Thresholds:
    kri_enabled = direct_query_default(kri_enabled)
    enabled_metrics = direct_query_default(enabled_metrics)
    edc_visit_entry_delay_days = direct_query_default(edc_visit_entry_delay_days)
    page_missing_days_all = direct_query_default(page_missing_days_all)
    page_missing_days_without_lab = direct_query_default(page_missing_days_without_lab)
    avg_open_query_age_days = direct_query_default(avg_open_query_age_days)
    page_sdv_pending_rate = direct_query_default(page_sdv_pending_rate)
    logline_sdv_pending_rate = direct_query_default(logline_sdv_pending_rate)
    manual_query_reissue_rate = direct_query_default(manual_query_reissue_rate)
    active = CONFIG_STORE.active_thresholds(DEFAULT_THRESHOLDS)
    return Thresholds(
        edc_visit_entry_delay_days=edc_visit_entry_delay_days if edc_visit_entry_delay_days is not None else active.edc_visit_entry_delay_days,
        page_missing_days_all=page_missing_days_all if page_missing_days_all is not None else active.page_missing_days_all,
        page_missing_days_without_lab=page_missing_days_without_lab if page_missing_days_without_lab is not None else active.page_missing_days_without_lab,
        avg_open_query_age_days=avg_open_query_age_days if avg_open_query_age_days is not None else active.avg_open_query_age_days,
        page_sdv_pending_rate=page_sdv_pending_rate if page_sdv_pending_rate is not None else active.page_sdv_pending_rate,
        logline_sdv_pending_rate=logline_sdv_pending_rate if logline_sdv_pending_rate is not None else active.logline_sdv_pending_rate,
        manual_query_reissue_rate=manual_query_reissue_rate if manual_query_reissue_rate is not None else active.manual_query_reissue_rate,
        kri_enabled=kri_enabled if kri_enabled is not None else active.kri_enabled,
        enabled_metrics=parse_enabled_metrics(enabled_metrics) if enabled_metrics is not None else active.enabled_metrics,
    )


def thresholds_from_config_input(config: KriConfigInput) -> Thresholds:
    defaults = threshold_values(DEFAULT_THRESHOLDS)
    values = {key: float(config.thresholds.get(key, defaults[key])) for key in KRI_METRIC_KEYS}
    enabled_metrics = tuple(metric for metric in config.enabled_metrics if metric in KRI_METRIC_KEYS)
    return Thresholds(**values, kri_enabled=config.kri_enabled, enabled_metrics=enabled_metrics)


def bool_zh(value: bool) -> str:
    return "是" if value else "否"


def clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def clean_identifier(value: Any) -> str:
    cleaned = clean_value(value)
    if cleaned is None:
        return ""
    if isinstance(cleaned, float) and cleaned.is_integer():
        return str(int(cleaned))
    text = str(cleaned)
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def clean_site_identifier(value: Any) -> str:
    text = clean_identifier(value)
    return text.zfill(3) if text.isdigit() else text


def first_clean_row_value(row: pd.Series, columns: list[str | None]) -> Any:
    for column in columns:
        if column and column in row.index:
            value = clean_value(row.get(column))
            if value not in (None, ""):
                return value
    return ""


def subject_status_values(subjects: pd.DataFrame) -> pd.Series | None:
    columns = [find_col(subjects, [alias]) for alias in ["subject_status", "受试者状态", "status", "状态"]]
    columns = [column for column in columns if column and column in subjects.columns]
    if not columns:
        return None
    return subjects[columns].bfill(axis=1).iloc[:, 0].fillna("未知").astype(str)


def records(df: pd.DataFrame, columns: list[str] | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    frame = df if columns is None else df[[col for col in columns if col in df.columns]]
    if limit is not None:
        frame = frame.head(limit)
    return [{key: clean_value(value) for key, value in row.items()} for row in frame.to_dict(orient="records")]


def action_log_from_signals(signals: pd.DataFrame) -> pd.DataFrame:
    columns = ["signal_id", "site_id", "signal", "severity", "owner", "action", "due_date", "status", "resolution_comment"]
    if signals.empty:
        return pd.DataFrame(columns=columns)
    log = signals[["signal_id", "site_id", "signal", "severity", "recommended_action"]].copy()
    log = log.rename(columns={"recommended_action": "action"})
    log["owner"] = ""
    log["due_date"] = ""
    log["status"] = "未开始"
    log["resolution_comment"] = ""
    return log[columns]


def subject_status_summary(tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    subjects = tables.get("subjects", pd.DataFrame())
    if subjects.empty:
        return []
    status_values = subject_status_values(subjects)
    if status_values is None:
        return []
    total_col = find_col(subjects, ["total", "count", "n", "合计", "受试者数"])
    if "__subject_id" in subjects and subjects["__subject_id"].notna().any():
        detail = subjects[subjects["__subject_id"].notna() & subjects["__subject_id"].astype(str).str.strip().ne("")]
        grouped = (
            detail.assign(status=status_values.loc[detail.index])
            .groupby("status")["__subject_id"]
            .nunique()
            .reset_index(name="count")
        )
    elif total_col:
        work = pd.DataFrame({
            "status": status_values,
            "count": numeric_series(subjects[total_col]).fillna(0),
        })
        grouped = work.groupby("status", as_index=False)["count"].sum()
    else:
        grouped = subjects.assign(status=status_values).groupby("status").size().reset_index(name="count")
    total = float(grouped["count"].sum() or 0)
    grouped = grouped.sort_values("count", ascending=False)
    rows = []
    for row in grouped.to_dict(orient="records"):
        count = float(row["count"] or 0)
        rows.append({
            "受试者状态": row["status"],
            "受试者数": int(count),
            "占比": round(count / total * 100, 1) if total else 0,
        })
    return rows


def subject_status_by_site(tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    subjects = tables.get("subjects", pd.DataFrame())
    if subjects.empty or "__site_id" not in subjects:
        return []
    status_values = subject_status_values(subjects)
    if status_values is None:
        return []
    total_col = find_col(subjects, ["total", "count", "n", "合计", "受试者数"])
    if "__subject_id" in subjects and subjects["__subject_id"].notna().any():
        detail = subjects[subjects["__subject_id"].notna() & subjects["__subject_id"].astype(str).str.strip().ne("")]
        work = detail.assign(
            site=detail["__site_id"].map(clean_site_identifier),
            status=status_values.loc[detail.index],
            subject=detail["__subject_id"].map(clean_identifier),
        )
        grouped = work.groupby(["site", "status"]).agg(
            count=("subject", "nunique"),
            subjects=("subject", lambda values: sorted({value for value in values if value})),
        ).reset_index()
    elif total_col:
        work = pd.DataFrame({
            "site": subjects["__site_id"].map(clean_site_identifier),
            "status": status_values,
            "count": numeric_series(subjects[total_col]).fillna(0),
            "subject": "",
        })
        grouped = work.groupby(["site", "status"], as_index=False)["count"].sum()
        grouped["subjects"] = [[] for _ in range(len(grouped))]
    else:
        grouped = subjects.assign(site=subjects["__site_id"].map(clean_site_identifier), status=status_values).groupby(["site", "status"]).size().reset_index(name="count")
        grouped["subjects"] = [[] for _ in range(len(grouped))]
    return [
        {
            "中心": row["site"],
            "受试者状态": row["status"],
            "受试者数": int(float(row["count"] or 0)),
            "受试者号列表": row.get("subjects", []),
        }
        for row in grouped.sort_values(["site", "status"]).to_dict(orient="records")
    ]


def raw_label_matches(label: str, tokens: list[str]) -> bool:
    value = label.lower()
    return any(token.lower() in value for token in tokens)


def medical_value_records(raw_tables: dict[str, pd.DataFrame], metric: str) -> list[dict[str, Any]]:
    if metric == "hba1c":
        sheet_tokens = ["lb_hba1c", "hba1c", "糖化血红蛋白"]
        date_aliases = ["采样日期(LBDAT)", "采样日期", "lbdat", "sample_date", "date"]
        value_aliases = ["结果", "result", "value", "aval", "糖化血红蛋白"]
        unit_aliases = ["单位", "unit"]
        page_name = "LB_HBA1C"
        label = "糖化血红蛋白"
    else:
        sheet_tokens = ["vs_w", "weight", "体重", "空腹体重"]
        date_aliases = ["测量日期(VSDAT)", "测量日期", "vsdat", "measurement_date", "date"]
        value_aliases = ["体重(WEIGHT)", "体重", "weight"]
        unit_aliases = ["体重单位(WEIGHTU)", "体重单位", "weightu", "unit"]
        page_name = "VS_W"
        label = "体重"
    rows: list[dict[str, Any]] = []
    for source_label, df in raw_tables.items():
        if df.empty or not raw_label_matches(source_label, sheet_tokens):
            continue
        work = standardize_columns(df)
        subject_col = find_col(work, ["参与者筛选号", "受试者编号", "subject_id", "subject", "participant"])
        site_col = find_col(work, ["试验中心编号", "中心编号", "site_id", "site"])
        site_name_col = find_col(work, ["试验中心名称", "中心名称", "site_name"])
        status_col = find_col(work, ["受试者状态", "subject_status", "status"])
        visit_col = find_col(work, ["数据节", "访视名称", "visit_name", "visit"])
        date_col = find_col(work, date_aliases)
        value_col = find_col(work, value_aliases)
        unit_col = find_col(work, unit_aliases)
        assessment_col = find_col(work, ["临床评估", "临床意义", "clinical_assessment", "clinical_significance"])
        if not subject_col or not value_col:
            continue
        dates = datetime_series(work[date_col]) if date_col else pd.Series(pd.NaT, index=work.index)
        values = numeric_series(work[value_col])
        for index, row in work.iterrows():
            value = values.loc[index]
            if pd.isna(value):
                continue
            measured_at = dates.loc[index] if index in dates.index else pd.NaT
            rows.append({
                "subject_id": clean_identifier(row.get(subject_col)),
                "site_id": clean_site_identifier(row.get(site_col)) if site_col else "",
                "site_name": clean_value(row.get(site_name_col)) if site_name_col else "",
                "subject_status": clean_value(row.get(status_col)) if status_col else "",
                "visit": clean_value(row.get(visit_col)) if visit_col else "",
                "date": measured_at.date().isoformat() if pd.notna(measured_at) else "",
                "day": int((measured_at.normalize() - pd.Timestamp("1970-01-01")).days) if pd.notna(measured_at) else 0,
                "metric": metric,
                "label": label,
                "page": page_name,
                "value": round(float(value), 3),
                "unit": clean_value(row.get(unit_col)) if unit_col else ("%" if metric == "hba1c" else "kg"),
                "assessment": clean_value(row.get(assessment_col)) if assessment_col else "",
            })
    return rows


def mean_or_zero(values: list[float]) -> float:
    return float(pd.Series(values, dtype="float64").mean()) if values else 0.0


def is_screen_failure_status(value: Any) -> bool:
    text = str(clean_value(value) or "").strip().lower().replace("_", " ").replace("-", " ")
    return any(token in text for token in ["筛选失败", "筛败", "screen fail", "screening fail"])


def formexcel_subject_statuses(raw_tables: dict[str, pd.DataFrame]) -> dict[str, dict[str, str]]:
    subjects: dict[str, dict[str, str]] = {}
    for df in raw_tables.values():
        if df.empty:
            continue
        work = standardize_columns(df)
        subject_col = find_col(work, ["参与者筛选号", "受试者编号", "subject_id", "subject", "participant"])
        site_col = find_col(work, ["试验中心编号", "中心编号", "site_id", "site"])
        status_col = find_col(work, ["受试者状态", "subject_status", "status", "状态"])
        if not subject_col or not status_col:
            continue
        for _, row in work.iterrows():
            subject = clean_identifier(row.get(subject_col))
            if not subject:
                continue
            site = clean_site_identifier(row.get(site_col)) if site_col else ""
            status = str(clean_value(row.get(status_col)) or "")
            current = subjects.setdefault(subject, {"site_id": site, "subject_status": status})
            if not current.get("site_id") and site:
                current["site_id"] = site
            if status and (not current.get("subject_status") or is_screen_failure_status(status)):
                current["subject_status"] = status
    return subjects


def blinded_efficacy_review(records: list[dict[str, Any]], subject_statuses: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    subject_statuses = dict(subject_statuses or {})
    for row in records:
        subject = str(row.get("subject_id") or "")
        if not subject:
            continue
        current = subject_statuses.setdefault(subject, {"site_id": str(row.get("site_id") or ""), "subject_status": str(row.get("subject_status") or "")})
        if not current.get("site_id") and row.get("site_id"):
            current["site_id"] = str(row["site_id"])
        if not current.get("subject_status") and row.get("subject_status"):
            current["subject_status"] = str(row["subject_status"])

    screen_failure_rows: list[dict[str, Any]] = []
    status_sites = sorted({str(item.get("site_id") or "") for item in subject_statuses.values() if item.get("site_id")})
    for site in status_sites:
        screened = [item for item in subject_statuses.values() if str(item.get("site_id") or "") == site]
        failed = [item for item in screened if is_screen_failure_status(item.get("subject_status"))]
        screen_failure_rows.append({
            "中心": site,
            "已筛选人数": len(screened),
            "筛选失败人数": len(failed),
            "中心筛败率（%）": round(len(failed) / len(screened) * 100, 2) if screened else 0.0,
        })
    screen_failure_rows.sort(key=lambda row: (-float(row["中心筛败率（%）"]), str(row["中心"])))

    by_subject_metric: dict[tuple[str, str], list[dict[str, Any]]] = {}
    subject_sites: dict[str, str] = {}
    for row in records:
        subject = str(row.get("subject_id") or "")
        metric = str(row.get("metric") or "")
        site = str(row.get("site_id") or "")
        if not subject or metric not in {"hba1c", "weight"} or is_screen_failure_status(subject_statuses.get(subject, {}).get("subject_status")):
            continue
        subject_sites.setdefault(subject, site)
        by_subject_metric.setdefault((subject, metric), []).append(row)

    subject_changes: dict[str, dict[str, float | str]] = {}
    for subject, site in subject_sites.items():
        changes: dict[str, float | str] = {"site_id": site}
        for metric in ("hba1c", "weight"):
            metric_records = sorted(
                by_subject_metric.get((subject, metric), []),
                key=lambda row: (int(row.get("day") or 0), str(row.get("date") or ""), str(row.get("visit") or "")),
            )
            if len(metric_records) < 2:
                continue
            baseline = float(metric_records[0]["value"])
            latest = float(metric_records[-1]["value"])
            if metric == "hba1c":
                changes["hba1c_drop_points"] = baseline - latest
                changes["hba1c_drop_pct"] = ((baseline - latest) / baseline * 100) if baseline else 0.0
            else:
                changes["weight_drop_kg"] = baseline - latest
        subject_changes[subject] = changes

    site_rows: list[dict[str, Any]] = []
    sites = sorted({site for site in subject_sites.values() if site})
    for site in sites:
        site_subjects = [subject for subject, subject_site in subject_sites.items() if subject_site == site]
        changes = [subject_changes.get(subject, {}) for subject in site_subjects]
        hba1c_points = [float(item["hba1c_drop_points"]) for item in changes if "hba1c_drop_points" in item]
        hba1c_pct = [float(item["hba1c_drop_pct"]) for item in changes if "hba1c_drop_pct" in item]
        weight_kg = [float(item["weight_drop_kg"]) for item in changes if "weight_drop_kg" in item]
        fully_evaluable = sum("hba1c_drop_pct" in item and "weight_drop_kg" in item for item in changes)
        incomplete_rate = 1 - (fully_evaluable / len(site_subjects)) if site_subjects else 0.0
        site_rows.append({
            "中心": site,
            "受试者数": len(site_subjects),
            "HbA1c可评估人数": len(hba1c_pct),
            "HbA1c平均下降值（百分点）": round(mean_or_zero(hba1c_points), 3),
            "HbA1c平均下降比例（%）": round(mean_or_zero(hba1c_pct), 2),
            "体重可评估人数": len(weight_kg),
            "体重平均下降值（kg）": round(mean_or_zero(weight_kg), 3),
            "配对数据不完整率（%）": round(incomplete_rate * 100, 2),
        })

    def project_values(key: str, evaluable_key: str) -> list[float]:
        return [float(row[key]) for row in site_rows if int(row[evaluable_key]) >= 3]

    hba1c_values = project_values("HbA1c平均下降比例（%）", "HbA1c可评估人数")
    weight_values = project_values("体重平均下降值（kg）", "体重可评估人数")
    hba1c_mean, hba1c_std = mean_or_zero(hba1c_values), float(pd.Series(hba1c_values, dtype="float64").std(ddof=0)) if hba1c_values else 0.0
    weight_mean, weight_std = mean_or_zero(weight_values), float(pd.Series(weight_values, dtype="float64").std(ddof=0)) if weight_values else 0.0

    def deviation_score(value: float, mean: float, std: float) -> float:
        return min(abs(value - mean) / std / 2 * 100, 100) if std > 0 else 0.0

    subject_hba1c_values = [float(item["hba1c_drop_pct"]) for item in subject_changes.values() if "hba1c_drop_pct" in item]
    subject_weight_values = [float(item["weight_drop_kg"]) for item in subject_changes.values() if "weight_drop_kg" in item]
    subject_hba1c_mean = mean_or_zero(subject_hba1c_values)
    subject_weight_mean = mean_or_zero(subject_weight_values)
    subject_hba1c_std = float(pd.Series(subject_hba1c_values, dtype="float64").std(ddof=0)) if subject_hba1c_values else 0.0
    subject_weight_std = float(pd.Series(subject_weight_values, dtype="float64").std(ddof=0)) if subject_weight_values else 0.0
    subject_rows: list[dict[str, Any]] = []
    for subject, changes in subject_changes.items():
        has_hba1c = "hba1c_drop_pct" in changes
        has_weight = "weight_drop_kg" in changes
        hba1c_score = deviation_score(float(changes["hba1c_drop_pct"]), subject_hba1c_mean, subject_hba1c_std) if has_hba1c else 100.0
        weight_score = deviation_score(float(changes["weight_drop_kg"]), subject_weight_mean, subject_weight_std) if has_weight else 100.0
        incomplete_score = 0.0 if has_hba1c and has_weight else 100.0
        influence_score = round(0.45 * hba1c_score + 0.35 * weight_score + 0.20 * incomplete_score, 1)
        if influence_score >= 70:
            influence_level = "高"
        elif influence_score >= 40:
            influence_level = "中"
        else:
            influence_level = "低"
        reasons: list[str] = []
        if not has_hba1c:
            reasons.append("缺少可配对HbA1c随访")
        elif hba1c_score >= 50:
            reasons.append("HbA1c下降比例偏离项目患者分布")
        if not has_weight:
            reasons.append("缺少可配对体重随访")
        elif weight_score >= 50:
            reasons.append("体重下降值偏离项目患者分布")
        subject_rows.append({
            "中心": changes["site_id"],
            "受试者": subject,
            "HbA1c下降值（百分点）": round(float(changes["hba1c_drop_points"]), 3) if "hba1c_drop_points" in changes else None,
            "HbA1c下降比例（%）": round(float(changes["hba1c_drop_pct"]), 2) if has_hba1c else None,
            "体重下降值（kg）": round(float(changes["weight_drop_kg"]), 3) if has_weight else None,
            "患者影响评分": influence_score,
            "影响等级": influence_level,
            "影响原因": "；".join(reasons) if reasons else "未见明显异常",
        })
    subject_rows.sort(key=lambda row: (str(row["中心"]), -float(row["患者影响评分"]), str(row["受试者"])))

    for row in site_rows:
        enough_hba1c = int(row["HbA1c可评估人数"]) >= 3
        enough_weight = int(row["体重可评估人数"]) >= 3
        hba1c_score = deviation_score(float(row["HbA1c平均下降比例（%）"]), hba1c_mean, hba1c_std) if enough_hba1c else 0.0
        weight_score = deviation_score(float(row["体重平均下降值（kg）"]), weight_mean, weight_std) if enough_weight else 0.0
        incomplete_score = min(float(row["配对数据不完整率（%）"]), 100.0)
        risk_score = round(0.4 * hba1c_score + 0.3 * weight_score + 0.3 * incomplete_score, 1)
        if int(row["受试者数"]) < 3:
            risk_level = "观察"
        elif risk_score >= 70:
            risk_level = "高"
        elif risk_score >= 40:
            risk_level = "中"
        else:
            risk_level = "低"
        reasons: list[str] = []
        if int(row["受试者数"]) < 3:
            reasons.append("样本量不足")
        if hba1c_score >= 50:
            reasons.append("HbA1c下降比例偏离项目整体")
        if weight_score >= 50:
            reasons.append("体重下降值偏离项目整体")
        if incomplete_score >= 20:
            reasons.append("配对随访数据不完整")
        row["盲态疗效异常风险评分"] = risk_score
        row["HbA1c异常评分"] = round(hba1c_score, 1)
        row["体重异常评分"] = round(weight_score, 1)
        row["数据不完整评分"] = round(incomplete_score, 1)
        row["风险等级"] = risk_level
        row["风险原因"] = "；".join(reasons) if reasons else "未见明显异常"

    site_rows.sort(key=lambda row: (-float(row["盲态疗效异常风险评分"]), str(row["中心"])))
    project_summary = [
        {"指标": "中心数", "数值": len(site_rows)},
        {"指标": "HbA1c中心平均下降比例（%）", "数值": round(hba1c_mean, 2)},
        {"指标": "体重中心平均下降值（kg）", "数值": round(weight_mean, 3)},
        {"指标": "高风险中心数", "数值": sum(row["风险等级"] == "高" for row in site_rows)},
    ]
    return {"site_summary": site_rows, "project_summary": project_summary, "subject_summary": subject_rows, "screen_failure_summary": screen_failure_rows}


def patient_medical_review(raw_tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    subject_statuses = formexcel_subject_statuses(raw_tables)
    records = medical_value_records(raw_tables, "hba1c") + medical_value_records(raw_tables, "weight")
    records = [
        row for row in records
        if row["subject_id"] and not is_screen_failure_status(subject_statuses.get(str(row["subject_id"]), {}).get("subject_status", row.get("subject_status")))
    ]
    records.sort(key=lambda row: (row["subject_id"], row["metric"], row["date"], row["visit"]))
    first_by_subject: dict[str, dict[str, Any]] = {}
    for row in records:
        subject = row["subject_id"]
        if subject not in first_by_subject:
            first_by_subject[subject] = {
                "subject_id": subject,
                "site_id": row["site_id"],
                "site_name": row["site_name"],
                "subject_status": row["subject_status"],
                "hba1c_count": 0,
                "weight_count": 0,
            }
        if row["metric"] == "hba1c":
            first_by_subject[subject]["hba1c_count"] += 1
        elif row["metric"] == "weight":
            first_by_subject[subject]["weight_count"] += 1
        for key in ["site_id", "site_name", "subject_status"]:
            if not first_by_subject[subject].get(key) and row.get(key):
                first_by_subject[subject][key] = row[key]
    subjects = sorted(
        first_by_subject.values(),
        key=lambda item: (
            not (int(item.get("hba1c_count") or 0) and int(item.get("weight_count") or 0)),
            -(int(item.get("hba1c_count") or 0) + int(item.get("weight_count") or 0)),
            str(item.get("site_id") or ""),
            str(item.get("subject_id") or ""),
        ),
    )
    return {"subjects": subjects, "records": records, **blinded_efficacy_review(records, subject_statuses)}


def is_yes_value(value: Any) -> bool:
    text = str(clean_value(value) or "").strip().lower()
    return text in {"是", "有", "yes", "y", "true", "1", "serious", "sae"}


def ae_event_review(raw_tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for source_label, df in raw_tables.items():
        sheet_name = source_label.rsplit("::", 1)[-1].strip().lower()
        if df.empty or sheet_name != "ae":
            continue
        work = standardize_columns(df)
        term_col = find_col(work, ["不良事件名称(AETERM)", "不良事件名称", "aeterm", "ae_term", "term"])
        ae_yn_col = find_col(work, ["是否存在PTE/不良事件？(AEYN)", "是否存在PTE/不良事件", "aeyn"])
        if not term_col:
            continue
        subject_col = find_col(work, ["参与者筛选号", "受试者编号", "subject_id"])
        site_col = find_col(work, ["试验中心编号", "中心编号", "site_id"])
        site_name_col = find_col(work, ["试验中心名称", "中心名称", "site_name"])
        status_col = find_col(work, ["受试者状态", "subject_status", "status"])
        start_col = find_col(work, ["开始日期(AESTDAT)", "开始日期", "aestdat", "start_date"])
        end_col = find_col(work, ["结束日期(AEENDAT)", "结束日期", "aeendat", "end_date"])
        grade_col = find_col(work, ["严重程度分级(AETOXGR)", "严重程度分级", "aetoxgr", "grade", "severity"])
        relation_col = find_col(work, ["与研究药物的相关性(AEREL)", "与研究药物的相关性", "aerel", "relationship"])
        outcome_col = find_col(work, ["转归(AEOUT)", "转归", "aeout", "outcome"])
        soc_col = find_col(work, ["AETERM_SOC", "soc", "系统器官分类", "器官系统分类"])
        hlt_col = find_col(work, ["AETERM_HLT", "hlt", "高位语"])
        pt_col = find_col(work, ["AETERM_PT", "pt", "首选语", "首选术语"])
        llt_col = find_col(work, ["AETERM_LLT", "llt", "低位语"])
        sae_col = find_col(work, ["是否是严重不良事件(AESER)", "是否为SAE", "是否是严重不良事件", "aeser", "is_sae"])
        death_col = find_col(work, ["导致死亡(AESDTH)", "导致死亡", "aesdth"])
        life_col = find_col(work, ["危及生命(AESLIFE)", "危及生命", "aeslife"])
        hosp_col = find_col(work, ["导致住院或住院时间延长(AESHOSP)", "导致住院或住院时间延长", "aeshosp"])
        discontinue_col = find_col(work, ["该不良事件是否导致退出试验？(AEDIS)", "导致退出试验", "aedis"])
        for _, row in work.iterrows():
            term = clean_value(row.get(term_col))
            if not term or (ae_yn_col and not is_yes_value(row.get(ae_yn_col))):
                continue
            reasons = []
            if death_col and is_yes_value(row.get(death_col)):
                reasons.append("死亡")
            if life_col and is_yes_value(row.get(life_col)):
                reasons.append("危及生命")
            if hosp_col and is_yes_value(row.get(hosp_col)):
                reasons.append("住院/住院延长")
            is_sae = bool(sae_col and is_yes_value(row.get(sae_col)))
            start_date = datetime_series(pd.Series([row.get(start_col)])).iloc[0] if start_col else pd.NaT
            rows.append({
                "中心": clean_site_identifier(row.get(site_col)) if site_col else "",
                "中心名称": clean_value(row.get(site_name_col)) if site_name_col else "",
                "受试者": clean_identifier(row.get(subject_col)) if subject_col else "",
                "受试者状态": clean_value(row.get(status_col)) if status_col else "",
                "AE名称": term,
                "SOC": clean_value(row.get(soc_col)) if soc_col else "未编码",
                "HLT": clean_value(row.get(hlt_col)) if hlt_col else "未编码",
                "PT": clean_value(row.get(pt_col)) if pt_col else "未编码",
                "LLT": clean_value(row.get(llt_col)) if llt_col else "未编码",
                "开始日期": start_date.date().isoformat() if pd.notna(start_date) else "",
                "结束日期": clean_value(row.get(end_col)) if end_col else "",
                "严重程度": clean_value(row.get(grade_col)) if grade_col else "未分级",
                "相关性": clean_value(row.get(relation_col)) if relation_col else "未说明",
                "转归": clean_value(row.get(outcome_col)) if outcome_col else "未说明",
                "是否SAE": "是" if is_sae else "否",
                "SAE原因": "、".join(reasons) if reasons else ("SAE" if is_sae else ""),
                "是否导致退出": clean_value(row.get(discontinue_col)) if discontinue_col else "",
            })
    ae_rows = rows
    sae_rows = [row for row in rows if row["是否SAE"] == "是"]

    def grouped_counts(source: list[dict[str, Any]], key: str, label: str) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for row in source:
            value = str(row.get(key) or "未说明")
            counts[value] = counts.get(value, 0) + 1
        return [{label: key, "事件数": value} for key, value in sorted(counts.items(), key=lambda item: item[1], reverse=True)]

    def grouped_multi_counts(source: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
        counts: dict[tuple[str, ...], int] = {}
        for row in source:
            group = tuple(str(row.get(key) or "未说明") for key in keys)
            counts[group] = counts.get(group, 0) + 1
        return [
            {**{key: group[index] for index, key in enumerate(keys)}, "事件数": count}
            for group, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
        ]

    return {
        "overview": [
            {"指标": "AE事件数", "数值": len(ae_rows)},
            {"指标": "SAE事件数", "数值": len(sae_rows)},
            {"指标": "涉及受试者数", "数值": len({row["受试者"] for row in ae_rows if row["受试者"]})},
            {"指标": "涉及中心数", "数值": len({row["中心"] for row in ae_rows if row["中心"]})},
        ],
        "by_site": grouped_counts(ae_rows, "中心", "中心"),
        "by_grade": grouped_counts(ae_rows, "严重程度", "严重程度"),
        "by_relation": grouped_counts(ae_rows, "相关性", "相关性"),
        "by_outcome": grouped_counts(ae_rows, "转归", "转归"),
        "by_soc": grouped_counts(ae_rows, "SOC", "SOC"),
        "by_pt": grouped_counts(ae_rows, "PT", "PT"),
        "by_site_soc": grouped_multi_counts(ae_rows, ["中心", "SOC"]),
        "by_site_pt": grouped_multi_counts(ae_rows, ["中心", "PT"]),
        "sae_by_site": grouped_counts(sae_rows, "中心", "中心"),
        "sae_by_reason": grouped_counts(sae_rows, "SAE原因", "SAE原因"),
        "sae_by_outcome": grouped_counts(sae_rows, "转归", "转归"),
        "sae_by_soc": grouped_counts(sae_rows, "SOC", "SOC"),
        "sae_by_pt": grouped_counts(sae_rows, "PT", "PT"),
        "sae_by_site_soc": grouped_multi_counts(sae_rows, ["中心", "SOC"]),
        "ae_details": ae_rows[:1000],
        "sae_details": sae_rows[:1000],
    }


def critical_query_review(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    queries = tables.get("queries", pd.DataFrame())
    if queries.empty or "__site_id" not in queries:
        return {"overview": [], "by_site": [], "open_by_site": [], "details": [], "open_details": []}
    columns = query_detail_columns(queries)
    critical_mask = critical_query_mask(queries, tables.get("critical_points", pd.DataFrame()))
    open_mask = open_query_mask(queries, columns)
    days = query_age_days(queries, columns)
    frame = queries.loc[critical_mask].copy()
    frame["__days"] = days.loc[critical_mask].fillna(0).clip(lower=0)
    open_frame = queries.loc[critical_mask & open_mask].copy()
    open_frame["__days"] = days.loc[critical_mask & open_mask].fillna(0).clip(lower=0)
    details = query_detail_rows(frame.sort_values("__days", ascending=False).head(1000), columns)
    open_details = query_detail_rows(open_frame.sort_values("__days", ascending=False).head(1000), columns)
    by_site = pd.DataFrame(details).groupby("中心").size().reset_index(name="质疑创建数") if details else pd.DataFrame(columns=["中心", "质疑创建数"])
    open_by_site = pd.DataFrame(open_details).groupby("中心").agg(
        未关闭质疑数=("中心", "size"),
        未关闭平均天数=("天数", lambda values: round(pd.to_numeric(values, errors="coerce").fillna(0).mean(), 1)),
    ).reset_index() if open_details else pd.DataFrame(columns=["中心", "未关闭质疑数", "未关闭平均天数"])
    return {
        "overview": [
            {"指标": "关键数据点Query创建数", "数值": len(details)},
            {"指标": "关键数据点未关闭Query数", "数值": len(open_details)},
            {"指标": "关键数据点未关闭平均天数", "数值": round(float(open_frame["__days"].mean() or 0), 1) if not open_frame.empty else 0},
            {"指标": "涉及中心数", "数值": int(frame["__site_id"].nunique()) if not frame.empty else 0},
        ],
        "by_site": by_site.sort_values("质疑创建数", ascending=False).to_dict(orient="records"),
        "open_by_site": open_by_site.sort_values("未关闭质疑数", ascending=False).to_dict(orient="records"),
        "details": details,
        "open_details": open_details,
    }


DYNAMIC_DRILLDOWN_METRICS = (
    ("edc_visit_entry_delay_days", "EDC访视录入延迟天数", "天"),
    ("page_missing_days_all", "页面缺失天数（全部）", "天"),
    ("page_missing_days_without_lab", "页面缺失天数（不含对接LAB）", "天"),
    ("page_sdv_pending_rate", "未SDV（页面）", "天"),
    ("logline_sdv_pending_rate", "未SDV（logline）", "天"),
    ("avg_open_query_age_days", "未关闭质疑天数", "天"),
    ("manual_query_reissue_rate", "人工质疑重发率", ""),
)


def query_detail_columns(queries: pd.DataFrame) -> dict[str, str | None]:
    return {
        "status": find_col(queries, ["query_status", "status", "query_state", "state", "查询状态", "处理状态", "质疑状态", "Query状态"]),
        "age": find_col(queries, ["age_days", "query_age", "open_days", "days_open", "账龄", "打开天数", "打开天数/回答天数", "打开天数_回答天数"]),
        "opened": find_col(queries, ["opened_date", "open_date", "created_date", "query_open_date", "打开日期", "创建日期", "质疑打开时间"]),
        "closed": find_col(queries, ["closed_date", "resolved_date", "answered_date", "关闭日期", "解决日期", "质疑回答日期"]),
        "type": find_col(queries, ["query_type", "type", "source", "category", "类型", "来源", "Query类型"]),
        "reissue": find_col(queries, ["reissued", "reopened", "status_change", "status_history", "reopen_count", "reissue_count", "重开次数"]),
        "subject": "__subject_id" if "__subject_id" in queries else find_col(queries, ["subject_id", "受试者编号", "受试者"]),
        "visit": find_col(queries, ["visit_name", "visit", "visit_folder", "访视名称"]),
        "page": find_col(queries, ["page_name", "data_page_name", "form_name", "form", "数据页名称", "表单名称"]),
        "field": find_col(queries, ["field_name", "field", "item_name", "字段名称", "变量名"]),
        "text": find_col(queries, ["query_text", "query", "query_message", "message", "质疑文本", "质疑内容", "文本"]),
    }


def query_age_days(queries: pd.DataFrame, columns: dict[str, str | None]) -> pd.Series:
    age_col = columns["age"]
    if age_col:
        return leading_number_series(queries[age_col]).fillna(0).clip(lower=0)
    opened_col = columns["opened"]
    if opened_col:
        return (pd.Timestamp.today().normalize() - datetime_series(queries[opened_col])).dt.days.fillna(0).clip(lower=0)
    return pd.Series(0, index=queries.index, dtype="float64")


def open_query_mask(queries: pd.DataFrame, columns: dict[str, str | None]) -> pd.Series:
    status_col = columns["status"]
    closed_col = columns["closed"]
    if status_col:
        return ~text_contains(queries, [status_col], "closed|resolved|cancelled|canceled|关闭|已解决|已回答|已处理")
    if closed_col:
        return datetime_series(queries[closed_col]).isna()
    return pd.Series(True, index=queries.index)


def reissued_query_mask(queries: pd.DataFrame, columns: dict[str, str | None]) -> pd.Series:
    reissue_col = columns["reissue"]
    mask = text_contains(queries, [columns["status"], reissue_col], "reopen|re-open|reissue|responded.*open|open.*responded|返回|重开|重新")
    if reissue_col and pd.api.types.is_numeric_dtype(queries[reissue_col]):
        mask = mask | numeric_series(queries[reissue_col]).gt(0).fillna(False)
    return mask


def critical_query_mask(queries: pd.DataFrame, critical_points: pd.DataFrame) -> pd.Series:
    if critical_points.empty:
        critical_col = find_col(queries, ["critical", "critical_data_point", "is_critical", "key_data_point", "critical_flag", "关键数据点"])
        if critical_col:
            return text_contains(queries, [critical_col], "critical|key|yes|true|1|是|关键|重要")
        return text_contains(queries, [find_col(queries, ["query_type", "type", "source", "category"])], "critical|key|endpoint|primary|safety|ae|sae|eligibility")
    query_visit_col = find_col(queries, ["visit_name", "visit", "visit_folder", "访视名称"])
    query_page_col = find_col(queries, ["page_name", "data_page_name", "form_name", "form", "数据页名称", "表单名称"])
    query_field_col = find_col(queries, ["field_name", "field", "item_name", "字段名称", "变量名"])
    critical_visit_col = find_col(critical_points, ["visit_name", "visit", "visit_folder", "访视名称"])
    critical_page_col = find_col(critical_points, ["page_name", "data_page_name", "form_name", "form", "数据页名称", "表单名称"])
    critical_field_col = find_col(critical_points, ["field_name", "field", "item_name", "字段名称", "变量名"])
    mask = pd.Series(False, index=queries.index)
    if query_field_col and critical_field_col:
        values = set(critical_points[critical_field_col].dropna().astype(str).str.strip().str.lower())
        if values:
            return queries[query_field_col].astype(str).str.strip().str.lower().isin(values)
    if query_page_col and critical_page_col:
        values = set(critical_points[critical_page_col].dropna().astype(str).str.strip().str.lower())
        if values:
            return queries[query_page_col].astype(str).str.strip().str.lower().isin(values)
    if query_visit_col and critical_visit_col:
        values = set(critical_points[critical_visit_col].dropna().astype(str).str.strip().str.lower())
        if values:
            return queries[query_visit_col].astype(str).str.strip().str.lower().isin(values)
    return mask


def query_detail_rows(frame: pd.DataFrame, columns: dict[str, str | None], include_days: bool = True) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        item = {
            "中心": clean_site_identifier(row.get("__site_id")),
            "受试者": clean_identifier(row.get(columns["subject"])) if columns["subject"] else "",
            "访视": clean_value(row.get(columns["visit"])) if columns["visit"] else "",
            "页面": clean_value(row.get(columns["page"])) if columns["page"] else "",
            "字段": clean_value(row.get(columns["field"])) if columns["field"] else "",
            "质疑类型": clean_value(row.get(columns["type"])) if columns["type"] else "",
            "质疑状态": clean_value(row.get(columns["status"])) if columns["status"] else "",
            "质疑文本": clean_value(row.get(columns["text"])) if columns["text"] else "",
        }
        if include_days:
            item["天数"] = clean_value(row.get("__days"))
        if columns["reissue"]:
            item["重开次数"] = clean_value(row.get(columns["reissue"]))
        rows.append(item)
    return rows


def rows_for_metric_details(tables: dict[str, pd.DataFrame], metric_key: str, threshold: float, limit: int = 1000) -> list[dict[str, Any]]:
    if metric_key in {"edc_visit_entry_delay_days", "page_missing_days_all", "page_missing_days_without_lab", "page_sdv_pending_rate", "logline_sdv_pending_rate"}:
        visits = tables.get("visits", pd.DataFrame())
        if visits.empty:
            return []
        source = visits.get("__source_name", pd.Series("", index=visits.index)).astype(str).str.lower()
        if metric_key == "edc_visit_entry_delay_days":
            mask = source.str.contains("缺失访视", regex=False, na=False)
            days_col = find_col(visits, ["irt_actual_visit_time", "irt_actual_visit_date", "irt实际访视时间", "visit_date", "visit_dt", "访视日期"])
            if not mask.any():
                mask = source.str.contains("缺失页", regex=False, na=False) & ~source.str.contains("不含", regex=False, na=False)
            days = (pd.Timestamp.today().normalize() - datetime_series(visits[days_col])).dt.days if days_col else pd.Series(0, index=visits.index)
        elif metric_key == "page_missing_days_all":
            mask = source.str.contains("缺失页", regex=False, na=False) & ~source.str.contains("不含", regex=False, na=False)
            days_col = find_col(visits, ["visit_date", "visit_dt", "访视日期", "开始日期"])
            days = (pd.Timestamp.today().normalize() - datetime_series(visits[days_col])).dt.days if days_col else pd.Series(0, index=visits.index)
        elif metric_key == "page_missing_days_without_lab":
            mask = source.str.contains("缺失页", regex=False, na=False) & source.str.contains("不含", regex=False, na=False)
            days_col = find_col(visits, ["visit_date", "visit_dt", "访视日期", "开始日期"])
            days = (pd.Timestamp.today().normalize() - datetime_series(visits[days_col])).dt.days if days_col else pd.Series(0, index=visits.index)
        elif metric_key == "page_sdv_pending_rate":
            mask = source.str.contains("未sdv", na=False) & source.str.contains("页面", na=False)
            days_col = find_col(visits, ["visit_date", "visit_dt", "访视日期", "开始日期"])
            days = (pd.Timestamp.today().normalize() - datetime_series(visits[days_col])).dt.days if days_col else pd.Series(0, index=visits.index)
        else:
            mask = source.str.contains("未sdv", na=False) & source.str.contains("logline", na=False)
            days_col = find_col(visits, ["days_to_today", "距今天数"])
            days = leading_number_series(visits[days_col]) if days_col else pd.Series(0, index=visits.index)
        site_col = "__site_id"
        subject_col = find_col(visits, ["筛选号", "subject_id", "受试者编号"]) or ("__subject_id" if "__subject_id" in visits else None)
        status_col = find_col(visits, ["status", "subject_status", "状态", "受试者状态"])
        visit_col = find_col(visits, ["visit_name", "visit", "访视名称", "edc_visit_name", "edc访视名称"])
        edc_visit_col = "edc访视名称" if "edc访视名称" in visits.columns else find_col(visits, ["edc_visit_name", "edc访视名称"])
        page_col = find_col(visits, ["page_name", "form_name", "data_page_name", "表单名称", "数据页名称"])
        frame = visits.loc[mask].copy()
        frame["__days"] = days.loc[mask].fillna(0).clip(lower=0)
        frame = frame[frame["__days"] > threshold]
        frame = frame.sort_values("__days", ascending=False).head(limit)
        return [
            {
                "中心": clean_site_identifier(row.get(site_col)),
                "受试者": clean_identifier(row.get(subject_col)) if subject_col else "",
                "受试者状态": clean_value(row.get(status_col)) if status_col else "",
                "访视": first_clean_row_value(row, [edc_visit_col, visit_col]),
                "页面": clean_value(row.get(page_col)) if page_col else "",
                "天数": clean_value(row.get("__days")),
            }
            for _, row in frame.iterrows()
        ]

    if metric_key in {"avg_open_query_age_days", "manual_query_reissue_rate", "critical_queries_created", "avg_critical_open_query_age_days"}:
        queries = tables.get("queries", pd.DataFrame())
        if queries.empty:
            return []
        columns = query_detail_columns(queries)
        days = query_age_days(queries, columns)
        if metric_key == "avg_open_query_age_days":
            source = queries.get("__source_name", pd.Series("", index=queries.index)).astype(str).str.lower()
            mask = source.str.contains("未回答质疑|未关闭质疑", regex=True, na=False)
            if not mask.any():
                mask = pd.Series(True, index=queries.index)
            frame = queries.loc[mask].copy()
            frame["__days"] = days.loc[mask].fillna(0).clip(lower=0)
            frame = frame[frame["__days"] > threshold]
            frame = frame.sort_values("__days", ascending=False).head(limit)
            return query_detail_rows(frame, columns)
        if metric_key == "manual_query_reissue_rate":
            manual_mask = text_contains(queries, [columns["type"]], r"\bdm\s*manual\b|dm_manual|人工质疑")
            mask = manual_mask & reissued_query_mask(queries, columns)
            frame = queries.loc[mask].copy().head(limit)
            frame["__days"] = days.loc[mask].fillna(0).clip(lower=0)
            return query_detail_rows(frame, columns)
        critical_mask = critical_query_mask(queries, tables.get("critical_points", pd.DataFrame()))
        if metric_key == "critical_queries_created":
            frame = queries.loc[critical_mask].copy().head(limit)
            frame["__days"] = days.loc[critical_mask].fillna(0).clip(lower=0)
            return query_detail_rows(frame, columns)
        open_mask = open_query_mask(queries, columns)
        mask = critical_mask & open_mask
        frame = queries.loc[mask].copy()
        frame["__days"] = days.loc[mask].fillna(0).clip(lower=0)
        frame = frame[frame["__days"] > threshold]
        frame = frame.sort_values("__days", ascending=False).head(limit)
        return query_detail_rows(frame, columns)
    return []


def kri_drilldowns(metrics: pd.DataFrame, tables: dict[str, pd.DataFrame], thresholds: Thresholds) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for key, label, unit in DYNAMIC_DRILLDOWN_METRICS:
        if key not in metrics.columns:
            continue
        threshold = float(getattr(thresholds, key))
        details = rows_for_metric_details(tables, key, threshold)
        if key in {"manual_query_reissue_rate", "critical_queries_created"}:
            over_sites = {
                clean_site_identifier(row["site_id"])
                for _, row in metrics.iterrows()
                if float(row.get(key, 0) or 0) > threshold
            }
            details = [row for row in details if row.get("中心") in over_sites]
        counts = pd.Series(dtype="int64")
        if details:
            counts = pd.DataFrame(details).groupby("中心").size()
        center_rows = []
        for _, row in metrics.iterrows():
            site = clean_site_identifier(row["site_id"])
            metric_value = float(row.get(key, 0) or 0)
            value = int(metric_value) if key == "critical_queries_created" and metric_value > threshold else int(counts.get(site, 0))
            center_rows.append({
                "中心": site,
                "超阈值条数": value,
                "当前值": round(metric_value, 3),
                "阈值": threshold,
                "状态": "有超阈值记录" if value > 0 else "未超阈值",
            })
        center_rows = sorted(center_rows, key=lambda item: int(item["超阈值条数"]), reverse=True)
        items.append({
            "key": key,
            "label": label,
            "unit": unit,
            "threshold": threshold,
            "center_rows": center_rows,
            "details": details,
        })
    return items


def data_source_status() -> dict[str, Any]:
    roles = set(current_source_roles.values())
    raw_names = " ".join(current_raw_tables.keys()).lower()
    progress_tokens = ["progress", "进展报告", "進展報告"]
    clinical_tokens = ["formexcel", "form excel", "form_excel", "临床研究数据", "臨床研究數據"]
    progress_report = "progress_report" in roles or any(token in raw_names for token in progress_tokens)
    clinical_data = "clinical_data" in roles or any(token in raw_names for token in clinical_tokens)
    return {
        "progress_report": progress_report,
        "clinical_data": clinical_data,
        "critical_points": "critical_points" in roles,
        "query_detail": "query_detail" in roles,
    }


def source_filename(source_name: str) -> str:
    return source_name.split("::", 1)[0]


def merge_uploaded_tables(
    loaded_tables: dict[str, pd.DataFrame],
    raw_tables: dict[str, pd.DataFrame],
    source_roles: dict[str, str],
) -> None:
    global current_tables, current_raw_tables, current_source_roles
    uploaded_files = set(source_roles)
    uploaded_roles = {role for role in source_roles.values() if role}
    if not current_tables:
        current_tables = loaded_tables
        current_raw_tables = raw_tables
        current_source_roles = source_roles
        return

    replaced_files = {
        filename
        for filename, role in current_source_roles.items()
        if filename in uploaded_files or (role and role in uploaded_roles)
    }
    replaced_files.update(uploaded_files)
    replaced_raw_sources = {
        name
        for name in current_raw_tables
        if source_filename(name) in replaced_files
    }

    next_raw_tables = {
        name: df
        for name, df in current_raw_tables.items()
        if name not in replaced_raw_sources
    }
    next_raw_tables.update(raw_tables)

    next_tables: dict[str, pd.DataFrame] = {}
    domains = set(current_tables) | set(loaded_tables)
    for domain in domains:
        frames: list[pd.DataFrame] = []
        existing = current_tables.get(domain)
        if existing is not None and not existing.empty:
            if "__source_name" in existing.columns:
                keep_mask = ~existing["__source_name"].astype(str).isin(replaced_raw_sources)
                keep_mask &= ~existing["__source_name"].astype(str).map(source_filename).isin(replaced_files)
                existing = existing[keep_mask]
            frames.append(existing)
        incoming = loaded_tables.get(domain)
        if incoming is not None and not incoming.empty:
            frames.append(incoming)
        if frames:
            next_tables[domain] = pd.concat(frames, ignore_index=True, sort=False)

    next_source_roles = {
        filename: role
        for filename, role in current_source_roles.items()
        if filename not in replaced_files and (not role or role not in uploaded_roles)
    }
    next_source_roles.update(source_roles)
    current_tables = next_tables
    current_raw_tables = next_raw_tables
    current_source_roles = next_source_roles


def build_state(thresholds: Thresholds) -> dict[str, Any]:
    tables = enrich_tables(current_tables)
    metrics, signals = compute_metrics(tables, thresholds)
    action_log = action_log_from_signals(signals)

    domain_summary = [
        {
            "数据域": DOMAIN_LABELS.get(domain, domain),
            "行数": len(df),
            "列数": len(df.columns),
            "已识别中心列": bool_zh("__site_id" in df.columns),
            "已识别受试者列": bool_zh("__subject_id" in df.columns),
        }
        for domain, df in tables.items()
    ]

    raw_summary = [
        {"数据集": name, "行数": len(df), "列数": len(df.columns)}
        for name, df in current_raw_tables.items()
    ]

    fields = [
        {"domain": DOMAIN_LABELS.get(domain, domain), "fields": DOMAIN_FIELDS[domain]}
        for domain in DOMAIN_LABELS
    ]

    metrics_zh = metrics.rename(columns=METRIC_LABELS)
    signals_zh = signals.rename(columns=SIGNAL_LABELS)
    action_log_zh = action_log.rename(columns=ACTION_LOG_LABELS)
    overview = (
        {
            "中心数": int(metrics["site_id"].nunique()),
            "受试者数": int(metrics["subjects"].sum()),
        }
        if not metrics.empty
        else {"中心数": "-", "受试者数": "-"}
    )

    return {
        "using_demo_data": using_demo_data,
        "kri": {
            "enabled": thresholds.kri_enabled,
            "enabled_metrics": list(thresholds.enabled_metrics),
        },
        "raw_summary": raw_summary,
        "domain_summary": domain_summary,
        "data_sources": data_source_status(),
        "fields": fields,
        "overview": overview,
        "subject_status_summary": subject_status_summary(tables),
        "subject_status_by_site": subject_status_by_site(tables),
        "patient_medical_review": patient_medical_review(current_raw_tables),
        "ae_event_review": ae_event_review(current_raw_tables),
        "critical_query_review": critical_query_review(tables),
        "kri_drilldowns": kri_drilldowns(metrics, tables, thresholds),
        "metrics": records(metrics_zh),
        "signals": records(signals_zh),
        "action_log": records(action_log_zh),
    }


@app.get("/api/state")
def get_state(thresholds: Thresholds = Depends(thresholds_from_query)) -> dict[str, Any]:
    return build_state(thresholds)


@app.get("/api/session")
def get_session() -> dict[str, str]:
    return {"session_id": APP_SESSION_ID}


@app.post("/api/reset")
def reset_state(thresholds: Thresholds = Depends(thresholds_from_query)) -> dict[str, Any]:
    clear_uploaded_state()
    return build_state(thresholds)


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return CONFIG_STORE.response(default_thresholds=DEFAULT_THRESHOLDS)


@app.post("/api/config")
def save_config(config: KriConfigInput) -> dict[str, Any]:
    thresholds = thresholds_from_config_input(config)
    return CONFIG_STORE.save(thresholds, saved_by=config.saved_by, change_reason=config.change_reason)


@app.post("/api/upload")
async def upload(
    files: list[UploadFile] = File(...),
    mapping_config: str | None = Form(None),
    source_roles: str | None = Form(None),
    thresholds: Thresholds = Depends(thresholds_from_query),
) -> dict[str, Any]:
    global current_tables, current_raw_tables, current_source_roles, using_demo_data
    memory_files = [MemoryUpload(upload.filename or "upload", await upload.read()) for upload in files]
    try:
        loaded_tables, raw_tables = read_uploaded_files(memory_files, mapping_config, source_roles)
        uploaded_roles = normalize_source_roles(source_roles)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not loaded_tables:
        raise HTTPException(status_code=400, detail="未识别到已知数据域，请检查文件名或工作表名称。")
    merge_uploaded_tables(loaded_tables, raw_tables, uploaded_roles)
    using_demo_data = False
    return build_state(thresholds)


@app.post("/api/upload/preview")
async def upload_preview(files: list[UploadFile] = File(...), source_roles: str | None = Form(None)) -> dict[str, Any]:
    memory_files = [MemoryUpload(upload.filename or "upload", await upload.read()) for upload in files]
    try:
        return preview_uploaded_files(memory_files, source_roles=source_roles)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/upload/commit")
async def upload_commit(
    files: list[UploadFile] = File(...),
    mapping_config: str = Form(...),
    source_roles: str | None = Form(None),
    thresholds: Thresholds = Depends(thresholds_from_query),
) -> dict[str, Any]:
    return await upload(files=files, mapping_config=mapping_config, source_roles=source_roles, thresholds=thresholds)


@app.get("/api/export")
def export(thresholds: Thresholds = Depends(thresholds_from_query)) -> Response:
    tables = enrich_tables(current_tables)
    metrics, signals = compute_metrics(tables, thresholds)
    drilldowns = [
        item
        for item in kri_drilldowns(metrics, tables, thresholds)
        if item["key"] in set(thresholds.enabled_metrics)
    ]
    payload = make_kri_detail_export(drilldowns)
    return Response(
        payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="rbqm_audit_package.xlsx"'},
    )


app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True, check_dir=False), name="frontend")
