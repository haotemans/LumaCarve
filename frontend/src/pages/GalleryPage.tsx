import { useEffect, useMemo, useRef, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import {
  ArrowDownToLine, ArrowLeftRight, ArrowRight, CalendarDays, Check, CheckSquare2,
  ChevronDown, CircleCheck, Clock3, Copy, FolderOpen, Grid2X2, Heart, Image as ImageIcon,
  Images, List, Maximize2, MoreHorizontal, Search, SlidersHorizontal, Square, Trash2,
  Upload, X,
} from 'lucide-react';
import Artwork from '../components/Artwork';
import { models, tasks } from '../data/demo';
import type { GalleryTab, OutputImage, Page } from '../types';
import type { SharedProps } from '../App';

type Props = SharedProps & {
  outputs: OutputImage[];
  setOutputs: Dispatch<SetStateAction<OutputImage[]>>;
  search: string;
  focusedTask: string;
  onNavigate: (page: Page) => void;
};

export default function GalleryPage({ outputs, setOutputs, search, focusedTask, onNavigate, notify }: Props) {
  const [tab, setTab] = useState<GalleryTab>('artworks');
  const [modelFilter, setModelFilter] = useState('all');
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [sort, setSort] = useState('recent');
  const [listMode, setListMode] = useState(false);
  const [selectedId, setSelectedId] = useState('gen-001');
  const [batch, setBatch] = useState<string[]>([]);
  const [taskId, setTaskId] = useState(focusedTask);
  const [sampleId, setSampleId] = useState(focusedTask + '-e1');
  const [compare, setCompare] = useState(false);
  useEffect(() => { if (focusedTask) { setTaskId(focusedTask); setSampleId(focusedTask + '-e1'); setTab('samples'); } }, [focusedTask]);
  const inputRef = useRef<HTMLInputElement>(null);

  const artworks = useMemo(() => outputs
    .filter((item) => item.kind === 'generation')
    .filter((item) => modelFilter === 'all' || item.model === modelFilter)
    .filter((item) => !favoriteOnly || item.favorite)
    .filter((item) => [item.name, item.model, item.prompt].join(' ').toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => sort === 'recent' ? b.date.localeCompare(a.date) : a.date.localeCompare(b.date)),
    [outputs, modelFilter, favoriteOnly, search, sort]);
  const selected = artworks.find((item) => item.id === selectedId) || artworks[0];
  const selectedTask = tasks.find((task) => task.id === taskId) || tasks[0];
  const samples = outputs.filter((item) => item.kind === 'sample' && item.taskId === selectedTask.id).sort((a, b) => (a.epoch || 0) - (b.epoch || 0));
  const activeSample = samples.find((item) => item.id === sampleId) || samples[samples.length - 1];
  const baseline = samples[0];

  async function copy(text: string, label: string) {
    try { await navigator.clipboard.writeText(text); notify(label + ' 已复制', 'success'); }
    catch { notify('浏览器未授权剪贴板，请手动复制', 'warning'); }
  }
  function toggleFavorite(item: OutputImage) {
    setOutputs((prev) => prev.map((img) => img.id === item.id ? { ...img, favorite: !img.favorite } : img));
  }
  function toggleBatch(id: string) { setBatch((current) => current.includes(id) ? current.filter((x) => x !== id) : [...current, id]); }
  function deleteBatch() {
    if (!batch.length) return;
    if (!window.confirm('从本次前端会话中移除 ' + batch.length + ' 张图片？')) return;
    setOutputs((old) => old.filter((item) => !batch.includes(item.id)));
    setBatch([]);
    notify('已从演示图库移除所选图片', 'success');
  }
  function importImages(files: FileList | null) {
    if (!files?.length) return;
    const imported: OutputImage[] = Array.from(files).filter((file) => file.type.startsWith('image/')).map((file, i) => ({
      id: 'upload-' + Date.now() + '-' + i,
      name: file.name,
      kind: 'generation',
      model: '本地导入',
      prompt: '',
      seed: 0,
      size: '原始尺寸',
      steps: 0,
      date: new Date().toISOString().slice(0, 10),
      variant: i,
      imported: true,
      imageUrl: URL.createObjectURL(file),
    }));
    setOutputs((old) => [...imported, ...old]);
    if (imported[0]) setSelectedId(imported[0].id);
    notify('已导入 ' + imported.length + ' 张图片 · 当前浏览器会话有效', 'success');
  }
  function downloadImage(item?: OutputImage) {
    if (!item) return;
    if (!item.imageUrl) { notify('示例插画不是实际生成文件，无法下载', 'warning'); return; }
    const a = document.createElement('a');
    a.href = item.imageUrl; a.download = item.name; a.click();
  }
  return (
    <div className="page page-gallery">
      <div className="page-heading">
        <div><div className="eyebrow"><span className="eyebrow-mark"/> CREATION LIBRARY / 01</div><h1>出图管理 <span className="heading-accent">/ Gallery</span></h1><p>捕捉灵感，回溯每一次创作。</p></div>
        <div className="page-heading-actions">
          <button className="btn btn-ghost" onClick={() => notify('生成文件由未来的 Python 后端写入工作空间')}><FolderOpen size={16}/>输出目录</button>
          <button className="btn btn-primary" onClick={() => inputRef.current?.click()}><Upload size={16}/>导入图片</button>
          <input ref={inputRef} className="visually-hidden" type="file" multiple accept="image/png,image/jpeg,image/webp" aria-label="导入图片" onChange={(e) => { importImages(e.target.files); e.target.value = ''; }} />
        </div>
      </div>
      <div className="tabs tabs-main" role="tablist" aria-label="图库分类">
        <button role="tab" aria-selected={tab === 'artworks'} className={tab === 'artworks' ? 'selected' : ''} onClick={() => setTab('artworks')}><Images size={16}/>文生图作品<span className="count-pill">{outputs.filter((x) => x.kind === 'generation').length}</span></button>
        <button role="tab" aria-selected={tab === 'samples'} className={tab === 'samples' ? 'selected' : ''} onClick={() => setTab('samples')}><Clock3 size={16}/>训练采样<span className="count-pill">{tasks.length}</span></button>
      </div>
      {tab === 'artworks' ? (
        <>
          <div className="surface-toolbar">
            <div className="toolbar-group">
              <span className="toolbar-label">{artworks.length} IMAGES</span>
              <div className="toolbar-sep"/>
              <button className={'filter-toggle ' + (!favoriteOnly ? 'is-active' : '')} onClick={() => setFavoriteOnly(false)}>全部</button>
              <button className={'filter-toggle ' + (favoriteOnly ? 'is-active' : '')} onClick={() => setFavoriteOnly(true)}><Heart size={14}/>收藏</button>
              <div className="toolbar-sep"/>
              <label className="select-wrapper"><SlidersHorizontal size={15}/><select aria-label="筛选模型" value={modelFilter} onChange={(e) => setModelFilter(e.target.value)}><option value="all">全部模型</option>{models.map((model) => <option key={model} value={model}>{model}</option>)}</select><ChevronDown size={13}/></label>
            </div>
            <div className="toolbar-group">
              {batch.length > 0 && <><span className="selection-count">{batch.length} 已选择</span><button className="mini-action danger" onClick={deleteBatch} aria-label="删除所选"><Trash2 size={16}/></button></>}
              <label className="select-wrapper compact"><select aria-label="排序" value={sort} onChange={(e) => setSort(e.target.value)}><option value="recent">最新优先</option><option value="old">最早优先</option></select><ChevronDown size={13}/></label>
              <div className="view-toggle"><button className={!listMode ? 'active' : ''} aria-label="网格视图" onClick={() => setListMode(false)}><Grid2X2 size={16}/></button><button className={listMode ? 'active' : ''} aria-label="列表视图" onClick={() => setListMode(true)}><List size={17}/></button></div>
            </div>
          </div>
          <div className="gallery-workspace">
            <section className="gallery-content">
              {artworks.length ? <div className={'art-grid ' + (listMode ? 'art-list' : '')}>
                {artworks.map((item) => (
                  <div role="button" tabIndex={0} key={item.id} className={'art-tile ' + (selected?.id === item.id ? 'selected' : '')} onClick={() => setSelectedId(item.id)} onKeyDown={(e) => { if (e.key === 'Enter') setSelectedId(item.id); }}>
                    <div className="art-tile-image">
                      <Artwork variant={item.variant} imageUrl={item.imageUrl} label={item.name} />
                      <div className="tile-overlay"/>
                      <button className={'tile-check ' + (batch.includes(item.id) ? 'checked' : '')} aria-label={batch.includes(item.id) ? '取消选择' : '选择图片'} onClick={(e) => { e.stopPropagation(); toggleBatch(item.id); }}>{batch.includes(item.id) ? <Check size={13}/> : null}</button>
                      <button className={'tile-heart ' + (item.favorite ? 'favorited' : '')} aria-label={item.favorite ? '取消收藏' : '收藏图片'} onClick={(e) => { e.stopPropagation(); toggleFavorite(item); }}><Heart size={17} fill={item.favorite ? 'currentColor' : 'none'} /></button>
                      <div className="tile-corner-id">{item.imported ? 'LOCAL IMPORT' : 'IMG / ' + item.id.slice(-3).toUpperCase()}</div>
                    </div>
                    <div className="tile-meta"><div><b title={item.name}>{item.name}</b><span>{item.model}</span></div><MoreHorizontal size={17}/></div>
                  </div>
                ))}
              </div> : <div className="empty-state"><Search size={30}/><strong>没有匹配的图片</strong><span>调整模型筛选或搜索条件</span><button className="btn btn-ghost" onClick={() => { setModelFilter('all'); setFavoriteOnly(false); }}>清除筛选</button></div>}
            </section>
            <aside className="inspector" aria-label="图片详情">
              {selected ? <>
                <div className="inspector-head"><div><span className="eyebrow">IMAGE INSPECTOR</span><h3>图片详情</h3></div><Maximize2 size={17}/></div>
                <div className="inspector-preview"><Artwork variant={selected.variant} imageUrl={selected.imageUrl} label={selected.name}/><div className="inspector-preview-shine"/></div>
                <div className="inspector-actions">
                  <button className="inspector-icon-btn" title="复制提示词" onClick={() => copy(selected.prompt || selected.name, '文本')}><Copy size={17}/></button>
                  <button className="inspector-icon-btn" title="收藏" onClick={() => toggleFavorite(selected)}><Heart size={17} fill={selected.favorite ? 'currentColor' : 'none'} color={selected.favorite ? '#ef7da5' : undefined}/></button>
                  <button className="inspector-icon-btn" title="下载图片" onClick={() => downloadImage(selected)}><ArrowDownToLine size={17}/></button>
                  <button className="inspector-icon-btn" title="在文生图界面使用" onClick={() => { onNavigate('generate'); notify('演示模式：生成参数复制请使用右侧按钮'); }}><ArrowRight size={17}/></button>
                </div>
                <div className="inspector-section"><div className="section-mini-label">FILE INFO</div><strong className="filename">{selected.name}</strong><p className="muted tiny">{selected.date} · {selected.size}</p></div>
                <div className="inspector-section"><div className="section-mini-label">GENERATION</div><div className="data-row"><span>Model</span><b>{selected.model}</b></div><div className="data-row"><span>Seed</span><b className="mono">{selected.imported ? '—' : selected.seed}</b></div><div className="data-row"><span>Steps</span><b>{selected.steps || '—'}</b></div><div className="data-row"><span>Resolution</span><b>{selected.size}</b></div></div>
                <div className="inspector-section"><div className="section-mini-label">PROMPT <button title="复制 Prompt" onClick={() => copy(selected.prompt, 'Prompt')}><Copy size={13}/></button></div><div className="prompt-box">{selected.prompt || '本地导入图片（尚未读取内嵌生成元数据）'}</div></div>
                <div className="inspector-bottom"><span className="dot-purple"/> {selected.imported ? 'LOCAL FILE' : 'DEMO ASSET'} <span>·</span> LUMACARVE</div>
              </> : <div className="empty-inspector">选择图片查看详情</div>}
            </aside>
          </div>
        </>
      ) : (
        <div className="task-gallery">
          <aside className="task-list-pane">
            <div className="pane-header"><span>TRAINING TASKS</span><span className="pane-count">{tasks.length}</span></div>
            <div className="task-list">
              {tasks.filter((task) => !search || [task.name, task.model].join(' ').toLowerCase().includes(search.toLowerCase())).map((task) => (
                <button key={task.id} className={'task-row ' + (selectedTask.id === task.id ? 'active' : '')} onClick={() => { setTaskId(task.id); setSampleId(task.id + '-e' + task.epoch); setCompare(false); }}>
                  <div className="task-cover"><Artwork variant={task.variant} label={task.name}/></div>
                  <div className="task-row-info"><b>{task.name}</b><small>{task.model}</small><div className="task-progress"><span style={{ width: (task.epoch / task.totalEpochs * 100) + '%' }}/></div></div>
                  <span className={'task-dot ' + task.status}/>
                </button>
              ))}
            </div>
            <div className="pane-foot"><FolderOpen size={15}/> 每个任务单独归档</div>
          </aside>
          <section className="task-main-pane">
            <div className="task-detail-head">
              <div><span className="eyebrow">TRAINING COLLECTION / {selectedTask.id.toUpperCase()}</span><h2>{selectedTask.name}</h2><div className="inline-subtitle"><span className={'status-mini ' + selectedTask.status}>{selectedTask.status === 'training' ? '训练中' : selectedTask.status === 'completed' ? '已完成' : '已暂停'}</span><span>{selectedTask.model}</span><span className="muted">·</span><span>Epoch {selectedTask.epoch} / {selectedTask.totalEpochs}</span></div></div>
              <button className="btn btn-ghost small" onClick={() => onNavigate('training')}><ArrowRight size={15}/>训练页面</button>
            </div>
            <div className="task-timeline-heading"><span><CalendarDays size={16}/>EPOCH TIMELINE</span><small>{samples.length} 张采样</small></div>
            <div className="epoch-strip" role="list" aria-label="Epoch 采样时间轴">
              {samples.map((item) => (
                <button key={item.id} role="listitem" onClick={() => setSampleId(item.id)} className={'epoch-frame ' + (activeSample?.id === item.id ? 'selected' : '')} title={item.name}>
                  <div className="epoch-art"><Artwork variant={item.variant} label={item.name}/></div>
                  <div className="epoch-text">{item.epoch === 0 ? 'STEP 0' : 'EPOCH ' + String(item.epoch).padStart(2, '0')}</div>
                  <div className="epoch-pin"/>
                </button>
              ))}
            </div>
            <div className="comparison-top"><div><span className="eyebrow">SAMPLE VIEWER</span><h3>{compare ? 'Epoch 对比' : '采样预览'}</h3></div><button className={'btn ' + (compare ? 'btn-primary' : 'btn-ghost')} onClick={() => setCompare((x) => !x)}><ArrowLeftRight size={16}/>{compare ? '退出对比' : '对比 Step 0'}</button></div>
            {activeSample && <div className={'sample-stage ' + (compare ? 'compare-mode' : '')}>
              {compare && baseline && <div className="sample-pane"><div className="sample-pane-label">BASELINE · STEP 0</div><Artwork variant={baseline.variant} label="训练前基线"/></div>}
              <div className="sample-pane"><div className="sample-pane-label">{activeSample.epoch === 0 ? 'STEP 0' : 'EPOCH ' + activeSample.epoch}</div><Artwork variant={activeSample.variant} label={activeSample.name}/></div>
            </div>}
            <div className="comparison-footer"><span><CircleCheck size={15}/>固定 Prompt / Seed</span><span>左右切换 Epoch 查看演变</span></div>
          </section>
          <aside className="inspector sample-inspector">
            <div className="inspector-head"><div><span className="eyebrow">SAMPLE DETAILS</span><h3>采样信息</h3></div><MoreHorizontal size={18}/></div>
            {activeSample && <>
              <div className="sample-inspector-preview"><Artwork variant={activeSample.variant} label={activeSample.name}/></div>
              <div className="inspector-section"><div className="section-mini-label">CHECKPOINT</div><div className="data-row"><span>Epoch</span><b>{activeSample.epoch}</b></div><div className="data-row"><span>Step</span><b className="mono">{activeSample.step}</b></div><div className="data-row"><span>Seed</span><b className="mono">{activeSample.seed}</b></div><div className="data-row"><span>Steps</span><b>{activeSample.steps}</b></div></div>
              <div className="inspector-section"><div className="section-mini-label">PROMPT <button aria-label="复制 Prompt" onClick={() => copy(activeSample.prompt, 'Prompt')}><Copy size={13}/></button></div><div className="prompt-box">{activeSample.prompt}</div></div>
              <button className="btn btn-ghost wide" onClick={() => copy(activeSample.prompt, 'Prompt')}><Copy size={16}/>复制采样提示词</button>
            </>}
            <div className="inspector-bottom"><span className="dot-purple"/> TASK-BASED ARCHIVE</div>
          </aside>
        </div>
      )}
    </div>
  );
}
