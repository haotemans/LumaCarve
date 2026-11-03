<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';
import { ArrowDownToLine, Box, CheckCircle2, Download, HardDrive, RefreshCw, ShieldAlert, Sparkles } from 'lucide-vue-next';
import { loadModelCatalog, loadModelIndex, loadDownloadJob, startModelDownload } from '../api';
import type { CatalogModel, DownloadJob, IndexedModel, ModelCatalog } from '../api';
const catalog = ref<ModelCatalog | null>(null);
const localModels = ref<IndexedModel[]>([]);
const provider = ref<'huggingface'|'modelscope'>('huggingface');
const downloading = ref<DownloadJob | null>(null);
const error = ref('');
const loading = ref(false);
let timer: number | undefined;
onMounted(() => { void refresh(); });
onUnmounted(() => { if(timer !== undefined) clearInterval(timer); });
function size(bytes: number) {
  const units=['B','KiB','MiB','GiB','TiB'];
  let n=Math.max(0,bytes),i=0;
  while(n>=1024 && i<units.length-1){n/=1024;i++;}
  return n.toFixed(i?1:0)+' '+units[i];
}
async function refresh() {
  loading.value=true;error.value='';
  try {
    const [index, remote] = await Promise.all([loadModelIndex(),loadModelCatalog()]);
    localModels.value=index.files;catalog.value=remote;
    provider.value=remote.models[0]?.provider==='modelscope'?'modelscope':'huggingface';
  }catch(reason){error.value=reason instanceof Error?reason.message:'无法读取模型库';}
  finally{loading.value=false;}
}
async function watchDownload() {
  if (!downloading.value || !['queued','running'].includes(downloading.value.state)) return;
  try {
    downloading.value = await loadDownloadJob(downloading.value.id);
    if (downloading.value.state==='completed') { if(timer!==undefined)clearInterval(timer); timer=undefined; void refresh(); }
    if (downloading.value.state==='failed') { if(timer!==undefined)clearInterval(timer); timer=undefined; error.value=downloading.value.error||'下载失败'; }
  }catch(reason){error.value=reason instanceof Error?reason.message:'下载状态不可用';}
}
async function download(model: CatalogModel) {
  error.value='';
  try {
    downloading.value=await startModelDownload(model.id,provider.value);
    if(timer!==undefined)clearInterval(timer);
    timer=window.setInterval(() => { void watchDownload(); },1900);
  }catch(reason){error.value=reason instanceof Error?reason.message:'无法开始下载';}
}
</script>
<template>
  <div class="models-view">
    <div class="utility-bar"><span class="count-indicator"><HardDrive :size="16"/>{{localModels.length}} 个本地模型文件</span>
      <div class="utility-actions"><label class="simple-select">下载来源 <select v-model="provider" aria-label="模型下载来源"><option value="huggingface">Hugging Face</option><option value="modelscope">ModelScope</option></select></label>
      <button class="subtle-button" :disabled="loading" @click="refresh"><RefreshCw :size="16"/>刷新</button></div>
    </div>
    <div v-if="error" class="inline-error" role="alert">{{error}}</div>
    <div v-if="downloading" class="download-state panel" role="status">
      <div class="download-state-icon"><ArrowDownToLine :size="21"/></div>
      <div><strong>{{downloading.model_id}}</strong><span>{{downloading.state==='running'?'正在下载模型':downloading.state==='queued'?'下载任务排队':downloading.state==='completed'?'下载完成':'下载失败'}} · {{downloading.provider}}</span></div>
      <span class="mini-tag">{{downloading.state}}</span>
    </div>
    <div class="section-header"><div><span class="eyebrow small">MODEL CATALOG</span><h2>模型目录</h2></div><span class="count-indicator">来源由用户选择</span></div>
    <div v-if="catalog?.models.length" class="model-catalog-grid">
      <article v-for="(model,index) in catalog.models" :key="model.id" class="catalog-card panel">
        <div class="catalog-cover" :class="'catalog-cover-'+index"><div class="catalog-cover-orbit"/><div class="catalog-glyph"><Box :size="29" :stroke-width="1.25"/></div></div>
        <div class="catalog-card-body">
          <div class="catalog-heading"><h3>{{model.title}}</h3><span v-if="model.id==='anima-base-1'&&provider==='huggingface'" class="mini-tag">首选</span></div>
          <div class="catalog-desc"><span>{{model.id}}</span><span>{{provider==='modelscope'?'魔搭':'Hugging Face'}}</span></div>
          <p class="catalog-license">{{model.license_note}}</p>
          <button class="download-button" :disabled="!catalog.downloads_enabled || (!!downloading && ['running','queued'].includes(downloading.state))" @click="download(model)">
            <Download :size="16"/>{{catalog.downloads_enabled?'下载模型':'下载未启用'}}
          </button>
        </div>
      </article>
    </div>
    <div v-else-if="!loading" class="empty-screen"><div class="empty-symbol"><Box :size="35"/></div><h2>暂无可用模型目录</h2><p>启动本地后端后显示支持的模型来源。</p></div>
    <div class="section-header lower-section"><div><span class="eyebrow small">LOCAL FILES</span><h2>已发现的权重文件</h2></div></div>
    <div v-if="localModels.length" class="local-models panel">
      <div v-for="model in localModels" :key="model.id" class="local-model-item">
        <div class="local-model-icon"><HardDrive :size="18"/></div>
        <div><strong>{{model.name}}</strong><small>{{model.relative_path}}</small></div>
        <span>{{size(model.size_bytes)}}</span>
      </div>
    </div>
    <div v-else class="empty-inline"><ShieldAlert :size="17"/>未发现已索引的模型文件。目录扫描不代表模型可运行。</div>
  </div>
</template>
