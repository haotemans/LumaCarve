# Isolated GPU Executor and observed Anima components

## Decision

LumaCarve targets one active GPU job per selected GPU. Rust/SQLite retains
the existing one-job-at-a-time scheduler. Inference runs inside a **separate
spawned Python process** so the API process does not own CUDA model weights.
The GPU executor starts lazily only when a queued Anima job is executed.

This is the default when `LUMACARVE_INFERENCE_BACKEND=anima`.
The `LUMACARVE_GPU_EXECUTOR_MODE=inprocess` compatibility mode exists for
legacy and mocked tests; production should use `subprocess`. The standalone
Tauri preview still ships only the lightweight API, with GPU inference disabled
unless the user installs the optional inference environment.

## Lifecycle

1. API validates a job and enqueues it in the existing SQLite queue.
2. The single queue thread starts the child with Python multiprocessing
   `spawn` (Windows/Linux) and receives a readiness message.
3. Child imports Anima/Torch and owns the model, LoRAs and CUDA context. The
   API never imports Torch merely because a user opens the monitor.
4. Parent sends one job command over a private local process Pipe, receives
   bounded real phase/parameter events and a final result.
5. A child heartbeat is emitted around every two seconds; lost heartbeats
   older than 180 seconds or a failed process terminate the worker before any
   replacement is started.
6. A cancellation flag travels through multiprocessing Event. After a
   cancellation grace period (12 seconds), the parent terminates the child.
7. An explicit idle unload first asks Anima to release its Python weights,
   then **always exits the child**, reaping/killing it before another CUDA
   process can start. If exit cannot be confirmed, model replacement fails
   closed. Worker crashes cannot leave a second live model process.

Anima model path changes within one worker still use the explicit
unload-then-load guard. The supervisor never starts another child while the
previous process is alive. Model instance state, PID, heartbeat age and mode
are returned read-only through `GET /api/v1/execution`.

## Component-level observations

- The monitor detects actual `transformer` (DiT), `vae` and
  `text_encoder` / `text_conditioner` modules when exposed by the
  installed ModularPipeline.
- At safe model-load/inference/unload boundaries it scans observed module
  parameters and buffers for **CPU/GPU device residency** and byte counts.
  These counts represent visible tensors, not complete allocator usage or
  overall device VRAM.
- Hooks on actual PyTorch module forward calls count invocations and record
  CUDA event time, **only when CUDA events are available**. If not available,
  observed Python dispatch time is reported with an explicit alternative
  timing source. The profiler uses the pipeline's existing final CUDA
  synchronization. No additional GPU sync is performed by UI polling.
- If a module is not visible, does not support hooks or was not called,
  its timing is marked unavailable. No inference duration is split
  proportionally or invented.
- Forward-hook event timings measure the observed modules only; nested modules
  may overlap in elapsed time and must not be summed as if independent.
- The detailed Vue monitoring page displays executor process/heartbeat,
  actual phase events and component residence with provenance.
- Execution monitor events stay in RAM (bounded to 80 completed entries);
  no prompts or image contents enter telemetry.

## Limits and follow-up

GPU Worker process isolation and module observation are implemented, but
**hardware validation on real CUDA hardware is still required**. Model-specific
Diffusers execution may use non-module or compiled call paths that hooks cannot
observe. The current executor handles **Anima inference**, not the future LoRA
training engine. It is supervised by Python while Rust scheduling remains the
existing queue bridge; migrating the worker supervisor into Rust is a later
architecture step.

Heartbeat is a liveness signal rather than proof of GPU progress. Forced
termination can interrupt an inference; training must use durable checkpoints
before any such recovery feature is enabled. Reuse across compatible jobs
happens in the same child process, which stays alive until idle trim, crash,
shutdown or failed release. The Windows Tauri desktop preview does not
automatically bundle Torch/CUDA just because this code exists.

## Validation

```sh
python -m pip install -e "./backend[dev]"
python -m unittest discover -s backend/tests -v
cd frontend
npm install --no-audit --no-fund
npm test
npm run build
```

In addition to CPU CI, test repeated Anima CUDA model swaps, hangs,
cancellation and process exits using physical GPU memory telemetry. Verify
that old model process PID has disappeared before any new GPU Executor starts.
