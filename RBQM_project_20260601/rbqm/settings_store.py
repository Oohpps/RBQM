from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .models import KRI_METRIC_KEYS, Thresholds


class KriConfigStore:
    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir
        self.path = config_dir / "kri_config_versions.json"

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"active_version": None, "versions": []}
        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return {
            "active_version": payload.get("active_version"),
            "versions": list(payload.get("versions", [])),
        }

    def active_record(self, default_thresholds: Thresholds) -> dict[str, Any]:
        payload = self.load()
        active_version = payload.get("active_version")
        for item in payload["versions"]:
            if item.get("version") == active_version:
                return item
        return self.default_record(default_thresholds)

    def active_thresholds(self, default_thresholds: Thresholds) -> Thresholds:
        return thresholds_from_record(self.active_record(default_thresholds), default_thresholds)

    def save(self, thresholds: Thresholds, saved_by: str | None = None, change_reason: str | None = None) -> dict[str, Any]:
        payload = self.load()
        next_version = max([int(item.get("version", 0)) for item in payload["versions"]] or [0]) + 1
        record = {
            "version": next_version,
            "is_active": True,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "saved_by": saved_by or "",
            "change_reason": change_reason or "",
            "kri_enabled": thresholds.kri_enabled,
            "enabled_metrics": list(thresholds.enabled_metrics),
            "thresholds": threshold_values(thresholds),
        }
        for item in payload["versions"]:
            item["is_active"] = False
        payload["versions"].append(record)
        payload["active_version"] = next_version
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return self.response(payload)

    def response(self, payload: dict[str, Any] | None = None, default_thresholds: Thresholds | None = None) -> dict[str, Any]:
        current = payload or self.load()
        active_version = current.get("active_version")
        active = None
        for item in current["versions"]:
            if item.get("version") == active_version:
                active = item
                break
        if active is None and default_thresholds is not None:
            active = self.default_record(default_thresholds)
        elif active is not None and default_thresholds is not None:
            active = normalized_record(active, default_thresholds)
        versions = current["versions"]
        if default_thresholds is not None:
            versions = [normalized_record(item, default_thresholds) for item in versions]
        return {"active": active, "versions": versions}

    @staticmethod
    def default_record(default_thresholds: Thresholds) -> dict[str, Any]:
        return {
            "version": 0,
            "is_active": True,
            "saved_at": "",
            "saved_by": "",
            "change_reason": "Default KRI configuration",
            "kri_enabled": default_thresholds.kri_enabled,
            "enabled_metrics": list(default_thresholds.enabled_metrics),
            "thresholds": threshold_values(default_thresholds),
        }


def threshold_values(thresholds: Thresholds) -> dict[str, float]:
    values = asdict(thresholds)
    values.pop("kri_enabled", None)
    values.pop("enabled_metrics", None)
    return {key: float(values[key]) for key in KRI_METRIC_KEYS}


def thresholds_from_record(record: dict[str, Any], default_thresholds: Thresholds) -> Thresholds:
    saved_values = record.get("thresholds", {})
    defaults = threshold_values(default_thresholds)
    values = {key: float(saved_values.get(key, defaults[key])) for key in KRI_METRIC_KEYS}
    for day_metric in ("page_sdv_pending_rate", "logline_sdv_pending_rate"):
        if values.get(day_metric, 0) < 1:
            values[day_metric] = defaults[day_metric]
    raw_enabled_metrics = tuple(record.get("enabled_metrics", KRI_METRIC_KEYS))
    enabled_set = {metric for metric in raw_enabled_metrics if metric in KRI_METRIC_KEYS}
    enabled_set.update(metric for metric in KRI_METRIC_KEYS if metric not in saved_values)
    if "page_missing_rate" in raw_enabled_metrics:
        enabled_set.update({"page_missing_days_all", "page_missing_days_without_lab"})
    if "page_sdv_pending_rate" in raw_enabled_metrics:
        enabled_set.add("logline_sdv_pending_rate")
    enabled_metrics = tuple(metric for metric in KRI_METRIC_KEYS if metric in enabled_set)
    if not enabled_metrics and raw_enabled_metrics:
        enabled_metrics = KRI_METRIC_KEYS
    return Thresholds(
        **values,
        kri_enabled=bool(record.get("kri_enabled", default_thresholds.kri_enabled)),
        enabled_metrics=enabled_metrics,
    )


def normalized_record(record: dict[str, Any], default_thresholds: Thresholds) -> dict[str, Any]:
    thresholds = thresholds_from_record(record, default_thresholds)
    return {
        **record,
        "enabled_metrics": list(thresholds.enabled_metrics),
        "thresholds": threshold_values(thresholds),
    }
