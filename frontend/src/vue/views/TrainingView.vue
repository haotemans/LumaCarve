<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { Activity, ArrowUpRight, ChevronDown, Database, Play, Settings2, ShieldAlert, SlidersHorizontal, UploadCloud } from 'lucide-vue-next';
import { datasetImageUrl, listDatasetItems, listDatasets } from '../api';
import type { DatasetItem, DatasetSummary } from '../api';

const datasets = ref<DatasetSummary[]>([]);
const currentDataset = ref('');
const sampleImages = ref<DatasetItem[]>([]);
const datasetError = ref('');
const showAdvanced = ref(false);
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
  { n:'01', name:'数据集', icon:UploadCloud },
  { n:'02', name:'参数', icon:SlidersHorizontal },
  { n:'03', name:'训练', icon:Play },
];
</script>
<template>
  <div class="training-view">
    <div class="training-compact-header">
      <div><strong>LoRA 训练</strong><span>参数草稿 · Worker 未接入</span></div>
      <RouterLink to="/datasets" class="subtle-button"><Database :size="15"/> 数据集</RouterLink>
    </div>
    <div class="training-progress" aria-label="训练流程；执行尚未开放">
      <div v-for="step in steps" :key="step.n" class="training-progress-step">
        <component :is="step.icon" :size="15"/>
        <span>{{step.name}}</span>
      </div>
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
          <label class="train-input"><span>Epoch</span><input v-model.number="epochs" type="number" min="1" max="500"/></label>
          <label class="train-input"><span>LoRA Rank</span><input v-model.number="rank" type="number" min="1" max="512"/></label>
        </div>
        <button type="button" class="disclosure-button train-advanced-toggle" :aria-expanded="showAdvanced" aria-controls="train-advanced" @click="showAdvanced=!showAdvanced">
          <span><Settings2 :size="15"/> 高级参数 <small>{{precision.toUpperCase()}} · {{optimizer}}</small></span>
          <ChevronDown :size="15" :class="{turned:showAdvanced}"/>
        </button>
        <div v-if="showAdvanced" id="train-advanced" class="train-config-grid">
          <label class="train-input"><span>学习率</span><input v-model="lr" type="text" inputmode="decimal"/></label>
          <label class="train-input"><span>训练精度</span><select v-model="precision"><option value="bf16">BF16</option><option value="fp16">FP16</option></select></label>
          <label class="train-input train-wide"><span>优化器</span><select v-model="optimizer"><option value="adamw8bit">AdamW 8-bit</option><option value="adamw">AdamW</option><option value="muon">Muon</option><option value="came">CAME</option><option value="magicauto">MagicAuto</option></select></label>
        </div>
        <div class="train-config-footer"><span>{{currentPreset}}</span><button class="primary-action" disabled><Play :size="17"/>训练暂不可用</button></div>
      </section>
      <section class="panel train-monitor">
        <div class="panel-heading"><div class="panel-title"><Activity :size="18"/><h2>训练监控</h2></div><span class="mini-tag">NO ACTIVE RUN</span></div>
        <div class="training-monitor-empty" role="status">
          <Activity :size="25" :stroke-width="1.5"/>
          <strong>暂无训练数据</strong>
          <span>Worker 接入后显示 Loss、LR 和 Grad</span>
        </div>
      </section>
    </div>
    <div class="training-bottom-note"><ShieldAlert :size="16"/><span>仅参数草稿，暂不执行训练。</span><RouterLink to="/datasets">管理数据集 <ArrowUpRight :size="15"/></RouterLink></div>
  </div>
</template>
