from __future__ import annotations

from io import BytesIO
import re
from typing import Any

import pandas as pd

from .config import ACTION_LOG_LABELS, DOMAIN_LABELS, METRIC_LABELS, SIGNAL_LABELS

def display_frame(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    return df.rename(columns=mapping).copy()


def export_localized_frame(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    return display_frame(df, mapping)


def make_excel_export(metrics: pd.DataFrame, signals: pd.DataFrame, action_log: pd.DataFrame, tables: dict[str, pd.DataFrame]) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export_localized_frame(metrics, METRIC_LABELS).to_excel(writer, sheet_name="中心风险排名", index=False)
        export_localized_frame(signals, SIGNAL_LABELS).to_excel(writer, sheet_name="风险信号", index=False)
        export_localized_frame(action_log, ACTION_LOG_LABELS).to_excel(writer, sheet_name="行动跟踪", index=False)
        summary = pd.DataFrame(
            [
                {"数据域": DOMAIN_LABELS.get(domain, domain), "行数": len(df), "列数": len(df.columns)}
                for domain, df in tables.items()
            ]
        )
        summary.to_excel(writer, sheet_name="数据摘要", index=False)
    return output.getvalue()


def safe_sheet_name(name: str, used_names: set[str]) -> str:
    cleaned = re.sub(r"[\[\]\:\*\?\/\\]", "_", str(name)).strip() or "KRI明细"
    base = cleaned[:31]
    candidate = base
    index = 2
    while candidate in used_names:
        suffix = f"_{index}"
        candidate = f"{base[:31 - len(suffix)]}{suffix}"
        index += 1
    used_names.add(candidate)
    return candidate


def make_kri_detail_export(drilldowns: list[dict[str, Any]]) -> bytes:
    output = BytesIO()
    used_names: set[str] = set()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_rows = []
        for item in drilldowns:
            details = item.get("details", [])
            center_rows = item.get("center_rows", [])
            summary_rows.append(
                {
                    "KRI指标": item.get("label", ""),
                    "阈值": item.get("threshold", ""),
                    "单位": item.get("unit", ""),
                    "明细条数": len(details),
                    "超阈值中心数": sum(1 for row in center_rows if int(row.get("超阈值条数") or 0) > 0),
                }
            )

        pd.DataFrame(summary_rows).to_excel(writer, sheet_name=safe_sheet_name("导出说明", used_names), index=False)

        for item in drilldowns:
            label = str(item.get("label", "KRI明细"))
            details = item.get("details", [])
            if details:
                frame = pd.DataFrame(details)
            else:
                frame = pd.DataFrame(
                    [
                        {
                            "KRI指标": label,
                            "阈值": item.get("threshold", ""),
                            "说明": "当前阈值下暂无超阈值明细",
                        }
                    ]
                )
            frame.to_excel(writer, sheet_name=safe_sheet_name(label, used_names), index=False)
    return output.getvalue()
