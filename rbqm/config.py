from __future__ import annotations

DOMAIN_LABELS = {
    "subjects": "受试者 / 入组",
    "visits": "访视 / EDC表单",
    "queries": "Query / 数据核查",
    "critical_points": "关键数据点",
    "ae": "AE / SAE",
    "dosing": "给药 / 剂量调整",
    "pk": "PK / PD采样",
    "tumor": "肿瘤评估",
    "labs": "实验室",
    "deviations": "方案偏离",
}

DOMAIN_FIELDS = {
    "subjects": ["subject_id", "site_id", "country", "status", "enrolled_date", "randomized_date"],
    "visits": ["subject_id", "site_id", "visit_date", "data_entry_date", "form_status"],
    "queries": ["subject_id", "site_id", "query_status", "opened_date", "closed_date", "age_days"],
    "critical_points": ["subject_id", "site_id", "visit_name", "page_name", "field_name"],
    "ae": ["subject_id", "site_id", "serious", "dlt", "ctcae_grade", "severity", "outcome", "start_date"],
    "dosing": ["subject_id", "site_id", "dose_level", "dose_modified", "modification_reason", "administration_date"],
    "pk": ["subject_id", "site_id", "timepoint", "scheduled_sample_time", "actual_sample_time", "window_deviation"],
    "tumor": ["subject_id", "site_id", "scheduled_assessment_date", "actual_assessment_date", "response"],
    "labs": ["subject_id", "site_id", "result", "lln", "uln", "reviewed"],
    "deviations": ["subject_id", "site_id", "deviation_type", "severity", "status", "deviation_date"],
}

REQUIRED_DOMAIN_FIELDS = {
    domain: ["subject_id", "site_id"] for domain in DOMAIN_FIELDS
}

METRIC_LABELS = {
    "site_id": "中心",
    "subjects": "受试者数",
    "missing_rate": "缺失率",
    "late_entry_rate": "延迟录入率",
    "avg_entry_delay_days": "平均录入延迟（天）",
    "open_queries": "未关闭Query数",
    "open_queries_per_subject": "每受试者未关闭Query数",
    "avg_open_query_age_days": "未关闭Query平均账期（天）",
    "safety_issues": "安全性问题数",
    "safety_issues_per_subject": "每受试者安全性问题数",
    "dlt_events": "DLT事件数",
    "dlt_rate": "DLT发生率",
    "grade3_ae_events": "≥3级AE事件数",
    "grade3_ae_rate": "≥3级AE发生率",
    "dose_modifications": "毒性相关剂量调整数",
    "dose_modification_rate": "毒性相关剂量调整率",
    "eligibility_deviations": "入排标准偏离数",
    "eligibility_deviation_rate": "入排标准偏离率",
    "pk_window_deviations": "PK/PD采样窗偏离数",
    "pk_window_deviation_rate": "PK/PD采样窗偏离率",
    "tumor_assessment_issues": "肿瘤评估缺失/延迟数",
    "tumor_assessment_issue_rate": "肿瘤评估缺失/延迟率",
    "lab_issues": "未复核异常实验室数",
    "lab_issues_per_subject": "每受试者未复核异常实验室数",
    "major_deviations": "重大偏离数",
    "major_deviations_per_subject": "每受试者重大偏离数",
    "Completeness_component": "完整性评分",
    "Timeliness_component": "及时性评分",
    "Query Burden_component": "Query负荷评分",
    "Safety Review_component": "安全性复核评分",
    "Dose Safety_component": "剂量安全评分",
    "Dose Administration_component": "给药调整评分",
    "PK Integrity_component": "PK/PD完整性评分",
    "Tumor Assessment_component": "肿瘤评估评分",
    "Protocol Compliance_component": "方案依从性评分",
    "Data Quality_component": "数据质量评分",
    "Labs and PD_component": "实验室与偏离评分",
    "risk_score": "风险评分",
    "risk_level": "风险等级",
}

SIGNAL_LABELS = {
    "signal_id": "信号编号",
    "site_id": "中心",
    "category": "类别",
    "signal": "风险信号",
    "metric": "指标",
    "value": "当前值",
    "threshold": "阈值",
    "severity": "严重度",
    "risk_score": "风险评分",
    "recommended_action": "建议动作",
}

ACTION_LOG_LABELS = {
    "signal_id": "信号编号",
    "site_id": "中心",
    "signal": "风险信号",
    "severity": "严重度",
    "owner": "责任人",
    "action": "行动",
    "due_date": "截止日期",
    "status": "状态",
    "resolution_comment": "关闭说明",
}

COMPONENT_LABELS = {
    "Completeness_component": "完整性",
    "Timeliness_component": "及时性",
    "Query Burden_component": "Query负荷",
    "Safety Review_component": "安全性",
    "Dose Safety_component": "剂量安全",
    "Dose Administration_component": "给药调整",
    "PK Integrity_component": "PK/PD完整性",
    "Tumor Assessment_component": "肿瘤评估",
    "Protocol Compliance_component": "方案依从性",
    "Labs and PD_component": "实验室与偏离",
}

METRIC_VALUE_LABELS = {
    "missing_rate": "缺失率",
    "late_entry_rate": "延迟录入率",
    "avg_entry_delay_days": "平均录入延迟（天）",
    "open_queries_per_subject": "每受试者未关闭Query数",
    "avg_open_query_age_days": "未关闭Query平均账期（天）",
    "safety_issues_per_subject": "每受试者安全性问题数",
    "dlt_rate": "DLT发生率",
    "grade3_ae_rate": "≥3级AE发生率",
    "dose_modification_rate": "毒性相关剂量调整率",
    "eligibility_deviation_rate": "入排标准偏离率",
    "pk_window_deviation_rate": "PK/PD采样窗偏离率",
    "tumor_assessment_issue_rate": "肿瘤评估缺失/延迟率",
    "lab_issues_per_subject": "每受试者未复核异常实验室数",
    "major_deviations_per_subject": "每受试者重大偏离数",
}

NEW_KRI_LABELS = {
    "data_points": "数据点数",
    "page_missing_days_all": "页面缺失天数（全部）",
    "page_missing_days_without_lab": "页面缺失天数（不含对接LAB）",
    "page_sdv_pending_rate": "未SDV（页面）",
    "logline_sdv_pending_rate": "未SDV（logline）",
    "manual_query_reissue_rate": "人工质疑重发率",
    "edc_visit_entry_delay_days": "EDC访视录入延迟天数",
    "avg_open_query_age_days": "未关闭质疑天数",
}

NEW_COMPONENT_LABELS = {
    "Query Creation_component": "Query创建评分",
    "Query Cycle Time_component": "Query周期评分",
    "Query Rework_component": "Query返工评分",
    "EDC Timeliness_component": "EDC及时性评分",
    "Page Quality_component": "页面质量评分",
    "SAE Reporting_component": "SAE报告评分",
    "Abnormal Trends_component": "异常趋势评分",
}

METRIC_LABELS.update(NEW_KRI_LABELS)
METRIC_LABELS.update(NEW_COMPONENT_LABELS)
METRIC_VALUE_LABELS.update(NEW_KRI_LABELS)
COMPONENT_LABELS.update(NEW_COMPONENT_LABELS)

SITE_ALIASES = [
    "site_id", "site", "site_no", "site_number", "center", "center_id", "centre", "institution",
    "中心", "中心编号", "研究中心", "机构编号", "试验中心编号",
]
SUBJECT_ALIASES = [
    "subject_id", "subject", "subjid", "usubjid", "participant_id", "patient_id", "patient", "screening_number",
    "受试者", "受试者编号", "受试者id", "患者", "患者编号", "患者id", "入组编号", "随机号", "筛选号", "参与者筛选号",
]

