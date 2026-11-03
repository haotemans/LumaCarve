# Flexible resource monitoring

## Purpose

Resource monitoring must be visually compact by default and must never consume
significant GPU resources merely to report their status. The system overview
supports **Simple** and **Detailed** views. Polling is driven by the visible
client, has configurable 2/3/5/10-second intervals, and stops on navigation,
pause, or when the document becomes hidden.

## Current implementation

- `GET /api/v1/telemetry?device=0` returns actual NVML device-wide metrics
  (name, memory used/total, utilization, optional temperature and power).
- The sampler lazily imports the optional `nvidia-ml-py` package, not PyTorch.
  A two-second per-device cache prevents parallel clients from oversampling.
- Missing NVIDIA drivers, missing optional dependency, unsupported sensors,
  and invalid indices are reported as unavailable/null, never synthetic.
- Install optional monitoring via
  `python -m pip install -e "./backend[monitor]"`.
- The existing `GET /api/v1/runtime` remains lightweight and does not probe
  CUDA on startup. It supplies the real job queue and engine configuration.
- Vue's System page has quick and detailed tabs, manual pause/refresh, multi-GPU
  selection when available, optional temperatures/power, and a bounded local
  history of up to 120 samples (latest 30 displayed).
- History is kept only in frontend memory; no disk traces or background
  retention. A refresh or leaving the page resets it.

## Limits

NVML measurements refer to **the whole physical GPU** and may include other
programs. They do not represent LumaCarve process allocation or component
memory ownership. Current code does not provide CPU/RAM telemetry, TE/VAE/DiT
phase timings, completed-task durations, or the independent supervised GPU
executor. No synthetic phase percentages, power data, or fake VRAM values
should appear as real observations.

For future GPU Worker integration, introduce separately sourced process-level
allocator counters, per-component residence events, phase start/end times,
and execution events. Label source, timestamp and accuracy. Do not call
`torch.cuda.synchronize()` on the UI polling path.

## Verification

```sh
cd backend
python -m unittest tests.test_telemetry tests.test_server
cd ../frontend
npm install
npm test
npm run build
```
