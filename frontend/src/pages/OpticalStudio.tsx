import { useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import {
  Activity, ArrowLeftRight, ArrowRight, Box, Check, ChevronDown, CircleDot,
  Copy, Cpu, Database, Download, Eye, FolderOpen, Gauge, Image as ImageIcon,
  Layers3, Lightbulb, Minus, Pause, Play, Plus, RefreshCw, Settings2,
  Shuffle, SlidersHorizontal, Sparkles, WandSparkles, Waves, Zap,
} from 'lucide-react';
import Artwork from '../components/Artwork';
import { models, tasks, initialDatasets } from '../data/demo';
import type { SharedProps } from '../App';

const tiles = [
  { name: 'Crystal Flora', weight: 0.78, shade: 'violet', variant: 2 },
  { name: 'Azure Light', weight: 0.42, shade: 'sky', variant: 3 },
  { name: 'Moonlit Bloom', weight: 0.31, shade: 'pink', variant: 4 },
  { name: 'Aurora Glass', weight: 0.18, shade: 'mint', variant: 5 },
];
const ratios = [
  { name: '1:1', size: '1024 × 1024', aspect: '1 / 1' },
  { name: '4:3', size: '1152 × 896', aspect: '4 / 3' },
  { name: '3:4', size: '896 × 1152', aspect: '3 / 4' },
  { name: '16:9', size: '1344 × 768', aspect: '16 / 9' },
];
const samplers = [
  { name: 'Karras', color: '#6366f1', curve: 'M4 4 C28 4 42 24 86 24' },
  { name: 'Euler', color: '#0ea5e9', curve: 'M4 4 Q20 22 86 24' },
  { name: 'Cosine', color: '#8b5cf6', curve: 'M4 5 C45 5 45 23 86 23' },
  { name: 'UniPC', color: '#10b981', curve: 'M4 4 L22 15 L44 20 L66 23 L86 24' },
];

function GlassTitle({ icon: Icon, children, trailing }: { icon: typeof Layers3; children: React.ReactNode; trailing?: React.ReactNode }) {
  return <div className="op-panel-title"><div><Icon size={17} strokeWidth={1.9}/><span>{children}</span></div>{trailing}</div>;
}

function GlassSection({ title, subtitle, actions, children }: { title: string; subtitle?: string; actions?: React.ReactNode; children: React.ReactNode }) {
  return <section className="op-glass-panel op-stage-panel"><div className="op-section-heading"><div><div className="op-overline">{subtitle || 'OPTICAL STUDIO'}</div><h2>{title}</h2></div>{actions}</div>{children}</section>;
}

function RingGauge({ label, value, min, max, step, onChange, color }: {
  label: string; value: number; min: number; max: number; step: number; onChange: (value: number) => void; color: string;
}) {
  const circumference = 2 * Math.PI * 32;
  const offset = circumference * (1 - (value - min) / (max - min));
  return <div className="op-dial">
    <div className="op-dial-ring">
      <svg viewBox="0 0 80 80" aria-hidden="true"><circle cx="40" cy="40" r="32" fill="none" stroke="#d4dfef" strokeWidth="6"/><circle cx="40" cy="40" r="32" fill="none" stroke={color} strokeWidth="6" strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round" transform="rotate(-90 40 40)"/></svg>
      <div className="op-ring-value"><strong>{value}</strong><small>{label}</small></div>
    </div>
    <input aria-label={label} className="op-slider" type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(Number(e.target.value))}/>
  </div>;
}

function LoRAPad() {
  const [coord, setCoord] = useState({ x: .4, y: .34 });
  const [selected, setSelected] = useState<number | null>(null);
  const target = useRef<HTMLDivElement>(null);
  const x = coord.x;
  const y = coord.y;
  const weights = [(1-x)*(1-y), x*(1-y), (1-x)*y, x*y].map(n => Number((n*1.69).toFixed(2)));
  function move(event: ReactPointerEvent<HTMLDivElement>) {
    const bounds = target.current?.getBoundingClientRect();
    if (!bounds) return;
    setCoord({x: Math.max(.07,Math.min(.93,(event.clientX-bounds.left)/bounds.width)),y:Math.max(.07,Math.min(.93,(event.clientY-bounds.top)/bounds.height))});
  }
  function pointerDown(event: ReactPointerEvent<HTMLDivElement>) { event.currentTarget.setPointerCapture(event.pointerId); move(event); }
  return <section className="op-glass-panel op-lora-panel">
    <GlassTitle icon={Layers3} trailing={<span className="op-tiny-tag">Σ {weights.reduce((a,b)=>a+b,0).toFixed(2)}</span>}>LoRA Field</GlassTitle>
    <div ref={target} role="slider" tabIndex={0} aria-label="LoRA 混合位置示意" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(x*100)} className="op-xy-pad op-dotted" onPointerDown={pointerDown} onPointerMove={e => {if(e.buttons===1) move(e);}} onKeyDown={e => {if (e.key==='ArrowLeft') setCoord(c=>({...c,x:Math.max(.07,c.x-.05)}));if(e.key==='ArrowRight')setCoord(c=>({...c,x:Math.min(.93,c.x+.05)}));if(e.key==='ArrowUp')setCoord(c=>({...c,y:Math.max(.07,c.y-.05)}));if(e.key==='ArrowDown')setCoord(c=>({...c,y:Math.min(.93,c.y+.05)}));}}>
      <div className="op-pad-aura a"/><div className="op-pad-aura b"/><div className="op-pad-aura c"/><div className="op-pad-aura d"/>
      <svg className="op-xy-lines" viewBox="0 0 240 240" preserveAspectRatio="none" aria-hidden="true">
        <circle cx="120" cy="120" r="86" fill="none" stroke="#b7c5db" strokeDasharray="3 5"/>
        <circle cx="120" cy="120" r="48" fill="none" stroke="#c8d4e8"/>
        {[[20,20],[220,20],[20,220],[220,220]].map(([x1,y1],i)=><line key={i} x1={x1} y1={y1} x2={x*240} y2={y*240} stroke={['#6366f1','#38bdf8','#d946ef','#10b981'][i]} strokeWidth="1.6" strokeOpacity=".7"/>)}
      </svg>
      {[[0,0],[1,0],[0,1],[1,1]].map(([col,row],i)=><div key={i} className={'op-pad-node node-'+i}><Artwork variant={tiles[i].variant} /><span>{weights[i].toFixed(2)}</span></div>)}
      <span className="op-puck" style={{left:(x*100)+'%',top:(y*100)+'%'}}><i/></span>
    </div>
    <div className="op-lora-cards">{tiles.map((item,i)=><button key={item.name} className={'op-lora-card '+item.shade+(selected===i?' selected':'')} onClick={()=>setSelected(selected===i?null:i)} aria-pressed={selected===i}><Artwork variant={item.variant}/><span><b>{item.name}</b><small>{selected===i?'SOLO / PREVIEW':'W · '+weights[i].toFixed(2)}</small></span></button>)}</div>
    <div className="op-mini-note">图形混合预览 · 连接模型后才会实际应用权重</div>
  </section>;
}

export function GeneratePage({ notify }: SharedProps) {
  const [model,setModel]=useState(models[0]);
  const [frame,setFrame]=useState(0);
  const [sampler,setSampler]=useState(0);
  const [steps,setSteps]=useState(28);
  const [cfg,setCfg]=useState(6.5);
  const [seed,setSeed]=useState(8492014);
  const [focus,setFocus]=useState(0);
  const [split,setSplit]=useState(36);
  const [compare,setCompare]=useState(true);
  const [mesh,setMesh]=useState(false);
  const [zoom,setZoom]=useState(100);
  const [prompt,setPrompt]=useState('translucent crystal lotus, subsurface pearl refraction, high-key studio daylight');
  const [chips,setChips]=useState(['cinematic lighting','delicate detail','soft bloom','optical glass']);
  const [light,setLight]=useState({x:64,y:32});
  const [caustics,setCaustics]=useState(.72);
  const [denoise,setDenoise]=useState(.65);
  const lightRef=useRef<HTMLDivElement>(null);
  const frameRef=useRef<HTMLDivElement>(null);
  function updateLight(event: ReactPointerEvent<HTMLDivElement>) {
    const rect=lightRef.current?.getBoundingClientRect(); if(!rect)return;
    setLight({x:Math.max(12,Math.min(88,(event.clientX-rect.left)/rect.width*100)),y:Math.max(12,Math.min(88,(event.clientY-rect.top)/rect.height*100))});
  }
  function updateSplit(event: ReactPointerEvent<HTMLDivElement>) {
    if(!compare)return;
    const rect=frameRef.current?.getBoundingClientRect();if(!rect)return;
    setSplit(Math.max(5,Math.min(95,(event.clientX-rect.left)/rect.width*100)));
  }
  return <div className="page op-page op-generate">
    <div className="op-workspace-head">
      <div><div className="op-overline">SYNTH / IMAGE GENERATION</div><h1>光影合成 <span>/ Synth Studio</span></h1></div>
      <div className="op-head-actions"><span className="op-status"><CircleDot size={13}/> UI PREVIEW</span><label className="op-select-small"><Box size={14}/><select aria-label="基础模型" value={model} onChange={e=>setModel(e.target.value)}>{models.map(m=><option key={m}>{m}</option>)}</select><ChevronDown size={12}/></label></div>
    </div>
    <div className="op-synth-grid">
      <div className="op-column op-left">
        <LoRAPad/>
        <section className="op-glass-panel">
          <GlassTitle icon={Box} trailing={<span className="op-readout">{ratios[frame].size}</span>}>Frame Geometry</GlassTitle>
          <div className="op-ratio-grid">{ratios.map((ratio,i)=><button className={'op-ratio-option op-glass-pill '+(frame===i?'active':'')} key={ratio.name} onClick={()=>setFrame(i)}><i style={{aspectRatio:ratio.aspect}}/><span>{ratio.name}</span></button>)}</div>
        </section>
      </div>
      <div className="op-column op-center">
        <section className="op-glass-panel op-viewport">
          <div className="op-viewport-controls">
            <div><button className={'op-glass-pill op-tool '+(compare?'active':'')} onClick={()=>setCompare(!compare)}><ArrowLeftRight size={15}/>Split</button><button className={'op-glass-pill op-tool '+(mesh?'active':'')} onClick={()=>setMesh(!mesh)}><Waves size={15}/>Grid</button><button className="op-glass-pill op-tool op-mono" onClick={()=>setSeed(Math.floor(1e6+Math.random()*9e6))}><Shuffle size={14}/>{seed}</button></div>
            <div><button className="op-glass-pill op-icon" aria-label="缩小" onClick={()=>setZoom(v=>Math.max(60,v-10))}><Minus size={15}/></button><span className="op-readout">{zoom}%</span><button className="op-glass-pill op-icon" aria-label="放大" onClick={()=>setZoom(v=>Math.min(140,v+10))}><Plus size={15}/></button></div>
          </div>
          <div className="op-canvas-stage op-dotted">
            <div ref={frameRef} className="op-canvas-frame" style={{aspectRatio:ratios[frame].aspect,transform:'scale('+(zoom/100)+')'}} onPointerDown={e=>{if(compare){e.currentTarget.setPointerCapture(e.pointerId);updateSplit(e);}}} onPointerMove={e=>{if(compare&&e.buttons===1) updateSplit(e);}}>
              <div className="op-base-layer"><Artwork variant={focus+2}/></div>
              <div className="op-carved-layer" style={{clipPath:compare?'inset(0 0 0 '+split+'%)':'none'}}><Artwork variant={focus+2}/></div>
              <div className="op-relight-layer" style={{background:'radial-gradient(circle at '+light.x+'% '+light.y+'%, rgba(255,255,255,'+(caustics*.45)+') 0%,transparent 65%)'}}/>
              {mesh&&<div className="op-mesh-grid" aria-hidden="true"/>}
              {compare&&<div className="op-compare-track" style={{left:split+'%'}}><div className="op-drag-handle"><ArrowLeftRight size={14}/></div><span className="op-split-tag left">BASE</span><span className="op-split-tag right">LORA</span></div>}
              <span className="op-canvas-watermark">STUDIO PREVIEW</span>
            </div>
          </div>
          <div className="op-filmstrip">{Array.from({length:6},(_,i)=><button key={i} aria-label={'选择示例 '+(i+1)} className={'op-film-tile '+(focus===i?'active':'')} onClick={()=>setFocus(i)}><Artwork variant={i+2}/></button>)}</div>
        </section>
        <section className="op-glass-panel op-prompt-panel"><div className="op-chip-row">{chips.map((chip)=><button className="op-glass-pill op-token-chip" key={chip} onClick={()=>{setChips(old=>old.filter(x=>x!==chip));setPrompt(p=>[p,chip].filter(Boolean).join(', '));}}>✦ {chip} <Plus size={11}/></button>)}{chips.length===0&&<span className="op-mini-note">风格标签已移入提示词</span>}</div><div className="op-prompt-row"><Sparkles size={18}/><input aria-label="正向提示词" value={prompt} onChange={e=>setPrompt(e.target.value)}/><button className="op-render-button" onClick={()=>notify('尚未接入 PyTorch 文生图后端，当前是交互式视觉原型','warning')}><Zap size={17}/>Render</button></div></section>
      </div>
      <div className="op-column op-right">
        <section className="op-glass-panel"><GlassTitle icon={Waves} trailing={<span className="op-readout op-indigo">{samplers[sampler].name}</span>}>Sigma Curve</GlassTitle><div className="op-sampler-grid">{samplers.map((s,i)=><button key={s.name} aria-pressed={sampler===i} className={'op-glass-pill op-sampler '+(sampler===i?'active':'')} onClick={()=>setSampler(i)}><svg viewBox="0 0 90 28" preserveAspectRatio="none"><path d={s.curve+' L86 28 L4 28 Z'} fill={s.color} opacity=".11"/><path d={s.curve} fill="none" stroke={s.color} strokeWidth="2.3" strokeLinecap="round"/></svg><span>{s.name}<i style={{background:sampler===i?s.color:'#c2ccd9'}}/></span></button>)}</div></section>
        <section className="op-glass-panel op-dials"><GlassTitle icon={Gauge}>Sampling</GlassTitle><div className="op-dials-grid"><RingGauge label="STEPS" value={steps} min={10} max={80} step={1} onChange={setSteps} color="#6366f1"/><RingGauge label="CFG" value={cfg} min={1} max={15} step={.5} onChange={setCfg} color="#38bdf8"/></div></section>
        <section className="op-glass-panel op-light-panel"><GlassTitle icon={Lightbulb} trailing={<span className="op-readout">{light.x.toFixed(0)}° · {light.y.toFixed(0)}°</span>}>Light Vector</GlassTitle><div className="op-light-body"><div className="op-light-orb" ref={lightRef} role="slider" tabIndex={0} aria-label="预览光照方向" aria-valuemin={0} aria-valuemax={100} aria-valuenow={light.x} onPointerDown={e=>{e.currentTarget.setPointerCapture(e.pointerId);updateLight(e);}} onPointerMove={e=>{if(e.buttons===1)updateLight(e);}} onKeyDown={e=>{if(e.key==='ArrowRight')setLight(v=>({...v,x:Math.min(88,v.x+4)}));if(e.key==='ArrowLeft')setLight(v=>({...v,x:Math.max(12,v.x-4)}));}} style={{background:'radial-gradient(circle at '+light.x+'% '+light.y+'%,#fff 0%,#e0e7ff 41%,#b9c5de 100%)'}}><span className="op-light-dot" style={{left:light.x+'%',top:light.y+'%'}}/></div><div className="op-light-sliders"><label>Caustics <span>{caustics.toFixed(2)}</span><input aria-label="Caustics" className="op-slider" type="range" min="0" max="1" step=".02" value={caustics} onChange={e=>setCaustics(Number(e.target.value))}/></label><label>Denoise <span>{denoise.toFixed(2)}</span><input aria-label="Denoise" className="op-slider" type="range" min=".1" max="1" step=".05" value={denoise} onChange={e=>setDenoise(Number(e.target.value))}/></label></div></div><span className="op-mini-note">光照控件为画面预览效果，不会改变模型输出</span></section>
        <div className="op-side-footer"><Eye size={15}/> 生成引擎尚未连接 <span>BF16</span></div>
      </div>
    </div>
  </div>;
}

function RankGraph({rank,alpha}:{rank:number;alpha:number}) {
 const midCount=rank===8?3:rank===16?5:rank===32?7:9;
 const left=[26,53,80,107,134,161],middle=Array.from({length:midCount},(_,i)=>27+i*137/(midCount-1));
 return <svg className="op-topology" viewBox="0 0 320 190" role="img" aria-label={'LoRA Rank '+rank+' Alpha '+alpha+' 矩阵结构示意'}>
 <defs><linearGradient id="op-line-grad"><stop stopColor="#38bdf8"/><stop offset=".5" stopColor="#7978f7"/><stop offset="1" stopColor="#c084fc"/></linearGradient></defs>
 {left.flatMap((ly,i)=>middle.map((my,j)=><line key={'a'+i+'-'+j} x1="57" y1={ly} x2="155" y2={my} stroke="#6366f1" strokeOpacity={.13+(alpha/32)*.15} strokeWidth=".8"/>))}
 {middle.flatMap((my,i)=>left.map((ly,j)=><line key={'b'+i+'-'+j} x1="167" y1={my} x2="263" y2={ly} stroke="#38bdf8" strokeOpacity={.13+(alpha/32)*.15} strokeWidth=".8"/>))}
 {left.map((y,i)=><g key={i}><circle cx="53" cy={y} r="5" fill="#7b8bff"/><circle cx="267" cy={y} r="5" fill="#8dd9ef"/></g>)}
 {middle.map((y,i)=><circle key={i} cx="161" cy={y} r="5.3" fill="#fff" stroke="#8b5cf6" strokeWidth="2"/>)}
 <g fontSize="10" fill="#64748b" textAnchor="middle" fontFamily="monospace"><text x="53" y="184">A MATRIX</text><text x="161" y="184">RANK {rank}</text><text x="267" y="184">B MATRIX</text></g>
 </svg>;
}

function LossCurve() {
 return <svg className="op-loss-curve" viewBox="0 0 340 150" role="img" aria-label="示例 Loss 曲线，非真实训练数据">
 <defs><linearGradient id="op-loss-fill" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#6366f1" stopOpacity=".27"/><stop offset="1" stopColor="#6366f1" stopOpacity="0"/></linearGradient></defs>
 {[30,65,100,135].map(y=><line key={y} x1="15" x2="325" y1={y} y2={y} stroke="#b4c2d6" strokeDasharray="3 5" strokeOpacity=".65"/>)}
 <path d="M16 30 C85 30 170 127 325 135" stroke="#38bdf8" fill="none" strokeWidth="1.8" strokeDasharray="4 5"/>
 <path d="M16 25 C35 60 45 47 70 70 S110 72 130 97 S180 95 205 111 S260 116 325 128 L325 137 L16 137 Z" fill="url(#op-loss-fill)"/>
 <path d="M16 25 C35 60 45 47 70 70 S110 72 130 97 S180 95 205 111 S260 116 325 128" stroke="#6366f1" fill="none" strokeWidth="2.5" strokeLinecap="round"/>
 {[70,130,205,265,325].map((x,i)=><circle key={x} cx={x} cy={[70,97,111,118,128][i]} r="4" fill="#fff" stroke="#6366f1" strokeWidth="2"/>)}
 </svg>;
}

export function TrainingPage({notify,onNavigateTask}:SharedProps & {onNavigateTask:(id:string)=>void}) {
 const [model,setModel]=useState(models[0]);
 const [dataset,setDataset]=useState(initialDatasets[0].id);
 const [rank,setRank]=useState(32);
 const [alpha,setAlpha]=useState(16);
 const [precision,setPrecision]=useState('BF16');
 const [epoch,setEpoch]=useState(8);
 const [epochs,setEpochs]=useState(20);
 const [learningRate,setLearningRate]=useState('0.0001');
 const [activeImg,setActiveImg]=useState(0);
 const selectedDataset=initialDatasets.find(d=>d.id===dataset)||initialDatasets[0];
 const datasetImages=selectedDataset.images;
 const [cache,setCache]=useState(true);
 function exportDraft() {
  const draft={model,dataset,rank,alpha,precision,epochs,learningRate,vaeLatentCache:cache,note:'UI draft, no training backend'};
  const blob=new Blob([JSON.stringify(draft,null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='lumacarve-training-draft.json';link.click();URL.revokeObjectURL(url);
  notify('已导出配置草稿 JSON（不是训练 TOML）','success');
 }
 return <div className="page op-page op-train">
  <div className="op-workspace-head"><div><div className="op-overline">CARVE / MODEL TRAINING</div><h1>权重雕琢 <span>/ Carve LoRA</span></h1></div><div className="op-head-actions"><span className="op-status"><CircleDot size={13}/> UI PREVIEW</span><button className="op-glass-pill op-tool" onClick={exportDraft}><Download size={15}/>配置</button><button className="op-render-button" onClick={()=>notify('尚未接入 LoRA 训练引擎，当前是交互式视觉原型','warning')}><Play size={16}/>开始训练</button></div></div>
  <div className="op-train-grid">
   <section className="op-glass-panel op-train-dataset">
    <GlassTitle icon={Database} trailing={<span className="op-tiny-tag">{datasetImages.length} IMAGES</span>}>Dataset Tensor</GlassTitle>
    <div className="op-field-row"><label>训练数据集<select aria-label="数据集" value={dataset} onChange={e=>{setDataset(e.target.value);setActiveImg(0);}}>{initialDatasets.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label><label>基础模型<select aria-label="基础模型" value={model} onChange={e=>setModel(e.target.value)}>{models.map(m=><option key={m}>{m}</option>)}</select></label></div>
    <div className="op-dataset-matrix">{datasetImages.slice(0,6).map((img,i)=><button onClick={()=>setActiveImg(i)} className={'op-dataset-cell '+(activeImg===i?'active':'')} key={img.id}><Artwork variant={img.variant}/><span>{i+1}</span></button>)}</div>
    <div className="op-bucket-bar"><div><span>LATENT BUCKETS</span><b>SCHEMA PREVIEW</b></div><div className="op-bucket-track"><i style={{width:'58%'}}/><i style={{width:'27%'}}/><i style={{width:'15%'}}/></div><div className="op-bucket-legend"><span>1:1 · 58%</span><span>4:3 · 27%</span><span>3:4 · 15%</span></div></div>
    <div className="op-dataset-caption"><ImageIcon size={16}/><span>{datasetImages[activeImg]?.name}</span></div>
    <div className="op-mini-note">分桶比例仅作视觉示例，实际统计由训练后端提供</div>
   </section>
   <section className="op-glass-panel op-train-topology">
    <GlassTitle icon={Layers3} trailing={<span className="op-tiny-tag">R{rank} · α{alpha}</span>}>Low-Rank Topology</GlassTitle>
    <div className="op-topology-frame op-dotted"><RankGraph rank={rank} alpha={alpha}/></div>
    <div className="op-option-group"><span>RANK (r)</span><div>{[8,16,32,64].map(v=><button className={'op-glass-pill '+(rank===v?'active':'')} onClick={()=>setRank(v)} key={v}>{v}</button>)}</div></div>
    <div className="op-option-group"><span>ALPHA (α)</span><div>{[4,8,16,32].map(v=><button className={'op-glass-pill '+(alpha===v?'active':'')} onClick={()=>setAlpha(v)} key={v}>{v}</button>)}</div></div>
    <div className="op-train-controls"><label>训练精度<select value={precision} aria-label="训练精度" onChange={e=>setPrecision(e.target.value)}><option>BF16</option><option>FP16</option></select></label><label>Epochs<input min="1" max="9999" type="number" aria-label="Epoch 总数" value={epochs} onChange={e=>setEpochs(Math.max(1,Number(e.target.value)))}/></label><label>学习率<input aria-label="学习率" value={learningRate} onChange={e=>setLearningRate(e.target.value)}/></label></div>
    <div className="op-cache-row"><button className={'op-glass-pill '+(cache?'active':'')} onClick={()=>setCache(v=>!v)}><Check size={15}/>VAE Latent 缓存 {cache?'开启':'关闭'}</button><span><Cpu size={14}/>Text Encoder 冻结</span></div>
   </section>
   <section className="op-glass-panel op-train-converge">
    <GlassTitle icon={Activity} trailing={<span className="op-tiny-tag">DEMO · NO GPU</span>}>Convergence</GlassTitle>
    <div className="op-chart-frame"><LossCurve/><div className="op-chart-labels"><span>LOSS · DEMO</span><span>LR · DEMO</span></div></div>
    <div className="op-metrics-row"><div><small>Loss</small><strong>—</strong></div><div><small>Learning Rate</small><strong>—</strong></div><div><small>Max Grad</small><strong>—</strong></div></div>
    <div className="op-train-epoch-head"><span>EPOCH SAMPLES</span><button onClick={()=>onNavigateTask(tasks[0].id)}>查看任务集合 <ArrowRight size={13}/></button></div>
    <div className="op-train-epoch-grid">{[0,1,2,3,4,5,6,7].map(e=><button key={e} className={epoch===e?'active':''} onClick={()=>setEpoch(e)} title={'Epoch '+e}><Artwork variant={2+e}/><span>{e===0?'Step 0':'E'+e}</span></button>)}</div>
    <div className="op-train-epoch-view"><Artwork variant={2+epoch}/><div><b>{epoch===0?'STEP 0':'EPOCH '+String(epoch).padStart(2,'0')}</b><small>固定 Prompt / Seed</small><button onClick={()=>onNavigateTask(tasks[0].id)}>完整对比 <ArrowRight size={13}/></button></div></div>
   </section>
  </div>
  <div className="op-caption-strip"><ShieldLine/> 图中的曲线、样本与分桶为界面示例 · 未启动真实训练</div>
 </div>;
}
function ShieldLine(){return <Sparkles size={14}/>;}

export function FlowPage({notify}:SharedProps) {
 const [selected,setSelected]=useState(2);
 const flow=[
  {tag:'01',type:'CHECKPOINT',detail:'Base Model',color:'indigo',icon:Box},
  {tag:'02',type:'TEXT ENCODER',detail:'Frozen · CPU',color:'sky',icon:Cpu},
  {tag:'03',type:'TRANSFORMER',detail:'LoRA / BF16',color:'violet',icon:Layers3},
  {tag:'04',type:'VAE',detail:'Latent Cache',color:'mint',icon:Waves},
  {tag:'05',type:'OUTPUT',detail:'PNG Metadata',color:'pink',icon:ImageIcon},
 ];
 return <div className="page op-page"><div className="op-workspace-head"><div><div className="op-overline">GRAPH / ARCHITECTURE VIEW</div><h1>流程图谱 <span>/ Optical Graph</span></h1></div><div className="op-head-actions"><span className="op-status">ARCHITECTURE PREVIEW</span><button className="op-glass-pill op-tool" onClick={()=>notify('图谱用于展示设计结构，尚不支持执行','warning')}><Play size={15}/>Execute Graph</button></div></div>
  <GlassSection title="Optical Pipeline" subtitle="SHARED MODEL ENGINE" actions={<span className="op-tiny-tag">NO ENGINE CONNECTED</span>}>
   <div className="op-flow-canvas op-dotted">
    <svg className="op-flow-wires" viewBox="0 0 1000 380" preserveAspectRatio="none" aria-hidden="true">
      <path d="M 185 160 C 265 160 260 160 338 160 S 445 160 540 160 S 650 160 735 160 S 830 160 900 160" fill="none" stroke="#8896ff" strokeOpacity=".35" strokeWidth="6" strokeLinecap="round"/>
      <path className="op-flow-stream" d="M 185 160 C 265 160 260 160 338 160 S 445 160 540 160 S 650 160 735 160 S 830 160 900 160" fill="none" stroke="#6366f1" strokeWidth="2.5" strokeDasharray="7 10" strokeLinecap="round"/>
    </svg>
    <div className="op-flow-nodes">{flow.map((n,i)=><button className={'op-glass-panel op-flow-node '+(selected===i?'active':'')} onClick={()=>setSelected(i)} key={n.tag}><div className="op-flow-node-title"><span className={n.color}>{n.tag} · {n.type}</span><CircleDot size={11}/></div><div className="op-flow-node-icon"><n.icon size={28}/></div><b>{n.detail}</b></button>)}</div>
   </div>
   <div className="op-flow-detail"><div><span>SELECTED NODE</span><b>{flow[selected].type}</b></div><span>训练与生成采用独立循环 · 共用模型注册表和组件管理</span><button onClick={()=>setSelected((selected+1)%flow.length)} className="op-glass-pill op-tool">下一个节点 <ArrowRight size={14}/></button></div>
  </GlassSection>
 </div>;
}
