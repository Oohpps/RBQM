import unittest

import pandas as pd

from app import Thresholds, compute_metrics


def make_thresholds(kri_enabled=True, enabled_metrics=("missing_rate",)):
    return Thresholds(
        missing_rate=0.50,
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
        kri_enabled=kri_enabled,
        enabled_metrics=enabled_metrics,
    )


class KRISwitchTests(unittest.TestCase):
    def setUp(self):
        self.tables = {
            "subjects": pd.DataFrame(
                {
                    "__site_id": ["S001", "S001"],
                    "__subject_id": ["S001-001", "S001-002"],
                    "critical_endpoint": [None, None],
                }
            )
        }

    def test_global_kri_switch_disables_scores_and_signals(self):
        metrics, signals = compute_metrics(self.tables, make_thresholds(kri_enabled=False))

        self.assertEqual(float(metrics.loc[0, "risk_score"]), 0.0)
        self.assertEqual(metrics.loc[0, "risk_level"], "低")
        self.assertTrue(signals.empty)

    def test_disabled_metric_is_excluded_from_scores_and_signals(self):
        metrics, signals = compute_metrics(self.tables, make_thresholds(enabled_metrics=()))

        self.assertEqual(float(metrics.loc[0, "risk_score"]), 0.0)
        self.assertTrue(signals.empty)

    def test_enabled_metric_scores_with_normalized_weight(self):
        metrics, signals = compute_metrics(self.tables, make_thresholds(enabled_metrics=("missing_rate",)))

        self.assertEqual(float(metrics.loc[0, "risk_score"]), 100.0)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals.iloc[0]["signal"], "缺失数据")

    def test_phase_one_oncology_dlt_metric_generates_signal(self):
        tables = {
            **self.tables,
            "ae": pd.DataFrame(
                {
                    "__site_id": ["S001"],
                    "__subject_id": ["S001-001"],
                    "dlt": ["Yes"],
                    "ctcae_grade": [3],
                }
            ),
        }

        metrics, signals = compute_metrics(tables, make_thresholds(enabled_metrics=("dlt_rate",)))

        self.assertEqual(float(metrics.loc[0, "dlt_rate"]), 0.5)
        self.assertEqual(signals.iloc[0]["signal"], "DLT发生率过高")


if __name__ == "__main__":
    unittest.main()
