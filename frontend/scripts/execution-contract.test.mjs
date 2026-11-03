import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { createServer } from 'vite';

let vite;
let parseExecutionTimeline;

before(async () => {
  vite = await createServer({
    server: { middlewareMode: true }, appType: 'custom', logLevel: 'silent',
  });
  ({ parseExecutionTimeline } = await vite.ssrLoadModule('/src/features/image-studio/telemetry.ts'));
});
after(async () => { if (vite) await vite.close(); });

test('empty events and unavailable TE/VAE/DiT stay unknown', () => {
  const value = parseExecutionTimeline({
    source: 'python_worker_in_memory', measured: false, active: [], events: [],
    phase_detail: {te:'instrumentation_not_connected',vae:'instrumentation_not_connected',dit:'instrumentation_not_connected'},
  });
  assert.equal(value.measured, false);
  assert.equal(value.events.length, 0);
  assert.equal(value.phase_detail.te, 'instrumentation_not_connected');
});

test('real reported event is sanitized without inventing CUDA measurements', () => {
  const value = parseExecutionTimeline({
    source: 'python_worker_in_memory', measured: true,
    active: [],
    events: [{
      id:'phase-1',stage:'inference',status:'completed',job_id:'job-1',
      model_id:'anima-base-1',started_at:100,ended_at:101,duration_ms:1000,
      allocated_bytes:null,reserved_bytes:0,allocator_source:null,
    },{
      id:'invalid',stage:'fake_gpu_phase',status:'completed',
    }],
    phase_detail:{},
  });
  assert.equal(value.events.length, 1);
  assert.equal(value.events[0].duration_ms,1000);
  assert.equal(value.events[0].allocated_bytes,null);
  assert.equal(value.events[0].reserved_bytes,0);
  assert.equal(value.phase_detail.dit,'unknown');
});

test('negative or invalid durations cannot appear as real', () => {
  const value = parseExecutionTimeline({
    source:'python_worker_in_memory',measured:true,active:[],
    events:[{id:'x',stage:'model_load',status:'running',started_at:3,
      duration_ms:-500,allocated_bytes:-1,reserved_bytes:Infinity}],
  });
  assert.equal(value.events[0].duration_ms,null);
  assert.equal(value.events[0].allocated_bytes,null);
  assert.equal(value.events[0].reserved_bytes,null);
});

test('invalid payloads fail cleanly', () => {
  for (const raw of [null, undefined, false]) {
    assert.throws(() => parseExecutionTimeline(raw));
  }
});
