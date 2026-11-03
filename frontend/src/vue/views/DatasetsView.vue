<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue';
import { ArrowDownToLine, Database, ImagePlus, Images, Info, Trash2, UploadCloud } from 'lucide-vue-next';

interface LocalImage { id: string; name: string; url: string; size: number; caption: string }
const items = ref<LocalImage[]>([]);
const selectedId = ref<string | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const notice = ref('');
const selected = computed(() => items.value.find(item => item.id === selectedId.value) ?? null);
const isImage = (file: File) => ['image/png','image/jpeg','image/webp'].includes(file.type);
const captionKey = (filename: string) => filename.toLowerCase().replace(/\.tags\.txt$|\.txt$|\.(png|jpg|jpeg|webp)$/g, '');
async function consumeFiles(files: File[]) {
  const captions = new Map<string, string>();
  for (const file of files) if (file.name.toLowerCase().endsWith('.txt') && file.size < 100000) {
    captions.set(captionKey(file.name), (await file.text()).slice(0, 20000));
  }
  let added=0;
  for (const file of files) {
    if (!isImage(file)) continue;
    if (file.size > 25*1024*1024 || items.value.length >= 80) { notice.value='仅展示前 80 张、单张不超过 25 MB 的本地图片'; continue; }
    const id='local-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2);
    items.value.push({ id, name:file.name, url: URL.createObjectURL(file), size:file.size, caption:captions.get(captionKey(file.name)) ?? '' });
    added++;
  }
  if (items.value.length && !selectedId.value) selectedId.value=items.value[0].id;
  if (added) notice.value='已在浏览器中预览 '+added+' 张图片（尚未保存到训练后端）';
  else if(!files.length) notice.value='';
}
async function filePicked(event: Event) {
  const el = event.target as HTMLInputElement;
  await consumeFiles(Array.from(el.files??[]));el.value='';
}
async function dropped(event: DragEvent) { await consumeFiles(Array.from(event.dataTransfer?.files??[])); }
function remove(item: LocalImage) {
  URL.revokeObjectURL(item.url);
  items.value=items.value.filter(x=>x.id!==item.id);
  if(selectedId.value===item.id) selectedId.value=items.value[0]?.id??null;
}
function clear() { items.value.forEach(x=>URL.revokeObjectURL(x.url));items.value=[];selectedId.value=null;notice.value='本地预览已清空'; }
function exportCaption() {
  const item=selected.value;if(!item)return;
  const url=URL.createObjectURL(new Blob([item.caption],{type:'text/plain;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download=captionKey(item.name)+'.tags.txt';a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
onUnmounted(() => items.value.forEach(item => URL.revokeObjectURL(item.url)));
</script>
<template>
  <div class="datasets-view">
    <div class="utility-bar"><span class="count-indicator"><Database :size="16"/>{{items.length}} 张本地预览</span>
      <button v-if="items.length" class="subtle-button" @click="clear"><Trash2 :size="16"/>清空预览</button>
    </div>
    <div class="datasets-layout">
      <section class="panel dataset-main">
        <div class="panel-heading"><div class="panel-title"><Images :size="18"/><h2>数据素材</h2></div><span class="mini-tag">LOCAL ONLY</span></div>
        <div v-if="!items.length" class="dataset-drop" role="button" tabindex="0" @click="fileInput?.click()" @keydown.enter="fileInput?.click()" @dragover.prevent @drop.prevent="dropped">
          <div class="drop-symbol"><UploadCloud :size="36" :stroke-width="1.4"/></div>
          <strong>拖放图片与 Caption 到这里</strong><span>PNG / JPG / WebP + TXT</span><button class="outline-link" type="button" @click.stop="fileInput?.click()"><ImagePlus :size="16"/>选择文件</button>
        </div>
        <div v-else class="dataset-grid">
          <button v-for="item in items" :key="item.id" class="dataset-thumb" :class="{selected:item.id===selectedId}" @click="selectedId=item.id">
            <img :src="item.url" :alt="item.name" loading="lazy"/><span>{{item.name}}</span>
          </button>
          <button class="dataset-add-tile" aria-label="添加更多文件" @click="fileInput?.click()"><ImagePlus :size="23"/><span>添加素材</span></button>
        </div>
        <input ref="fileInput" type="file" accept="image/png,image/jpeg,image/webp,.txt" multiple class="sr-only" @change="filePicked"/>
        <p class="dataset-notice"><Info :size="15"/>仅在当前浏览器会话预览，不会自动保存或上传。</p>
        <p v-if="notice" class="inline-notice">{{notice}}</p>
      </section>
      <aside class="panel dataset-inspector">
        <div class="panel-heading"><div class="panel-title"><Database :size="17"/><h2>Caption 检查</h2></div><span class="mini-tag">DANBOORU TXT</span></div>
        <template v-if="selected">
          <img class="dataset-inspector-preview" :src="selected.url" :alt="selected.name"/>
          <strong class="dataset-inspector-name">{{selected.name}}</strong>
          <label class="field-label" for="dataset-caption">标签 / 自然语言 Caption</label>
          <textarea id="dataset-caption" v-model="selected.caption" class="caption-textarea" placeholder="与图片配对的文本标签…" maxlength="20000"/>
          <button class="download-button" @click="exportCaption"><ArrowDownToLine :size="16"/>导出当前 .tags.txt</button>
          <button class="outline-link dataset-remove" @click="remove(selected)"><Trash2 :size="15"/>移除图片</button>
        </template>
        <div v-else class="dataset-inspector-empty"><Database :size="29"/><span>选中图片后显示 Caption</span></div>
      </aside>
    </div>
  </div>
</template>
