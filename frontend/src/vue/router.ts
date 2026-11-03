import { createRouter, createWebHashHistory } from 'vue-router';
import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/studio' },
  { path: '/generate', redirect: '/studio' },
  { path: '/flow', redirect: '/studio' },
  { path: '/studio', name: 'studio', component: () => import('./views/StudioView.vue'), meta: { title: '图像工作室', section: 'CREATE / STUDIO' } },
  { path: '/training', name: 'training', component: () => import('./views/TrainingView.vue'), meta: { title: 'LoRA 训练', section: 'TRAIN / CARVE' } },
  { path: '/gallery', name: 'gallery', component: () => import('./views/GalleryView.vue'), meta: { title: '作品画廊', section: 'OUTPUT / LIBRARY' } },
  { path: '/models', name: 'models', component: () => import('./views/ModelsView.vue'), meta: { title: '模型库', section: 'MODELS / HUB' } },
  { path: '/datasets', name: 'datasets', component: () => import('./views/DatasetsView.vue'), meta: { title: '数据集', section: 'DATA / MANAGER' } },
  { path: '/tasks', name: 'tasks', component: () => import('./views/TasksView.vue'), meta: { title: '任务队列', section: 'JOBS / HISTORY' } },
  { path: '/system', name: 'system', component: () => import('./views/SystemView.vue'), meta: { title: '运行环境', section: 'RUNTIME / SYSTEM' } },
  { path: '/:pathMatch(.*)*', redirect: '/studio' },
];

export default createRouter({ history: createWebHashHistory(), routes, scrollBehavior: () => ({ top: 0 }) });
