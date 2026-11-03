<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { Activity, ArrowUpRight, Cpu, HardDrive, Info, RefreshCw, Settings2, ShieldCheck, Zap, Pause, Play, Thermometer, Gauge } from 'lucide-vue-next';
import { useStudioStore } from '../stores/studio';
import { API_ORIGIN } from '../api';
import { fetchTelemetry, fetchExecutionTimeline } from '../../features/image-studio/telemetry';
import type { TelemetrySample, ExecutionTimeline, ExecutionStage, PhaseStatus } from '../../features/image-studio/telemetry';

const studio = useStudioStore();
const displayMode = ref<'simple'|'detailed'>('simple');
const intervalSeconds = ref(3);
const deviceIndex = ref(0);
const paused = ref(false);
const reading = ref<TelemetrySample | null>(null);
const timeline = ref<ExecutionTimeline | null>(null);
const executionUnavailable = ref(false);
const history = ref<{ time: number; used: number | null; load: number | null }[]>([]);
const monitorError = ref('');
const sampleBusy = ref(false);
let timer: ReturnType<typeof setInterval> | undefined;
let controller: AbortController | undefined;
const kernels = [
  { key: 'adaln' as const, name: 'AdaLN Fusion', desc: '归一化与调制' },
  { key: 'rope' as const, name: 'RoPE Fusion', desc: 'Q/K 旋转位置编码' },
  { key: 'residual' as const, name: 'Residual Fusion', desc: '门控残差' },
  { key: 'ffn' as const, name: 'FFN GELU', desc: '线性层与激活' },
];
const engineLabel = computed(() => studio.runtime?.engine === 'anima' ? 'Anima 资源就绪'
  : studio.runtimeError ? '本地 API 未连接' : '尚未配置推理引擎');
const gpu = computed(() => reading.value?.gpu);
const percent = computed(() => gpu.value?.used_bytes !== null && gpu.value?.used_bytes !== undefined
  && gpu.value?.total_bytes ? Math.min(100, 100 * gpu.value.used_bytes / gpu.value.total_bytes) : null);
const formatBytes = (bytes: number | null | undefined) => bytes === null || bytes === undefined ? '—' : (bytes / (1024 ** 3)).toFixed(2) + ' GiB';
const formatReading = (value: number | null | undefined, unit: string) => value === null || value === undefined ? '—' : value + unit;
const updatedAt = computed(() => reading.value?.sampled_at ? new Date(reading.value.sampled_at * 1000).toLocaleTimeString() : '未采集');
const activeCount = computed(() => (studio.runtime?.queue?.running ?? 0) + (studio.runtime?.queue?.queued ?? 0));
const visibleHistory = computed(() => history.value.slice(-30));
const recentPhases = computed(() => [...(timeline.value?.active ?? []), ...(timeline.value?.events ?? [])].slice(0, 12));
const labels: Record<ExecutionStage, string> = {
  job: '任务总流程', model_unload: '卸载底模', model_load: '加载底模',
  lora_update: 'LoRA 更新', inference: '推理生成', output_save: '保存图像',
  te: '文本编码', vae: 'VAE', dit: 'DiT',
};
const phaseStatus: Record<PhaseStatus, string> = { running: '运行中', completed: '完成', failed: '失败', cancelled: '取消' };
const displayDuration = (ms: number | null) => ms === null ? '—' : ms >= 1000 ? (ms / 1000).toFixed(2) + ' 秒' : Math.round(ms) + ' 毫秒';
function stop() {
  if (timer !== undefined) clearInterval(timer);
  timer = undefined;
  controller?.abort();
  controller = undefined;
  sampleBusy.value = false;
}
async function sample() {
  if (paused.value || document.hidden || sampleBusy.value) return;
  sampleBusy.value = true;
  const current = new AbortController();
  controller = current;
  try {
    const [next, execution] = await Promise.all([
      fetchTelemetry(deviceIndex.value, current.signal),
      fetchExecutionTimeline(current.signal).catch(() => null),
      studio.refreshRuntime(current.signal),
    ]);
    if (execution) { timeline.value = execution; executionUnavailable.value = false; }
    else { executionUnavailable.value = true; timeline.value = null; }
    if (current.signal.aborted) return;
    reading.value = next;
    monitorError.value = next.status === 'ok' ? '' : (next.reason ?? 'GPU 监控不可用');
    if (next.status === 'ok' && next.sampled_at) {
      history.value.push({ time: next.sampled_at, used: next.gpu.used_bytes, load: next.gpu.utilization_percent });
      history.value = history.value.slice(-120);
    }
  } catch (error) {
    if (!current.signal.aborted) monitorError.value = error instanceof Error ? error.message : '采样失败';
  } finally {
    if (controller === current) controller = undefined;
    sampleBusy.value = false;
  }
}
function restart() {
  stop();
  if (!paused.value) {
    void sample();
    timer = setInterval(() => { void sample(); }, intervalSeconds.value * 1000);
  }
}
function visibilityChange() {
  if (document.hidden) {
    stop();
  } else {
    restart();
  }
}
watch([intervalSeconds, paused, deviceIndex], () => {
  if (deviceIndex.value !== reading.value?.device_index) history.value = [];
  restart();
});
onMounted(() => { restart(); document.addEventListener('visibilitychange', visibilityChange); });
onUnmounted(() => { stop(); document.removeEventListener('visibilitychange', visibilityChange); });
</script>
<template>
  <div class="system-view">
    <div class="utility-bar monitor-toolbar">
      <span class="count-indicator"><Activity :size="15"/>本地资源监控 · 设备级数据</span>
      <div class="utility-actions monitor-controls">
        <div class="mode-segments" role="group" aria-label="监控模式">
          <button :class="{active:displayMode==='simple'}" :aria-pressed="displayMode==='simple'" @click="displayMode='simple'">简洁</button>
          <button :class="{active:displayMode==='detailed'}" :aria-pressed="displayMode==='detailed'" @click="displayMode='detailed'">详细</button>
        </div>
        <label class="simple-select">间隔
          <select v-model.number="intervalSeconds" aria-label="监控刷新间隔">
            <option :value="2">2秒</option><option :value="3">3秒</option><option :value="5">5秒</option><option :value="10">10秒</option>
          </select>
        </label>
        <button class="subtle-button" :aria-pressed="paused" @click="paused=!paused">
          <Play v-if="paused" :size="15"/><Pause v-else :size="15"/>{{paused?'继续':'暂停'}}
        </button>
        <button class="subtle-button" :disabled="sampleBusy || paused" @click="sample"><RefreshCw :size="15"/>刷新</button>
      </div>
    </div>
    <div v-if="reading?.devices.length && reading.devices.length > 1" class="monitor-device-row">
      <label class="simple-select">监控设备
        <select v-model.number="deviceIndex" aria-label="选择 GPU">
          <option v-for="device in reading.devices" :key="device.index" :value="device.index">{{device.index}} · {{device.name}}</option>
        </select>
      </label>
    </div>
    <div class="system-summary">
      <section class="system-tile panel"><div class="system-tile-icon blue"><Cpu :size="21"/></div><span>引擎 / 活动任务</span><strong>{{engineLabel}}</strong><small>{{activeCount}} 项排队或执行</small></section>
      <section class="system-tile panel">
        <div class="system-tile-icon purple"><HardDrive :size="21"/></div><span>GPU 显存（整卡）</span>
        <strong>{{formatBytes(gpu?.used_bytes)}} <span class="monitor-split">/ {{formatBytes(gpu?.total_bytes)}}</span></strong>
        <div class="monitor-meter" :aria-label="percent === null ? '显存未知' : '显存占用 '+Math.round(percent)+'%'"><div :style="{width:(percent??0)+'%'}"/></div>
        <small>{{gpu?.name ?? '设备未知'}} · 非仅本应用显存</small>
      </section>
      <section class="system-tile panel"><div class="system-tile-icon cyan"><Gauge :size="21"/></div><span>GPU 利用率</span><strong>{{formatReading(gpu?.utilization_percent, '%')}}</strong><small>NVML 采样 · {{updatedAt}}</small></section>
    </div>
    <div v-if="monitorError" class="inline-notice" role="status">{{monitorError}}。可能未安装可选 NVML 依赖，或 NVIDIA 驱动不支持。</div>
    <div class="monitor-note"><Info :size="15"/>数据采样可暂停；页面隐藏时停止刷新。GPU 指标为整张显卡的 NVML 结果，不等于 LumaCarve 独占使用量。未采集不显示估算值。</div>
    <div v-if="studio.runtime?.queue" class="system-queue-overview panel">
      <span>任务队列</span>
      <div class="system-queue-counter"><strong>{{studio.runtime.queue.running}}</strong><small>运行中</small></div>
      <div class="system-queue-counter"><strong>{{studio.runtime.queue.queued}}</strong><small>等待中</small></div>
      <div class="system-queue-counter"><strong>{{studio.runtime.queue.capacity}}</strong><small>容量</small></div>
      <RouterLink to="/tasks" class="subtle-button">查看任务</RouterLink>
    </div>
    <div v-if="displayMode==='detailed'" class="monitor-expanded">
      <section class="panel monitor-details monitor-timeline-panel">
        <div class="panel-heading"><div class="panel-title"><Activity :size="18"/><h2>执行时间线</h2></div><span class="mini-tag">WORKER EVENTS</span></div>
        <div v-if="executionUnavailable" class="empty-inline">后端未提供执行事件接口</div>
        <div v-else-if="recentPhases.length" class="execution-timeline">
          <div v-for="event in recentPhases" :key="event.id" class="execution-event">
            <span class="execution-dot" :class="'execution-'+event.status"/>
            <div class="execution-content">
              <div class="execution-event-head"><strong>{{labels[event.stage]}}</strong><span class="execution-status">{{phaseStatus[event.status]}}</span><span class="execution-duration">{{displayDuration(event.duration_ms)}}</span></div>
              <div class="execution-event-meta"><span v-if="event.model_id">{{event.model_id}}</span><span v-if="event.job_id">任务 {{event.job_id.slice(0, 10)}}</span><span v-if="event.allocated_bytes !== null">PyTorch 已分配 {{formatBytes(event.allocated_bytes)}}</span><span v-if="event.reserved_bytes !== null">预留 {{formatBytes(event.reserved_bytes)}}</span></div>
            </div>
          </div>
        </div>
        <div v-else class="empty-inline">尚无真实执行记录；运行任务后显示阶段耗时。</div>
        <small class="monitor-hint">事件来自 Python Worker；耗时为阶段墙钟时间。显存数值为 PyTorch 进程分配器，不代表整卡显存。</small>
      </section>
      <section class="panel monitor-details monitor-phase-panel">
        <div class="panel-heading"><div class="panel-title"><Cpu :size="18"/><h2>组件级阶段</h2></div></div>
        <div class="component-phase-grid">
          <div v-for="item in [{key:'te', name:'Text Encoder'}, {key:'vae', name:'VAE'}, {key:'dit', name:'DiT'}] as const" :key="item.key" class="component-phase-item">
            <strong>{{item.name}}</strong><span>{{timeline?.phase_detail[item.key]==='instrumentation_not_connected'?'等待 Worker 埋点':'尚无实测阶段'}}</span>
          </div>
        </div>
        <small class="monitor-hint">当前 Anima 的组件内部执行未单独埋点，不会把总推理时长拆成虚构的 TE / VAE / DiT 数字。</small>
      </section>
      <section class="panel monitor-details">
        <div class="panel-heading"><div class="panel-title"><Activity :size="18"/><h2>采样历史</h2></div><span class="mini-tag">{{visibleHistory.length}} / 30</span></div>
        <div v-if="visibleHistory.length" class="monitor-history" aria-label="最近显存占用趋势">
          <div v-for="(item,index) in visibleHistory" :key="index" class="monitor-history-column"
            :title="new Date(item.time*1000).toLocaleTimeString()+' · '+formatBytes(item.used)"
            :style="{height:(gpu?.total_bytes && item.used !== null ? Math.max(3, Math.min(100, 100*item.used/gpu.total_bytes)) : 3)+'%'}"/>
        </div>
        <div v-else class="empty-inline">没有可用采样历史</div>
        <small class="monitor-hint">最近 30 个有效样本，仅在本页面内存中保存，不写入磁盘。</small>
      </section>
      <section class="panel monitor-details">
        <div class="panel-heading"><div class="panel-title"><Thermometer :size="18"/><h2>设备传感器</h2></div></div>
        <dl class="system-specs">
          <div><dt>GPU 温度</dt><dd>{{formatReading(gpu?.temperature_c,'°C')}}</dd></div>
          <div><dt>功率</dt><dd>{{formatReading(gpu?.power_w,' W')}}</dd></div>
          <div><dt>显存占比</dt><dd>{{formatReading(percent === null ? null : Math.round(percent),'%')}}</dd></div>
          <div><dt>显存释放策略</dt><dd>{{studio.runtime?.offload ?? '未知'}}</dd></div>
        </dl>
      </section>
      <section class="panel monitor-details">
        <div class="panel-heading"><div class="panel-title"><ShieldCheck :size="18"/><h2>Triton 配置</h2></div><span class="mini-tag">EXPERIMENTAL</span></div>
        <div class="kernel-cards">
          <div v-for="kernel in kernels" :key="kernel.key" class="kernel-card"><div class="kernel-card-icon"><Zap :size="17"/></div>
            <div><strong>{{kernel.name}}</strong><span>{{kernel.desc}}</span></div>
            <span class="kernel-mode" :class="{on:studio.runtime?.kernels[kernel.key]==='experimental'}">{{studio.runtime?.kernels[kernel.key] === 'experimental' ? '实验配置' : studio.runtime?.kernels[kernel.key] === 'off' ? '关闭' : '未知'}}</span>
          </div>
        </div>
      </section>
      <section class="panel monitor-details">
        <div class="panel-heading"><div class="panel-title"><Settings2 :size="18"/><h2>本地 API</h2></div></div>
        <dl class="system-specs">
          <div><dt>API 地址</dt><dd class="text-break">{{API_ORIGIN}}</dd></div>
          <div><dt>GPU 监控来源</dt><dd>{{reading?.source ?? '未连接'}}</dd></div>
          <div><dt>GPU 测量</dt><dd>{{reading?.status === 'ok' ? 'NVML 设备级' : '未采集'}}</dd></div>
          <div><dt>智能显存调度</dt><dd>尚未全部接入</dd></div>
        </dl>
        <div v-if="studio.runtimeError" class="inline-error" role="alert">{{studio.runtimeError}}</div>
        <RouterLink to="/models" class="outline-link">查看模型驻留 <ArrowUpRight :size="16"/></RouterLink>
      </section>
    </div>
  </div>
</template>
