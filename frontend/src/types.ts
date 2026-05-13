export type Locale = "zh" | "en";
export type Theme = "light" | "dark";
export type TabKey = "import" | "overview" | "kri" | "ranking" | "details" | "actions";

export interface LocalizedText {
  zh: string;
  en: string;
}

export interface ThresholdItem {
  key: string;
  label: LocalizedText;
  group: LocalizedText;
  min: number;
  max: number;
  step: number;
  value: number;
  decimals: number;
  enabled: boolean;
}

export type DataRow = Record<string, string | number | boolean | null>;

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
  fields: FieldGroup[];
  overview: Record<string, string | number>;
  metrics: DataRow[];
  signals: DataRow[];
  action_log: DataRow[];
}

export interface PreviewDomain {
  key: string;
  label: string;
  fields: string[];
  required_fields: string[];
}

export interface PreviewSource {
  source_id: string;
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
