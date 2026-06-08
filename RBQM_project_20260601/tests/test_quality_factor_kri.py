import tempfile
import unittest
from pathlib import Path

import pandas as pd

import backend.main as main
from app import Thresholds, compute_metrics
from rbqm.settings_store import KriConfigStore


class QualityFactorKriTests(unittest.TestCase):
    def test_efficacy_missing_rates_score_and_signal_by_threshold(self):
        thresholds = Thresholds(
            edc_visit_entry_delay_days=30.0,
            page_missing_days_all=30.0,
            page_missing_days_without_lab=30.0,
            avg_open_query_age_days=30.0,
            page_sdv_pending_rate=42.0,
            logline_sdv_pending_rate=42.0,
            manual_query_reissue_rate=0.10,
            hba1c_missing_rate=0.15,
            weight_missing_rate=0.15,
            enabled_metrics=("hba1c_missing_rate", "weight_missing_rate"),
        )
        tables = {
            "subjects": pd.DataFrame(
                {
                    "__site_id": ["S001", "S001", "S001", "S001"],
                    "__subject_id": ["S001-001", "S001-002", "S001-003", "S001-004"],
                }
            ),
            "visits": pd.DataFrame(
                {
                    "__site_id": ["S001", "S001", "S001", "S001"],
                    "__subject_id": ["S001-001", "S001-002", "S001-003", "S001-004"],
                    "visit": ["W24", "W24", "W24", "W24"],
                    "hba1c": [None, 6.8, None, 7.1],
                    "weight": [70.0, None, 80.0, None],
                }
            ),
        }

        metrics, signals = compute_metrics(tables, thresholds)

        self.assertEqual(float(metrics.loc[0, "hba1c_missing_rate"]), 0.5)
        self.assertEqual(float(metrics.loc[0, "weight_missing_rate"]), 0.5)
        self.assertEqual(float(metrics.loc[0, "risk_score"]), 100.0)
        self.assertEqual(set(signals["signal"]), {"HbA1c数据缺失比例偏高", "体重数据缺失比例偏高"})

    def test_kri_catalog_exposes_quality_factor_thresholds(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_store = main.CONFIG_STORE
            main.CONFIG_STORE = KriConfigStore(Path(temp_dir) / "config")
            try:
                catalog = main.kri_catalog()
            finally:
                main.CONFIG_STORE = original_store
        keys = {item["key"] for item in catalog["metrics"]}

        self.assertIn("hba1c_missing_rate", keys)
        self.assertIn("pregnancy_rate", keys)
        self.assertIn("data_consistency_issue_days", keys)
        hba1c = next(item for item in catalog["metrics"] if item["key"] == "hba1c_missing_rate")
        self.assertEqual(hba1c["value"], 0.15)
        self.assertTrue(hba1c["enabled"])


if __name__ == "__main__":
    unittest.main()
