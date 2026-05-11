from __future__ import annotations

import pandas as pd

from .config import SITE_ALIASES, SUBJECT_ALIASES
from .utils import find_col

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


