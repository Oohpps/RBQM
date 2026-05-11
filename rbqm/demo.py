from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from .utils import standardize_columns

TODAY = pd.Timestamp(date.today())

def generate_demo_data(seed: int = 20260510) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    sites = [f"S{i:03d}" for i in range(1, 13)]
    countries = ["China", "United States", "Poland", "Brazil"]
    risk_factor = {site: rng.uniform(0.4, 1.8) for site in sites}
    risk_factor["S003"] = 2.4
    risk_factor["S008"] = 2.1
    risk_factor["S011"] = 1.9

    subject_rows: list[dict[str, Any]] = []
    start_date = pd.Timestamp("2025-10-01")
    for idx, site in enumerate(sites):
        count = int(rng.integers(22, 58))
        for sub in range(1, count + 1):
            enrolled_date = start_date + pd.Timedelta(days=int(rng.integers(0, 180)))
            subject_rows.append(
                {
                    "subject_id": f"{site}-{sub:03d}",
                    "site_id": site,
                    "country": countries[idx % len(countries)],
                    "status": rng.choice(["Active", "Completed", "Early Terminated"], p=[0.55, 0.35, 0.10]),
                    "enrolled_date": enrolled_date,
                    "randomized_date": enrolled_date + pd.Timedelta(days=int(rng.integers(0, 10))),
                }
            )
    subjects = pd.DataFrame(subject_rows)

    visits = []
    for row in subjects.itertuples(index=False):
        factor = risk_factor[row.site_id]
        for visit_no in range(1, 6):
            visit_date = pd.Timestamp(row.randomized_date) + pd.Timedelta(days=28 * (visit_no - 1))
            delay = max(0, int(rng.normal(2.5 * factor, 3.5)))
            completion_probability = max(0.72, 0.98 - 0.045 * factor)
            completed = rng.random() < completion_probability
            endpoint_missing = rng.random() < min(0.28, 0.035 * factor)
            visits.append(
                {
                    "subject_id": row.subject_id,
                    "site_id": row.site_id,
                    "visit": f"V{visit_no}",
                    "visit_date": visit_date,
                    "data_entry_date": visit_date + pd.Timedelta(days=delay) if completed else pd.NaT,
                    "form_status": "Complete" if completed else "Incomplete",
                    "primary_endpoint": np.nan if endpoint_missing else rng.normal(52, 12),
                    "egfr": np.nan if rng.random() < 0.02 * factor else rng.normal(82, 18),
                }
            )
    visits_df = pd.DataFrame(visits)

    query_rows = []
    for row in subjects.itertuples(index=False):
        factor = risk_factor[row.site_id]
        query_count = int(rng.poisson(0.45 * factor))
        for query_no in range(query_count):
            opened = TODAY - pd.Timedelta(days=int(rng.integers(2, 60)))
            is_closed = rng.random() < max(0.30, 0.80 - 0.14 * factor)
            closed = opened + pd.Timedelta(days=int(rng.integers(1, 24))) if is_closed else pd.NaT
            age_days = (closed - opened).days if is_closed else (TODAY - opened).days
            query_rows.append(
                {
                    "subject_id": row.subject_id,
                    "site_id": row.site_id,
                    "form": rng.choice(["AE", "Labs", "Visit", "Exposure", "Eligibility"]),
                    "field": rng.choice(["Date", "Result", "Outcome", "Endpoint", "Dose"]),
                    "query_status": "Closed" if is_closed else "Open",
                    "opened_date": opened,
                    "closed_date": closed,
                    "age_days": age_days,
                }
            )
    queries = pd.DataFrame(query_rows)

    ae_rows = []
    for row in subjects.itertuples(index=False):
        factor = risk_factor[row.site_id]
        ae_count = int(rng.poisson(0.30 + 0.16 * factor))
        for _ in range(ae_count):
            serious = rng.random() < 0.09
            missing_followup = serious and rng.random() < min(0.45, 0.08 * factor)
            ae_rows.append(
                {
                    "subject_id": row.subject_id,
                    "site_id": row.site_id,
                    "ae_term": rng.choice(["Headache", "Nausea", "ALT increased", "Fatigue", "Dizziness"]),
                    "serious": "Yes" if serious else "No",
                    "severity": np.nan if missing_followup else rng.choice(["Mild", "Moderate", "Severe"], p=[0.55, 0.35, 0.10]),
                    "outcome": np.nan if missing_followup else rng.choice(["Recovered", "Recovering", "Ongoing"]),
                    "start_date": TODAY - pd.Timedelta(days=int(rng.integers(5, 160))),
                }
            )
    ae = pd.DataFrame(ae_rows)

    lab_rows = []
    tests = {
        "ALT": (0, 40, 24, 18),
        "AST": (0, 40, 22, 16),
        "HGB": (120, 175, 142, 16),
        "eGFR": (60, 140, 86, 22),
    }
    for row in subjects.itertuples(index=False):
        factor = risk_factor[row.site_id]
        for test, (lln, uln, mean, sd) in tests.items():
            for visit_no in range(1, 4):
                result = rng.normal(mean, sd)
                if rng.random() < 0.025 * factor:
                    result = uln + abs(rng.normal(18, 12))
                out_of_range = result < lln or result > uln
                reviewed = not (out_of_range and rng.random() < min(0.60, 0.12 * factor))
                lab_rows.append(
                    {
                        "subject_id": row.subject_id,
                        "site_id": row.site_id,
                        "visit": f"V{visit_no}",
                        "test": test,
                        "result": round(float(result), 1),
                        "lln": lln,
                        "uln": uln,
                        "reviewed": "Yes" if reviewed else "No",
                        "collection_date": TODAY - pd.Timedelta(days=int(rng.integers(1, 180))),
                    }
                )
    labs = pd.DataFrame(lab_rows)

    deviation_rows = []
    for row in subjects.itertuples(index=False):
        factor = risk_factor[row.site_id]
        deviation_count = int(rng.poisson(0.12 * factor))
        for _ in range(deviation_count):
            deviation_rows.append(
                {
                    "subject_id": row.subject_id,
                    "site_id": row.site_id,
                    "deviation_type": rng.choice(["Visit Window", "Eligibility", "IP Compliance", "Procedure Missed"]),
                    "severity": rng.choice(["Minor", "Major", "Critical"], p=[0.62, 0.30, 0.08]),
                    "status": rng.choice(["Open", "Closed"], p=[0.42, 0.58]),
                    "deviation_date": TODAY - pd.Timedelta(days=int(rng.integers(3, 150))),
                }
            )
    deviations = pd.DataFrame(deviation_rows)

    dosing_rows = []
    for row in subjects.itertuples(index=False):
        factor = risk_factor[row.site_id]
        for cycle in range(1, 4):
            toxicity_modification = rng.random() < min(0.35, 0.035 * factor)
            dosing_rows.append(
                {
                    "subject_id": row.subject_id,
                    "site_id": row.site_id,
                    "cycle": cycle,
                    "dose_level": rng.choice(["DL1", "DL2", "DL3", "DL4"]),
                    "dose_modified": "Yes" if toxicity_modification else "No",
                    "modification_reason": "Toxicity" if toxicity_modification else "",
                    "administration_date": TODAY - pd.Timedelta(days=int(rng.integers(5, 120))),
                }
            )
    dosing = pd.DataFrame(dosing_rows)

    pk_rows = []
    for row in subjects.itertuples(index=False):
        factor = risk_factor[row.site_id]
        for timepoint in ["C1D1 pre-dose", "C1D1 2h", "C1D8"]:
            scheduled = TODAY - pd.Timedelta(days=int(rng.integers(5, 90)))
            deviated = rng.random() < min(0.32, 0.04 * factor)
            pk_rows.append(
                {
                    "subject_id": row.subject_id,
                    "site_id": row.site_id,
                    "timepoint": timepoint,
                    "scheduled_sample_time": scheduled,
                    "actual_sample_time": scheduled + pd.Timedelta(hours=int(rng.integers(0, 8) if deviated else rng.integers(0, 2))),
                    "window_deviation": "Yes" if deviated else "No",
                }
            )
    pk = pd.DataFrame(pk_rows)

    tumor_rows = []
    for row in subjects.itertuples(index=False):
        factor = risk_factor[row.site_id]
        for assessment_no in range(1, 3):
            scheduled = pd.Timestamp(row.randomized_date) + pd.Timedelta(days=56 * assessment_no)
            issue = rng.random() < min(0.30, 0.035 * factor)
            tumor_rows.append(
                {
                    "subject_id": row.subject_id,
                    "site_id": row.site_id,
                    "assessment": f"RECIST-{assessment_no}",
                    "scheduled_assessment_date": scheduled,
                    "actual_assessment_date": scheduled + pd.Timedelta(days=int(rng.integers(0, 25))) if not issue else pd.NaT,
                    "response": np.nan if issue else rng.choice(["CR", "PR", "SD", "PD"], p=[0.02, 0.18, 0.56, 0.24]),
                }
            )
    tumor = pd.DataFrame(tumor_rows)

    return {
        "subjects": standardize_columns(subjects),
        "visits": standardize_columns(visits_df),
        "queries": standardize_columns(queries),
        "ae": standardize_columns(ae),
        "dosing": standardize_columns(dosing),
        "pk": standardize_columns(pk),
        "tumor": standardize_columns(tumor),
        "labs": standardize_columns(labs),
        "deviations": standardize_columns(deviations),
    }


