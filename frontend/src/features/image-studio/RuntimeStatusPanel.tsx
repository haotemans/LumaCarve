import { useEffect, useState } from 'react';
import { Activity, CircleHelp, RefreshCw, ShieldCheck, Zap } from 'lucide-react';
import { fetchRuntimeSnapshot } from './runtime';
import type { KernelMode, OffloadMode, RuntimeSnapshot } from './runtime';

type ReadState = 'loading' | 'ready' | 'error';

const labels: ReadonlyArray<{ id: keyof RuntimeSnapshot['kernels']; name: string }> = [
  { id: 'adaln', name: 'AdaLN' },
  { id: 'rope', name: 'RoPE' },
  { id: 'residual', name: 'Residual' },
  { id: 'ffn', name: 'FFN' },
];

function offloadLabel(mode: OffloadMode): string {
  switch (mode) {
    case 'auto': return '基础自动 CPU 卸载';
    case 'model_cpu': return '模型 CPU 卸载';
    case 'full': return 'GPU 完整驻留';
    default: return '尚未提供';
  }
}

function engineLabel(snapshot: RuntimeSnapshot): string {
  if (snapshot.configuredEngine === 'disabled') return '未启用生成后端';
  if (snapshot.engine === 'anima') return 'Anima 本地资源就绪';
  if (snapshot.configuredEngine === 'anima') return 'Anima 等待模型或依赖';
  return '后端状态未知';
}

function kernelText(mode: KernelMode): string {
  if (mode === 'experimental') return '实验配置';
  if (mode === 'off') return '关闭';
  return '未知';
}

export default function RuntimeStatusPanel() {
  const [revision, setRevision] = useState(0);
  const [snapshot, setSnapshot] = useState<RuntimeSnapshot | null>(null);
  const [state, setState] = useState<ReadState>('loading');
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setState('loading');
    setError('');
    void fetchRuntimeSnapshot(controller.signal).then(result => {
      if (!controller.signal.aborted) {
        setSnapshot(result);
        setState('ready');
      }
    }).catch(reason => {
      if (!controller.signal.aborted) {
        setSnapshot(null);
        setError(reason instanceof Error ? reason.message : '读取运行状态失败');
        setState('error');
      }
    });
    return () => controller.abort();
  }, [revision]);

  const experimentalCount = snapshot
    ? labels.filter(item => snapshot.kernels[item.id] === 'experimental').length
    : 0;
  const configuredKernelCount = snapshot
    ? labels.filter(item => snapshot.kernels[item.id] !== 'unknown').length
    : 0;

  return (
    <section className="is-panel is-runtime-panel" aria-label="运行状态与推理优化">
      <div className="is-runtime-heading">
        <div className="is-heading"><Activity size={15}/><span>推理运行状态</span></div>
        <button
          className="is-runtime-refresh"
          type="button"
          title="仅读取本地服务状态，不探测 GPU"
          aria-label="刷新推理运行状态"
          disabled={state === 'loading'}
          onClick={() => setRevision(value => value + 1)}
        ><RefreshCw size={14} aria-hidden="true"/>刷新</button>
      </div>

      {state === 'loading' && !snapshot
        ? <div className="is-runtime-message" role="status">正在读取本地服务状态…</div>
        : null}
      {state === 'error'
        ? <div className="is-runtime-error" role="alert">
          <strong>本地服务尚未连接</strong>
          <span>{error}</span>
          <small>工作台仍可编辑参数，但无法提交真实生成任务。</small>
        </div>
        : null}

      {snapshot && state !== 'error' && <div className="is-runtime-body">
        <div className="is-runtime-primary">
          <span className="is-runtime-indicator" aria-hidden="true"/>
          <div>
            <strong>{engineLabel(snapshot)}</strong>
            <small>{snapshot.engine === 'anima'
              ? '已检查本地模型文件和依赖，不代表 GPU 已加载'
              : '生成任务需要配置本地 Python 推理服务'}</small>
          </div>
        </div>

        <dl className="is-runtime-facts">
          <div><dt>显存策略</dt><dd>{offloadLabel(snapshot.offload)}</dd></div>
          <div><dt>智能自动均衡</dt><dd>尚未接入</dd></div>
          <div><dt>GPU 状态</dt><dd>{snapshot.gpuMeasured
            ? snapshot.gpuAvailable === true ? 'GPU 可用' : snapshot.gpuAvailable === false ? 'GPU 不可用' : '未知'
            : '未采集（非故障）'}</dd></div>
          <div><dt>显存占用</dt><dd>—</dd></div>
        </dl>

        <details className="is-runtime-details">
          <summary><Zap size={14}/><span>Triton 实验优化</span>
            <small>{configuredKernelCount === 0 ? '后端未提供配置' : experimentalCount + '/4 已配置'}</small>
          </summary>
          <div className="is-runtime-kernels">
            {labels.map(item => <div key={item.id}>
              <span>{item.name}</span>
              <strong className={snapshot.kernels[item.id] === 'experimental' ? 'is-runtime-experimental' : ''}>
                {kernelText(snapshot.kernels[item.id])}
              </strong>
            </div>)}
          </div>
          <p><ShieldCheck size={13} aria-hidden="true"/>
            仅显示配置值，不代表 Kernel 已加载或经过 GPU 验证。
          </p>
        </details>

        <p className="is-runtime-disclaimer">
          <CircleHelp size={13} aria-hidden="true"/>
          后端不为此面板执行 CUDA 探测或性能预测；配置状态不等于实测性能。
        </p>
      </div>}
    </section>
  );
}
