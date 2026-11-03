/** Device-wide NVML sample, not LumaCarve process ownership or tensor memory. */
import { apiFetch } from './api';

export interface GpuReading {
  name: string | null;
  used_bytes: number | null;
  total_bytes: number | null;
  utilization_percent: number | null;
  temperature_c: number | null;
  power_w: number | null;
}
export interface TelemetrySample {
  status: 'ok' | 'unavailable';
  scope: 'physical_device';
  source: string;
  reason: string | null;
  sampled_at: number | null;
  device_index: number;
  devices: { index: number; name: string }[];
  gpu: GpuReading;
}
export function validNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
}
export function parseTelemetry(raw: unknown): TelemetrySample {
  if (!raw || typeof raw !== 'object') throw new Error('GPU 监控响应格式错误');
  const item = raw as Partial<TelemetrySample>;
  if (item.status !== 'ok' && item.status !== 'unavailable') throw new Error('GPU 监控状态无效');
  const gpu = item.gpu ?? {} as Partial<GpuReading>;
  return {
    status: item.status, scope: 'physical_device', source: String(item.source ?? 'unknown'),
    reason: typeof item.reason === 'string' ? item.reason : null,
    sampled_at: validNumber(item.sampled_at), device_index: validNumber(item.device_index) ?? 0,
    devices: Array.isArray(item.devices) ? item.devices.filter(d => Number.isInteger(d?.index) && typeof d?.name === 'string') : [],
    gpu: {
      name: typeof gpu.name === 'string' ? gpu.name : null,
      used_bytes: validNumber(gpu.used_bytes),
      total_bytes: validNumber(gpu.total_bytes),
      utilization_percent: validNumber(gpu.utilization_percent),
      temperature_c: validNumber(gpu.temperature_c),
      power_w: validNumber(gpu.power_w),
    },
  };
}
export async function fetchTelemetry(deviceIndex: number, signal?: AbortSignal): Promise<TelemetrySample> {
  const response = await apiFetch('/api/v1/telemetry?device=' + encodeURIComponent(String(deviceIndex)), { cache: 'no-store', signal });
  if (!response.ok) throw new Error('GPU 监控服务暂不可用（HTTP ' + response.status + '）');
  return parseTelemetry(await response.json());
}

/** Event-based timings from the real Python worker, not NVML device sampling. */
export type ExecutionStage = 'job'|'model_unload'|'model_load'|'lora_update'|'inference'|'output_save'|'te'|'vae'|'dit';
export type PhaseStatus = 'running'|'completed'|'failed'|'cancelled';
export interface ExecutionEvent {
  id: string; stage: ExecutionStage; status: PhaseStatus; model_id: string | null;
  timing_source?: string | null; calls?: number | null;
  job_id: string | null; started_at: number; ended_at: number | null;
  duration_ms: number | null; allocated_bytes: number | null;
  reserved_bytes: number | null; allocator_source: string | null;
}
export interface ComponentResidency {
  key: string; state: string; gpu_weight_bytes: number | null;
  cpu_weight_bytes: number | null; source: string; observed_at: number | null;
}
export interface ExecutionTimeline {
  executor: { mode: string; state: string; pid: number | null; heartbeat_age_seconds: number | null } | null;
  components: ComponentResidency[];
  source: string;
  measured: boolean;
  active: ExecutionEvent[];
  events: ExecutionEvent[];
  phase_detail: Record<'te'|'vae'|'dit', string>;
}
const allowedStages = ['job', 'model_unload', 'model_load', 'lora_update', 'inference', 'output_save', 'te', 'vae', 'dit'];
const allowedStatuses = ['running', 'completed', 'failed', 'cancelled'];
function parseEvents(value: unknown): ExecutionEvent[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item): ExecutionEvent[] => {
    if (!item || typeof item !== 'object') return [];
    const v = item as Record<string, unknown>;
    if (typeof v.id !== 'string' || !allowedStages.includes(String(v.stage)) ||
        !allowedStatuses.includes(String(v.status))) return [];
    return [{
      id: v.id, stage: v.stage as ExecutionStage, status: v.status as PhaseStatus,
      model_id: typeof v.model_id === 'string' ? v.model_id : null,
      job_id: typeof v.job_id === 'string' ? v.job_id : null,
      started_at: validNumber(v.started_at) ?? 0,
      ended_at: validNumber(v.ended_at),
      duration_ms: validNumber(v.duration_ms),
      allocated_bytes: validNumber(v.allocated_bytes),
      reserved_bytes: validNumber(v.reserved_bytes),
      allocator_source: typeof v.allocator_source === 'string' ? v.allocator_source : null,
      timing_source: typeof v.timing_source === 'string' ? v.timing_source : null,
      calls: validNumber(v.calls),
    }];
  });
}
export function parseExecutionTimeline(raw: unknown): ExecutionTimeline {
  if (!raw || typeof raw !== 'object') throw new Error('执行时间线格式无效');
  const value = raw as Record<string, unknown>;
  const executor = value.executor && typeof value.executor === 'object'
    ? value.executor as Record<string, unknown> : null;
  const stages = value.phase_detail && typeof value.phase_detail === 'object'
    ? value.phase_detail as Record<string, unknown> : {};
  const phase = (key: string) => typeof stages[key] === 'string' ? stages[key] as string : 'unknown';
  return {
    executor: executor ? {
      mode: typeof executor.mode === 'string' ? executor.mode : 'unknown',
      state: typeof executor.state === 'string' ? executor.state : 'unknown',
      pid: validNumber(executor.pid),
      heartbeat_age_seconds: validNumber(executor.heartbeat_age_seconds),
    } : null,
    components: Array.isArray(value.components) ? value.components.flatMap((item): ComponentResidency[] => {
      if (!item || typeof item !== 'object') return [];
      const entry = item as Record<string, unknown>;
      if (!['te', 'vae', 'dit'].includes(String(entry.key))) return [];
      return [{
        key: String(entry.key), state: typeof entry.state === 'string' ? entry.state : 'unknown',
        gpu_weight_bytes: validNumber(entry.gpu_weight_bytes),
        cpu_weight_bytes: validNumber(entry.cpu_weight_bytes),
        source: typeof entry.source === 'string' ? entry.source : 'unknown',
        observed_at: validNumber(entry.observed_at),
      }];
    }) : [],
    source: typeof value.source === 'string' ? value.source : 'unknown',
    measured: value.measured === true,
    active: parseEvents(value.active),
    events: parseEvents(value.events),
    phase_detail: { te: phase('te'), vae: phase('vae'), dit: phase('dit') },
  };
}
export async function fetchExecutionTimeline(signal?: AbortSignal): Promise<ExecutionTimeline> {
  const response = await apiFetch('/api/v1/execution?limit=30', { cache: 'no-store', signal });
  if (!response.ok) throw new Error('执行时间线暂不可用（HTTP ' + response.status + '）');
  return parseExecutionTimeline(await response.json());
}
