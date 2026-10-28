import { useMemo, useRef, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { Check, Database, FileText, FolderPlus, Grid2X2, ImagePlus, Layers, Save, Search, Upload } from 'lucide-react';
import Artwork from '../components/Artwork';
import type { Dataset } from '../types';
import type { SharedProps } from '../App';

type Props = SharedProps & { datasets: Dataset[]; setDatasets: Dispatch<SetStateAction<Dataset[]>>; search: string };
export default function DatasetsPage({ datasets, setDatasets, search, notify }: Props) {
  const [datasetId, setDatasetId] = useState('ds-001');
  const [imageId, setImageId] = useState('char-0');
  const [view, setView] = useState<'images'|'captions'|'buckets'>('images');
  const [captionDraft, setCaptionDraft] = useState<string | null>(null);
  const upload = useRef<HTMLInputElement>(null);
  const dataset = datasets.find(x => x.id === datasetId) || datasets[0];
  const filtered = useMemo(() => dataset.images.filter(x => [x.name,x.caption].join(' ').toLowerCase().includes(search.toLowerCase())),[dataset,search]);
  const current = dataset.images.find(x => x.id === imageId) || filtered[0] || dataset.images[0];
  function importFiles(files: FileList | null) {
    if (!files) return;
    const all = Array.from(files);
    const captions = new Map(all.filter(f => f.name.toLowerCase().endsWith('.txt')).map(f => [f.name.slice(0,-4).toLowerCase(),f]));
    const images = all.filter(f => f.type.startsWith('image/'));
    Promise.all(images.map(async (file,i) => {
      const paired = captions.get(file.name.replace(/\.[^.]+$/, '').toLowerCase());
      return { id:'dataset-import-'+Date.now()+'-'+i, name:file.name, imageUrl:URL.createObjectURL(file),variant:i+5,caption:paired ? await paired.text() : '' };
    })).then(items => {
      setDatasets(old => old.map(ds => ds.id === dataset.id ? {...ds,images:[...items,...ds.images]} : ds));
      if(items[0])setImageId(items[0].id);
      notify('已导入 '+items.length+' 张图片 · 当前页面会话有效','success');
    });
  }
  function saveCaption() {
    if (!current) return;
    setDatasets(old => old.map(ds => ds.id === dataset.id ? {...ds,images:ds.images.map(im => im.id === current.id ? {...im,caption:captionDraft ?? im.caption} : im)} : ds));
    setCaptionDraft(null);
    notify('Caption 已更新（前端会话）','success');
  }
  return <div className="page">
    <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-mark"/> DATASET STUDIO / 02</div><h1>数据集管理 <span className="heading-accent">/ Datasets</span></h1><p>整理视觉素材，构建更精准的训练数据。</p></div>
      <div className="page-heading-actions"><button className="btn btn-ghost" onClick={() => { const name=window.prompt('新数据集名称');if(name?.trim()){const id='ds-'+Date.now();setDatasets(old=>[...old,{id,name:name.trim(),kind:'自定义数据集',accent:'#7389ff',images:[]}]);setDatasetId(id);notify('数据集已创建（前端会话）','success');} }}><FolderPlus size={16}/>新数据集</button><button className="btn btn-primary" onClick={() => upload.current?.click()}><Upload size={16}/>导入素材</button><input ref={upload} className="visually-hidden" type="file" accept="image/*,.txt" multiple onChange={e=>{importFiles(e.target.files);e.target.value='';}} /></div>
    </div>
    <div className="dataset-layout">
      <aside className="dataset-sidebar"><div className="pane-header"><span>DATASET COLLECTIONS</span><span className="pane-count">{datasets.length}</span></div>{datasets.map(ds=><button className={'dataset-list-item '+(dataset.id===ds.id?'active':'')} key={ds.id} onClick={()=>{setDatasetId(ds.id);setImageId(ds.images[0]?.id||'');setCaptionDraft(null);}}><div className="dataset-folder" style={{'--dataset-color':ds.accent} as React.CSSProperties}><Database size={20}/></div><div><b>{ds.name}</b><small>{ds.kind} · {ds.images.length} Images</small></div></button>)}<div className="pane-foot"><Database size={15}/> 与出图作品分开管理</div></aside>
      <section className="dataset-content"><div className="dataset-heading"><div><span className="eyebrow">SELECTED DATASET</span><h2>{dataset.name}</h2><p>{dataset.kind} · {dataset.images.length} 张素材</p></div><div className="dataset-view-count"><Layers size={16}/>{dataset.images.length} ASSETS</div></div>
        <div className="tabs small-tabs" role="tablist"><button role="tab" aria-selected={view==='images'} className={view==='images'?'selected':''} onClick={()=>setView('images')}><Grid2X2 size={15}/>图片浏览</button><button role="tab" aria-selected={view==='captions'} className={view==='captions'?'selected':''} onClick={()=>setView('captions')}><FileText size={15}/>Caption 检查</button><button role="tab" aria-selected={view==='buckets'} className={view==='buckets'?'selected':''} onClick={()=>setView('buckets')}><Layers size={15}/>分桶预览</button></div>
        {view==='buckets' ? <div className="empty-state"><Layers size={36}/><strong>分桶预览</strong><span>等待连接 Python 数据处理引擎以计算真实分桶与 Token 数</span></div> : view==='captions' ? <div className="captions-list">{filtered.map(img=><button key={img.id} className={'caption-list-row '+(current?.id===img.id?'active':'')} onClick={()=>{setImageId(img.id);setCaptionDraft(null);}}><Artwork variant={img.variant} imageUrl={img.imageUrl}/><div><b>{img.name}</b><p>{img.caption||'Caption 未设置'}</p></div><Check size={16}/></button>)}</div> : <div className="dataset-image-grid">{filtered.map(img=><button className={'dataset-image-tile '+(current?.id===img.id?'selected':'')} onClick={()=>{setImageId(img.id);setCaptionDraft(null);}} key={img.id}><Artwork variant={img.variant} imageUrl={img.imageUrl} label={img.name}/><div className="dataset-tile-caption"><FileText size={13}/><span>{img.name}</span></div></button>)}</div>}
        {!filtered.length && view!=='buckets' && <div className="empty-state"><Search size={28}/><strong>暂无匹配素材</strong><span>导入图片与同名 .txt，或调整搜索</span><button className="btn btn-ghost" onClick={()=>upload.current?.click()}><ImagePlus size={15}/>导入图片</button></div>}
      </section>
      <aside className="inspector dataset-inspector"><div className="inspector-head"><div><span className="eyebrow">DATA INSPECTOR</span><h3>素材详情</h3></div><FileText size={17}/></div>{current&&<><div className="inspector-preview"><Artwork variant={current.variant} imageUrl={current.imageUrl} label={current.name}/></div><div className="inspector-section"><div className="section-mini-label">FILENAME</div><strong className="filename">{current.name}</strong></div><div className="inspector-section"><div className="section-mini-label">CAPTION EDITOR</div><textarea className="caption-editor" aria-label="编辑 Caption" value={captionDraft??current.caption} onChange={e=>setCaptionDraft(e.target.value)} /><button className="btn btn-primary wide" disabled={captionDraft===null||captionDraft===current.caption} onClick={saveCaption}><Save size={15}/>保存 Caption</button></div><div className="inspector-bottom"><span className="dot-purple"/> DATASET ONLY</div></>}</aside>
    </div>
  </div>;
}
