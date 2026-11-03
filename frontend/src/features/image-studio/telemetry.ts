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
