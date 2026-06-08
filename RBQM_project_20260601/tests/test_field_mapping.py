import json
import unittest
from io import BytesIO

import pandas as pd

from app import preview_uploaded_files, read_uploaded_files


class NamedBytesIO(BytesIO):
    def __init__(self, name, payload):
        super().__init__(payload)
        self.name = name


def excel_upload(name, sheets):
    payload = BytesIO()
    with pd.ExcelWriter(payload, engine="openpyxl") as writer:
        for sheet_name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=sheet_name, index=False)
    payload.seek(0)
    return NamedBytesIO(name, payload.getvalue())


class FieldMappingTests(unittest.TestCase):
    def test_preview_lists_each_sheet_with_columns_and_guessed_domain(self):
        upload = excel_upload(
            "study.xlsx",
            {
                "Demography": pd.DataFrame({"Subject No": ["S001-001"], "Center No": ["S001"]}),
                "AE": pd.DataFrame({"Subject No": ["S001-001"], "Toxicity Grade": [3]}),
            },
        )

        preview = preview_uploaded_files([upload])

        self.assertEqual([item["source_id"] for item in preview["sources"]], ["study.xlsx::Demography", "study.xlsx::AE"])
        self.assertEqual(preview["sources"][0]["columns"], ["Subject No", "Center No"])
        self.assertEqual(preview["sources"][1]["guessed_domain"], "ae")

    def test_explicit_mapping_overrides_source_and_column_guessing(self):
        upload = excel_upload(
            "neutral.xlsx",
            {
                "Sheet1": pd.DataFrame(
                    {
                        "Participant Code": ["S001-001", "S001-002"],
                        "Clinic Code": ["S001", "S002"],
                    }
                )
            },
        )
        mapping = {
            "sources": {
                "neutral.xlsx::Sheet1": {
                    "domain": "subjects",
                    "fields": {
                        "subject_id": "Participant Code",
                        "site_id": "Clinic Code",
                    },
                }
            }
        }

        tables, _ = read_uploaded_files([upload], mapping)

        self.assertIn("subjects", tables)
        self.assertEqual(tables["subjects"]["subject_id"].tolist(), ["S001-001", "S001-002"])
        self.assertEqual(tables["subjects"]["site_id"].tolist(), ["S001", "S002"])

    def test_mapping_rejects_missing_source_column(self):
        upload = excel_upload("neutral.xlsx", {"Sheet1": pd.DataFrame({"Subject": ["S001-001"]})})
        mapping = {
            "sources": {
                "neutral.xlsx::Sheet1": {
                    "domain": "subjects",
                    "fields": {"site_id": "Missing Column"},
                }
            }
        }

        with self.assertRaisesRegex(ValueError, "Missing Column"):
            read_uploaded_files([upload], mapping)

    def test_json_mapping_config_is_accepted(self):
        upload = NamedBytesIO("unknown.csv", b"Participant,Clinic\nS001-001,S001\n")
        mapping = json.dumps(
            {
                "sources": {
                    "unknown.csv": {
                        "domain": "subjects",
                        "fields": {"subject_id": "Participant", "site_id": "Clinic"},
                    }
                }
            }
        )

        tables, _ = read_uploaded_files([upload], mapping)

        self.assertEqual(tables["subjects"]["site_id"].tolist(), ["S001"])

    def test_clinical_role_reads_only_supported_sheets_when_possible(self):
        upload = excel_upload(
            "FormExcel.xlsx",
            {
                "AE": pd.DataFrame({"Subject No": ["S001-001"], "Toxicity Grade": [3]}),
                "Unused": pd.DataFrame({"Notes": ["not used by RBQM"]}),
            },
        )

        tables, raw = read_uploaded_files([upload], source_roles=json.dumps({"FormExcel.xlsx": "clinical_data"}))

        self.assertIn("ae", tables)
        self.assertEqual(list(raw), ["FormExcel.xlsx::AE"])

    def test_clinical_role_falls_back_to_all_sheets_if_none_are_recognized(self):
        upload = excel_upload(
            "FormExcel.xlsx",
            {
                "Sheet1": pd.DataFrame({"Notes": ["keep available"]}),
                "Sheet2": pd.DataFrame({"Other": [1]}),
            },
        )

        _, raw = read_uploaded_files([upload], source_roles=json.dumps({"FormExcel.xlsx": "clinical_data"}))

        self.assertEqual(list(raw), ["FormExcel.xlsx::Sheet1", "FormExcel.xlsx::Sheet2"])


if __name__ == "__main__":
    unittest.main()
