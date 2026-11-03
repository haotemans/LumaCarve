<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { CircleCheck, Clock3, ListTodo, Loader2, RefreshCw, ShieldAlert, Square, XCircle } from 'lucide-vue-next';
import { cancelImageJob, loadJobs } from '../api';
import type { ImageJob, JobCounts, JobFilter } from '../api';

const jobs = ref<ImageJob[]>([]);
const state = ref<JobFilter>('all');
const counts = ref<JobCounts>({ queued: 0, running: 0, completed: 0, failed: 0, cancelled: 0 });
const total = ref(0);
const offset = ref(0);
const loading = ref(false);
const error = ref('');
const busyId = ref<string | null>(null);
const filters: { id: JobFilter; title: string }[] = [
  { id: 'all', title: '全部' }, { id: 'queued', title: '排队' },
  { id: 'running', title: '运行中' }, { id: 'completed', title: '已完成' },
  { id: 'failed', title: '失败' }, { id: 'cancelled', title: '已取消' },
];
const labels: Record<ImageJob['state'], string> = {
  queued: '排队中', running: '执行中', completed: '已完成', failed: '失败', cancelled: '已取消',
};
function totalOf(filter: JobFilter) { return filter === 'all' ? Object.values(counts.value).reduce((a,b) => a+b,0) : counts.value[filter]; }
function age(createdAt: number | undefined): string {
  if (!createdAt) return '—';
  const date = new Date(createdAt * 1000);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('zh-CN', { hour12:false, month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' });
}
async function refresh() {
  loading.value = true; error.value = '';
  try {
    const data = await loadJobs(state.value, 30, offset.value);
    jobs.value = data.jobs; counts.value = data.counts; total.value = data.total;
  } catch (reason) { error.value = reason instanceof Error ? reason.message : '任务列表加载失败'; }
  finally { loading.value = false; }
}
async function choose(filter: JobFilter) { state.value = filter; offset.value = 0; await refresh(); }
async function next(delta: number) { offset.value = Math.max(0, offset.value + delta * 30); await refresh(); }
async function cancel(id: string) {
  busyId.value = id;
  try { await cancelImageJob(id); await refresh(); }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '取消任务失败'; }
  finally { busyId.value = null; }
}
onMounted(() => { void refresh(); });
</script>
<template>
  <div class="tasks-view">
    <div class="utility-bar"><span class="count-indicator">任务队列 · {{totalOf('all')}} 个作业</span>
      <button class="subtle-button" :disabled="loading" @click="refresh"><RefreshCw :size="16"/>刷新</button>
    </div>
    <div class="task-filter-grid" role="group" aria-label="任务状态筛选">
      <button v-for="item in filters" :key="item.id" :class="{active:state===item.id}" @click="choose(item.id)">
        <span>{{item.title}}</span><strong>{{totalOf(item.id)}}</strong>
      </button>
    </div>
    <div v-if="error" class="inline-error" role="alert">{{error}}</div>
    <div v-if="jobs.length" class="task-table panel">
      <div class="task-header"><span>任务</span><span>状态</span><span>创建时间</span><span>操作</span></div>
      <div v-for="job in jobs" :key="job.id" class="task-row">
        <span class="job-id" :title="job.id"><ListTodo :size="16"/><span>{{job.id.slice(0,12)}}</span></span>
        <span class="task-state" :class="'job-'+job.state">
          <Loader2 v-if="job.state==='running'" :size="15"/>
          <Clock3 v-else-if="job.state==='queued'" :size="15"/>
          <CircleCheck v-else-if="job.state==='completed'" :size="15"/>
          <ShieldAlert v-else-if="job.state==='failed'" :size="15"/>
          <XCircle v-else :size="15"/>
          {{labels[job.state]}}
        </span>
        <span class="task-result" :title="job.error || ''">{{age(job.created_at)}}<small v-if="job.error">{{job.error}}</small></span>
        <button v-if="job.state==='queued' || job.state==='running'" class="subtle-button task-cancel" :disabled="busyId===job.id" @click="cancel(job.id)"><Square :size="14"/>取消</button>
        <span v-else class="task-dash">—</span>
      </div>
    </div>
    <div v-else class="empty-screen"><div class="empty-symbol"><ListTodo :size="36"/></div><h2>{{loading?'读取任务中…':'没有符合条件的任务'}}</h2><RouterLink class="primary-link" to="/studio">前往生成</RouterLink></div>
    <div v-if="total>30" class="task-pagination">
      <button :disabled="offset===0" @click="next(-1)">上一页</button>
      <span>{{offset+1}}–{{Math.min(total,offset+30)}} / {{total}}</span>
      <button :disabled="offset+jobs.length>=total" @click="next(1)">下一页</button>
    </div>
  </div>
</template>
