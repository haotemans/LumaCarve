<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import {
  Aperture, Brush, Check, ChevronDown, CirclePlay, Clock3, Eraser, Image as ImageIcon,
  Images, Layers3, Maximize2, Plus, RotateCcw, Save, Settings2, Shuffle, Sparkles,
  Trash2, Upload, WandSparkles, X, Zap,
} from 'lucide-vue-next';
import { useStudioStore } from '../stores/studio';
import { studioModels, validateImport } from '../../features/image-studio/workflow';
import type { StudioIntent } from '../../features/image-studio/workflow';

const studio = useStudioStore();
const showNegative = ref(false);
const presetFile = ref<HTMLInputElement | null>(null);
const feedback = ref('');
interface LocalReference { id: string; url: string; name: string; width: number; height: number }
const referenceImages = ref<LocalReference[]>([]);
const selectedReferenceId = ref<string | null>(null);
const sourceInput = ref<HTMLInputElement | null>(null);
const maskCanvas = ref<HTMLCanvasElement | null>(null);
const maskDirty = ref(false);
const brushSize = ref(30);
const eraseMask = ref(false);
const isPainting = ref(false);
const activeReference = computed(() => referenceImages.value.find(x => x.id === selectedReferenceId.value) ?? referenceImages.value[0] ?? null);
const ratios = [
  { value: '1:1', label: '1:1', w: 21, h: 21 },
  { value: '4:3', label: '4:3', w: 25, h: 19 },
  { value: '3:4', label: '3:4', w: 19, h: 25 },
  { value: '16:9', label: '16:9', w: 28, h: 16 },
  { value: '9:16', label: '9:16', w: 16, h: 28 },
  { value: '3:2', label: '3:2', w: 27, h: 18 },
  { value: '2:3', label: '2:3', w: 18, h: 27 },
];
const previewRatio = computed(() =>
  studio.workflow.intent !== 'create' && activeReference.value
    ? `${activeReference.value.width} / ${activeReference.value.height}`
    : studio.selected
      ? `${studio.selected.width} / ${studio.selected.height}`
      : studio.aspect.replace(':', ' / ')
);
const busy = computed(() => !!studio.activeJobId || studio.jobState === 'submitting');
const statusText = computed(() => {
  switch (studio.jobState) {
    case 'queued': return '排队中';
    case 'running': return '正在生成';
    case 'submitting': return '提交中';
    case 'completed': return '生成完成';
    case 'failed': return '运行失败';
    case 'cancelled': return '已取消';
    default: return '就绪';
  }
});
const recent = computed(() => studio.history.filter(o => o.modelId === studio.modelId).slice(0, 10));
let pollTimer: number | undefined;
onMounted(() => {
  void studio.loadRecent();
  void studio.syncLocalCheckpoints();
  if (!studio.runtime && !studio.runtimeLoading) void studio.refreshRuntime();
  pollTimer = window.setInterval(() => { if (studio.activeJobId) void studio.pollActive(); }, 1500);
});
onUnmounted(() => {
  if (pollTimer !== undefined) window.clearInterval(pollTimer);
  referenceImages.value.forEach(item => URL.revokeObjectURL(item.url));
});

function fieldInput(event: Event) { return (event.target as HTMLInputElement).value; }
function setSteps(event: Event) { studio.edit('sampler', 'steps', Math.max(1, Math.min(150, Math.round(Number(fieldInput(event)) || 1)))); }
function setGuidance(event: Event) { studio.edit('sampler', 'guidance', Math.max(0, Math.min(20, Number(fieldInput(event)) || 0))); }
function randomSeed() { studio.edit('sampler', 'seed', Math.floor(Math.random() * 4294967295)); }
function setSeed(event: Event) { studio.edit('sampler', 'seed', Math.max(0, Math.min(4294967295, Math.round(Number(fieldInput(event)) || 0)))); }
function downloadPreset() {
  const file = new Blob([JSON.stringify(studio.workflow, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(file);
  const link = document.createElement('a');
  link.href = url; link.download = 'lumacarve-preset.json'; link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  feedback.value = '预设已保存';
}
async function importPreset(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0]; input.value = '';
  if (!file) return;
  if (file.size > 2 * 1024 * 1024) { feedback.value = '预设超过 2 MB'; return; }
  try { studio.setPreset(validateImport(JSON.parse(await file.text()))); feedback.value = '预设已导入'; }
  catch (error) { feedback.value = error instanceof Error ? error.message : '预设格式不正确'; }
}
function setIntent(intent: StudioIntent) {
  if (!studio.model.intents.includes(intent)) return;
  studio.setIntent(intent);
}
function setModel(event: Event) {
  studio.setModel(fieldInput(event));
  referenceImages.value.forEach(item => URL.revokeObjectURL(item.url));
  referenceImages.value = []; selectedReferenceId.value = null; maskDirty.value = false;
}
function updateLora(id: string, field: 'name' | 'strength' | 'enabled', value: string | number | boolean) {
  if (field === 'strength') studio.editLora(id, { strength: Math.max(-2, Math.min(2, Number(value))) });
  else if (field === 'name') studio.editLora(id, { name: String(value) });
  else studio.editLora(id, { enabled: Boolean(value) });
}
async function addReferenceImages(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []); input.value = '';
  for (const file of files) {
    if (!['image/png','image/jpeg','image/webp'].includes(file.type) || file.size > 25 * 1024 * 1024) continue;
    if (referenceImages.value.length >= studio.model.maxReferences) break;
    try {
      const decoded = await createImageBitmap(file);
      const scale = Math.min(1, 1600 / Math.max(decoded.width, decoded.height));
      const width = Math.max(1, Math.round(decoded.width * scale));
      const height = Math.max(1, Math.round(decoded.height * scale));
      const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
      const context = canvas.getContext('2d');
      if (!context) { decoded.close(); throw new Error('Canvas 无法初始化'); }
      context.drawImage(decoded, 0, 0, width, height);
      decoded.close();
      const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/webp', .9));
      if (!blob) throw new Error('参考图预览失败');
      const id = 'ref-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
      referenceImages.value.push({ id, name:file.name, width, height, url:URL.createObjectURL(blob) });
      selectedReferenceId.value = id;
      maskDirty.value = false;
    } catch (err) { feedback.value = err instanceof Error ? err.message : '图片无法打开'; }
  }
}
function removeReference(id: string) {
  const found = referenceImages.value.find(item => item.id === id);
  if (found) URL.revokeObjectURL(found.url);
  referenceImages.value = referenceImages.value.filter(item => item.id !== id);
  if (selectedReferenceId.value === id) selectedReferenceId.value = referenceImages.value[0]?.id ?? null;
  maskDirty.value = false;
}
function maskPoint(event: PointerEvent, canvas: HTMLCanvasElement) {
  const rect=canvas.getBoundingClientRect();
  return { x:(event.clientX-rect.left)/rect.width*canvas.width, y:(event.clientY-rect.top)/rect.height*canvas.height };
}
function paint(event: PointerEvent, start: boolean) {
  const canvas=maskCanvas.value;const ctx=canvas?.getContext('2d');if(!canvas||!ctx)return;
  const p=maskPoint(event,canvas);
  ctx.lineWidth=brushSize.value*canvas.width/Math.max(1,canvas.getBoundingClientRect().width);
  ctx.lineJoin='round';ctx.lineCap='round';
  ctx.globalCompositeOperation=eraseMask.value?'destination-out':'source-over';
  ctx.strokeStyle='rgba(255,255,255,.92)';
  if(start){isPainting.value=true;canvas.setPointerCapture(event.pointerId);ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(p.x+.01,p.y+.01);}
  else if(isPainting.value){ctx.lineTo(p.x,p.y);}
  if(isPainting.value){ctx.stroke();maskDirty.value=true;}
}
function maskDown(event: PointerEvent) { paint(event,true); }
function maskMove(event: PointerEvent) { if (isPainting.value) paint(event,false); }
function maskUp() { isPainting.value=false; }
function clearMask() { const c=maskCanvas.value;c?.getContext('2d')?.clearRect(0,0,c.width,c.height);maskDirty.value=false; }
function exportMask() {
  const c=maskCanvas.value;if(!c||!maskDirty.value){feedback.value='先在原图上绘制蒙版';return;}
  c.toBlob(blob=>{if(!blob)return;const url=URL.createObjectURL(blob);
    const a=document.createElement('a');a.href=url;a.download='lumacarve-mask.png';a.click();
    window.setTimeout(()=>URL.revokeObjectURL(url),1000);
  },'image/png');
}
function start() { feedback.value = ''; void studio.submit(); }
</script>

<template>
  <div class="studio-page">
    <div class="studio-commandbar">
      <div class="mode-segments" role="group" aria-label="创作模式">
        <button :class="{active:studio.workflow.intent==='create'}" @click="setIntent('create')">
          <WandSparkles :size="16"/> 文字生成
        </button>
        <button :disabled="!studio.model.intents.includes('reference')" :class="{active:studio.workflow.intent==='reference'}" title="当前模型不支持时不可选" @click="setIntent('reference')">
          <ImageIcon :size="16"/> 参考编辑
        </button>
        <button :disabled="!studio.model.intents.includes('inpaint')" :class="{active:studio.workflow.intent==='inpaint'}" title="当前模型不支持时不可选" @click="setIntent('inpaint')">
          <Layers3 :size="16"/> 局部重绘
        </button>
      </div>
      <div class="commandbar-right">
        <span v-if="feedback" class="action-feedback" role="status">{{feedback}}</span>
        <button class="subtle-button" title="导入参数预设" @click="presetFile?.click()"><Upload :size="16"/><span>导入</span></button>
        <button class="subtle-button" title="导出参数预设" @click="downloadPreset"><Save :size="16"/><span>保存预设</span></button>
        <button class="icon-action" title="恢复默认参数" aria-label="恢复默认参数" @click="studio.restore()"><RotateCcw :size="16"/></button>
        <input ref="presetFile" type="file" accept=".json,application/json" class="sr-only" @change="importPreset"/>
      </div>
    </div>

    <div class="studio-grid">
      <aside class="studio-left">
        <section class="panel model-panel">
          <div class="panel-caption"><span>01 / 基础模型</span><span class="mini-tag">MODEL</span></div>
          <div class="model-avatar"><span class="model-avatar-mark"><Sparkles :size="23"/></span><span class="model-avatar-dot"/></div>
          <label class="field-label" for="model-select">当前模型</label>
          <div class="native-select-wrap">
            <select id="model-select" class="native-select" :value="studio.modelId" @change="setModel">
              <option v-for="model in studioModels" :key="model.id" :value="model.id">{{model.label}}</option>
            </select>
            <ChevronDown :size="16"/>
          </div>
          <div class="model-meta"><span class="tiny-dot" :class="{green:studio.backendReady}"/>{{studio.modelId!=='anima-base-1'?'模型适配未接入':studio.backendReady?'后端模型已就绪':studio.backendSnapshot?'模型已发现，依赖未就绪':'未安装完整 Anima 模型'}}</div>
          <div v-if="studio.modelId==='anima-base-1'" class="under-panel-note">
            <span v-if="studio.backendSnapshot" :title="studio.backendSnapshot">已验证目录：{{studio.backendSnapshot}}</span>
            <RouterLink v-else to="/models" class="tiny-text-button">前往模型库安装 →</RouterLink>
            <button type="button" class="tiny-text-button" title="重新扫描后端" @click="studio.syncLocalCheckpoints()"><RotateCcw :size="12"/>刷新模型</button>
          </div>
        </section>

        <section v-if="studio.workflow.intent!=='create'" class="panel reference-panel">
          <div class="panel-heading">
            <div class="panel-title"><ImageIcon :size="17"/><h2>参考图片</h2></div>
            <span class="mini-tag">{{referenceImages.length}} / {{studio.model.maxReferences}}</span>
          </div>
          <button class="reference-upload" :disabled="referenceImages.length>=studio.model.maxReferences" @click="sourceInput?.click()"><Upload :size="20"/><span>添加图片</span><small>PNG / JPG / WebP</small></button>
          <input ref="sourceInput" class="sr-only" type="file" accept="image/png,image/jpeg,image/webp" multiple @change="addReferenceImages"/>
          <div v-if="referenceImages.length" class="reference-thumbs">
            <div v-for="item in referenceImages" :key="item.id" class="reference-item" :class="{chosen:activeReference?.id===item.id}">
              <button :title="item.name" :aria-label="'查看 '+item.name" @click="selectedReferenceId=item.id;maskDirty=false"><img :src="item.url" :alt="item.name"/></button>
              <button class="reference-remove" :aria-label="'删除 '+item.name" @click="removeReference(item.id)"><X :size="12"/></button>
            </div>
          </div>
          <div v-if="studio.workflow.intent==='inpaint' && activeReference" class="mask-settings">
            <div class="control-label"><span>蒙版笔刷</span><output>{{brushSize}} px</output></div>
            <input v-model.number="brushSize" type="range" min="6" max="100" step="1" class="range-input" aria-label="蒙版笔刷大小"/>
            <div class="mask-buttons">
              <button :class="{active:!eraseMask}" @click="eraseMask=false"><Brush :size="14"/>绘制</button>
              <button :class="{active:eraseMask}" @click="eraseMask=true"><Eraser :size="14"/>擦除</button>
              <button @click="clearMask"><RotateCcw :size="14"/>清除</button>
              <button :disabled="!maskDirty" @click="exportMask"><Save :size="14"/>导出</button>
            </div>
          </div>
          <div class="under-panel-note">仅本地预览；编辑模型后端尚未连接</div>
        </section>

        <section class="panel prompt-panel">
          <div class="panel-heading"><div class="panel-title"><Sparkles :size="17"/><h2>提示词</h2></div><span class="count-label">{{studio.prompt.length}} / 20000</span></div>
          <label class="sr-only" for="positive-prompt">正向提示词</label>
          <textarea id="positive-prompt" class="prompt-textarea" :value="studio.prompt" maxlength="20000"
            spellcheck="false" placeholder="描绘你希望生成的画面、角色、光影与风格…"
            @input="studio.edit('prompt','prompt',fieldInput($event))"/>
          <button class="disclosure-button" :aria-expanded="showNegative" @click="showNegative=!showNegative">
            <span><Settings2 :size="15"/> 负面提示词</span><ChevronDown :size="15" :class="{turned:showNegative}"/>
          </button>
          <textarea v-if="showNegative" class="prompt-textarea negative-textarea" aria-label="负面提示词"
            :value="studio.negativePrompt" maxlength="20000" placeholder="不希望出现的元素…"
            @input="studio.edit('prompt','negativePrompt',fieldInput($event))"/>
        </section>

        <section class="panel lora-panel">
          <div class="panel-heading"><div class="panel-title"><Layers3 :size="17"/><h2>LoRA 叠加</h2></div><span class="count-label">{{studio.loras.filter(item=>item.enabled).length}} 已启用</span></div>
          <div v-if="!studio.loras.length" class="lora-empty"><div class="lora-icon"><Layers3 :size="21"/></div><span>尚未添加 LoRA</span></div>
          <div v-for="item in studio.loras" :key="item.id" class="lora-entry">
            <div class="lora-entry-top">
              <label class="check-label"><input type="checkbox" :checked="item.enabled" :aria-label="'启用 '+(item.name||'新 LoRA')" @change="updateLora(item.id,'enabled',($event.target as HTMLInputElement).checked)"/></label>
              <input :value="item.name" class="lora-name-input" placeholder="已安装 LoRA 名称" :aria-label="'LoRA 名称 '+item.id" maxlength="255" @input="updateLora(item.id,'name',fieldInput($event))"/>
              <button class="icon-action danger-hover" title="移除 LoRA" :aria-label="'移除 '+item.name" @click="studio.removeLora(item.id)"><X :size="15"/></button>
            </div>
            <div class="lora-weight"><input type="range" min="-2" max="2" step=".05" :value="item.strength" :aria-label="(item.name||'LoRA')+' 权重'" @input="updateLora(item.id,'strength',Number(fieldInput($event)))"/><span>{{item.strength.toFixed(2)}}</span></div>
          </div>
          <button class="add-lora" @click="studio.addLora()"><Plus :size="16"/> 添加 LoRA</button>
          <div class="under-panel-note">复用同一基础模型，不复制权重</div>
        </section>
      </aside>

      <div class="studio-center">
        <section class="panel preview-panel">
          <div class="preview-top">
            <div class="panel-title"><ImageIcon :size="17"/><h2>生成画布</h2></div>
            <div class="preview-actions">
              <span class="preview-mode"><span class="tiny-dot" :class="{green:studio.selected || activeReference}"/>{{activeReference && studio.workflow.intent!=='create'?'本地参考图':studio.selected?'实际生成结果':'空画布'}}</span>
              <a v-if="studio.selected && studio.workflow.intent==='create'" class="icon-action" :href="studio.selected.imageUrl" target="_blank" rel="noopener noreferrer" title="在新标签页打开图像" aria-label="查看原始图像"><Maximize2 :size="16"/></a>
            </div>
          </div>
          <div class="canvas-stage">
            <div class="canvas-frame" :style="{aspectRatio:previewRatio}">
              <template v-if="activeReference && studio.workflow.intent!=='create'">
                <img :src="activeReference.url" :alt="activeReference.name" class="generated-image"/>
                <canvas v-if="studio.workflow.intent==='inpaint'" :key="activeReference.id" ref="maskCanvas"
                  class="mask-overlay" :width="activeReference.width" :height="activeReference.height"
                  @pointerdown.prevent="maskDown" @pointermove.prevent="maskMove"
                  @pointerup="maskUp" @pointercancel="maskUp" aria-label="蒙版涂抹区域"/>
              </template>
              <img v-else-if="studio.selected" :src="studio.selected.imageUrl" alt="本地模型实际生成的图像" class="generated-image"/>
              <div v-else class="empty-illustration">
                <div class="art-grid"/>
                <div class="art-orbit orbit-one"/><div class="art-orbit orbit-two"/>
                <div class="art-symbol"><Aperture :size="48" :stroke-width="1"/></div>
                <span class="art-label">LUMA / CANVAS</span>
                <strong>{{busy?'正在处理任务':'让灵感成形'}}</strong>
                <span class="art-subtitle">{{busy?'画面完成后将在这里展示':'输入提示词，生成你的第一张作品'}}</span>
              </div>
              <div class="canvas-watermark">LUMACARVE <span>•</span> {{activeReference && studio.workflow.intent!=='create'?'REFERENCE':studio.aspect}}</div>
            </div>
          </div>
          <div class="preview-filmstrip">
            <div class="filmstrip-images" v-if="recent.length">
              <button v-for="output in recent" :key="output.outputId"
                class="filmstrip-item" :class="{selected:studio.selected?.outputId===output.outputId}"
                :title="'Seed '+output.seed" @click="studio.selectedOutputId=output.outputId">
                <img :src="output.imageUrl" alt="实际生成结果缩略图" loading="lazy"/>
              </button>
            </div>
            <div v-else class="filmstrip-empty"><Images :size="17"/><span>生成结果将在这里组成画廊</span></div>
            <span class="filmstrip-count">{{recent.length ? recent.length+' 张作品' : '0 张作品'}}</span>
          </div>
        </section>
        <div class="generate-bar">
          <div class="generate-status">
            <div class="generate-state-icon"><Clock3 v-if="busy" :size="18"/><Check v-else :size="18"/></div>
            <div><strong>{{statusText}}</strong><span>{{busy?'可以切换页面，后台任务继续执行':studio.selected?'图片已保存到后端工作区':'准备进行本地推理'}}</span></div>
          </div>
          <button v-if="busy" class="secondary-action" @click="studio.cancel()"><X :size="16"/>取消</button>
          <button class="primary-action" :disabled="!studio.canSubmit" @click="start"><CirclePlay :size="19"/>{{busy?'生成中…':'开始生成'}}<span class="button-arrow">↗</span></button>
        </div>
        <div v-if="studio.jobError" class="inline-error" role="alert">{{studio.jobError}}</div>
        <div v-if="studio.modelId==='anima-base-1' && studio.checkpointMismatch" class="studio-ready-hint">
          <span>当前预设中的模型路径与后端快照不一致</span>
          <button class="tiny-text-button" @click="studio.edit('model','checkpoint',studio.backendSnapshot ?? '')">使用已安装快照</button>
        </div>
        <div v-if="studio.modelId==='anima-base-1' && !studio.backendReady" class="studio-ready-hint">
          <span>后端 Anima 模型尚未就绪</span><RouterLink to="/models">检查模型库 →</RouterLink>
        </div>
        <div v-if="studio.modelId!=='anima-base-1' || studio.workflow.intent!=='create'" class="inline-notice" role="status">
          当前只有 Anima 文字生成连接到真实推理后端；其它模式保留为界面预设。
        </div>
      </div>

      <aside class="studio-right">
        <section class="panel control-panel">
          <div class="panel-heading"><div class="panel-title"><Settings2 :size="17"/><h2>采样参数</h2></div><span class="mini-tag">SAMPLER</span></div>
          <div class="control-field">
            <div class="control-label"><label for="steps-range">采样步数</label><output>{{studio.steps}}</output></div>
            <input id="steps-range" class="range-input" type="range" min="1" max="80" step="1" :value="studio.steps" @input="setSteps"/>
            <div class="range-markers"><span>1</span><span>40</span><span>80</span></div>
          </div>
          <div class="control-field">
            <div class="control-label"><label for="cfg-range">引导强度</label><output>{{studio.guidance.toFixed(1)}}</output></div>
            <input id="cfg-range" class="range-input" type="range" min="0" max="20" step=".5" :value="studio.guidance" @input="setGuidance"/>
            <div class="range-markers"><span>0</span><span>10</span><span>20</span></div>
          </div>
          <div class="control-field seed-field">
            <div class="control-label"><label for="seed-number">随机种子</label><button class="tiny-text-button" @click="randomSeed"><Shuffle :size="13"/> 随机</button></div>
            <div class="seed-input-wrap"><input id="seed-number" type="number" min="0" max="4294967295" :value="studio.seed" @change="setSeed"/><button aria-label="随机生成种子" title="随机种子" @click="randomSeed"><Shuffle :size="15"/></button></div>
          </div>
        </section>

        <section class="panel ratio-panel">
          <div class="panel-heading"><div class="panel-title"><Maximize2 :size="17"/><h2>画幅比例</h2></div><span class="mini-tag">CANVAS</span></div>
          <div class="ratio-grid">
            <button v-for="ratio in ratios" :key="ratio.value" class="ratio-button" :class="{selected:studio.aspect===ratio.value}"
              :aria-pressed="studio.aspect===ratio.value" @click="studio.edit('sampler','aspect',ratio.value)">
              <div class="ratio-shape" :style="{width:ratio.w+'px',height:ratio.h+'px'}"/><span>{{ratio.label}}</span>
            </button>
          </div>
        </section>

        <section class="panel status-panel">
          <div class="panel-heading"><div class="panel-title"><Zap :size="17"/><h2>运行状态</h2></div><button class="tiny-text-button" title="手动刷新后端状态" @click="studio.refreshRuntime()"><RotateCcw :size="14"/>刷新</button></div>
          <div class="status-overview"><span class="runtime-dot" :class="{ready:studio.runtime?.engine==='anima'}"/><div><strong>{{studio.runtime?.engine==='anima'?'Anima 本地资源就绪':studio.runtimeError?'后端未连接':'等待模型就绪'}}</strong><small>{{studio.runtimeError||'GPU 尚未检测；仅报告配置状态'}}</small></div></div>
          <div class="status-metrics">
            <div><span>GPU VRAM</span><strong>—</strong></div>
            <div><span>CPU 卸载</span><strong>{{studio.runtime?.offload??'未知'}}</strong></div>
          </div>
          <div class="runtime-engine-note">智能显存均衡 <span>尚未接入</span></div>
          <details class="kernel-details">
            <summary>实验加速配置 <ChevronDown :size="14"/></summary>
            <div v-for="name in (['adaln','rope','residual','ffn'] as const)" :key="name" class="kernel-row">
              <span>{{name.toUpperCase()}}</span><span>{{studio.runtime?.kernels[name]==='experimental'?'实验配置':studio.runtime?.kernels[name]==='off'?'关闭':'未知'}}</span>
            </div>
            <p>配置不代表已实测加速</p>
          </details>
        </section>
      </aside>
    </div>
  </div>
</template>
