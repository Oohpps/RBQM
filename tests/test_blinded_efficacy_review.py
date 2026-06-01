import unittest

from backend.main import blinded_efficacy_review


def subject_records(site: str, subject: str, hba1c_baseline: float, hba1c_latest: float, weight_baseline: float, weight_latest: float):
    return [
        {"site_id": site, "subject_id": subject, "metric": "hba1c", "day": 1, "date": "2026-01-01", "visit": "Baseline", "value": hba1c_baseline},
        {"site_id": site, "subject_id": subject, "metric": "hba1c", "day": 2, "date": "2026-06-01", "visit": "Week 24", "value": hba1c_latest},
        {"site_id": site, "subject_id": subject, "metric": "weight", "day": 1, "date": "2026-01-01", "visit": "Baseline", "value": weight_baseline},
        {"site_id": site, "subject_id": subject, "metric": "weight", "day": 2, "date": "2026-06-01", "visit": "Week 24", "value": weight_latest},
    ]


class BlindedEfficacyReviewTests(unittest.TestCase):
    def test_flags_site_with_blinded_efficacy_pattern_far_from_project_distribution(self):
        records = []
        for site_index in range(1, 6):
            site = f"S{site_index:03d}"
            for subject_index in range(1, 4):
                records.extend(subject_records(site, f"{site}-{subject_index:03d}", 8.0, 7.2, 80.0, 78.0))
        for subject_index in range(1, 4):
            records.extend(subject_records("S006", f"S006-{subject_index:03d}", 8.0, 4.0, 80.0, 68.0))

        review = blinded_efficacy_review(records)

        highest_risk = review["site_summary"][0]
        self.assertEqual(highest_risk["中心"], "S006")
        self.assertEqual(highest_risk["风险等级"], "高")
        self.assertIn("HbA1c下降比例偏离项目整体", highest_risk["风险原因"])
        self.assertIn("体重下降值偏离项目整体", highest_risk["风险原因"])
        self.assertEqual(highest_risk["HbA1c平均下降比例（%）"], 50.0)
        self.assertEqual(highest_risk["体重平均下降值（kg）"], 12.0)
        self.assertEqual(highest_risk["HbA1c异常评分"], 100.0)
        self.assertEqual(highest_risk["体重异常评分"], 100.0)
        influential_patients = [row for row in review["subject_summary"] if row["中心"] == "S006"]
        self.assertEqual(len(influential_patients), 3)
        self.assertTrue(all(row["影响等级"] == "高" for row in influential_patients))

    def test_marks_small_site_for_observation_instead_of_high_risk(self):
        review = blinded_efficacy_review(subject_records("S001", "S001-001", 8.0, 7.2, 80.0, 78.0))

        site = review["site_summary"][0]
        self.assertEqual(site["风险等级"], "观察")
        self.assertIn("样本量不足", site["风险原因"])

    def test_highlights_patient_with_missing_weight_follow_up(self):
        records = subject_records("S001", "S001-001", 8.0, 7.2, 80.0, 78.0)
        records += subject_records("S001", "S001-002", 8.0, 7.2, 80.0, 78.0)[:2]

        review = blinded_efficacy_review(records)

        missing_weight = next(row for row in review["subject_summary"] if row["受试者"] == "S001-002")
        self.assertIn("缺少可配对体重随访", missing_weight["影响原因"])
        self.assertGreaterEqual(float(missing_weight["患者影响评分"]), 40.0)

    def test_excludes_screen_failures_from_efficacy_and_reports_site_screen_failure_rate(self):
        records = subject_records("S001", "S001-001", 8.0, 7.2, 80.0, 78.0)
        records += subject_records("S001", "S001-002", 8.0, 4.0, 80.0, 68.0)
        statuses = {
            "S001-001": {"site_id": "S001", "subject_status": "已入组"},
            "S001-002": {"site_id": "S001", "subject_status": "筛选失败"},
        }

        review = blinded_efficacy_review(records, statuses)

        site = review["site_summary"][0]
        self.assertEqual(site["受试者数"], 1)
        self.assertEqual(site["HbA1c平均下降比例（%）"], 10.0)
        self.assertEqual([row["受试者"] for row in review["subject_summary"]], ["S001-001"])
        self.assertEqual(review["screen_failure_summary"], [{
            "中心": "S001",
            "已筛选人数": 2,
            "筛选失败人数": 1,
            "中心筛败率（%）": 50.0,
        }])


if __name__ == "__main__":
    unittest.main()
