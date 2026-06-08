from __future__ import annotations

import re
from typing import Any

import pandas as pd

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
    columns = list(df.columns)
    # Exact match first
    for alias in aliases:
        norm = snake_case(alias)
        if norm in columns:
            return norm
    # Substring match: find best (longest alias match, preferring shorter col name)
    best: str | None = None
    best_score = -1
    for alias in aliases:
        alias_lower = alias.lower()
        for col in columns:
            col_lower = col.lower()
            if alias_lower not in col_lower:
                continue
            # Skip unit columns (e.g. hcgorresu = unit, not result)
            if col_lower.endswith("u") and col_lower.rstrip("u").endswith("orres"):
                continue
            if col_lower.endswith("unit") or col_lower.endswith("orresu"):
                continue
            score = len(alias) * 100 - len(col)
            if score > best_score:
                best_score = score
                best = col
    return best


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


