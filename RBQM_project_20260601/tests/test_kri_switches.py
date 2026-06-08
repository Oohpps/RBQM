import unittest
from datetime import date

import pandas as pd

from app import Thresholds, compute_metrics


def make_thresholds(kri_enabled=True, enabled_metrics=("page_missing_days_all",)):
    return Thresholds(
        edc_visit_entry_delay_days=7.0,
        page_missing_days_all=7.0,
        page_missing_days_without_lab=7.0,
        avg_open_query_age_days=21.0,
        page_sdv_pending_rate=7.0,
        logline_sdv_pending_rate=7.0,
        manual_query_reissue_rate=0.10,
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
                    "critical_endpoint": [1, 2],
                }
            ),
            "queries": pd.DataFrame(
                {
                    "__site_id": ["S001"],
                    "__subject_id": ["S001-001"],
                    "query_status": ["Open"],
                    "opened_date": [pd.Timestamp("2026-01-01")],
                }
            ),
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
        ten_days_ago = pd.Timestamp(date.today()) - pd.Timedelta(days=10)
        tables = {
            **self.tables,
            "visits": pd.DataFrame(
                {
                    "__site_id": ["S001", "S001"],
                    "__subject_id": ["S001-001", "S001-002"],
                    "visit_date": [ten_days_ago, pd.Timestamp(date.today())],
                    "form_status": ["Missing", "Complete"],
                }
            ),
        }
        metrics, signals = compute_metrics(tables, make_thresholds(enabled_metrics=("page_missing_days_all",)))

        self.assertEqual(float(metrics.loc[0, "risk_score"]), 100.0)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals.iloc[0]["signal"], "页面缺失天数（全部）偏长")

    def test_page_missing_metric_generates_signal(self):
        ten_days_ago = pd.Timestamp(date.today()) - pd.Timedelta(days=10)
        tables = {
            **self.tables,
            "visits": pd.DataFrame(
                {
                    "__site_id": ["S001", "S001"],
                    "__subject_id": ["S001-001", "S001-002"],
                    "visit_date": [ten_days_ago, pd.Timestamp(date.today())],
                    "form_status": ["Missing", "Complete"],
                }
            ),
        }

        metrics, signals = compute_metrics(tables, make_thresholds(enabled_metrics=("page_missing_days_all",)))

        self.assertEqual(float(metrics.loc[0, "page_missing_days_all"]), 10.0)
        self.assertEqual(signals.iloc[0]["signal"], "页面缺失天数（全部）偏长")

    def test_page_sdv_metric_generates_signal(self):
        ten_days_ago = pd.Timestamp(date.today()) - pd.Timedelta(days=10)
        tables = {
            **self.tables,
            "visits": pd.DataFrame(
                {
                    "__site_id": ["S001", "S001"],
                    "__subject_id": ["S001-001", "S001-002"],
                    "__source_name": ["HS-20094-302_进展报告_.xlsx::未SDV（页面）", "HS-20094-302_进展报告_.xlsx::未SDV（页面）"],
                    "visit_date": [ten_days_ago, pd.Timestamp(date.today())],
                    "sdv_status": ["Pending", "Complete"],
                }
            ),
        }

        metrics, signals = compute_metrics(tables, make_thresholds(enabled_metrics=("page_sdv_pending_rate",)))

        self.assertEqual(float(metrics.loc[0, "page_sdv_pending_rate"]), 5.0)
        self.assertTrue(signals.empty)

    def test_logline_sdv_metric_generates_signal(self):
        tables = {
            **self.tables,
            "visits": pd.DataFrame(
                {
                    "__site_id": ["S001"],
                    "__subject_id": ["S001-001"],
                    "__source_name": ["HS-20094-302_进展报告_.xlsx::未SDV（Logline ）"],
                    "距今天数": ["12 / 0"],
                    "sdv_status": [0],
                }
            ),
        }

        metrics, signals = compute_metrics(tables, make_thresholds(enabled_metrics=("logline_sdv_pending_rate",)))

        self.assertEqual(float(metrics.loc[0, "logline_sdv_pending_rate"]), 12.0)
        self.assertEqual(signals.iloc[0]["signal"], "未SDV（logline）天数偏长")


if __name__ == "__main__":
    unittest.main()
