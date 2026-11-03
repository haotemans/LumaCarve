# image-studio.css · 轻量参数 UI 样式

源码：`../image-studio.css`。以浅色、细线边框与固定的冷色调为基础，默认三栏：素材 / 画布 / 参数与运行状态。断点在 1460 / 1200 / 820 / 570 px，确保窄屏上下阅读与表单操作。按钮、输入控件和运行状态折叠项均有可见焦点状态；`prefers-reduced-motion` 禁用额外运动。

**性能原则**：在工作室页通过 `.lc-low-gpu` 隐藏三个大面积模糊环境光层，`.is-panel` 使用高对比度静态表面替代 `backdrop-filter`。空画布不放 GIF、持续动画或假生成图；不会渲染 Graph Canvas 或反复加载 React Flow。图像预览仍限制最长边 1600 px。

RuntimeStatusPanel 使用紧凑的状态卡片和可折叠实验内核配置区，不表示实际的显卡遥测或实时 TPS。历史 Graph 的样式仍留在 CSS 中以便未来迁移，但公开工作台不再挂载这些 DOM。

验证：`npm run build`；浏览器尺寸、键盘焦点及真实 GPU 资源占用需另行实测。
