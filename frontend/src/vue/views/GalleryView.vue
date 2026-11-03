<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { ArrowUpRight, Image as ImageIcon, Images, RefreshCw, Search, X } from 'lucide-vue-next';
import { useStudioStore } from '../stores/studio';

const studio = useStudioStore();
const query = ref('');
const focused = ref<string | null>(null);
const filtered = computed(() => studio.history.filter(item =>
  !query.value.trim() || (item.modelId+' '+item.seed).toLowerCase().includes(query.value.trim().toLowerCase()),
));
const image = computed(() => studio.history.find(item => item.outputId === focused.value));
onMounted(() => { void studio.loadRecent(); });
</script>
<template>
  <section class="gallery-view">
    <div class="utility-bar">
      <div class="search-field"><Search :size="17"/><input v-model="query" placeholder="搜索模型或 Seed..." aria-label="搜索作品"/></div>
      <div class="utility-actions">
        <span class="count-indicator">{{filtered.length}} 张真实输出</span>
        <button class="subtle-button" @click="studio.loadRecent()"><RefreshCw :size="16"/>刷新</button>
      </div>
    </div>
    <div v-if="filtered.length" class="gallery-grid">
      <button v-for="item in filtered" :key="item.outputId" class="gallery-tile" @click="focused=item.outputId">
        <img :src="item.imageUrl" :alt="'模型 '+item.modelId+' 生成图像'" loading="lazy"/>
        <div class="gallery-overlay"><span>{{item.modelId}}</span><strong>{{item.width}} × {{item.height}}</strong></div>
      </button>
    </div>
    <div v-else class="empty-screen gallery-empty">
      <div class="empty-symbol"><Images :size="35" :stroke-width="1.3"/></div>
      <h2>{{query?'未找到匹配作品':'画廊还没有作品'}}</h2>
      <p>{{query?'尝试更换 Seed 或模型名称':'真实生图完成后自动收录到本地画廊'}}</p>
      <RouterLink to="/studio" class="primary-link">前往图像工作室 <ArrowUpRight :size="17"/></RouterLink>
    </div>
    <div v-if="image" class="image-lightbox" role="dialog" aria-modal="true" aria-label="查看生成图片" @click.self="focused=null">
      <button class="lightbox-close" aria-label="关闭预览" @click="focused=null"><X :size="22"/></button>
      <img :src="image.imageUrl" alt="原始生成作品"/>
      <div class="lightbox-meta"><span>{{image.modelId}} · Seed {{image.seed}}</span><a :href="image.imageUrl" target="_blank" rel="noopener noreferrer">打开原图 <ArrowUpRight :size="15"/></a></div>
    </div>
  </section>
</template>
