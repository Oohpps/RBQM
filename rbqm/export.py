from __future__ import annotations

from io import BytesIO

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
