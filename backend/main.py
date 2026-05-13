from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

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
from rbqm.demo import generate_demo_data
from rbqm.enrichment import enrich_tables
from rbqm.export import make_excel_export
from rbqm.ingestion import preview_uploaded_files, read_uploaded_files
from rbqm.metrics import compute_metrics
from rbqm.models import (
    KRI_METRIC_KEYS,
    Thresholds,
)
from rbqm.settings_store import KriConfigStore, threshold_values


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
CONFIG_STORE = KriConfigStore(ROOT / "data" / "config")

DEFAULT_THRESHOLDS = Thresholds(
    missing_rate=0.10,
    late_entry_rate=0.20,
    avg_entry_delay_days=7.0,
    open_queries_per_subject=1.50,
    avg_open_query_age_days=21.0,
    safety_issues_per_subject=0.15,
    dlt_rate=0.10,
    grade3_ae_rate=0.20,
    dose_modification_rate=0.20,
    eligibility_deviation_rate=0.10,
    pk_window_deviation_rate=0.15,
    tumor_assessment_issue_rate=0.20,
    lab_issues_per_subject=0.20,
    major_deviations_per_subject=0.10,
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

current_tables: dict[str, pd.DataFrame] = generate_demo_data()
current_raw_tables: dict[str, pd.DataFrame] = {}
using_demo_data = True


class MemoryUpload(BytesIO):
    def __init__(self, name: str, payload: bytes) -> None:
        super().__init__(payload)
        self.name = name


def thresholds_from_query(
    kri_enabled: bool | None = Query(None),
    enabled_metrics: str | None = Query(None),
    missing_rate: float | None = Query(None, ge=0.01, le=0.30),
    late_entry_rate: float | None = Query(None, ge=0.01, le=0.60),
    avg_entry_delay_days: float | None = Query(None, ge=1.0, le=30.0),
    open_queries_per_subject: float | None = Query(None, ge=0.10, le=5.00),
    avg_open_query_age_days: float | None = Query(None, ge=1.0, le=60.0),
    safety_issues_per_subject: float | None = Query(None, ge=0.01, le=1.00),
    dlt_rate: float | None = Query(None, ge=0.01, le=1.00),
    grade3_ae_rate: float | None = Query(None, ge=0.01, le=2.00),
    dose_modification_rate: float | None = Query(None, ge=0.01, le=2.00),
    eligibility_deviation_rate: float | None = Query(None, ge=0.01, le=1.00),
    pk_window_deviation_rate: float | None = Query(None, ge=0.01, le=1.00),
    tumor_assessment_issue_rate: float | None = Query(None, ge=0.01, le=1.00),
    lab_issues_per_subject: float | None = Query(None, ge=0.01, le=1.00),
    major_deviations_per_subject: float | None = Query(None, ge=0.01, le=1.00),
) -> Thresholds:
    kri_enabled = direct_query_default(kri_enabled)
    enabled_metrics = direct_query_default(enabled_metrics)
    missing_rate = direct_query_default(missing_rate)
    late_entry_rate = direct_query_default(late_entry_rate)
    avg_entry_delay_days = direct_query_default(avg_entry_delay_days)
    open_queries_per_subject = direct_query_default(open_queries_per_subject)
    avg_open_query_age_days = direct_query_default(avg_open_query_age_days)
    safety_issues_per_subject = direct_query_default(safety_issues_per_subject)
    dlt_rate = direct_query_default(dlt_rate)
    grade3_ae_rate = direct_query_default(grade3_ae_rate)
    dose_modification_rate = direct_query_default(dose_modification_rate)
    eligibility_deviation_rate = direct_query_default(eligibility_deviation_rate)
    pk_window_deviation_rate = direct_query_default(pk_window_deviation_rate)
    tumor_assessment_issue_rate = direct_query_default(tumor_assessment_issue_rate)
    lab_issues_per_subject = direct_query_default(lab_issues_per_subject)
    major_deviations_per_subject = direct_query_default(major_deviations_per_subject)
    active = CONFIG_STORE.active_thresholds(DEFAULT_THRESHOLDS)
    return Thresholds(
        missing_rate=missing_rate if missing_rate is not None else active.missing_rate,
        late_entry_rate=late_entry_rate if late_entry_rate is not None else active.late_entry_rate,
        avg_entry_delay_days=avg_entry_delay_days if avg_entry_delay_days is not None else active.avg_entry_delay_days,
        open_queries_per_subject=open_queries_per_subject if open_queries_per_subject is not None else active.open_queries_per_subject,
        avg_open_query_age_days=avg_open_query_age_days if avg_open_query_age_days is not None else active.avg_open_query_age_days,
        safety_issues_per_subject=safety_issues_per_subject if safety_issues_per_subject is not None else active.safety_issues_per_subject,
        dlt_rate=dlt_rate if dlt_rate is not None else active.dlt_rate,
        grade3_ae_rate=grade3_ae_rate if grade3_ae_rate is not None else active.grade3_ae_rate,
        dose_modification_rate=dose_modification_rate if dose_modification_rate is not None else active.dose_modification_rate,
        eligibility_deviation_rate=eligibility_deviation_rate if eligibility_deviation_rate is not None else active.eligibility_deviation_rate,
        pk_window_deviation_rate=pk_window_deviation_rate if pk_window_deviation_rate is not None else active.pk_window_deviation_rate,
        tumor_assessment_issue_rate=tumor_assessment_issue_rate if tumor_assessment_issue_rate is not None else active.tumor_assessment_issue_rate,
        lab_issues_per_subject=lab_issues_per_subject if lab_issues_per_subject is not None else active.lab_issues_per_subject,
        major_deviations_per_subject=major_deviations_per_subject if major_deviations_per_subject is not None else active.major_deviations_per_subject,
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

    return {
        "using_demo_data": using_demo_data,
        "kri": {
            "enabled": thresholds.kri_enabled,
            "enabled_metrics": list(thresholds.enabled_metrics),
        },
        "raw_summary": raw_summary,
        "domain_summary": domain_summary,
        "fields": fields,
        "overview": {
            "中心数": int(metrics["site_id"].nunique()),
            "受试者数": int(metrics["subjects"].sum()),
            "高风险中心数": int((metrics["risk_level"] == "高").sum()),
            "待处理风险信号数": int(len(signals)),
        },
        "metrics": records(metrics_zh),
        "signals": records(signals_zh),
        "action_log": records(action_log_zh),
    }


@app.get("/api/state")
def get_state(thresholds: Thresholds = Depends(thresholds_from_query)) -> dict[str, Any]:
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
    thresholds: Thresholds = Depends(thresholds_from_query),
) -> dict[str, Any]:
    global current_tables, current_raw_tables, using_demo_data
    memory_files = [MemoryUpload(upload.filename or "upload", await upload.read()) for upload in files]
    try:
        loaded_tables, raw_tables = read_uploaded_files(memory_files, mapping_config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not loaded_tables:
        raise HTTPException(status_code=400, detail="未识别到已知数据域，请检查文件名或工作表名称。")
    current_tables = loaded_tables
    current_raw_tables = raw_tables
    using_demo_data = False
    return build_state(thresholds)


@app.post("/api/upload/preview")
async def upload_preview(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    memory_files = [MemoryUpload(upload.filename or "upload", await upload.read()) for upload in files]
    try:
        return preview_uploaded_files(memory_files)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/upload/commit")
async def upload_commit(
    files: list[UploadFile] = File(...),
    mapping_config: str = Form(...),
    thresholds: Thresholds = Depends(thresholds_from_query),
) -> dict[str, Any]:
    return await upload(files=files, mapping_config=mapping_config, thresholds=thresholds)


@app.post("/api/demo")
def use_demo(thresholds: Thresholds = Depends(thresholds_from_query)) -> dict[str, Any]:
    global current_tables, current_raw_tables, using_demo_data
    current_tables = generate_demo_data()
    current_raw_tables = {}
    using_demo_data = True
    return build_state(thresholds)


@app.get("/api/export")
def export(thresholds: Thresholds = Depends(thresholds_from_query)) -> Response:
    tables = enrich_tables(current_tables)
    metrics, signals = compute_metrics(tables, thresholds)
    action_log = action_log_from_signals(signals)
    payload = make_excel_export(metrics, signals, action_log, tables)
    return Response(
        payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="rbqm_audit_package.xlsx"'},
    )


app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True, check_dir=False), name="frontend")
