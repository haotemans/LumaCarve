# Real execution phase timeline

LumaCarve's System page exposes a worker event timeline in **Detailed**
monitoring mode. All observations are associated with actual execution; the
simple mode remains low-overhead.

## Instrumentation

- `ExecutionMonitor` is a bounded (80-event), thread-safe, in-memory
  recorder. Only the running Python queue thread creates model-related events.
- The job thread attaches `job_id` to nested phases.
- Anima records these **wall-clock** phases: model load, model unload,
  LoRA update, inference (including existing synchronization), output save.
  The queue records the overall job phase and its failure.
- `GET /api/v1/execution?limit=40` only copies already-recorded events; it
  does not import PyTorch, synchronize CUDA or probe a GPU.
- In the worker, after a phase finishes, optional
  `torch.cuda.memory_allocated()` and `memory_reserved()` values may be
  attached. These are **process-local PyTorch allocator** readings, not
  device-wide NVML usage, model component allocation or peak memory.
- Each event has stage, status, wall-clock timestamps, elapsed milliseconds,
  optional job/model identity, optional memory and explicit source.
  Only valid events are shown. No prompts or user model filesystem paths
  are stored by this recorder.
- The UI refreshes these events along with the on-screen monitor, stops
  when hidden or paused, and displays real recent events only.

## Explicit gaps

We **do not** yet have direct hooks into Anima ModularPipeline's internal
Text Encoder, VAE and DiT execution. The detailed view labels these
components as waiting for Worker instrumentation rather than splitting
inference time into fabricated numbers.

This first implementation still runs the GPU job worker inside the FastAPI
process. A separately supervised GPU Executor and its automatic
restart/recovery path have **not** been added. Training has not yet been
instrumented. Execution time is wall time, **not** a per-kernel CUDA event
benchmark; PCIe, CPU, I/O and CUDA synchronization can contribute.

Events stay in memory only and are lost on application restart. Neither
event data nor CUDA telemetry should block an active generation.

## Verification

```sh
cd backend
python -m unittest tests.test_execution_monitor tests.test_server tests.test_anima -v
cd ../frontend
npm install
npm test
npm run build
```

Real GPU validation remains necessary to confirm component hook behavior,
allocator readings and overhead on supported NVIDIA drivers.
