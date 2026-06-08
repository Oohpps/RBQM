from __future__ import annotations

import json
from typing import Any

import pandas as pd

from .config import DOMAIN_FIELDS, DOMAIN_LABELS, REQUIRED_DOMAIN_FIELDS
from .utils import snake_case, standardize_columns

FORCED_ROLE_DOMAINS = {
    "critical_points": "critical_points",
    "query_detail": "queries",
}

CLINICAL_RAW_SHEET_TOKENS = (
    "ae",
    "lb_hba1c",
    "hba1c",
    "vs_w",
    "weight",
    "体重",
    "糖化",
)


def normalize_source_roles(source_roles: Any | None) -> dict[str, str]:
    if not source_roles:
        return {}
    if isinstance(source_roles, str):
        try:
            source_roles = json.loads(source_roles)
        except json.JSONDecodeError as exc:
            raise ValueError(f"上传来源类型不是有效JSON：{exc.msg}") from exc
    if not isinstance(source_roles, dict):
        raise ValueError("上传来源类型必须是JSON对象")
    return {str(name): str(role) for name, role in source_roles.items()}


def role_domain(filename: str, source_roles: dict[str, str]) -> str | None:
    return FORCED_ROLE_DOMAINS.get(source_roles.get(filename, ""))


def should_read_excel_sheet(
    filename: str,
    sheet_name: str,
    roles: dict[str, str],
    configured_sources: dict[str, Any] | None = None,
) -> bool:
    configured_sources = configured_sources or {}
    label = source_id(filename, sheet_name)
    if label in configured_sources:
        return True
    if role_domain(filename, roles):
        return True
    role = roles.get(filename, "")
    if role != "clinical_data":
        return True
    if infer_domain(sheet_name):
        return True
    normalized_sheet = snake_case(sheet_name)
    return any(token in normalized_sheet for token in CLINICAL_RAW_SHEET_TOKENS)


def infer_domain(name: str) -> str | None:
    value = snake_case(name)
    if any(token in value for token in ["关键数据点", "key_data_point", "critical_data_point", "critical_points"]):
        return "critical_points"
    if any(token in value for token in ["query_detail", "query_details", "质疑明细", "质疑明细报告"]):
        return "queries"
    if any(token in value for token in ["缺失页", "页面状态明细", "未sdv", "页面sdv"]):
        return "visits"
    if any(token in value for token in ["未关闭质疑", "未回答质疑"]):
        return "queries"
    if any(token in value for token in ["受试者summary", "受试者_summary"]):
        return "subjects"
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


def normalize_mapping_config(mapping_config: Any | None) -> dict[str, Any]:
    if not mapping_config:
        return {"sources": {}}
    if isinstance(mapping_config, str):
        try:
            mapping_config = json.loads(mapping_config)
        except json.JSONDecodeError as exc:
            raise ValueError(f"字段映射配置不是有效JSON：{exc.msg}") from exc
    if not isinstance(mapping_config, dict):
        raise ValueError("字段映射配置必须是JSON对象")
    sources = mapping_config.get("sources", {})
    if not isinstance(sources, dict):
        raise ValueError("字段映射配置的sources必须是对象")
    for source_key, source_mapping in sources.items():
        if not isinstance(source_mapping, dict):
            raise ValueError(f"{source_key} 的映射配置必须是对象")
    return {"sources": sources}


def source_id(filename: str, sheet_name: str | None = None) -> str:
    return f"{filename}::{sheet_name}" if sheet_name else filename


def dataframe_preview_records(df: pd.DataFrame, limit: int = 3) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in df.head(limit).to_dict(orient="records"):
        records.append({str(key): preview_value(value) for key, value in row.items()})
    return records


def preview_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def preview_uploaded_files(uploaded_files: list[Any], sample_rows: int = 3, source_roles: Any | None = None) -> dict[str, Any]:
    roles = normalize_source_roles(source_roles)
    sources: list[dict[str, Any]] = []
    for uploaded in uploaded_files:
        filename = uploaded.name
        forced_domain = role_domain(filename, roles)
        suffix = filename.rsplit(".", 1)[-1].lower()
        if suffix == "csv":
            df = pd.read_csv(uploaded)
            sources.append(
                {
                    "source_id": source_id(filename),
                    "filename": filename,
                    "sheet_name": None,
                    "rows": len(df),
                    "columns": [str(column) for column in df.columns],
                    "sample": dataframe_preview_records(df, sample_rows),
                    "upload_role": roles.get(filename),
                    "guessed_domain": forced_domain or infer_domain(filename),
                }
            )
            continue

        workbook = pd.ExcelFile(uploaded)
        for sheet_name in workbook.sheet_names:
            df = pd.read_excel(workbook, sheet_name=sheet_name)
            sources.append(
                {
                    "source_id": source_id(filename, sheet_name),
                    "filename": filename,
                    "sheet_name": sheet_name,
                    "rows": len(df),
                    "columns": [str(column) for column in df.columns],
                    "sample": dataframe_preview_records(df, sample_rows),
                    "upload_role": roles.get(filename),
                    "guessed_domain": forced_domain or infer_domain(sheet_name) or infer_domain(filename),
                }
            )
    return {
        "sources": sources,
        "domains": [
            {
                "key": domain,
                "label": DOMAIN_LABELS[domain],
                "fields": DOMAIN_FIELDS[domain],
                "required_fields": REQUIRED_DOMAIN_FIELDS.get(domain, []),
            }
            for domain in DOMAIN_LABELS
        ],
    }


def mapped_frame(source_key: str, df: pd.DataFrame, source_mapping: dict[str, Any]) -> pd.DataFrame:
    domain = source_mapping.get("domain")
    if domain not in DOMAIN_LABELS:
        raise ValueError(f"{source_key} 的数据域无效：{domain}")
    fields = source_mapping.get("fields", {})
    if fields is None:
        fields = {}
    if not isinstance(fields, dict):
        raise ValueError(f"{source_key} 的字段映射必须是对象")

    allowed_fields = set(DOMAIN_FIELDS[domain])
    standardized = standardize_columns(df)
    original_to_standard = {str(original): standard for original, standard in zip(df.columns, standardized.columns)}
    rename_map: dict[str, str] = {}
    for target_field, source_column in fields.items():
        if not source_column:
            continue
        if target_field not in allowed_fields:
            raise ValueError(f"{source_key} 的字段 {target_field} 不属于数据域 {domain}")
        if str(source_column) not in original_to_standard:
            raise ValueError(f"{source_key} 缺少映射列：{source_column}")
        rename_map[original_to_standard[str(source_column)]] = snake_case(target_field)
    mapped = standardized.rename(columns=rename_map)
    mapped["__source_name"] = source_key
    return mapped


def read_uploaded_files(uploaded_files: list[Any], mapping_config: Any | None = None, source_roles: Any | None = None) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    mapping = normalize_mapping_config(mapping_config)
    roles = normalize_source_roles(source_roles)
    configured_sources = dict(mapping["sources"])
    seen_sources: set[str] = set()
    domain_tables: dict[str, list[pd.DataFrame]] = {domain: [] for domain in DOMAIN_LABELS}
    raw_tables: dict[str, pd.DataFrame] = {}

    for uploaded in uploaded_files:
        filename = uploaded.name
        forced_domain = role_domain(filename, roles)
        suffix = filename.rsplit(".", 1)[-1].lower()
        if suffix == "csv":
            df = pd.read_csv(uploaded)
            raw_tables[filename] = df
            key = source_id(filename)
            seen_sources.add(key)
            source_mapping = configured_sources.get(key)
            if source_mapping and source_mapping.get("domain"):
                mapped = mapped_frame(key, df, source_mapping)
                domain = source_mapping["domain"]
                domain_tables[domain].append(mapped)
                continue
            domain = forced_domain or infer_domain(filename)
            if domain:
                standardized = standardize_columns(df)
                standardized["__source_name"] = key
                domain_tables[domain].append(standardized)
            continue

        workbook = pd.ExcelFile(uploaded)
        sheet_names = [
            sheet_name
            for sheet_name in workbook.sheet_names
            if should_read_excel_sheet(filename, sheet_name, roles, configured_sources)
        ]
        if not sheet_names:
            sheet_names = workbook.sheet_names
        for sheet_name in sheet_names:
            df = pd.read_excel(workbook, sheet_name=sheet_name)
            label = source_id(filename, sheet_name)
            raw_tables[label] = df
            seen_sources.add(label)
            source_mapping = configured_sources.get(label)
            if source_mapping and source_mapping.get("domain"):
                mapped = mapped_frame(label, df, source_mapping)
                domain = source_mapping["domain"]
                domain_tables[domain].append(mapped)
                continue
            domain = forced_domain or infer_domain(sheet_name) or infer_domain(filename)
            if domain:
                standardized = standardize_columns(df)
                standardized["__source_name"] = label
                domain_tables[domain].append(standardized)

    unknown_sources = sorted(set(configured_sources) - seen_sources)
    if unknown_sources:
        raise ValueError(f"字段映射引用了不存在的数据源：{', '.join(unknown_sources)}")

    combined: dict[str, pd.DataFrame] = {}
    for domain, parts in domain_tables.items():
        if parts:
            combined[domain] = pd.concat(parts, ignore_index=True, sort=False)
    return combined, raw_tables


