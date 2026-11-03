<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import {
  ArrowDownToLine, Check, ChevronLeft, ChevronRight, Database, ImagePlus,
  Images, Plus, RefreshCw, Save, Trash2, UploadCloud,
} from 'lucide-vue-next';
import {
  createDataset, datasetImageUrl, deleteDatasetImage, listDatasetItems,
  listDatasets, updateDatasetCaption, uploadDatasetImage,
} from '../api';
import type { DatasetItem, DatasetSummary } from '../api';

const datasets = ref<DatasetSummary[]>([]);
const currentId = ref('');
const nameInput = ref('');
const creating = ref(false);
const items = ref<DatasetItem[]>([]);
const total = ref(0);
const offset = ref(0);
const selectedId = ref<string | null>(null);
const captionDraft = ref('');
const fileInput = ref<HTMLInputElement | null>(null);
const importing = ref(false);
const imported = ref(0);
const uploadTotal = ref(0);
const saving = ref(false);
const loading = ref(false);
const error = ref('');
const notice = ref('');
const selected = computed(() => items.value.find(item => item.id === selectedId.value) ?? null);
const dirty = computed(() => selected.value !== null && captionDraft.value !== selected.value.caption);
const current = computed(() => datasets.value.find(item => item.id === currentId.value));
const hasNext = computed(() => offset.value + items.value.length < total.value);

watch(selected, item => { captionDraft.value = item?.caption ?? ''; });
onMounted(() => { void refreshSets(); });
function captionKey(name: string): string {
  return name.toLowerCase().replace(/\.tags\.txt$|\.txt$|\.(png|jpg|jpeg|webp)$/, '');
}
function readError(reason: unknown): string { return reason instanceof Error ? reason.message : '操作失败'; }
async function refreshSets() {
  if (dirty.value && !window.confirm('当前 Caption 未保存，确定刷新数据集？')) return;
  loading.value = true; error.value = '';
  try {
    datasets.value = (await listDatasets()).datasets;
    if (!datasets.value.some(dataset => dataset.id === currentId.value)) currentId.value = datasets.value[0]?.id ?? '';
    if (currentId.value) await refreshItems();
    else { items.value = []; total.value = 0; selectedId.value = null; }
  } catch (reason) { error.value = readError(reason); }
  finally { loading.value = false; }
}
async function refreshItems() {
  if (!currentId.value) return;
  try {
    const page = await listDatasetItems(currentId.value, 48, offset.value);
    items.value = page.items; total.value = page.total;
    if (!items.value.some(image => image.id === selectedId.value)) selectedId.value = items.value[0]?.id ?? null;
  } catch (reason) { error.value = readError(reason); }
}
function chooseItem(id: string) {
  if (id === selectedId.value) return;
  if (dirty.value && !window.confirm('当前 Caption 未保存，确定切换图片？')) return;
  selectedId.value = id;
}
async function changeSet(event: Event) {
  if (dirty.value && !window.confirm('当前 Caption 尚未保存，确定切换数据集？')) {
    (event.target as HTMLSelectElement).value = currentId.value;
    return;
  }
  currentId.value = (event.target as HTMLSelectElement).value;
  offset.value = 0; selectedId.value = null; error.value = '';
  await refreshItems();
}
async function createNew() {
  const title = nameInput.value.trim();
  if (!title) { error.value = '输入数据集名称'; return; }
  creating.value = true; error.value = '';
  const slug = title.toLowerCase().replace(/[^a-z0-9_-]/g, '-').replace(/^-+|-+$/g, '').slice(0, 36);
  const identifier = (slug || 'dataset') + '-' + Date.now().toString(36).slice(-6);
  try {
    const added = await createDataset(identifier, title);
    datasets.value = [added, ...datasets.value]; currentId.value = added.id;
    items.value = []; total.value = 0; selectedId.value = null; offset.value = 0;
    nameInput.value = ''; notice.value = '已创建训练集';
  } catch (reason) { error.value = readError(reason); }
  finally { creating.value = false; }
}
async function consumeFiles(files: File[]) {
  if (!currentId.value || importing.value) return;
  const captions = new Map<string, string>();
  for (const file of files) if (file.name.toLowerCase().endsWith('.txt') && file.size <= 100_000) {
    captions.set(captionKey(file.name), (await file.text()).slice(0, 20_000));
  }
  const images = files.filter(file => ['image/png', 'image/jpeg', 'image/webp'].includes(file.type));
  if (!images.length) { notice.value = '请选择 PNG / JPG / WebP 图片'; return; }
  if (images.length > 80) { error.value = '单次最多上传 80 张图片'; return; }
  importing.value = true; imported.value = 0; uploadTotal.value = images.length;
  error.value = ''; notice.value = '';
  const target = currentId.value;
  const failures: string[] = [];
  let index = 0;
  async function worker() {
    while (index < images.length) {
      const file = images[index++];
      try {
        if (file.size > 25 * 1024 * 1024) throw new Error('超过 25 MB');
        await uploadDatasetImage(target, file, captions.get(captionKey(file.name)) ?? '');
        imported.value++;
      } catch (reason) { failures.push(file.name + ': ' + readError(reason)); }
    }
  }
  try {
    await Promise.all(Array.from({ length: Math.min(3, images.length) }, () => worker()));
    if (currentId.value === target) { offset.value = 0; await refreshItems(); }
    const result = await listDatasets(); datasets.value = result.datasets;
    notice.value = imported.value + ' / ' + images.length + ' 张已保存';
    if (failures.length) error.value = failures.slice(0, 3).join('；') + (failures.length > 3 ? '…' : '');
  } finally { importing.value = false; }
}
async function filePicked(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []); input.value = '';
  await consumeFiles(files);
}
async function dropped(event: DragEvent) { await consumeFiles(Array.from(event.dataTransfer?.files ?? [])); }
async function saveCaption() {
  if (!selected.value || !currentId.value || !dirty.value) return;
  saving.value = true; error.value = '';
  try {
    const id = selected.value.id;
    const result = await updateDatasetCaption(currentId.value, id, captionDraft.value);
    items.value = items.value.map(item => item.id === id ? { ...item, caption: result.caption, updated_at: result.updated_at } : item);
    notice.value = 'Caption 已保存到 .tags.txt';
  } catch (reason) { error.value = readError(reason); }
  finally { saving.value = false; }
}
async function removeSelected() {
  if (!selected.value || !currentId.value || !window.confirm('确定删除这张图片及其 Caption 文件？')) return;
  try {
    await deleteDatasetImage(currentId.value, selected.value.id);
    notice.value = '已删除图片'; await refreshItems();
    datasets.value = (await listDatasets()).datasets;
  } catch (reason) { error.value = readError(reason); }
}
function exportCaption() {
  if (!selected.value) return;
  const url = URL.createObjectURL(new Blob([captionDraft.value], { type: 'text/plain;charset=utf-8' }));
  const a = document.createElement('a'); a.href = url;
  a.download = captionKey(selected.value.name) + '.tags.txt'; a.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function nextPage(direction: -1 | 1) {
  if (dirty.value && !window.confirm('Caption 尚未保存，确定翻页？')) return;
  offset.value = Math.max(0, offset.value + 48 * direction);
  await refreshItems();
}
</script>

<template>
  <div class="datasets-view">
    <div class="utility-bar dataset-toolbar">
      <div class="dataset-select-row">
        <span class="count-indicator"><Database :size="16"/>训练集</span>
        <select class="dataset-select native-select" :value="currentId" aria-label="选择训练集" @change="changeSet">
          <option v-if="!datasets.length" value="">尚无训练集</option>
          <option v-for="dataset in datasets" :key="dataset.id" :value="dataset.id">{{ dataset.title }} ({{ dataset.image_count }})</option>
        </select>
      </div>
      <div class="utility-actions">
        <span class="mini-tag">{{total}} 张图</span>
        <button class="subtle-button" :disabled="loading || importing" @click="refreshSets"><RefreshCw :size="15"/>刷新</button>
        <button class="primary-action" :disabled="!currentId || importing" @click="fileInput?.click()"><ImagePlus :size="16"/>导入图片</button>
      </div>
      <input ref="fileInput" type="file" accept="image/png,image/jpeg,image/webp,.txt" multiple class="sr-only" @change="filePicked"/>
    </div>
    <div v-if="error" class="inline-error" role="alert">{{error}}</div>
    <div v-if="notice" class="inline-notice" role="status">{{notice}}</div>
    <div v-if="importing" class="dataset-import-progress" role="progressbar" :aria-valuemin="0" :aria-valuemax="uploadTotal" :aria-valuenow="imported">
      <span>正在保存数据集</span><strong>{{imported}} / {{uploadTotal}}</strong>
      <div class="dataset-progress-track"><i :style="{ width: (uploadTotal ? 100*imported/uploadTotal : 0) + '%' }"/></div>
    </div>
    <div v-if="!currentId" class="panel dataset-create-screen">
      <div class="empty-symbol"><Database :size="33"/></div>
      <h2>创建第一个训练集</h2>
      <div class="dataset-create-actions">
        <input v-model="nameInput" class="dataset-title-input" maxlength="80" placeholder="例如：画师风格 LoRA" aria-label="新训练集名称" @keydown.enter="createNew"/>
        <button class="primary-action" :disabled="creating || !nameInput.trim()" @click="createNew"><Plus :size="16"/>创建</button>
      </div>
    </div>
    <div v-else class="datasets-layout">
      <section class="panel dataset-main">
        <div class="panel-heading">
          <div class="panel-title"><Images :size="17"/><h2>图像数据</h2></div>
          <span class="mini-tag">{{current?.title ?? currentId}}</span>
        </div>
        <div v-if="!total" class="dataset-drop" role="button" tabindex="0" @click="fileInput?.click()" @keydown.enter="fileInput?.click()" @dragover.prevent @drop.prevent="dropped">
          <div class="drop-symbol"><UploadCloud :size="30" :stroke-width="1.6"/></div>
          <strong>拖入图片和 .tags.txt</strong>
          <span>上传后保存至 LumaCarveData</span>
        </div>
        <div v-else class="dataset-grid" @dragover.prevent @drop.prevent="dropped">
          <button v-for="item in items" :key="item.id" class="dataset-thumb" :class="{ selected: item.id===selectedId }"
            :title="item.name" :aria-label="'编辑 '+item.name" @click="chooseItem(item.id)">
            <img :src="datasetImageUrl(currentId, item.id)" :alt="item.name" loading="lazy"/>
            <span>{{item.name}}</span>
          </button>
          <button class="dataset-add-tile" aria-label="添加更多图片" @click="fileInput?.click()"><ImagePlus :size="23"/><span>添加</span></button>
        </div>
        <div v-if="total>48" class="dataset-pagination">
          <button :disabled="offset===0" @click="nextPage(-1)"><ChevronLeft :size="16"/>上一页</button>
          <span>{{offset+1}}–{{Math.min(total,offset+48)}} / {{total}}</span>
          <button :disabled="!hasNext" @click="nextPage(1)">下一页<ChevronRight :size="16"/></button>
        </div>
      </section>
      <aside class="panel dataset-inspector">
        <div class="panel-heading"><div class="panel-title"><Database :size="17"/><h2>Caption</h2></div><span class="mini-tag">SIDE-CAR TXT</span></div>
        <template v-if="selected">
          <img class="dataset-inspector-preview" :src="datasetImageUrl(currentId,selected.id)" :alt="selected.name"/>
          <strong class="dataset-inspector-name">{{selected.name}}</strong>
          <div class="dataset-image-metadata">{{selected.width}} × {{selected.height}} · {{Math.ceil(selected.size_bytes/1024)}} KiB</div>
          <label class="field-label" for="dataset-caption">图片标签</label>
          <textarea id="dataset-caption" v-model="captionDraft" class="caption-textarea" maxlength="20000" placeholder="描述画面、风格、动作…"/>
          <div class="dataset-save-row">
            <button class="primary-action" :disabled="!dirty || saving" @click="saveCaption"><Save :size="15"/>{{saving?'保存中':'保存 TXT'}}<Check v-if="!dirty" :size="14"/></button>
            <button class="subtle-button" title="下载 Caption" @click="exportCaption"><ArrowDownToLine :size="16"/></button>
            <button class="icon-action danger-hover" title="删除图片" aria-label="删除图片及标签" @click="removeSelected"><Trash2 :size="16"/></button>
          </div>
        </template>
        <div v-else class="dataset-inspector-empty"><Database :size="28"/><span>选择图片后编辑 Caption</span></div>
      </aside>
    </div>
  </div>
