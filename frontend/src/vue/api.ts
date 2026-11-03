/** HTTP only. No fake model/GPU status and no polling outside active jobs. */
import { API_ORIGIN, getImageJob, cancelImageJob, submitImageJob, outputFromJob } from '../features/image-studio/api';
import type { ImageJob } from '../features/image-studio/api';
import { fetchRuntimeSnapshot } from '../features/image-studio/runtime';
export { API_ORIGIN, getImageJob, cancelImageJob, submitImageJob, outputFromJob, fetchRuntimeSnapshot };
export type { ImageJob };

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try { response = await fetch(API_ORIGIN + path, { cache: 'no-store', ...options }); }
  catch { throw new Error('无法连接本地后端'); }
  let payload: unknown;
  try { payload = await response.json(); }
  catch { throw new Error('服务端返回了无效的 JSON 响应'); }
  if (!response.ok) {
    const detail = payload && typeof payload === 'object' && 'detail' in payload
      ? (payload as { detail: unknown }).detail : undefined;
    throw new Error(typeof detail === 'string' ? detail : 'HTTP ' + response.status);
  }
  return payload as T;
}

export interface IndexedModel {
  id: string;
  category: string;
  name: string;
  relative_path: string;
  size_bytes: number;
}
export interface ModelIndex { files: IndexedModel[]; loaded: string[]; backend_ready: boolean; planned_families: string[] }
export interface CatalogModel { id: string; title: string; provider: string; repository: string; format: string; license_note: string; supports_lumacarve_inference: boolean }
export interface ModelCatalog { region: string; downloads_enabled: boolean; models: CatalogModel[] }
export interface DownloadJob { id: string; model_id: string; state: 'queued'|'running'|'completed'|'failed'; provider: string; repository: string; destination: string|null; error: string|null }
export const loadModelIndex = () => request<ModelIndex>('/api/v1/models');
export const loadModelCatalog = () => request<ModelCatalog>('/api/v1/downloads/catalog');
export const startModelDownload = (modelId: string, provider: string) => request<DownloadJob>('/api/v1/downloads', {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ model_id: modelId, provider }),
});
export const loadDownloadJob = (id: string) => request<DownloadJob>('/api/v1/downloads/' + encodeURIComponent(id));
export const loadJobs = () => request<{ jobs: ImageJob[] }>('/api/v1/jobs');
