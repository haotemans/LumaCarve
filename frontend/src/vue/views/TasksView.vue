<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { CircleCheck, Clock3, ListTodo, Loader2, RefreshCw, ShieldAlert, Square, XCircle } from 'lucide-vue-next';
import { cancelImageJob } from '../api';
import type { ImageJob } from '../api';
import { useStudioStore } from '../stores/studio';

const studio = useStudioStore();
const error = ref('');
const busyId = ref<string | null>(null);
const labels: Record<ImageJob['state'], string> = {
  queued:'排队中', running:'执行中', completed:'已完成', failed:'失败', cancelled:'已取消',
};
async function refresh() { error.value=''; await studio.loadRecent(); }
async function cancel(id: string) {
  busyId.value=id;
  try { await cancelImageJob(id); await refresh(); }
  catch (reason) { error.value = reason instanceof Error?reason.message:'取消失败'; }
  finally { busyId.value=null; }
}
onMounted(() => { void refresh(); });
</script>
<template>
  <div class="tasks-view">
    <div class="utility-bar"><span class="count-indicator">SQLite · 本地任务队列</span>
      <button class="subtle-button" @click="refresh"><RefreshCw :size="16"/>刷新任务</button>
    </div>
    <div v-if="error || studio.jobError" class="inline-error" role="alert">{{error || studio.jobError}}</div>
    <div v-if="studio.jobs.length" class="task-table panel">
      <div class="task-header"><span>任务 ID</span><span>执行状态</span><span>结果</span><span>操作</span></div>
      <div v-for="job in studio.jobs" :key="job.id" class="task-row">
        <span class="job-id"><ListTodo :size="16"/><span>{{job.id.slice(0,12)}}</span></span>
        <span class="task-state" :class="'job-'+job.state">
          <Loader2 v-if="job.state==='running'" :size="15"/>
          <Clock3 v-else-if="job.state==='queued'" :size="15"/>
          <CircleCheck v-else-if="job.state==='completed'" :size="15"/>
          <ShieldAlert v-else-if="job.state==='failed'" :size="15"/>
          <XCircle v-else :size="15"/>
          {{labels[job.state]}}
        </span>
        <span class="task-result">{{job.result ? job.result.width+' × '+job.result.height : job.error || '—'}}</span>
        <button v-if="job.state==='queued'||job.state==='running'" class="subtle-button task-cancel" :disabled="busyId===job.id" @click="cancel(job.id)"><Square :size="14"/>取消</button>
        <span v-else class="task-dash">—</span>
      </div>
    </div>
    <div v-else class="empty-screen">
      <div class="empty-symbol"><ListTodo :size="36" :stroke-width="1.25"/></div>
      <h2>任务队列为空</h2>
      <p>在图像工作室提交后，这里会记录真实的任务状态。</p>
      <RouterLink class="primary-link" to="/studio">开始生成</RouterLink>
    </div>
  </div>
</template>
