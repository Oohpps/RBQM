from __future__ import annotations

from dataclasses import dataclass

KRI_METRIC_KEYS = (
    "edc_visit_entry_delay_days",
    "page_missing_days_all",
    "page_missing_days_without_lab",
    "avg_open_query_age_days",
    "page_sdv_pending_rate",
    "logline_sdv_pending_rate",
    "manual_query_reissue_rate",
)


@dataclass(frozen=True)
class Thresholds:
    edc_visit_entry_delay_days: float
    page_missing_days_all: float
    page_missing_days_without_lab: float
    avg_open_query_age_days: float
    page_sdv_pending_rate: float
    logline_sdv_pending_rate: float
    manual_query_reissue_rate: float
    kri_enabled: bool = True
    enabled_metrics: tuple[str, ...] = KRI_METRIC_KEYS


