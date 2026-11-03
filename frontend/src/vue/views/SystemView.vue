<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { Activity, ArrowUpRight, Cpu, HardDrive, Info, RefreshCw, Settings2, ShieldCheck, Zap } from 'lucide-vue-next';
import { useStudioStore } from '../stores/studio';
import { API_ORIGIN } from '../api';
const studio = useStudioStore();
const kernels = [
  { key: 'adaln' as const, name: 'AdaLN Fusion', desc: '归一化与调制' },
  { key: 'rope' as const, name: 'RoPE Fusion', desc: 'Q/K 旋转位置编码' },
  { key: 'residual' as const, name: 'Residual Fusion', desc: '门控残差' },
  { key: 'ffn' as const, name: 'FFN GELU', desc: '线性层与激活' },
];
const engineLabel = computed(() => studio.runtime?.engine === 'anima' ? 'Anima 资源就绪'
  : studio.runtimeError ? '本地 API 未连接' : '尚未配置推理引擎');
onMounted(() => { if(!studio.runtime) void studio.refreshRuntime(); });
</script>
<template>
  <div class="system-view">
    <div class="utility-bar"><span class="count-indicator"><Activity :size="15"/>本地运行环境 · 只读状态</span>
      <button class="subtle-button" :disabled="studio.runtimeLoading" @click="studio.refreshRuntime"><RefreshCw :size="16"/>手动刷新</button>
    </div>
    <div class="system-summary">
      <section class="system-tile panel"><div class="system-tile-icon blue"><Cpu :size="21"/></div><span>推理引擎</span><strong>{{engineLabel}}</strong><small>不代表 GPU 已加载</small></section>
      <section class="system-tile panel"><div class="system-tile-icon purple"><HardDrive :size="21"/></div><span>GPU 显存</span><strong>—</strong><small>未采集实时数据</small></section>
      <section class="system-tile panel"><div class="system-tile-icon cyan"><Zap :size="21"/></div><span>显存策略</span><strong>{{studio.runtime?.offload || '未知'}}</strong><small>非 AMEP 智能均衡</small></section>
    </div>
    <div class="system-details-grid">
      <section class="panel system-detail">
        <div class="panel-heading"><div class="panel-title"><ShieldCheck :size="18"/><h2>Triton 实验配置</h2></div><span class="mini-tag">EXPERIMENTAL</span></div>
        <div class="kernel-cards">
          <div v-for="kernel in kernels" :key="kernel.key" class="kernel-card">
            <div class="kernel-card-icon"><Zap :size="17"/></div>
            <div><strong>{{kernel.name}}</strong><span>{{kernel.desc}}</span></div>
            <span class="kernel-mode" :class="{on:studio.runtime?.kernels[kernel.key]==='experimental'}">
              {{studio.runtime?.kernels[kernel.key]==='experimental'?'实验配置':studio.runtime?.kernels[kernel.key]==='off'?'关闭':'未知'}}
            </span>
          </div>
        </div>
        <div class="system-note"><Info :size="16"/>配置状态不表示内核正在运行，也不代表已验证加速。</div>
      </section>
      <section class="panel system-detail">
        <div class="panel-heading"><div class="panel-title"><Settings2 :size="18"/><h2>本地 API</h2></div></div>
        <dl class="system-specs">
          <div><dt>API 地址</dt><dd class="text-break">{{API_ORIGIN}}</dd></div>
          <div><dt>GPU 检测</dt><dd>{{studio.runtime?.gpuMeasured?'已测量':'未采集'}}</dd></div>
          <div><dt>自适应显存管理</dt><dd>尚未接入</dd></div>
          <div><dt>优化验证</dt><dd>{{studio.runtime?.verifiedOnGPU?'已验证':'尚未验证'}}</dd></div>
        </dl>
        <div v-if="studio.runtimeError" class="inline-error" role="alert">{{studio.runtimeError}}</div>
        <RouterLink to="/models" class="outline-link">检查模型资源 <ArrowUpRight :size="16"/></RouterLink>
      </section>
    </div>
  </div>
</template>
