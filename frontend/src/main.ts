import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './vue/App.vue';
import router from './vue/router';
import './vue/styles.css';

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount('#app');
