import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { createServer } from 'vite';

let vite;
let parseTelemetry;
before(async () => {
  vite = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'silent' });
  ({ parseTelemetry } = await vite.ssrLoadModule('/src/features/image-studio/telemetry.ts'));
});
after(async () => { if (vite) await vite.close(); });
test('device-wide readings are not invented when unavailable', () => {
  const v = parseTelemetry({ status: 'unavailable', devices: [], gpu: {}, reason: 'NVML unavailable' });
  assert.equal(v.scope, 'physical_device');
  assert.equal(v.gpu.used_bytes, null);
  assert.equal(v.gpu.total_bytes, null);
  assert.equal(v.sampled_at, null);
});
test('invalid or negative readings are rejected without crashing the UI', () => {
  const v = parseTelemetry({ status: 'ok', gpu: { used_bytes: -1, total_bytes: Infinity, utilization_percent: 38, temperature_c: 62 }, devices: [] });
  assert.equal(v.gpu.used_bytes, null);
  assert.equal(v.gpu.total_bytes, null);
  assert.equal(v.gpu.utilization_percent, 38);
  assert.equal(v.gpu.temperature_c, 62);
});
test('malformed API status fails rather than showing fake healthy values', () => {
  assert.throws(() => parseTelemetry(null));
  assert.throws(() => parseTelemetry({ status: 'simulated' }));
});
