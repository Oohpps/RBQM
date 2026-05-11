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


