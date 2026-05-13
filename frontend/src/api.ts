import type { KriConfigResponse, MappingConfig, RbqmState, ThresholdItem, UploadPreview } from "./types";

export function thresholdParams(kriEnabled: boolean, thresholds: { key: string; value: number; enabled: boolean }[]): URLSearchParams {
  const params = new URLSearchParams();
  params.set("kri_enabled", kriEnabled ? "true" : "false");
  params.set("enabled_metrics", kriEnabled ? thresholds.filter((item) => item.enabled).map((item) => item.key).join(",") : "");
  thresholds.forEach((item) => params.set(item.key, String(item.value)));
  return params;
}

async function readJson<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || fallbackMessage);
  }
  return response.json() as Promise<T>;
}

export async function fetchState(params: URLSearchParams): Promise<RbqmState> {
  return readJson<RbqmState>(await fetch(`/api/state?${params.toString()}`), "Failed to load RBQM data");
}

export async function resetDemo(params: URLSearchParams): Promise<RbqmState> {
  return readJson<RbqmState>(await fetch(`/api/demo?${params.toString()}`, { method: "POST" }), "Failed to reset demo data");
}

export async function previewUpload(files: File[]): Promise<UploadPreview> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  return readJson<UploadPreview>(await fetch("/api/upload/preview", { method: "POST", body: formData }), "Upload preview failed");
}

export async function commitUpload(files: File[], config: MappingConfig, params: URLSearchParams): Promise<RbqmState> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  formData.append("mapping_config", JSON.stringify(config));
  return readJson<RbqmState>(await fetch(`/api/upload/commit?${params.toString()}`, { method: "POST", body: formData }), "Upload failed");
}

export async function fetchConfig(): Promise<KriConfigResponse> {
  return readJson<KriConfigResponse>(await fetch("/api/config"), "Failed to load KRI config");
}

export async function saveConfig(kriEnabled: boolean, thresholds: ThresholdItem[]): Promise<KriConfigResponse> {
  const thresholdValues: Record<string, number> = {};
  thresholds.forEach((item) => {
    thresholdValues[item.key] = item.value;
  });
  return readJson<KriConfigResponse>(
    await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kri_enabled: kriEnabled,
        enabled_metrics: thresholds.filter((item) => item.enabled).map((item) => item.key),
        thresholds: thresholdValues,
        saved_by: "ui",
        change_reason: "Saved from RBQM threshold panel",
      }),
    }),
    "Failed to save KRI config",
  );
}
