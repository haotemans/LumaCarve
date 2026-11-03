import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { createServer } from 'vite';

let vite;
let parseRuntimeSnapshot;

before(async () => {
  // Vite's SSR loader parses the real TypeScript module and its import.meta.env
  // dependency without running a browser, importing CUDA, or hitting the API.
  vite = await createServer({
    server: { middlewareMode: true },
    appType: 'custom',
    logLevel: 'silent',
  });
  ({ parseRuntimeSnapshot } = await vite.ssrLoadModule('/src/features/image-studio/runtime.ts'));
});

after(async () => {
  if (vite) await vite.close();
});

test('unknown GPU and AMEP remain unknown even with configured Anima', () => {
  const value = parseRuntimeSnapshot({
    engine: 'anima',
    configured_engine: 'anima',
    gpu: { available: null, measured: false },
    inference_offload: 'auto',
    memory_planner: { adaptive: 'not_implemented', current: 'auto' },
    optimization: {
      state: 'configured_only',
      validated_on_gpu: false,
      anima: { adaln: 'experimental', rope: 'off', residual: 'experimental', ffn: 'off' },
    },
  });
  assert.equal(value.engine, 'anima');
  assert.equal(value.gpuMeasured, false);
  assert.equal(value.gpuAvailable, null);
  assert.equal(value.adaptivePlanner, 'not_implemented');
  assert.equal(value.offload, 'auto');
  assert.equal(value.optimizationState, 'configured_only');
  assert.equal(value.verifiedOnGPU, false);
  assert.equal(value.kernels.adaln, 'experimental');
  assert.equal(value.kernels.rope, 'off');
});

test('older backend does not fabricate kernel settings or VRAM telemetry', () => {
  const value = parseRuntimeSnapshot({
    engine: 'not_connected', configured_engine: 'disabled',
    gpu: { available: false, measured: false }, inference_offload: 'full',
  });
  assert.equal(value.engine, 'not_connected');
  assert.equal(value.configuredEngine, 'disabled');
  assert.equal(value.gpuAvailable, null);
  assert.equal(value.offload, 'full');
  assert.equal(value.adaptivePlanner, 'unknown');
  assert.equal(value.optimizationState, 'unknown');
  assert.deepEqual(Object.values(value.kernels), ['unknown', 'unknown', 'unknown', 'unknown']);
});

test('only explicit backend measurement is treated as GPU availability', () => {
  assert.equal(parseRuntimeSnapshot({
    engine: 'anima', gpu: { available: true, measured: true },
  }).gpuAvailable, true);
  assert.equal(parseRuntimeSnapshot({
    engine: 'anima', gpu: { available: false, measured: true },
  }).gpuAvailable, false);
});

test('malformed status cannot appear as healthy', () => {
  for (const value of [null, [], {}, { engine: null }, { engine: 7 }]) {
    assert.throws(() => parseRuntimeSnapshot(value), /运行状态响应/);
  }
  assert.equal(parseRuntimeSnapshot({ engine: 'unexpected' }).engine, 'unknown');
});
