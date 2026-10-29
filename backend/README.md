# LumaCarve Python runtime foundation

This is a **device-independent scheduling prototype**, not a PyTorch training
engine or a runnable diffusion pipeline. It has no external dependencies.

The design intentionally separates:
- \`compile_workflow\`: stable topological order, dependency validation, intermediate-output lifetimes.
- \`preflight\`: estimate simultaneously required *weight* bytes against a budget with activation/staging headroom.
- \`ModelResidencyManager\`: single-instance hot GPU / warm CPU / cold unloaded cache with LRU eviction and leases.
- \`run_plan\`: callback-based node execution; keeps only live intermediate outputs and final outputs.

## Tests

From the repository root:

\`\`\`bash
cd backend
python -m unittest discover -s tests -v
\`\`\`

These tests use a fake model backend; they **do not** measure GPU utilization,
CUDA peak allocations, model compatibility, or generation speed.

## ModelBackend adapter contract

The concrete model-specific adapter must implement:

\`\`\`python
def load(spec, target): ...
def move(spec, instance, source, target): ...
def unload(spec, instance, source): ...
\`\`\`

- \`load(HOT)\` should stream/model-dispatch directly to GPU when supported, rather than materializing a second full-weight copy in RAM.
- A successful \`move\` must release the old copy; avoid duplicate model residency. Failures must leave the old object usable (or clean up explicitly).
- Account for transient CPU/GPU staging allocations and pinned memory; the budget describes **persistent estimated weight bytes** only.
- Record actual CUDA peak usage with PyTorch and dynamically adjust reserves in a future adapter.
- A user of \`lease()\` must synchronize pending CUDA operations before releasing it; otherwise weights could be evicted while a kernel is still running.
- Optimizer state, gradients and activation memory during training need separate budgeting and policy.
- CUDA caching allocator memory is **not** released by simply deleting live tensors. No unconditional \`empty_cache()\` calls after each generation.

## Performance behavior

- **No unload after each generation.** Inactive hot components remain resident while budget permits.
- **No forced CPU offload.** If weight set fits, keep DiT and frequently used LoRA components on GPU.
- On pressure, evict idle GPU components to RAM if there is room; otherwise unload directly.
- Never evict actively leased components. Repeated component keys represent one shared instance.
- Use a stable version/precision-aware component key, including LoRA identity and target architecture, to prevent accidental reuse.
- The Graph is executed only once as a compiled plan; no React Flow renderer is needed during inference.
- On real GPUs, benchmark full residency vs component offload vs quantization before enabling more aggressive techniques.

## Not implemented yet

PyTorch/CUDA adapters, model-family compatibility checks, real transfer scheduling,
quantized loaders, asynchronous prefetch, profiling/telemetry, inference and training
loops, Graph JSON serialization and dynamic parameter-panel exposure. These require
model-specific integration and tests on actual hardware (8/16/24 GB).
