import tempfile
import unittest
from pathlib import Path

import backend.main as main
from rbqm.models import KRI_METRIC_KEYS
from rbqm.settings_store import KriConfigStore


def config_payload(**overrides):
    thresholds = {
        "edc_visit_entry_delay_days": 8.0,
        "page_missing_days_all": 8.0,
        "page_missing_days_without_lab": 8.0,
        "avg_open_query_age_days": 25.0,
        "page_sdv_pending_rate": 8.0,
        "logline_sdv_pending_rate": 8.0,
        "manual_query_reissue_rate": 0.12,
    }
    payload = {
        "kri_enabled": True,
        "enabled_metrics": list(KRI_METRIC_KEYS),
        "thresholds": thresholds,
        "saved_by": "unit-test",
        "change_reason": "baseline test config",
    }
    payload.update(overrides)
    return payload


class KriConfigVersionApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.original_store = main.CONFIG_STORE
        main.CONFIG_STORE = KriConfigStore(Path(self.temp_dir.name) / "config")
        self.addCleanup(lambda: setattr(main, "CONFIG_STORE", self.original_store))

    def test_post_config_creates_new_active_version_in_config_folder(self):
        first = main.save_config(main.KriConfigInput(**config_payload()))
        second = main.save_config(
            main.KriConfigInput(
                **config_payload(
                    thresholds={**config_payload()["thresholds"], "manual_query_reissue_rate": 0.18}
                )
            )
        )

        self.assertEqual(first["active"]["version"], 1)
        self.assertEqual(second["active"]["version"], 2)
        self.assertEqual([item["version"] for item in second["versions"]], [1, 2])
        self.assertEqual(second["active"]["thresholds"]["manual_query_reissue_rate"], 0.18)
        self.assertTrue((Path(self.temp_dir.name) / "config" / "kri_config_versions.json").exists())

    def test_saved_active_config_is_used_by_state_when_query_is_absent(self):
        main.save_config(main.KriConfigInput(**config_payload(kri_enabled=False)))

        state = main.get_state(main.thresholds_from_query())

        self.assertFalse(state["kri"]["enabled"])
        self.assertEqual(set(state["overview"].keys()), {"中心数", "受试者数"})


if __name__ == "__main__":
    unittest.main()
