export type Locale = "zh" | "en";
export type Theme = "light" | "dark";
export type TabKey = "import" | "overview" | "efficacy" | "risk_forecast" | "kri" | "ranking" | "details" | "actions";
export type UploadRole = "clinical_data" | "progress_report" | "critical_points" | "query_detail";

export interface LocalizedText {
  zh: string;
  en: string;
}

export interface ThresholdItem {
  key: string;
  label: LocalizedText;
  group: LocalizedText;
  department?: string;
  department_label?: LocalizedText;
  min: number;
  max: number;
  step: number;
  value: number;
  decimals: number;
  enabled: boolean;
}

export type DataValue = string | number | boolean | null | string[];
export type DataRow = Record<string, DataValue>;

export interface FieldGroup {
  domain: string;
  fields: string[];
}

export interface RbqmState {
  using_demo_data: boolean;
  kri: {
    enabled: boolean;
    enabled_metrics: string[];
  };
  raw_summary: DataRow[];
  domain_summary: DataRow[];
  data_sources: {
    progress_report: boolean;
    clinical_data: boolean;
    critical_points: boolean;
    query_detail: boolean;
  };
  fields: FieldGroup[];
  overview: Record<string, string | number>;
  subject_status_summary: DataRow[];
  subject_status_by_site: DataRow[];
  patient_medical_review: PatientMedicalReview;
  ae_event_review: AeEventReview;
  critical_query_review: CriticalQueryReview;
  kri_drilldowns: KriDrilldown[];
  metrics: DataRow[];
  signals: DataRow[];
  action_log: DataRow[];
}

export interface PatientMedicalSubject {
  subject_id: string;
  site_id: string;
  site_name: string;
  subject_status: string;
  hba1c_count: number;
  weight_count: number;
}

export interface PatientMedicalRecord {
  subject_id: string;
  site_id: string;
  site_name: string;
  subject_status: string;
  visit: string;
  date: string;
  day: number;
  metric: "hba1c" | "weight";
  label: string;
  page: string;
  value: number;
  unit: string;
  assessment: string;
}

export interface PatientMedicalReview {
  subjects: PatientMedicalSubject[];
  records: PatientMedicalRecord[];
  site_summary: DataRow[];
  project_summary: DataRow[];
  subject_summary: DataRow[];
  bayesian_hba1c_prediction?: {
    available: boolean;
    message?: string;
    model?: string;
    note?: string;
    posterior?: Record<string, number>;
    summary: DataRow[];
    probabilities: DataRow[];
    drug_benchmarks: DataRow[];
    center_rows: DataRow[];
  };
  screen_failure_summary: DataRow[];
  screen_failure_details: DataRow[];
}

export interface AeEventReview {
  overview: DataRow[];
  by_site: DataRow[];
  by_grade: DataRow[];
  by_relation: DataRow[];
  by_outcome: DataRow[];
  by_soc: DataRow[];
  by_pt: DataRow[];
  by_site_soc: DataRow[];
  by_site_pt: DataRow[];
  sae_by_site: DataRow[];
  sae_by_reason: DataRow[];
  sae_by_outcome: DataRow[];
  sae_by_soc: DataRow[];
  sae_by_pt: DataRow[];
  sae_by_site_soc: DataRow[];
  ae_details: DataRow[];
  sae_details: DataRow[];
}

export interface CriticalQueryReview {
  overview: DataRow[];
  by_site: DataRow[];
  open_by_site: DataRow[];
  details: DataRow[];
  open_details: DataRow[];
}

export interface KriDrilldown {
  key: string;
  label: string;
  department?: string;
  unit: string;
  threshold: number | string;
  center_rows: DataRow[];
  details: DataRow[];
  project_subjects?: number | null;
  project_events?: number | null;
}

export interface PreviewDomain {
  key: string;
  label: string;
  fields: string[];
  required_fields: string[];
}

export interface PreviewSource {
  source_id: string;
  upload_role?: UploadRole;
  rows: number;
  columns: string[];
  sample_rows?: DataRow[];
  guessed_domain?: string;
}

export interface UploadPreview {
  sources: PreviewSource[];
  domains: PreviewDomain[];
}

export interface SourceMapping {
  domain: string;
  fields: Record<string, string>;
}

export interface MappingConfig {
  sources: Record<string, SourceMapping>;
}

export type MappingSelections = Record<string, SourceMapping>;

export interface KriConfigRecord {
  version: number;
  is_active: boolean;
  saved_at: string;
  saved_by: string;
  change_reason: string;
  kri_enabled: boolean;
  enabled_metrics: string[];
  thresholds: Record<string, number>;
}

export interface KriConfigResponse {
  active: KriConfigRecord;
  versions: KriConfigRecord[];
}

export interface KriCatalogResponse {
  kri_enabled: boolean;
  metrics: ThresholdItem[];
}
