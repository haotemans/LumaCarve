/// <reference types="vite/client" />
/** Local image generation API. No mock job completion or synthesized images. */
import type { StudioWorkflow } from './workflow';

export const API_ORIGIN = (
  (import.meta.env.VITE_LUMACARVE_API_URL as string | undefined)?.trim() ||
  'http://127.0.0.1:8000'
).replace(/\/$/, '');

export type JobState = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface GeneratedImage {
  outputId: string;
  imageUrl: string;
  width: number;
  height: number;
  seed: number;
  modelId: string;
}

export interface ImageJob {
  id: string;
  state: JobState;
  result: {
    output_id: string;
    width: number;
    height: number;
    seed: number;
    model_id: string;
  } | null;
  error: string | null;
  priority?: 'interactive' | 'normal' | 'background';
  created_at?: number;
  updated_at?: number;
}

async function jsonOrError(response: Response): Promise<ImageJob> {
  let value: unknown;
  try { value = await response.json(); }
  catch { throw new Error(`后端返回了无效响应（HTTP ${response.status}）`); }
  if (!response.ok) {
    const detail = value && typeof value === 'object' && 'detail' in value
      ? (value as {detail:unknown}).detail : undefined;
    throw new Error(typeof detail === 'string' ? detail : `后端请求失败（HTTP ${response.status}）`);
  }
  return value as ImageJob;
}

export async function submitImageJob(workflow: StudioWorkflow): Promise<ImageJob> {
  try {
    const response = await fetch(API_ORIGIN + '/api/v1/jobs', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ workflow, priority: 'interactive' }),
    });
    return jsonOrError(response);
  } catch (error) {
    if (error instanceof TypeError) throw new Error('无法连接到本地图像生成后端（127.0.0.1:8000）');
    throw error;
  }
}

export async function getImageJob(id: string): Promise<ImageJob> {
  const response = await fetch(API_ORIGIN + '/api/v1/jobs/' + encodeURIComponent(id));
  return jsonOrError(response);
}

export async function cancelImageJob(id: string): Promise<ImageJob> {
  const response = await fetch(API_ORIGIN + '/api/v1/jobs/' + encodeURIComponent(id) + '/cancel', {
    method: 'POST',
  });
  return jsonOrError(response);
}

export function outputFromJob(job: ImageJob): GeneratedImage {
  const result = job.result;
  if (!result || !/^[a-f0-9]{32}$/.test(result.output_id) || !result.width || !result.height) {
    throw new Error('生成任务没有返回有效的 PNG 输出 ID');
  }
  return {
    outputId: result.output_id,
    imageUrl: API_ORIGIN + '/api/v1/outputs/' + result.output_id,
    width: result.width,
    height: result.height,
    seed: result.seed,
    modelId: result.model_id,
  };
}
