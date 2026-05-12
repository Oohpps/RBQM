import type { MappingConfig, RbqmState, UploadPreview } from "./types";

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
