import unittest

import pandas as pd

from backend.main import kri_drilldowns
from rbqm.metrics import compute_metrics
from rbqm.models import Thresholds


class AllCentersInQtlTests(unittest.TestCase):
    def test_each_qtl_contains_centers_from_all_imported_datasets(self):
        tables = {
            "subjects": pd.DataFrame(
                {
                    "__site_id": ["S001"],
                    "__subject_id": ["S001-001"],
                    "age": [50],
                    "sex": ["M"],
                }
            ),
            "visits": pd.DataFrame(
                {
                    "__site_id": ["S002"],
                    "__subject_id": ["S002-001"],
                    "__source_name": ["FormExcel.xlsx::筛选期体重"],
                    "visit": ["Baseline"],
                    "bmi": [28.0],
                }
            ),
            "queries": pd.DataFrame(
                {
                    "__site_id": ["S003"],
                    "__subject_id": ["S003-001"],
                    "query_status": ["Open"],
                }
            ),
        }
        thresholds = Thresholds()

        metrics, _ = compute_metrics(tables, thresholds)
        drilldowns = kri_drilldowns(metrics, tables, thresholds)

        expected_sites = {"S001", "S002", "S003"}
        self.assertTrue(drilldowns)
        for item in drilldowns:
            self.assertEqual(
                {row["中心"] for row in item["center_rows"]},
                expected_sites,
                item["key"],
            )


if __name__ == "__main__":
    unittest.main()
