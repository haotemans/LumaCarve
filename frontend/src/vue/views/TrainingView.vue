<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { Activity, ArrowUpRight, ChevronDown, Cpu, Database, Layers3, Play, Plus, Settings2, ShieldAlert, SlidersHorizontal, Sparkles, UploadCloud } from 'lucide-vue-next';
import { datasetImageUrl, listDatasetItems, listDatasets } from '../api';
import type { DatasetItem, DatasetSummary } from '../api';

const datasets = ref<DatasetSummary[]>([]);
const currentDataset = ref('');
const sampleImages = ref<DatasetItem[]>([]);
const datasetError = ref('');
async function refreshSamples() {
  try {
    sampleImages.value = currentDataset.value ? (await listDatasetItems(currentDataset.value, 8)).items : [];
  } catch (error) {
    datasetError.value = error instanceof Error ? error.message : '样本读取失败';
  }
}
async function refreshDatasets() {
  try {
    datasets.value = (await listDatasets()).datasets;
    if (!datasets.value.some(d=>d.id===currentDataset.value)) currentDataset.value = datasets.value[0]?.id ?? '';
    await refreshSamples();
  } catch (error) {
    datasetError.value = error instanceof Error ? error.message : '数据集读取失败';
  }
}
onMounted(() => { void refreshDatasets(); });
const epochs = ref(20);
const rank = ref(32);
const lr = ref('0.0001');
const precision = ref('bf16');
const optimizer = ref('adamw8bit');
const modelId = ref('anima-base-1');
const currentPreset = computed(() => rank.value+' Rank · '+epochs.value+' Epoch');
const steps = [
  { n:'01', name:'训练数据', desc:'导入图片与 Caption', icon:UploadCloud },
  { n:'02', name:'参数设置', desc:'调整优化器与精度', icon:SlidersHorizontal },
  { n:'03', name:'开始训练', desc:'等待训练 Worker 接入', icon:Play },
];
</script>
<template>
  <div class="training-view">
    <div class="training-banner">
      <div class="training-banner-copy"><span class="eyebrow small">LORA LABORATORY</span><h2>训练，从清晰的工作流开始。</h2><p>训练后端尚未接入。本页面保留可编辑参数，不会启动虚假的 GPU 任务。</p>
        <div class="training-banner-chips"><span>BF16 优先</span><span>多优化器预设</span><span>Epoch 管理</span></div>
      </div>
      <div class="training-banner-art" aria-hidden="true"><div class="training-ring ring-outer"/><div class="training-ring ring-inner"/><Layers3 :size="42" :stroke-width="1.1"/></div>
    </div>
    <div class="training-step-grid">
      <div v-for="step in steps" :key="step.n" class="training-step panel"><span>{{step.n}}</span><component :is="step.icon" :size="19"/><strong>{{step.name}}</strong><small>{{step.desc}}</small></div>
    </div>
    <div class="training-layout">
      <section class="panel train-config">
        <div class="panel-heading"><div class="panel-title"><Settings2 :size="18"/><h2>训练参数</h2></div><span class="mini-tag">LOCAL DRAFT</span></div>
        <label class="field-label" for="train-base">基础模型</label>
        <select id="train-base" v-model="modelId" class="full-select"><option value="anima-base-1">Anima Base 1.0</option></select>
        <div class="graphic-param-block">
          <div class="control-label"><label for="train-dataset">训练数据集</label><RouterLink to="/datasets" class="tiny-text-button">管理图片</RouterLink></div>
          <select id="train-dataset" v-model="currentDataset" class="full-select" @change="refreshSamples">
            <option value="">暂无可用数据集</option>
            <option v-for="dataset in datasets" :key="dataset.id" :value="dataset.id">{{dataset.title}} · {{dataset.image_count}} 张</option>
          </select>
          <div v-if="datasetError" class="inline-error" role="alert">{{datasetError}}</div>
          <div v-if="sampleImages.length" class="training-dataset-preview">
            <img v-for="item in sampleImages" :key="item.id" :src="datasetImageUrl(currentDataset,item.id)" :alt="item.name" loading="lazy"/>
          </div>
          <div v-else class="training-dataset-empty"><Database :size="15"/>暂无保存的训练图片</div>
        </div>
        <div class="train-config-grid">
          <label class="train-input"><span>LoRA Rank</span><input v-model.number="rank" type="number" min="1" max="512"/></label>
          <label class="train-input"><span>Epoch</span><input v-model.number="epochs" type="number" min="1" max="500"/></label>
          <label class="train-input"><span>学习率</span><input v-model="lr" type="text" inputmode="decimal"/></label>
          <label class="train-input"><span>训练精度</span><select v-model="precision"><option value="bf16">BF16</option><option value="fp16">FP16</option></select></label>
          <label class="train-input train-wide"><span>优化器</span><select v-model="optimizer"><option value="adamw8bit">AdamW 8-bit</option><option value="adamw">AdamW</option><option value="muon">Muon</option><option value="came">CAME</option><option value="magicauto">MagicAuto</option></select></label>
        </div>
        <div class="train-config-footer"><span>{{currentPreset}}</span><button class="primary-action" disabled><Play :size="17"/>训练暂不可用</button></div>
      </section>
      <section class="panel train-monitor">
        <div class="panel-heading"><div class="panel-title"><Activity :size="18"/><h2>训练监控</h2></div><span class="mini-tag">NO ACTIVE RUN</span></div>
        <div class="monitor-placeholder"><div class="monitor-axes"><div class="axes-lines"/><div class="monitor-center"><Activity :size="31" :stroke-width="1.4"/><strong>等待真实训练数据</strong><small>Loss、LR 与梯度曲线将在执行后显示</small></div></div></div>
        <div class="monitor-metrics"><div><span>LOSS</span><strong>—</strong></div><div><span>LEARNING RATE</span><strong>—</strong></div><div><span>GRAD NORM</span><strong>—</strong></div></div>
      </section>
    </div>
    <div class="training-bottom-note"><ShieldAlert :size="16"/><span>这些参数仅保留于当前页面，不会提交训练任务。</span><RouterLink to="/datasets">查看数据集 <ArrowUpRight :size="15"/></RouterLink></div>
  </div>
</template>
