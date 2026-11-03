# GPU base-model residency and UI contract

## Invariant

For one consumer GPU, one active compute task and one GPU base-model
identity are permitted at a time. Do not allow both old and new base weights
to coexist simply because estimated VRAM permits it.

- Components specify the owning `base_id` (DiT, TE, VAE and LoRA).
- Keep compatible components for reuse within one base model; CPU and disk
  caches may retain other bases, but GPU base residency is exclusive.
- Switching requires no live leases, unloading every foreign hot component,
  verification by the concrete GPU backend, then loading the next model.
- Failure to verify release **blocks the next load**. Policy counters alone
  are not CUDA proof. A process supervisor must confirm actual GPU executor
  termination before resetting the blocked state.
- No forced interruption of a training step; safe pause/resume also requires
  optimizer, scheduler, RNG and sampler checkpoint state.

## Implemented in this iteration

- The generic Python residency policy now accepts `base_id` and an optional
  concrete release verifier, rejects mixed-base and live-lease transitions,
  and fails closed if verification is missing or fails.
- Anima's lazy adapter reports actual loaded pipeline state. When its snapshot
  path changes, it runs a conservative cleanup first; it refuses another load
  if PyTorch still reports allocated GPU tensors.
- `JobQueue.unload_idle_model` sends requests to the existing single worker,
  not to the HTTP handler, and refuses requests with queued/running jobs.
- `GET /api/v1/models` includes the truthful `residency` object.
  `POST /api/v1/models/unload` requests idle-only release.
- Vue 3 model-management UI shows model residency, active queue count and
  a guarded unload action. It never calls disk model discovery "GPU loaded."

## Not yet implemented / restrictions

The Anima adapter still operates in the API process job-queue worker, rather
than a separately supervised GPU child process. Restart-on-leak is a design
requirement, **not** an implemented feature. Other model adapters and the
training worker are not integrated with the residency policy. No genuine
GPU memory telemetry or multi-model CUDA tests have been completed.
If CUDA release fails, restart the backend instead of assuming cleanup.
PyTorch's allocated-bytes check does not measure external CUDA consumers.

The current Windows desktop sidecar includes only the core API, not GPU
training/inference dependencies. This UI must never claim it measured VRAM.

## UI semantics

State-first and compact: existing light Vue studio design, clear "loaded /
unloaded / unknown" status, queue activity, explicit guarded action, errors
that stay visible. The "no known block" status is not equivalent to a
measured CUDA clean slate.

## Tests

Run Python unit tests in the backend environment and frontend Vue build:

```sh
cd backend
python -m unittest tests.test_runtime tests.test_models -v
cd ../frontend
npm install
npm test
npm run build
```

A separate real-GPU validation suite must check 50+ repeated snapshot swaps,
forced CUDA references, failed releases, and Windows process termination.
