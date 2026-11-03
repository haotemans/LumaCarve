import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './vue/App.vue';
import router from './vue/router';
import './vue/styles.css';
import { initializeDesktop } from './vue/desktop';

const app = createApp(App);
app.use(createPinia());
app.use(router);
void initializeDesktop().catch(error => {
  document.body.dataset.desktopError = error instanceof Error ? error.message : '桌面后端启动失败';
  console.error('LumaCarve desktop API initialization failed');
}).finally(() => app.mount('#app'));
