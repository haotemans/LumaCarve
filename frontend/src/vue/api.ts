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
export interface ModelIndex { files: IndexedModel[]; loaded: string[]; backend_ready: boolean; backend_configured?: boolean; anima_snapshot?: string | null; planned_families: string[] }
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
export type JobFilter = ImageJob['state'] | 'all';
export interface JobCounts { queued: number; running: number; completed: number; failed: number; cancelled: number }
export interface JobPage { jobs: ImageJob[]; total: number; counts: JobCounts; limit: number; offset: number }
export const loadJobs = (filter: JobFilter = 'all', limit = 50, offset = 0) => {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (filter !== 'all') params.set('state', filter);
  return request<JobPage>('/api/v1/jobs?' + params.toString());
};

export interface DatasetSummary { id: string; title: string; image_count: number; size_bytes: number; created_at?: number }
export interface DatasetItem {
  id: string; name: string; ext: 'png' | 'jpg' | 'webp'; width: number; height: number;
  size_bytes: number; caption: string; created_at: number; updated_at: number;
}
export interface DatasetPage { items: DatasetItem[]; total: number; limit: number; offset: number }
export const listDatasets = () => request<{ datasets: DatasetSummary[] }>('/api/v1/datasets');
export const createDataset = (id: string, title: string) => request<DatasetSummary>('/api/v1/datasets', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, title }),
});
export const listDatasetItems = (id: string, limit = 48, offset = 0) =>
  request<DatasetPage>('/api/v1/datasets/' + encodeURIComponent(id) + '/images?' + new URLSearchParams({ limit: String(limit), offset: String(offset) }));
export function datasetImageUrl(id: string, imageId: string): string {
  return API_ORIGIN + '/api/v1/datasets/' + encodeURIComponent(id) + '/images/' + encodeURIComponent(imageId);
}
export async function uploadDatasetImage(id: string, image: File, caption: string): Promise<DatasetItem> {
  const body = new FormData();
  body.append('file', image, image.name);
  body.append('caption', caption);
  return request<DatasetItem>('/api/v1/datasets/' + encodeURIComponent(id) + '/images', { method: 'POST', body });
}
export const updateDatasetCaption = (datasetId: string, imageId: string, caption: string) =>
  request<{ id: string; caption: string; updated_at: number }>(
    '/api/v1/datasets/' + encodeURIComponent(datasetId) + '/images/' + encodeURIComponent(imageId) + '/caption',
    { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ caption }) },
  );
export async function deleteDatasetImage(datasetId: string, imageId: string): Promise<void> {
  const response = await fetch(API_ORIGIN + '/api/v1/datasets/' + encodeURIComponent(datasetId) + '/images/' + encodeURIComponent(imageId), { method: 'DELETE' });
  if (!response.ok) {
    let error: string | undefined;
    try { const data: unknown = await response.json(); if (data && typeof data === 'object' && 'detail' in data && typeof data.detail === 'string') error = data.detail; } catch { /* no JSON */ }
    throw new Error(error ?? '删除图片失败（HTTP ' + response.status + '）');
  }
}

