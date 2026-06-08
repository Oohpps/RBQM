import type { KriCatalogResponse, KriConfigResponse, MappingConfig, RbqmState, ThresholdItem, UploadPreview, UploadRole } from "./types";

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

export async function fetchSession(): Promise<{ session_id: string }> {
  return readJson<{ session_id: string }>(await fetch("/api/session"), "Failed to load app session");
}

export async function fetchKriCatalog(): Promise<KriCatalogResponse> {
  return readJson<KriCatalogResponse>(await fetch("/api/kri/catalog"), "Failed to load KRI catalog");
}

export async function resetState(params: URLSearchParams): Promise<RbqmState> {
  return readJson<RbqmState>(await fetch(`/api/reset?${params.toString()}`, { method: "POST" }), "Failed to reset RBQM data");
}

export async function previewUpload(files: File[], sourceRoles: Record<string, UploadRole> = {}): Promise<UploadPreview> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  formData.append("source_roles", JSON.stringify(sourceRoles));
  return readJson<UploadPreview>(await fetch("/api/upload/preview", { method: "POST", body: formData }), "Upload preview failed");
}

export async function commitUpload(files: File[], config: MappingConfig, params: URLSearchParams, sourceRoles: Record<string, UploadRole> = {}): Promise<RbqmState> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  formData.append("mapping_config", JSON.stringify(config));
  formData.append("source_roles", JSON.stringify(sourceRoles));
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
