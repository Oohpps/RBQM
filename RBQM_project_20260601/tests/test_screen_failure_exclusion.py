import unittest

import pandas as pd

from backend.main import kri_drilldowns
from rbqm.metrics import available_sites, compute_metrics, exclude_screen_failure_subjects
from rbqm.models import Thresholds


class ScreenFailureExclusionTests(unittest.TestCase):
    def test_risk_metrics_exclude_screen_failures_and_use_screening_weight_bmi(self):
        tables = {
            "subjects": pd.DataFrame(
                {
                    "__site_id": ["S001", "S001", "S002"],
                    "__subject_id": ["S001-001", "S001-002", "S002-001"],
                    "subject_status": ["已入组", "筛选失败", "筛选失败"],
                    "age": [50, 80, 70],
                    "sex": ["F", "M", "M"],
                }
            ),
            "visits": pd.DataFrame(
                {
                    "__site_id": ["S001", "S001", "S001", "S002"],
                    "__subject_id": ["S001-001", "S001-002", "S001-001", "S002-001"],
                    "__source_name": [
                        "FormExcel.xlsx::VS_W",
                        "FormExcel.xlsx::VS_W",
                        "FormExcel.xlsx::其他访视体重",
                        "FormExcel.xlsx::VS_W",
                    ],
                    "数据节": ["筛选期（W-2~D-1）", "筛选期（W-2~D-1）", "Week 12", "筛选期（W-2~D-1）"],
                    "BMI(Derived)(BMI)": [28.0, 38.0, 35.0, 40.0],
                }
            ),
        }

        sites = available_sites(tables)
        risk_tables = exclude_screen_failure_subjects(tables)
        metrics, _ = compute_metrics(risk_tables, Thresholds(), sites=sites)
        by_site = metrics.set_index("site_id")

        self.assertEqual(float(by_site.loc["S001", "subjects"]), 1.0)
        self.assertEqual(float(by_site.loc["S001", "avg_age_years"]), 50.0)
        self.assertEqual(float(by_site.loc["S001", "male_rate"]), 0.0)
        self.assertEqual(float(by_site.loc["S001", "baseline_bmi_avg"]), 28.0)
        self.assertEqual(float(by_site.loc["S001", "bmi_over_35_count"]), 0.0)
        self.assertEqual(float(by_site.loc["S002", "subjects"]), 0.0)
        self.assertEqual(float(by_site.loc["S002", "baseline_bmi_avg"]), 0.0)

        age_item = next(item for item in kri_drilldowns(metrics, risk_tables, Thresholds()) if item["key"] == "avg_age_years")
        self.assertEqual(age_item["details"], [{"中心": "S001", "受试者编号": "S001-001", "年龄": 50.0}])
        sex_item = next(item for item in kri_drilldowns(metrics, risk_tables, Thresholds()) if item["key"] == "male_rate")
        self.assertEqual(sex_item["details"], [{"中心": "S001", "受试者编号": "S001-001", "性别": "女性"}])
        bmi_item = next(item for item in kri_drilldowns(metrics, risk_tables, Thresholds()) if item["key"] == "baseline_bmi_avg")
        self.assertEqual(bmi_item["details"], [{
            "中心": "S001",
            "受试者编号": "S001-001",
            "访视": "筛选期（W-2~D-1）",
            "BMI": 28.0,
            "BMI分组": "BMI 24-30",
            "中心均值": 28.0,
        }])

    def test_bmi_uses_fasting_weight_derived_bmi_column(self):
        tables = {
            "visits": pd.DataFrame(
                {
                    "__site_id": ["S001", "S001", "S001", "S001", "S001"],
                    "__subject_id": ["S001-001", "S001-002", "S001-003", "S001-004", "S001-005"],
                    "__source_name": [
                        "FormExcel.xlsx::VS_W",
                        "FormExcel.xlsx::空腹体重",
                        "FormExcel.xlsx::Fasting Weight",
                        "FormExcel.xlsx::Other Weight",
                        "FormExcel.xlsx::VS_WL",
                    ],
                    "数据节": ["筛选期（W-2~D-1）", "Screening", "Week 12", "Screening", "Screening"],
                    "BMI(Derived)(BMI)": [28.0, 32.0, 40.0, 22.0, 23.0],
                    "bmi": [99.0, 99.0, 99.0, 99.0, 99.0],
                }
            )
        }

        metrics, _ = compute_metrics(tables, Thresholds())
        item = next(item for item in kri_drilldowns(metrics, tables, Thresholds()) if item["key"] == "baseline_bmi_avg")

        self.assertEqual(float(metrics.loc[0, "baseline_bmi_avg"]), 30.0)
        self.assertEqual(float(metrics.loc[0, "bmi_30_35_rate"]), 0.5)
        self.assertEqual([row["BMI"] for row in item["details"]], [28.0, 32.0])

    def test_baseline_hba1c_uses_screening_hba1c_page_only(self):
        tables = {
            "visits": pd.DataFrame(
                {
                    "__site_id": ["S001", "S001", "S001"],
                    "__subject_id": ["S001-001", "S001-002", "S001-003"],
                    "__source_name": [
                        "FormExcel.xlsx::糖化血红蛋白",
                        "FormExcel.xlsx::糖化血红蛋白",
                        "FormExcel.xlsx::糖化血红蛋白",
                    ],
                    "数据节": ["筛选期（W-2~D-1）", "筛选期(W-2～D-1)", "治疗期（W12）"],
                    "hba1c": [8.0, 9.0, 12.0],
                }
            ),
        }
        metrics, _ = compute_metrics(tables, Thresholds())
        item = next(item for item in kri_drilldowns(metrics, tables, Thresholds()) if item["key"] == "baseline_hba1c_avg")

        self.assertEqual(float(metrics.loc[0, "baseline_hba1c_avg"]), 8.5)
        self.assertEqual(item["details"], [
            {"中心": "S001", "受试者编号": "S001-001", "访视": "筛选期（W-2~D-1）", "HbA1c": 8.0, "中心均值": 8.5},
            {"中心": "S001", "受试者编号": "S001-002", "访视": "筛选期(W-2～D-1)", "HbA1c": 9.0, "中心均值": 8.5},
        ])

    def test_baseline_hba1c_accepts_percent_values_without_sheet_name_token(self):
        tables = {
            "labs": pd.DataFrame(
                {
                    "__site_id": ["001", "001", "002"],
                    "__subject_id": ["001-001", "001-002", "002-001"],
                    "__source_name": ["FormExcel.xlsx::检查结果"] * 3,
                    "数据节": ["筛选期（W-2~D-1）", "筛选期（W-2 ~ D-1）", "治疗期（W12）"],
                    "实验室指标名称": ["糖化血红蛋白（HbA1c）"] * 3,
                    "HbA1c(%)": ["8.2%", "8.4 %", "7.1%"],
                }
            ),
        }

        metrics, _ = compute_metrics(tables, Thresholds())

        self.assertAlmostEqual(float(metrics.loc[0, "baseline_hba1c_avg"]), 8.3)
        self.assertEqual(float(metrics.loc[1, "baseline_hba1c_avg"]), 0.0)

    def test_baseline_hba1c_uses_result_in_lb_hba1c_instead_of_check_flag(self):
        tables = {
            "labs": pd.DataFrame(
                {
                    "__site_id": ["001", "001", "002"],
                    "__subject_id": ["001-001", "001-002", "002-001"],
                    "__source_name": ["FormExcel.xlsx::LB_HBA1C"] * 3,
                    "数据节": ["筛选期（W-2~D-1）", "筛选期（W-2~D-1）", "治疗期（W0）"],
                    "参与者是否进行HbA1c检查？(LBYN)": ["是", "是", "是"],
                    "实验室指标名称": ["糖化血红蛋白（HbA1c）"] * 3,
                    "结果": [8.1, 8.5, 7.4],
                }
            ),
        }

        metrics, _ = compute_metrics(tables, Thresholds())

        self.assertAlmostEqual(float(metrics.loc[0, "baseline_hba1c_avg"]), 8.3)
        self.assertEqual(float(metrics.loc[1, "baseline_hba1c_avg"]), 0.0)

    def test_baseline_hba1c_does_not_mix_other_screening_lab_results(self):
        tables = {
            "labs": pd.DataFrame(
                {
                    "__site_id": ["001", "001", "001"],
                    "__subject_id": ["001-001", "001-001", "001-002"],
                    "__source_name": [
                        "FormExcel.xlsx::LB_HBA1C",
                        "FormExcel.xlsx::LB_CHEM",
                        "FormExcel.xlsx::LB_HBA1C",
                    ],
                    "数据节": ["筛选期（W-2~D-1）"] * 3,
                    "实验室指标名称": ["糖化血红蛋白（HbA1c）", "丙氨酸氨基转移酶", "糖化血红蛋白（HbA1c）"],
                    "结果": [8.0, 90.0, 8.4],
                }
            ),
        }

        metrics, _ = compute_metrics(tables, Thresholds())

        self.assertAlmostEqual(float(metrics.loc[0, "baseline_hba1c_avg"]), 8.2)

    def test_pregnancy_rate_uses_lb_hcg_positive_results(self):
        tables = {
            "subjects": pd.DataFrame(
                {
                    "__site_id": ["033", "033", "001"],
                    "__subject_id": ["203303", "203305", "200101"],
                    "受试者状态": ["提前退出", "提前退出", "已入组"],
                }
            ),
            "labs": pd.DataFrame(
                {
                    "__site_id": ["033", "033", "001"],
                    "__subject_id": ["203303", "203305", "200101"],
                    "__source_name": ["FormExcel.xlsx::LB_HCG"] * 3,
                    "数据节": ["血/尿妊娠试验"] * 3,
                    "检查日期_lbdat": ["2026-01-28", "2026-02-11", "2026-01-01"],
                    "检查结果_hcgorres": ["阳性", "阳性", "阴性"],
                }
            ),
        }

        metrics, _ = compute_metrics(tables, Thresholds(), sites=available_sites(tables))
        item = next(item for item in kri_drilldowns(metrics, tables, Thresholds()) if item["key"] == "pregnancy_rate")

        self.assertAlmostEqual(float(metrics.set_index("site_id").loc["033", "pregnancy_rate"]), 1.0)
        self.assertEqual([row["受试者编号"] for row in item["details"]], ["203303", "203305"])


if __name__ == "__main__":
    unittest.main()
