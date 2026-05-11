from __future__ import annotations

from dataclasses import dataclass

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


