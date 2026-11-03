/** Tauri-provided random localhost API port and per-launch token. */
import { invoke, isTauri } from '@tauri-apps/api/core';
import { configureApiConnection, apiFetch } from '../features/image-studio/api';

export async function initializeDesktop(): Promise<void> {
  if (!isTauri()) return;
  const connection = await invoke<{ origin: string; token: string }>('desktop_connection');
  if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(connection.origin) || !/^[0-9a-f]{64}$/.test(connection.token)) {
    throw new Error('Tauri returned an invalid local API connection');
  }
  configureApiConnection(connection.origin, connection.token);
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    try {
      const response = await apiFetch('/api/v1/health');
      if (response.ok) return;
    } catch { /* frozen Python process still starting */ }
    await new Promise(resolve => setTimeout(resolve, 300));
  }
  throw new Error('本地服务启动失败，请查看 LumaCarve 应用数据目录中的 logs/api.log');
}
