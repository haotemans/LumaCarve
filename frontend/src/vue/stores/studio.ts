import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { cancelImageJob, fetchRuntimeSnapshot, getImageJob, loadJobs, loadModelIndex, outputFromJob, submitImageJob } from '../api';
import type { ImageJob } from '../api';
import { getStudioModel, makeWorkflow, updateNodeValue } from '../../features/image-studio/workflow';
import type { FieldId, FieldValue, LoRAEntry, StudioIntent, StudioWorkflow } from '../../features/image-studio/workflow';
import type { GeneratedImage } from '../../features/image-studio/api';
import type { RuntimeSnapshot } from '../../features/image-studio/runtime';

export const useStudioStore = defineStore('studio', () => {
  const workflow = ref<StudioWorkflow>(makeWorkflow());
  const history = ref<GeneratedImage[]>([]);
  const jobs = ref<ImageJob[]>([]);
  const selectedOutputId = ref<string | null>(null);
  const activeJobId = ref<string | null>(null);
  const jobState = ref<'idle' | 'submitting' | ImageJob['state']>('idle');
  const jobError = ref('');
  const runtime = ref<RuntimeSnapshot | null>(null);
  const runtimeError = ref('');
  const runtimeLoading = ref(false);
  const backendSnapshot = ref<string | null>(null);
  const backendReady = ref(false);
  const backendConfigured = ref(false);

  const modelNode = computed(() => workflow.value.nodes.find(node => node.kind === 'model'));
  const promptNode = computed(() => workflow.value.nodes.find(node => node.kind === 'prompt'));
  const samplerNode = computed(() => workflow.value.nodes.find(node => node.kind === 'sampler'));
  const loraNode = computed(() => workflow.value.nodes.find(node => node.kind === 'lora'));
  const modelId = computed(() => String(modelNode.value?.params.modelId ?? 'anima-base-1'));
  const model = computed(() => getStudioModel(modelId.value));
  const prompt = computed(() => String(promptNode.value?.params.prompt ?? ''));
  const negativePrompt = computed(() => String(promptNode.value?.params.negativePrompt ?? ''));
  const steps = computed(() => Number(samplerNode.value?.params.steps ?? 28));
  const seed = computed(() => Number(samplerNode.value?.params.seed ?? 0));
  const aspect = computed(() => String(samplerNode.value?.params.aspect ?? '1:1'));
  const guidance = computed(() => Number(samplerNode.value?.params.guidance ?? 4));
  const loras = computed<LoRAEntry[]>(() => {
    const values = loraNode.value?.params.loras;
    return Array.isArray(values) ? values as LoRAEntry[] : [];
  });
  const selected = computed(() => {
    const matches = history.value.filter(o => o.modelId === modelId.value);
    return matches.find(o => o.outputId === selectedOutputId.value) ?? matches[0] ?? null;
  });
  const checkpoint = computed(() => String(modelNode.value?.params.checkpoint ?? ''));
  const checkpointMismatch = computed(() => !!checkpoint.value && checkpoint.value !== backendSnapshot.value);
  const canSubmit = computed(() =>
    modelId.value === 'anima-base-1' &&
    workflow.value.intent === 'create' &&
    backendReady.value &&
    !!backendSnapshot.value &&
    !checkpointMismatch.value &&
    !!prompt.value.trim() &&
    !activeJobId.value &&
    jobState.value !== 'submitting'
  );
  async function syncLocalCheckpoints() {
    try {
      const index = await loadModelIndex();
      backendSnapshot.value = index.anima_snapshot ?? null;
      backendReady.value = index.backend_ready === true;
      backendConfigured.value = index.backend_configured === true;
      // Browser local paths are never equivalent to installed GPU-worker paths.
      if (backendSnapshot.value && !checkpoint.value && modelId.value === 'anima-base-1') {
        edit('model', 'checkpoint', backendSnapshot.value);
      }
    } catch {
      backendSnapshot.value = null;
      backendReady.value = false;
      backendConfigured.value = false;
    }
  }


  function edit(kind: 'prompt' | 'sampler' | 'model' | 'lora', field: FieldId, value: FieldValue) {
    const node = workflow.value.nodes.find(item => item.kind === kind);
    if (node) workflow.value = updateNodeValue(workflow.value, node.id, field, value);
  }
  function setModel(id: string) {
    const priorPrompt = prompt.value;
    const priorNegative = negativePrompt.value;
    const next = makeWorkflow('create', id);
    const promptPart = next.nodes.find(node => node.kind === 'prompt');
    if (promptPart) { promptPart.params.prompt = priorPrompt; promptPart.params.negativePrompt = priorNegative; }
    workflow.value = next;
    selectedOutputId.value = null;
    if (id === 'anima-base-1' && backendSnapshot.value) edit('model', 'checkpoint', backendSnapshot.value);
  }
  function setIntent(intent: StudioIntent) {
    if (!model.value.intents.includes(intent)) return;
    const next = makeWorkflow(intent, modelId.value);
    for (const kind of ['prompt', 'sampler', 'lora'] as const) {
      const source = workflow.value.nodes.find(n => n.kind === kind);
      const target = next.nodes.find(n => n.kind === kind);
      if (source && target) target.params = { ...target.params, ...source.params };
    }
    workflow.value = next;
  }
  function restore() { workflow.value = makeWorkflow(workflow.value.intent, modelId.value); }
  function setPreset(preset: StudioWorkflow) { workflow.value = preset; }
  function setLoras(values: LoRAEntry[]) { edit('lora', 'loras', values); }
  function addLora() {
    if (loras.value.length >= 1000) return;
    setLoras([...loras.value, { id: 'lora-' + Date.now().toString(36), name: '', strength: 1, enabled: false }]);
  }
  function removeLora(id: string) { setLoras(loras.value.filter(l => l.id !== id)); }
  function editLora(id: string, patch: Partial<LoRAEntry>) { setLoras(loras.value.map(l => l.id === id ? { ...l, ...patch } : l)); }

  async function refreshRuntime(signal?: AbortSignal) {
    runtimeLoading.value = true; runtimeError.value = '';
    try { runtime.value = await fetchRuntimeSnapshot(signal); }
    catch (error) {
      if ((error as Error)?.name !== 'AbortError') { runtimeError.value = error instanceof Error ? error.message : '后端未连接'; runtime.value = null; }
    } finally { runtimeLoading.value = false; }
  }
  async function loadRecent() {
    try {
      const result = await loadJobs();
      jobs.value = result.jobs;
      if (!activeJobId.value) {
        const pending = result.jobs.find(job => job.state === 'running' || job.state === 'queued');
        if (pending) { activeJobId.value = pending.id; jobState.value = pending.state; }
      }
      const outputs: GeneratedImage[] = [];
      for (const job of result.jobs) {
        if (job.state !== 'completed') continue;
        try { outputs.push(outputFromJob(job)); } catch { /* malformed outputs never displayed */ }
      }
      history.value = outputs.slice(0, 60);
      if (selectedOutputId.value && !outputs.some(x => x.outputId === selectedOutputId.value)) selectedOutputId.value = null;
    } catch (error) {
      jobError.value = error instanceof Error ? error.message : '任务历史暂时不可读取';
    }
  }
  async function submit() {
    if (!canSubmit.value) {
      jobError.value = modelId.value !== 'anima-base-1'
        ? '当前仅 Anima Base 1.0 支持真实生成'
        : checkpointMismatch.value ? '当前底模与后端已安装快照不一致'
        : !backendReady.value ? '请先安装完整 Anima 模型并启动后端'
        : '请填写提示词或等待当前任务结束';
      return;
    }
    jobError.value = ''; jobState.value = 'submitting';
    try {
      const job = await submitImageJob(workflow.value);
      activeJobId.value = job.id; jobState.value = job.state;
      jobs.value = [job, ...jobs.value.filter(x => x.id !== job.id)].slice(0, 50);
    } catch (error) {
      jobState.value = 'failed'; jobError.value = error instanceof Error ? error.message : '任务提交失败';
    }
  }
  async function pollActive() {
    const id = activeJobId.value; if (!id) return;
    try {
      const job = await getImageJob(id);
      if (id !== activeJobId.value) return;
      jobState.value = job.state;
      jobs.value = [job, ...jobs.value.filter(x => x.id !== id)].slice(0, 50);
      if (job.state === 'completed') {
        try {
          const output = outputFromJob(job);
          history.value = [output, ...history.value.filter(x => x.outputId !== output.outputId)].slice(0, 60);
          selectedOutputId.value = output.outputId;
        } catch (error) { jobError.value = error instanceof Error ? error.message : '输出文件数据不合法'; }
      }
      if (job.state === 'failed') jobError.value = job.error || '生成失败';
      if (['completed', 'failed', 'cancelled'].includes(job.state)) activeJobId.value = null;
    } catch (error) {
      // A transient network error should not falsely complete or cancel GPU work.
      jobError.value = error instanceof Error ? error.message : '无法读取任务状态';
    }
  }
  async function cancel() {
    if (!activeJobId.value) return;
    try { await cancelImageJob(activeJobId.value); }
    catch (error) { jobError.value = error instanceof Error ? error.message : '取消任务失败'; }
  }

  return {
    workflow, history, jobs, selectedOutputId, activeJobId, jobState, jobError,
    runtime, runtimeError, runtimeLoading, backendSnapshot, backendReady, backendConfigured,
    checkpoint, checkpointMismatch, syncLocalCheckpoints, modelId, model, prompt, negativePrompt,
    steps, seed, aspect, guidance, loras, selected, canSubmit,
    edit, setModel, setIntent, restore, setPreset, setLoras, addLora, editLora, removeLora,
    refreshRuntime, loadRecent, submit, pollActive, cancel,
  };
});
