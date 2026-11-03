/** Read-only local backend runtime snapshot. No GPU telemetry or polling. */
import { API_ORIGIN } from './api';

export type KernelMode = 'off' | 'experimental' | 'unknown';
export type OffloadMode = 'auto' | 'model_cpu' | 'full' | 'unknown';
export type RuntimeEngine = 'anima' | 'not_connected' | 'unknown';

export interface RuntimeSnapshot {
  engine: RuntimeEngine;
  configuredEngine: 'anima' | 'disabled' | 'unknown';
  gpuMeasured: boolean;
  gpuAvailable: boolean | null;
  offload: OffloadMode;
  adaptivePlanner: 'not_implemented' | 'unknown';
  optimizationState: 'configured_only' | 'unknown';
  verifiedOnGPU: boolean;
  queue: { queued: number; running: number; capacity: number } | null;
  kernels: Record<'adaln' | 'rope' | 'residual' | 'ffn', KernelMode>;
}

function record(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown> : undefined;
}
function kernelMode(value: unknown): KernelMode {
  return value === 'off' || value === 'experimental' ? value : 'unknown';
}

/**
 * Keep unknown/unmeasured distinct from disabled/unavailable.
 * The API may be an older backend; do not invent optimization telemetry.
 */
export function parseRuntimeSnapshot(raw: unknown): RuntimeSnapshot {
  const value = record(raw);
  if (!value || typeof value.engine !== 'string') {
    throw new Error('运行状态响应不符合本地 API 格式');
  }
  const gpu = record(value.gpu);
  const planner = record(value.memory_planner);
  const optimization = record(value.optimization);
  const kernels = record(optimization?.anima);
  const queue = record(value.queue);
  const counts = record(queue?.counts);
  return {
    engine: value.engine === 'anima' || value.engine === 'not_connected'
      ? value.engine : 'unknown',
    configuredEngine: value.configured_engine === 'anima' || value.configured_engine === 'disabled'
      ? value.configured_engine : 'unknown',
    gpuMeasured: gpu?.measured === true,
    gpuAvailable: gpu?.measured === true && typeof gpu.available === 'boolean'
      ? gpu.available : null,
    offload: value.inference_offload === 'auto' || value.inference_offload === 'model_cpu' || value.inference_offload === 'full'
      ? value.inference_offload : 'unknown',
    adaptivePlanner: planner?.adaptive === 'not_implemented' ? 'not_implemented' : 'unknown',
    optimizationState: optimization?.state === 'configured_only' ? 'configured_only' : 'unknown',
    verifiedOnGPU: optimization?.validated_on_gpu === true,
    queue: queue && counts && typeof counts.queued === 'number' && typeof counts.running === 'number' && typeof queue.capacity === 'number'
      ? { queued: counts.queued, running: counts.running, capacity: queue.capacity } : null,
    kernels: {
      adaln: kernelMode(kernels?.adaln),
      rope: kernelMode(kernels?.rope),
      residual: kernelMode(kernels?.residual),
      ffn: kernelMode(kernels?.ffn),
    },
  };
}

/** One fetch on entry, then refresh only after a deliberate user click. */
export async function fetchRuntimeSnapshot(signal?: AbortSignal): Promise<RuntimeSnapshot> {
  let response: Response;
  try {
    response = await fetch(API_ORIGIN + '/api/v1/runtime', {
      method: 'GET', signal, cache: 'no-store',
    });
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error;
    throw new Error('无法连接本地后端，请检查服务是否启动');
  }
  if (!response.ok) throw new Error('读取运行状态失败（HTTP ' + response.status + '）');
  let parsed: unknown;
  try {
    parsed = await response.json();
  } catch {
    throw new Error('运行状态响应不是合法 JSON');
  }
  return parseRuntimeSnapshot(parsed);
}
