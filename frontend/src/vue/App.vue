<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { RouterView, useRoute, useRouter } from 'vue-router';
import {
  Aperture, Boxes, ChevronRight, CircleHelp, Cpu, Database,
  Images, Layers3, Menu, Settings2, WandSparkles, X, ListTodo,
} from 'lucide-vue-next';
import { useStudioStore } from './stores/studio';

const route = useRoute();
const router = useRouter();
const studio = useStudioStore();
const menuOpen = ref(false);
const desktopStartupError = ref('');
const mainNav = [
  { path: '/studio', label: '图像生成', en: 'GENERATE', icon: WandSparkles },
  { path: '/training', label: 'LoRA 训练', en: 'TRAINING', icon: Layers3 },
  { path: '/gallery', label: '作品画廊', en: 'GALLERY', icon: Images },
];
const manageNav = [
  { path: '/models', label: '模型管理', icon: Boxes },
  { path: '/datasets', label: '数据集', icon: Database },
  { path: '/tasks', label: '任务队列', icon: ListTodo },
  { path: '/system', label: '运行环境', icon: Settings2 },
];
const title = computed(() => String(route.meta.title || '图像工作室'));
const section = computed(() => String(route.meta.section || 'STUDIO'));
const runtimeStatus = computed(() =>
  desktopStartupError.value || studio.runtimeError ? '本地 API 未连接' :
  studio.runtime?.engine === 'anima' ? 'Anima 推理就绪' :
  studio.runtime?.configuredEngine === 'disabled' ? 'API 已连接 · GPU 未启用' :
  studio.runtime ? 'API 已连接 · 模型未就绪' : '正在读取本地 API'
);
watch(() => route.path, () => { menuOpen.value = false; });
onMounted(() => {
  desktopStartupError.value = document.body.dataset.desktopError || '';
  if (!studio.runtime && !desktopStartupError.value) void studio.refreshRuntime();
});
function go(path: string) { void router.push(path); menuOpen.value = false; }
</script>

<template>
  <div class="app-shell">
    <button v-if="menuOpen" class="mobile-scrim" aria-label="关闭导航" @click="menuOpen=false"/>
    <aside class="app-sidebar" :class="{ 'sidebar-open': menuOpen }">
      <div class="brand" @click="go('/studio')" role="button" tabindex="0" @keydown.enter="go('/studio')">
        <div class="brand-mark"><Aperture :size="24" :stroke-width="1.85"/></div>
        <div class="brand-name"><strong>LumaCarve</strong><span>CREATIVE ENGINE</span></div>
        <button class="mobile-close ghost-button" aria-label="关闭导航" @click.stop="menuOpen=false"><X :size="18"/></button>
      </div>
      <div class="sidebar-section-label">创作空间 <span>WORKSPACE</span></div>
      <nav class="nav-stack" aria-label="创作导航">
        <button v-for="item in mainNav" :key="item.path" class="nav-link"
          :class="{ 'nav-active': route.path === item.path }" @click="go(item.path)">
          <component :is="item.icon" :size="19" :stroke-width="1.7"/>
          <span class="nav-copy">{{item.label}}<small>{{item.en}}</small></span>
          <ChevronRight v-if="route.path === item.path" :size="16" class="nav-arrow"/>
        </button>
      </nav>
      <div class="sidebar-section-label second-label">资源中心 <span>LIBRARY</span></div>
      <nav class="nav-stack" aria-label="资源管理导航">
        <button v-for="item in manageNav" :key="item.path" class="nav-link nav-secondary"
          :class="{ 'nav-active': route.path === item.path }" @click="go(item.path)">
          <component :is="item.icon" :size="18" :stroke-width="1.7"/>
          <span class="nav-copy">{{item.label}}</span>
          <ChevronRight v-if="route.path === item.path" :size="15" class="nav-arrow"/>
        </button>
      </nav>
      <div class="sidebar-fill"/>
      <div class="sidebar-runtime">
        <div class="runtime-symbol"><Cpu :size="19"/></div>
        <div class="runtime-copy"><strong>LOCAL ENGINE</strong><span>{{runtimeStatus}}</span></div>
        <span class="engine-dot" :class="{ready:studio.runtime?.engine==='anima',connected:!!studio.runtime && studio.runtime.configuredEngine==='disabled'}"/>
      </div>
      <div class="sidebar-foot"><span>VUE 3 · LOCAL FIRST</span><span>v0.2.3</span></div>
    </aside>

    <div class="app-content">
      <header class="topbar">
        <div class="topbar-left">
          <button class="icon-button mobile-trigger" aria-label="打开导航" :aria-expanded="menuOpen" @click="menuOpen=!menuOpen"><Menu :size="21"/></button>
          <div class="breadcrumbs"><span>LUMACARVE</span><ChevronRight :size="14"/><span>{{section}}</span></div>
        </div>
        <div class="topbar-right">
          <span class="api-chip"><span class="status-pulse" :class="{ok:studio.runtime?.engine==='anima',connected:!!studio.runtime && studio.runtime.configuredEngine==='disabled'}"/>{{runtimeStatus}}</span>
          <button class="icon-button help-button" aria-label="查看运行环境" title="运行环境" @click="go('/system')"><CircleHelp :size="19"/></button>
        </div>
      </header>

      <div v-if="desktopStartupError" class="desktop-startup-error" role="alert">
        <strong>本地 API 启动失败</strong>
        <span>{{ desktopStartupError }}。请检查便携目录下 LumaCarveData/logs/api.log。不要直接运行 lumacarve-api.exe。</span>
      </div>
      <main class="workspace-content">
        <div class="page-header">
          <div class="page-heading">
            <div class="eyebrow"><span class="eyebrow-rule"/>{{section}}</div>
            <h1>{{title}}</h1>
          </div>
        </div>
        <RouterView/>
      </main>
      <footer class="main-footer"><span>© LumaCarve · 琢影</span><RouterLink to="/system">运行详情</RouterLink></footer>
    </div>
  </div>
</template>
