from __future__ import annotations

from dataclasses import dataclass

KRI_METRIC_KEYS = (
    "avg_age_years",
    "male_rate",
    "baseline_hba1c_avg",
    "baseline_bmi_avg",
    "bmi_under_24_rate",
    "bmi_30_35_rate",
    "bmi_over_35_count",
    "edc_visit_entry_delay_days",
    "page_missing_days_all",
    "page_missing_days_without_lab",
    "avg_open_query_age_days",
    "page_sdv_pending_rate",
    "logline_sdv_pending_rate",
    "manual_query_reissue_rate",
    "hba1c_missing_rate",
    "weight_missing_rate",
    "concomitant_event_rate",
    "early_termination_rate",
    "pregnancy_rate",
    "data_consistency_issue_days",
)


@dataclass(frozen=True)
class Thresholds:
    avg_age_years: float = 50.0
    male_rate: float = 0.60
    baseline_hba1c_avg: float = 8.5
    baseline_bmi_avg: float = 29.0
    bmi_under_24_rate: float = 0.03
    bmi_30_35_rate: float = 0.15
    bmi_over_35_count: float = 0.0
    edc_visit_entry_delay_days: float = 30.0
    page_missing_days_all: float = 30.0
    page_missing_days_without_lab: float = 30.0
    avg_open_query_age_days: float = 30.0
    page_sdv_pending_rate: float = 42.0
    logline_sdv_pending_rate: float = 42.0
    manual_query_reissue_rate: float = 0.10
    hba1c_missing_rate: float = 0.15
    weight_missing_rate: float = 0.15
    concomitant_event_rate: float = 0.20
    early_termination_rate: float = 0.10
    pregnancy_rate: float = 0.02
    data_consistency_issue_days: float = 30.0
    kri_enabled: bool = True
    enabled_metrics: tuple[str, ...] = KRI_METRIC_KEYS


