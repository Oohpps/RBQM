from __future__ import annotations

import pandas as pd

from .config import SITE_ALIASES, SUBJECT_ALIASES
from .utils import snake_case


def column_matches_alias(column: str, alias: str) -> bool:
    norm = snake_case(alias)
    compact_col = str(column).replace("_", "")
    compact_norm = norm.replace("_", "")
    return (
        column == norm
        or str(column).endswith(f"_{norm}")
        or norm in str(column)
        or compact_col == compact_norm
        or compact_col.endswith(compact_norm)
        or compact_norm in compact_col
    )


def is_status_like_column(column: str | None) -> bool:
    if not column:
        return False
    value = snake_case(column)
    return "status" in value or "状态" in str(column)


def matching_columns(df: pd.DataFrame, aliases: list[str], skip_status: bool = False) -> list[str]:
    columns: list[str] = []
    for alias in aliases:
        for column in df.columns:
            if column_matches_alias(str(column), alias) and (not skip_status or not is_status_like_column(str(column))):
                if column not in columns:
                    columns.append(column)
    return columns


def coalesced_text(df: pd.DataFrame, columns: list[str]) -> pd.Series | None:
    if not columns:
        return None
    values = df[columns].bfill(axis=1).iloc[:, 0]
    return values.where(values.notna(), "").astype(str)


def normalize_site_series(values: pd.Series | None) -> pd.Series | None:
    if values is None:
        return None
    text = values.astype(str).str.strip()
    text = text.str.replace(r"\.0$", "", regex=True)
    return text.map(lambda value: value.zfill(3) if value.isdigit() else value)


def enrich_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    enriched: dict[str, pd.DataFrame] = {}
    subject_to_site: dict[str, str] = {}

    subjects = tables.get("subjects", pd.DataFrame()).copy()
    if not subjects.empty:
        subject_values = coalesced_text(subjects, matching_columns(subjects, SUBJECT_ALIASES, skip_status=True))
        site_values = coalesced_text(subjects, matching_columns(subjects, SITE_ALIASES))
        site_values = normalize_site_series(site_values)
        if subject_values is not None:
            subjects["__subject_id"] = subject_values
        if site_values is not None:
            subjects["__site_id"] = site_values
        elif "__subject_id" in subjects:
            subjects["__site_id"] = "Unknown"
        if "__subject_id" in subjects and "__site_id" in subjects:
            subject_to_site = dict(zip(subjects["__subject_id"], subjects["__site_id"]))
        enriched["subjects"] = subjects

    for domain, source in tables.items():
        if domain == "subjects":
            continue
        df = source.copy()
        subject_values = coalesced_text(df, matching_columns(df, SUBJECT_ALIASES, skip_status=True))
        site_values = coalesced_text(df, matching_columns(df, SITE_ALIASES))
        site_values = normalize_site_series(site_values)
        if subject_values is not None:
            df["__subject_id"] = subject_values
        if site_values is not None:
            df["__site_id"] = site_values
        elif "__subject_id" in df and subject_to_site:
            df["__site_id"] = df["__subject_id"].map(subject_to_site).fillna("Unknown")
        else:
            df["__site_id"] = "Unknown"
        enriched[domain] = df
    return enriched


