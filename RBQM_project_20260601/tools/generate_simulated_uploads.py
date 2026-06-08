from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


random.seed(20260517)

FORM_PATH = Path(r"C:/Users/81566/Downloads/HS-20094-302_FormExcel_V1.0_202605130936.xlsx")
OUT_DIR = Path(r"E:/RBQM/outputs/simulated_uploads")

META_COLS = {
    "项目编号",
    "表单编号",
    "参与者筛选号",
    "姓名缩写",
    "受试者状态",
    "试验中心编号",
    "试验中心名称",
    "数据节",
    "Instance顺序号",
    "数据块",
    "Block顺序号",
    "数据页",
    "最后修改时间",
    "行号",
}

SUBJECT_COL = "参与者筛选号"
SITE_COL = "试验中心编号"
SITE_NAME_COL = "试验中心名称"
STATUS_COL = "受试者状态"
VISIT_COL = "数据节"
PAGE_COL = "数据页"
FORM_COL = "表单编号"


def subject_text(value: object) -> str:
    if pd.isna(value):
        return ""
    try:
        return str(int(float(value)))
    except Exception:
        return str(value).strip().replace(".0", "")


def site_text(value: object) -> str:
    if pd.isna(value):
        return ""
    try:
        return str(int(float(value))).zfill(3)
    except Exception:
        text = str(value).strip().replace(".0", "")
        return text.zfill(3) if text.isdigit() else text


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    dm = pd.read_excel(FORM_PATH, sheet_name="DM")
    dm = dm[[SUBJECT_COL, STATUS_COL, SITE_COL, SITE_NAME_COL]].dropna(subset=[SUBJECT_COL, SITE_COL]).copy()
    dm[SUBJECT_COL] = dm[SUBJECT_COL].map(subject_text)
    dm[SITE_COL] = dm[SITE_COL].map(site_text)
    subject_status = dict(zip(dm[SUBJECT_COL], dm[STATUS_COL].fillna("")))
    subject_site = dict(zip(dm[SUBJECT_COL], dm[SITE_COL]))
    subject_site_name = dict(zip(dm[SUBJECT_COL], dm[SITE_NAME_COL]))

    ae = pd.read_excel(FORM_PATH, sheet_name="AE")
    sae_col = "是否是严重不良事件(AESER)"
    sae_subjects = set(
        ae.loc[ae[sae_col].astype(str).str.strip().str.upper().isin({"是", "Y", "YES", "TRUE", "1"}), SUBJECT_COL]
        .dropna()
        .map(subject_text)
    )

    xls = pd.ExcelFile(FORM_PATH)
    candidates: list[dict[str, object]] = []
    for sheet in xls.sheet_names:
        if sheet == "TOC" or sheet.startswith("~$"):
            continue
        df = pd.read_excel(FORM_PATH, sheet_name=sheet)
        if SUBJECT_COL not in df.columns or SITE_COL not in df.columns:
            continue
        value_cols = [col for col in df.columns if col not in META_COLS and not str(col).startswith("Unnamed")]
        if not value_cols:
            continue
        for _, row in df.head(900).iterrows():
            subject_id = subject_text(row.get(SUBJECT_COL))
            if not subject_id:
                continue
            for col in random.sample(value_cols, min(len(value_cols), 4)):
                value = row.get(col)
                if pd.isna(value) and random.random() > 0.20:
                    continue
                candidates.append(
                    {
                        "项目编号": row.get("项目编号", "HS-20094-302 [PROD]"),
                        "中心编号": site_text(row.get(SITE_COL)) or subject_site.get(subject_id, ""),
                        "中心名称": row.get(SITE_NAME_COL, subject_site_name.get(subject_id, "")),
                        "受试者编号": subject_id,
                        "受试者状态": row.get(STATUS_COL, subject_status.get(subject_id, "")),
                        "访视名称": row.get(VISIT_COL, ""),
                        "表单编号": row.get(FORM_COL, sheet),
                        "数据页名称": row.get(PAGE_COL, sheet),
                        "字段名称": str(col),
                        "当前值": "" if pd.isna(value) else str(value)[:120],
                    }
                )

    if len(candidates) < 300:
        raise RuntimeError(f"Not enough datapoint candidates: {len(candidates)}")

    critical_pool = random.sample(candidates, min(420, len(candidates)))
    critical_rows: list[dict[str, object]] = []
    seen_critical: set[tuple[object, object, object]] = set()
    for item in critical_pool:
        key = (item["访视名称"], item["数据页名称"], item["字段名称"])
        if key in seen_critical:
            continue
        seen_critical.add(key)
        critical_rows.append(
            {
                "site_id": item["中心编号"],
                "subject_id": item["受试者编号"],
                "visit_name": item["访视名称"],
                "page_name": item["数据页名称"],
                "field_name": item["字段名称"],
                "项目编号": item["项目编号"],
                "中心编号": item["中心编号"],
                "中心名称": item["中心名称"],
                "受试者编号": item["受试者编号"],
                "受试者状态": item["受试者状态"],
                "访视名称": item["访视名称"],
                "数据页名称": item["数据页名称"],
                "字段名称": item["字段名称"],
                "关键数据点类别": random.choice(["主要终点", "安全性", "入排标准", "疗效评估", "关键实验室", "给药暴露"]),
                "来源表单": item["表单编号"],
            }
        )
        if len(critical_rows) >= 320:
            break

    critical_keys = {(row["访视名称"], row["数据页名称"], row["字段名称"]) for row in critical_rows}
    critical_candidates = [item for item in candidates if (item["访视名称"], item["数据页名称"], item["字段名称"]) in critical_keys]
    noncritical_candidates = [item for item in candidates if (item["访视名称"], item["数据页名称"], item["字段名称"]) not in critical_keys]

    query_templates = [
        "请核对该字段取值与源文件是否一致，并补充说明。",
        "该数据点为空或格式异常，请确认是否适用并更新。",
        "该字段与同访视其他页面信息不一致，请复核。",
        "请确认录入日期、访视日期及相关逻辑关系。",
        "该值超出预期范围，请确认是否为录入错误。",
        "请根据监查发现更新该数据点或提供解释。",
        "请核对单位、参考范围和原始记录。",
    ]
    sae_templates = [
        "[SAE Recon] 请核对SAE报告与AE页面信息是否一致。",
        "[SAE Recon] SAE相关日期/转归/严重性字段需复核并补充说明。",
        "[SAE Recon] 请确认该SAE事件是否已完成一致性 reconciliation。",
        "[SAE Recon] 请核对SAE随访信息与EDC录入内容。",
    ]

    statuses = ["Open", "Answered", "Closed", "Open", "Closed"]
    base_date = datetime(2026, 5, 17)
    query_rows: list[dict[str, object]] = []
    for i in range(1, 901):
        pool = critical_candidates if critical_candidates and random.random() < 0.42 else noncritical_candidates
        item = random.choice(pool)
        is_critical = (item["访视名称"], item["数据页名称"], item["字段名称"]) in critical_keys
        is_sae = item["受试者编号"] in sae_subjects and random.random() < 0.45
        if not is_sae and random.random() < 0.055:
            is_sae = True
        opened_days_ago = random.randint(1, 95)
        opened = base_date - timedelta(days=opened_days_ago)
        status = random.choice(statuses)
        if status == "Closed":
            close_after = random.randint(1, min(45, opened_days_ago))
            closed = opened + timedelta(days=close_after)
            age_text = f"{close_after}/0"
        elif status == "Answered":
            close_after = random.randint(1, min(35, opened_days_ago))
            closed = ""
            age_text = f"{close_after}/0"
        else:
            closed = ""
            age_text = f"{opened_days_ago}/0"
        reopen_count = random.choice([0, 0, 0, 1, 1, 2]) if random.random() < 0.28 else 0
        query_text = random.choice(sae_templates if is_sae else query_templates)
        if not query_text.startswith("[SAE Recon]") and random.random() < 0.18:
            query_text += " 请DM人工复核后反馈。"
        query_type_value = "SAE Recon" if is_sae else random.choice(["DM Manual", "DM Manual", "DM Manual", "CRA Manual", "System"])
        query_rows.append(
            {
                "Query ID": f"QRY-{i:05d}",
                "site_id": item["中心编号"],
                "subject_id": item["受试者编号"],
                "visit_name": item["访视名称"],
                "page_name": item["数据页名称"],
                "field_name": item["字段名称"],
                "query_status": status,
                "opened_date": opened.strftime("%Y-%m-%d"),
                "closed_date": closed.strftime("%Y-%m-%d") if isinstance(closed, datetime) else "",
                "age_days": age_text,
                "query_type": query_type_value,
                "reissue_count": reopen_count,
                "sae": "是" if is_sae else "否",
                "critical": "是" if is_critical else "否",
                "query_text": query_text,
                "项目编号": item["项目编号"],
                "中心编号": item["中心编号"],
                "中心名称": item["中心名称"],
                "受试者编号": item["受试者编号"],
                "受试者状态": item["受试者状态"],
                "访视名称": item["访视名称"],
                "数据页名称": item["数据页名称"],
                "字段名称": item["字段名称"],
                "当前值": item["当前值"],
                "Query状态": status,
                "打开日期": opened.strftime("%Y-%m-%d"),
                "关闭日期": closed.strftime("%Y-%m-%d") if isinstance(closed, datetime) else "",
                "打开天数/回答天数": age_text,
                "Query类型": query_type_value,
                "重开次数": reopen_count,
                "是否关键数据点": "是" if is_critical else "否",
                "是否SAE": "是" if is_sae else "否",
                "质疑文本": query_text,
            }
        )

    query_df = pd.DataFrame(query_rows)
    critical_df = pd.DataFrame(critical_rows)

    query_path = OUT_DIR / "HS-20094-302_模拟质疑明细报告.xlsx"
    critical_path = OUT_DIR / "HS-20094-302_模拟关键数据点.xlsx"
    with pd.ExcelWriter(query_path, engine="openpyxl") as writer:
        query_df.to_excel(writer, sheet_name="Query detail", index=False)
    with pd.ExcelWriter(critical_path, engine="openpyxl") as writer:
        critical_df.to_excel(writer, sheet_name="关键数据点", index=False)

    print(query_path)
    print(critical_path)
    print("query rows", len(query_df))
    print("sae recon", int(query_df["质疑文本"].str.startswith("[SAE Recon]").sum()))
    print("critical queries", int((query_df["是否关键数据点"] == "是").sum()))
    print("reissued", int((query_df["重开次数"] > 0).sum()))
    print("critical rows", len(critical_df))
    print("AE SAE subjects from FormExcel AE AESER=是", len(sae_subjects), sorted(sae_subjects)[:10])


if __name__ == "__main__":
    main()
