import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import type { ChangeEvent, PointerEvent as ReactPointerEvent } from 'react';
import {
  ArrowDownToLine, ArrowLeftRight, ArrowUpRight, Brush, Check, CheckCircle2,
  ChevronDown, CircleHelp, Copy, Download, Eye, FileImage, FolderOpen,
  Image as ImageIcon, ImagePlus, Layers3, Maximize, MoreHorizontal,
  MousePointer2, PenTool, Plus, RotateCcw, Settings2, Shuffle, SlidersHorizontal,
  Sparkles, Trash2, Upload, Workflow, X, Zap,
} from 'lucide-react';
import Artwork from '../../components/Artwork';
import type { SharedProps } from '../../App';
import {
  appendGraphNode, connectGraphNodes, fieldRegistry, getField, getModelId,
  getStudioModel, kinds, makeWorkflow, nodeTitle, removeGraphNode, studioModels,
  toggleFieldExposure, updateNodeValue, validateImport, visibleFields,
} from './workflow';
import type {
  FieldId, FieldValue, LoRAEntry, NodeKind, StudioIntent, StudioNode, StudioWorkflow,
} from './workflow';
import {
  cancelImageJob, getImageJob, outputFromJob, submitImageJob,
} from './api';
import type { GeneratedImage, JobState } from './api';
const GraphCanvas = lazy(() => import('./GraphCanvas'));

type StudioView = 'parameters' | 'graph';
type RefImage = { id:string; name:string; url:string; width:number; height:number; bytes:number; file:File };
const intents:ReadonlyArray<{id:StudioIntent;label:string;help:string}> = [
  {id:'create',label:'文字生成',help:'从提示词生成新图像'},
  {id:'reference',label:'参考编辑',help:'融合参考图、调整画面内容'},
  {id:'inpaint',label:'局部重绘',help:'使用蒙版限定编辑区域'},
];
const MAX_FILE_BYTES = 25*1024*1024;
const RATIO_OPTIONS = ['1:1','4:3','3:4','16:9','9:16','2:3','3:2'];

function copyValues(from:StudioWorkflow, to:StudioWorkflow): StudioWorkflow {
  // Switching starter templates preserves common model/LoRA/prompt/sampling values.
  return {...to,nodes:to.nodes.map(node=>{
    const previous=from.nodes.find(n=>n.kind===node.kind);
    return previous?{...node,params:{...node.params,...previous.params},exposed:previous.exposed.slice()}:node;
  })};
}
async function createPreview(file:File):Promise<Omit<RefImage,'id'>> {
  let bitmap:ImageBitmap | null=null;
  if(typeof createImageBitmap==='function'){
    bitmap=await createImageBitmap(file);
    const width=bitmap.width;
    const height=bitmap.height;
    const ratio=Math.min(1,1600/Math.max(width,height));
    const canvas=document.createElement('canvas');
    canvas.width=Math.max(1,Math.round(width*ratio));
    canvas.height=Math.max(1,Math.round(height*ratio));
    const ctx=canvas.getContext('2d');
    if(!ctx){bitmap.close();throw new Error('无法创建预览画布');}
    ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);
    bitmap.close();
    const preview=await new Promise<Blob>((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('图片预览编码失败')),'image/webp',.84));
    canvas.width=0;canvas.height=0;
    return {name:file.name,url:URL.createObjectURL(preview),width,height,bytes:file.size,file};
  }
  const url=URL.createObjectURL(file);
  return await new Promise((resolve,reject)=>{
    const image=new Image();
    image.onload=()=>resolve({name:file.name,url,width:image.naturalWidth,height:image.naturalHeight,bytes:file.size,file});
    image.onerror=()=>{URL.revokeObjectURL(url);reject(new Error('浏览器无法解码图片'))};
    image.src=url;
  });
}
function downloadText(content:string,filename:string,type:string) {
  const url=URL.createObjectURL(new Blob([content],{type}));
  const link=document.createElement('a');
  link.href=url;link.download=filename;link.click();
  window.setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function SmallLabel({children,extra}:{children:React.ReactNode;extra?:React.ReactNode}){
  return <div className="is-heading"><span>{children}</span>{extra}</div>;
}
function InlineControl({children}:{children:React.ReactNode}){
  return <div className="is-inline-control">{children}</div>;
}
function Setting({label,children,tip}:{label:string;children:React.ReactNode;tip?:string}){
  return <label className="is-field"><span>{label}{tip&&<small>{tip}</small>}</span>{children}</label>;
}
type LoRAsProps={entries:LoRAEntry[];onChange:(list:LoRAEntry[])=>void};
function LoRAStack({entries,onChange}:LoRAsProps){
  function add(){onChange([...entries,{id:'lora-'+Date.now().toString(36),name:'',strength:1,enabled:true}]);}
  return <section className="is-panel is-lora-panel">
    <SmallLabel extra={<span className="is-soft-tag">{entries.length} 个</span>}>LoRA Stack</SmallLabel>
    <div className="is-panel-explanation">所有 LoRA 共享基础模型，不复制主模型权重。</div>
    <div className="is-lora-items">
      {entries.map((item,i)=><div key={item.id} className={'is-lora-entry'+(!item.enabled?' is-muted':'')}>
        <div className="is-lora-top">
          <label className="is-switch is-switch-small" title="启用 / 禁用">
            <input type="checkbox" checked={item.enabled} onChange={e=>onChange(entries.map(x=>x.id===item.id?{...x,enabled:e.target.checked}:x))}/>
            <span/>
          </label>
          <span className="is-entry-index">{String(i+1).padStart(2,'0')}</span>
          <input aria-label={'LoRA '+(i+1)+' 文件名'} value={item.name} placeholder="选择或输入 LoRA 名称" onChange={e=>onChange(entries.map(x=>x.id===item.id?{...x,name:e.target.value}:x))}/>
          <button className="is-quiet-icon" aria-label={'移除 LoRA '+(i+1)} onClick={()=>onChange(entries.filter(x=>x.id!==item.id))}><X size={14}/></button>
        </div>
        <div className="is-lora-strength"><span>权重</span><input type="range" min="-2" max="2" step=".05" value={item.strength} disabled={!item.enabled} onChange={e=>onChange(entries.map(x=>x.id===item.id?{...x,strength:Number(e.target.value)}:x))} aria-label={'LoRA '+(i+1)+' 权重'}/><b>{item.strength.toFixed(2)}</b></div>
      </div>)}
      {entries.length===0&&<div className="is-lora-empty">尚未添加 LoRA · 不影响基础模型使用</div>}
    </div>
    <button className="is-outline-add" onClick={add}><Plus size={15}/> 添加 LoRA</button>
  </section>;
}

export default function ImageStudioPage({notify}:SharedProps){
  const [workflow,setWorkflow]=useState<StudioWorkflow>(()=>makeWorkflow());
  const [view,setView]=useState<StudioView>('parameters');
  const [advanced,setAdvanced]=useState(true);
  const [references,setReferences]=useState<RefImage[]>([]);
  const [selectedRef,setSelectedRef]=useState<string|null>(null);
  const [selectedNode,setSelectedNode]=useState<string|null>('sampler');
  const [brushSize,setBrushSize]=useState(38);
  const [erase,setErase]=useState(false);
  const [maskDirty,setMaskDirty]=useState(false);
  const [drawing,setDrawing]=useState(false);
  const [sampleIndex,setSampleIndex]=useState(0);
  const [generatedImages,setGeneratedImages]=useState<GeneratedImage[]>([]);
  const [selectedOutputId,setSelectedOutputId]=useState<string|null>(null);
  const [activeJobId,setActiveJobId]=useState<string|null>(null);
  const [runState,setRunState]=useState<JobState|'idle'|'submitting'>('idle');
  const [compare,setCompare]=useState(false);
  const pickerRef=useRef<HTMLInputElement>(null);
  const graphImportRef=useRef<HTMLInputElement>(null);
  const canvasRef=useRef<HTMLCanvasElement>(null);
  const imageUrls=useRef(new Set<string>());
  const maskPosition=useRef<{x:number;y:number}|null>(null);
  const notifyRef=useRef(notify);
  useEffect(()=>{notifyRef.current=notify;},[notify]);
  useEffect(()=>{
    if(!activeJobId)return;
    let live=true, busy=false;
    async function poll(){
      if(busy)return;
      busy=true;
      try{
        const job=await getImageJob(activeJobId!);
        if(!live)return;
        setRunState(job.state);
        if(job.state==='completed'){
          const output=outputFromJob(job);
          setGeneratedImages(previous=>[...previous,output].slice(-20));
          setSelectedOutputId(output.outputId);
          setActiveJobId(null);
          notifyRef.current('Anima 已生成真实 PNG 图片','success');
        }else if(job.state==='failed'||job.state==='cancelled'){
          setActiveJobId(null);
          notifyRef.current(job.state==='failed'?(job.error||'Anima 生成失败'):'已取消生成','warning');
        }
      }catch(error){
        if(live)notifyRef.current(error instanceof Error?error.message:'无法查询生成状态','warning');
      }finally{busy=false;}
    }
    void poll();
    const timer=window.setInterval(()=>void poll(),1500);
    return()=>{live=false;window.clearInterval(timer);};
  },[activeJobId]);

  useEffect(()=>()=>{imageUrls.current.forEach(url=>URL.revokeObjectURL(url));imageUrls.current.clear();},[]);

  const modelId=getModelId(workflow);
  const model=getStudioModel(modelId);
  const activeRef=references.find(image=>image.id===selectedRef)||references[0];
  const selectedGraphNode=workflow.nodes.find(node=>node.id===selectedNode);
  const exposedPrimary=visibleFields(workflow,'primary');
  const exposedAdvanced=visibleFields(workflow,'advanced');
  const showField=(id:FieldId)=>exposedPrimary.some(item=>item.field.id===id)||exposedAdvanced.some(item=>item.field.id===id);
  const getValue=(id:FieldId):FieldValue|undefined=>getField(workflow,id)?.value;
  function updateField(id:FieldId,value:FieldValue){
    const match=getField(workflow,id);
    if(match)setWorkflow(prev=>updateNodeValue(prev,match.node.id,id,value));
  }
  function updateNode(id:string,field:FieldId,value:FieldValue){setWorkflow(prev=>updateNodeValue(prev,id,field,value));}
  function changeIntent(intent:StudioIntent){
    if(!model.intents.includes(intent)){notify(model.label+' 尚未声明支持此编辑模式','warning');return;}
    if(workflow.intent===intent)return;
    setWorkflow(prev=>copyValues(prev,makeWorkflow(intent,getModelId(prev))));
    setSelectedNode('sampler');
    setMaskDirty(false);
    setCompare(false);
  }
  function changeModel(id:string){
    const target=getStudioModel(id);
    setWorkflow(prev=>{
      const validIntent=target.intents.includes(prev.intent)?prev.intent:'create';
      const next=validIntent===prev.intent?prev:copyValues(prev,makeWorkflow(validIntent,id));
      const node=next.nodes.find(n=>n.kind==='model');
      return node?updateNodeValue(next,node.id,'modelId',id):next;
    });
    if(!target.intents.includes(workflow.intent)) notify('当前模型未声明编辑能力，已切回文字生成','info');
  }
  async function uploadImages(e:ChangeEvent<HTMLInputElement>){
    const files=Array.from(e.target.files||[]);
    e.target.value='';
    if(!files.length)return;
    if(!model.maxReferences){notify('当前模型未声明图像输入能力','warning');return;}
    const room=Math.max(0,model.maxReferences-references.length);
    if(!room){notify('当前模型最多可添加 '+model.maxReferences+' 张参考图','warning');return;}
    if(files.length>room)notify('已按模型能力限制为 '+model.maxReferences+' 张参考图','warning');
    const next:RefImage[]=[];
    for(const file of files.slice(0,room)){
      if(!file.type.startsWith('image/') || file.size>MAX_FILE_BYTES){notify(file.name+' 格式不符或超过 25MB 预览限制','warning');continue;}
      try{
        const preview=await createPreview(file);
        const id='ref-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,8);
        imageUrls.current.add(preview.url);
        next.push({...preview,id});
      }catch{notify(file.name+' 图片读取失败','warning');}
    }
    if(next.length){
      setReferences(prev=>[...prev,...next]);
      setSelectedRef(prev=>prev||next[0].id);
      if(workflow.intent==='create'&&model.intents.includes('reference'))changeIntent('reference');
      notify('已添加 '+next.length+' 张参考图（仅当前会话，不会上传）','success');
    }
  }
  function removeReference(id:string){
    const item=references.find(x=>x.id===id);
    if(item){URL.revokeObjectURL(item.url);imageUrls.current.delete(item.url);}
    setReferences(prev=>prev.filter(x=>x.id!==id));
    setSelectedRef(prev=>prev===id?(references.find(x=>x.id!==id)?.id||null):prev);
    clearMask();
  }
  useEffect(()=>{
    const canvas=canvasRef.current;
    if(!canvas)return;
    const width=activeRef?activeRef.width:1024;
    const height=activeRef?activeRef.height:1024;
    const scale=Math.min(1,1536/Math.max(width,height));
    canvas.width=Math.max(1,Math.round(width*scale));
    canvas.height=Math.max(1,Math.round(height*scale));
    setMaskDirty(false);
    maskPosition.current=null;
  },[activeRef?.id,workflow.intent]);
  function clearMask(){
    const canvas=canvasRef.current;
    canvas?.getContext('2d')?.clearRect(0,0,canvas.width,canvas.height);
    maskPosition.current=null;
    setMaskDirty(false);
  }
  function canvasPos(event:ReactPointerEvent<HTMLCanvasElement>){
    const rect=event.currentTarget.getBoundingClientRect();
    const canvas=event.currentTarget;
    return {x:(event.clientX-rect.left)/rect.width*canvas.width,y:(event.clientY-rect.top)/rect.height*canvas.height};
  }
  function drawMask(event:ReactPointerEvent<HTMLCanvasElement>,start=false){
    const canvas=event.currentTarget;
    const ctx=canvas.getContext('2d');
    if(!ctx)return;
    const point=canvasPos(event);
    ctx.lineCap='round';ctx.lineJoin='round';
    ctx.globalCompositeOperation=erase?'destination-out':'source-over';
    ctx.strokeStyle='#fff';ctx.fillStyle='#fff';
    ctx.lineWidth=Math.max(2,brushSize/100*canvas.width/5);
    if(start||!maskPosition.current){
      ctx.beginPath();ctx.arc(point.x,point.y,ctx.lineWidth/2,0,Math.PI*2);ctx.fill();
    } else {
      const last=maskPosition.current;
      ctx.beginPath();ctx.moveTo(last.x,last.y);ctx.lineTo(point.x,point.y);ctx.stroke();
    }
    maskPosition.current=point;
    setMaskDirty(true);
  }
  function pointerDown(event:ReactPointerEvent<HTMLCanvasElement>){
    if(workflow.intent!=='inpaint'||!activeRef)return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrawing(true);
    drawMask(event,true);
  }
  function pointerMove(event:ReactPointerEvent<HTMLCanvasElement>){if(drawing)drawMask(event);}
  function pointerUp(){
    setDrawing(false);
    maskPosition.current=null;
  }
  function downloadMask(){
    const canvas=canvasRef.current;
    if(!canvas||!maskDirty){notify('请先在原图上涂抹编辑区域','warning');return;}
    canvas.toBlob(blob=>{
      if(!blob){notify('蒙版导出失败','warning');return;}
      const url=URL.createObjectURL(blob);
      const link=document.createElement('a');
      link.href=url;link.download='lumacarve_mask.png';link.click();
      window.setTimeout(()=>URL.revokeObjectURL(url),1000);
    },'image/png');
  }
  function exportWorkflow(){
    downloadText(JSON.stringify(workflow,null,2),'lumacarve-workflow.json','application/json;charset=utf-8');
    notify('已导出工作流定义（不包含参考图和蒙版）','success');
  }
  async function importWorkflow(event:ChangeEvent<HTMLInputElement>){
    const file=event.target.files?.[0];event.target.value='';
    if(!file)return;
    if(file.size>2*1024*1024){notify('工作流 JSON 超过 2MB 安全限制','warning');return;}
    try{
      const data=validateImport(JSON.parse(await file.text()));
      setWorkflow(data);
      setView('graph');
      setSelectedNode(data.nodes[0]?.id||null);
      notify('已导入工作流结构；参考图片需重新选择','success');
    }catch(error){notify('导入失败：'+(error instanceof Error?error.message:'文件格式错误'),'warning');}
  }
  function addNode(kind:NodeKind){
    setWorkflow(prev=>appendGraphNode(prev,kind));
  }
  function connectNodes(source:string,target:string){
    setWorkflow(prev=>connectGraphNodes(prev,source,target));
  }
  function removeNodes(nodeIds:string[],edgeIds:string[]){
    const removed=new Set(nodeIds);const removedEdges=new Set(edgeIds);
    setWorkflow(prev=>({...prev,nodes:prev.nodes.filter(node=>!removed.has(node.id)),edges:prev.edges.filter(edge=>!removed.has(edge.source)&&!removed.has(edge.target)&&!removedEdges.has(edge.id))}));
    if(selectedNode&&removed.has(selectedNode))setSelectedNode(null);
  }
  function setNodePosition(id:string,x:number,y:number){
    setWorkflow(prev=>({...prev,nodes:prev.nodes.map(node=>node.id===id?{...node,x,y}:node)}));
  }
  async function requestRun(){
    if(activeJobId||runState==='submitting')return;
    if(modelId!=='anima-base-1'||workflow.intent!=='create'){
      notify('当前已接入 Anima Base 1.0 文字生成；其他模型与编辑后端尚未连接','warning');
      return;
    }
    const prompt=workflow.nodes.find(node=>node.kind==='prompt')?.params.prompt;
    if(typeof prompt!=='string'||!prompt.trim()){
      notify('请先输入创作指令','warning');
      return;
    }
    setRunState('submitting');
    try{
      const job=await submitImageJob(workflow);
      setRunState(job.state);
      setActiveJobId(job.id);
      notify('Anima 任务已进入本地队列','info');
    }catch(error){
      setRunState('failed');
      notify(error instanceof Error?error.message:'创建 Anima 任务失败','warning');
    }
  }
  async function requestCancel(){
    if(!activeJobId)return;
    try{
      await cancelImageJob(activeJobId);
      notify('已请求取消，正在运行的 CUDA 步骤可能需要完成后才能停止','info');
    }catch(error){
      notify(error instanceof Error?error.message:'取消请求失败','warning');
    }
  }
  const loraBind=getField(workflow,'loras');
  const loras=Array.isArray(loraBind?.value)?(loraBind!.value as LoRAEntry[]):[];
  const visibleOutput=generatedImages.find(item=>item.outputId===selectedOutputId)||generatedImages.at(-1);
  const previewRatio=activeRef?activeRef.width+' / '+activeRef.height:
    (visibleOutput?visibleOutput.width+' / '+visibleOutput.height:String(getValue('aspect')||'1:1').replace(':',' / '));
  const previewSource=Boolean(activeRef);
  const showPrompt=showField('prompt');
  const masked=showField('mask')&&model.supportsMask;
  const needsImage=workflow.intent!=='create'||showField('images');

  return <div className="is-page page">
    <div className="is-toolbar">
      <div className="is-workspace-brand">
        <div className="is-overline"><span className="is-overline-dot"/> LUMACARVE / IMAGE STUDIO</div>
        <h1>图像工作室 <span>Image Studio</span></h1>
        <p>生成、参考编辑与局部重绘，统一工作流。</p>
      </div>
      <div className="is-toolbar-actions">
        <div className="is-view-switch" role="group" aria-label="工作台视图">
          <button className={view==='parameters'?'active':''} onClick={()=>setView('parameters')}><SlidersHorizontal size={16}/> 参数视图</button>
          <button className={view==='graph'?'active':''} onClick={()=>setView('graph')}><Workflow size={16}/> 节点工作流</button>
        </div>
        <button className="is-action-icon" title="导入工作流" aria-label="导入工作流" onClick={()=>graphImportRef.current?.click()}><FolderOpen size={17}/></button>
        <button className="is-action-icon" title="导出工作流" aria-label="导出工作流" onClick={exportWorkflow}><Download size={17}/></button>
      </div>
    </div>

    <div className="is-mode-bar">
      <div className="is-mode-tabs" role="group" aria-label="创作类型">
        {intents.map(intent=><button key={intent.id} title={intent.help} disabled={!model.intents.includes(intent.id)} className={workflow.intent===intent.id?'active':''} onClick={()=>changeIntent(intent.id)}>
          {intent.id==='create'?<Sparkles size={15}/>:intent.id==='reference'?<ImageIcon size={15}/>:<Brush size={15}/>}
          {intent.label}
        </button>)}
      </div>
      <div className="is-workflow-context"><span>{workflow.nodes.length} 节点</span><span className="is-separator">/</span><span>{workflow.edges.length} 连接</span><span className="is-separator">/</span><span className="is-context-status">前端预览 · 未连接 GPU</span></div>
    </div>

    {view==='parameters'?
    <div className="is-layout">
      <aside className="is-column is-input-column">
        {showField('modelId')&&<section className="is-panel is-model-card">
          <SmallLabel extra={<span className="is-mini-badge">{model.status}</span>}>基础模型</SmallLabel>
          <div className="is-model-selector">
            <span className="is-model-symbol"><Layers3 size={20}/></span>
            <div>
              <select aria-label="基础模型" value={modelId} onChange={e=>changeModel(e.target.value)}>{studioModels.map(item=><option value={item.id} key={item.id}>{item.label}</option>)}</select>
              <small>{model.subtitle}</small>
            </div>
            <ChevronDown size={14}/>
          </div>
          <div className="is-model-capabilities">{model.intents.map(intent=><span key={intent}>{intent==='create'?'文字生成':intent==='reference'?'参考图编辑':'局部重绘'}</span>)}{model.supportsAlpha&&<span>透明图像</span>}</div>
        </section>}

        {showField('images')&&<section className="is-panel is-sources">
          <SmallLabel extra={<span className="is-soft-tag">{references.length} / {model.maxReferences} 张</span>}>输入素材</SmallLabel>
          <p className="is-panel-explanation">为图像编辑提供原图、服装、场景或其他参考。支持多张。</p>
          <button className="is-upload-tile" onClick={()=>pickerRef.current?.click()} disabled={references.length>=model.maxReferences}>
            <span><ImagePlus size={22}/></span><strong>添加参考图片</strong><small>PNG / JPG / WebP · 仅本地预览</small>
          </button>
          <div className="is-reference-list">{references.map((ref,i)=><div className={'is-reference-tile'+(activeRef?.id===ref.id?' selected':'')} key={ref.id}>
            <button onClick={()=>{setSelectedRef(ref.id)}} aria-label={'查看参考图 '+(i+1)}><img src={ref.url} alt={ref.name}/><span>{String(i+1).padStart(2,'0')}</span></button>
            <div className="is-reference-name"><strong title={ref.name}>{ref.name}</strong><small>{ref.width} × {ref.height}</small></div>
            <button className="is-quiet-icon" aria-label={'移除 '+ref.name} onClick={()=>removeReference(ref.id)}><X size={15}/></button>
          </div>)}</div>
          {references.length>0&&<div className="is-muted-hint">参考图按添加顺序对应 Image 1、Image 2 ……</div>}
        </section>}

        {masked&&showField('mask')&&<section className="is-panel is-mask-panel">
          <SmallLabel extra={<span className="is-soft-tag">选区工具</span>}>蒙版编辑</SmallLabel>
          <p className="is-panel-explanation">在中间原图上涂抹白色区域，表示需要修改的部分。</p>
          <div className="is-mask-tools"><button className={!erase?'active':''} onClick={()=>setErase(false)}><Brush size={15}/>画笔</button><button className={erase?'active':''} onClick={()=>setErase(true)}><RotateCcw size={15}/>擦除</button></div>
          <Setting label="笔刷大小"><InlineControl><input className="is-range" aria-label="蒙版笔刷大小" type="range" min="6" max="100" value={brushSize} onChange={e=>setBrushSize(Number(e.target.value))}/><b>{brushSize}</b></InlineControl></Setting>
          <div className="is-mask-actions"><button onClick={clearMask}><Trash2 size={14}/>清空蒙版</button><button onClick={downloadMask}><Download size={14}/>导出 PNG</button></div>
          <div className="is-muted-hint">{maskDirty?'蒙版已有内容 · 当前会话有效':'尚未绘制蒙版'}</div>
        </section>}

        {loraBind&&<LoRAStack entries={loras} onChange={items=>updateNode(loraBind.node.id,'loras',items)}/>}
      </aside>

      <div className="is-column is-center-column">
        <section className="is-panel is-canvas-panel">
          <div className="is-canvas-top"><div className="is-preview-title"><span className="is-preview-dot"/><strong>{previewSource?'原图预览':'创作画布'}</strong><small>{previewSource?'REFERENCE IMAGE':visibleOutput?'GENERATED PNG':'SAMPLE VIEW'}</small></div><div className="is-canvas-actions">
            {previewSource&&<button className={'is-icon-label'+(compare?' active':'')} onClick={()=>setCompare(v=>!v)} title="对照示例"><ArrowLeftRight size={14}/>对比</button>}
            <span className="is-canvas-size">{activeRef?activeRef.width+' × '+activeRef.height:visibleOutput?visibleOutput.width+' × '+visibleOutput.height:String(getValue('aspect')||'1:1')}</span>
          </div></div>
          <div className="is-canvas-backdrop">
            <div className="is-preview-frame" style={{aspectRatio:previewRatio}}>
              {previewSource?<img className="is-main-image" src={activeRef!.url} alt={activeRef!.name}/>:
              visibleOutput?<img className="is-main-image" src={visibleOutput.imageUrl} alt="Anima 实际生成图片"/>:
              <Artwork variant={sampleIndex+2} className="is-main-image" label="界面示意图，非真实生成结果"/>}
              {previewSource&&compare&&<div className="is-compare-placeholder"><Artwork variant={sampleIndex+2}/><span>示例对照</span></div>}
              {masked&&previewSource&&<canvas key={activeRef?.id+'-'+workflow.intent} ref={canvasRef} className={'is-mask-canvas'+(drawing?' drawing':'')} style={{opacity:.62}} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={pointerUp} aria-label="局部编辑蒙版绘制画布"/>}
              <span className="is-preview-caption">{previewSource?(masked?'蒙版编辑 · 本地画布':'参考原图 · 本地预览'):visibleOutput?'Anima 生成结果 · Seed '+visibleOutput.seed:'示例预览 · 未生成实际图片'}</span>
            </div>
            {!previewSource&&!visibleOutput&&<div className="is-placeholder-text"><span><Sparkles size={15}/> 连接生成后端后，结果将在这里显示</span></div>}
          </div>
          <div className="is-canvas-bottom"><div className="is-canvas-filmstrip">{generatedImages.length?
              generatedImages.map(item=><button key={item.outputId} className={item.outputId===visibleOutput?.outputId?'active':''} onClick={()=>setSelectedOutputId(item.outputId)} title={'真实生成图片 · Seed '+item.seed}><img src={item.imageUrl} alt={'Anima 输出 '+item.outputId}/></button>):
              Array.from({length:5},(_,i)=><button className={sampleIndex===i?'active':''} key={i} title={'示例画面 '+(i+1)} onClick={()=>setSampleIndex(i)}><Artwork variant={i+2}/></button>)}</div><span>{generatedImages.length?'Anima 生成历史':'示例素材'}</span></div>
        </section>

        {showPrompt&&<section className="is-panel is-prompt-panel">
          <div className="is-prompt-head"><div><Sparkles size={17}/><strong>{needsImage?'图像编辑指令':'画面描述'}</strong></div><span>从 Graph / 文本编码节点暴露</span></div>
          <textarea aria-label="创作指令" value={String(getValue('prompt')||'')} onChange={e=>updateField('prompt',e.target.value)} placeholder={needsImage?'描述要修改的内容，例如：保留人物身份，将衣服替换为第二张参考图中的外套，并保持背景一致':'描述想生成的画面、主体、光影、构图与风格……'} rows={3}/>
          {showField('negativePrompt')&&<div className="is-negative-prompt"><label htmlFor="studio-negative">排除内容 · Negative prompt</label><textarea id="studio-negative" aria-label="排除内容" rows={2} value={String(getValue('negativePrompt')||'')} onChange={e=>updateField('negativePrompt',e.target.value)} placeholder="排除不想出现的元素（实际支持程度由模型适配器决定）"/></div>}
          <div className="is-prompt-footer"><span><CheckCircle2 size={14}/> 参数修改同步写入当前工作流</span><div className="is-generation-actions"><span aria-live="polite">{runState==='queued'?'任务排队中':runState==='running'?'正在生成图片':runState==='submitting'?'正在提交任务':''}</span>
            {activeJobId&&<button className="is-cancel-generation" onClick={()=>void requestCancel()} type="button">取消任务</button>}
            <button className="is-generate-button" onClick={()=>void requestRun()} disabled={Boolean(activeJobId)||runState==='submitting'}><Zap size={16}/>{activeJobId?'生成中':runState==='submitting'?'提交中':needsImage?'开始编辑':'开始生成'}<ArrowUpRight size={15}/></button></div></div>
        </section>}
        {!showPrompt&&<section className="is-panel is-prompt-disabled">工作流未暴露文本编码节点的 Prompt 参数。你可以在「节点工作流」视图中开放它。</section>}
      </div>

      <aside className="is-column is-settings-column">
        <section className="is-panel is-params-panel">
          <SmallLabel extra={<button className="is-subtle-link" onClick={()=>setView('graph')}><Workflow size={14}/>编辑工作流</button>}>参数控制</SmallLabel>
          <p className="is-panel-explanation">只展示当前工作流显式开放的参数，不复制一套配置。</p>
          {exposedAdvanced.length>0?<div className="is-advanced-fields">
            <button className="is-collapse-header" aria-expanded={advanced} onClick={()=>setAdvanced(v=>!v)}><span><SlidersHorizontal size={15}/>高级参数</span><ChevronDown size={15} className={advanced?'':'rotated'}/></button>
            {advanced&&exposedAdvanced.map(({node,field},i)=>{
              const id=field.id;
              if(id==='transparent'&&!model.supportsAlpha)return <div className="is-unsupported" key={node.id+id}>当前模型未声明透明背景能力</div>;
              return <div className="is-control-block" key={node.id+'-'+id+'-'+i}>
                {id==='steps'?<Setting label={field.title}><InlineControl><input className="is-range" type="range" min="1" max="80" value={Number(node.params.steps||28)} onChange={e=>updateNode(node.id,'steps',Number(e.target.value))}/><b>{Number(node.params.steps||28)}</b></InlineControl></Setting>:
                id==='seed'?<Setting label={field.title}><InlineControl><input className="is-small-input" type="number" min="0" max="2147483647" value={Number(node.params.seed||0)} onChange={e=>updateNode(node.id,'seed',Number(e.target.value))}/><button className="is-shuffle" aria-label="随机生成种子" onClick={()=>updateNode(node.id,'seed',Math.floor(Math.random()*2147483647))}><Shuffle size={15}/></button></InlineControl></Setting>:
                id==='aspect'?<Setting label={field.title}><select className="is-select" value={String(node.params.aspect||'1:1')} onChange={e=>updateNode(node.id,'aspect',e.target.value)}>{RATIO_OPTIONS.map(r=><option key={r}>{r}</option>)}</select></Setting>:
                id==='guidance'?<Setting label={field.title}><InlineControl><input className="is-range" type="range" min="0" max="12" step=".5" value={Number(node.params.guidance||0)} onChange={e=>updateNode(node.id,'guidance',Number(e.target.value))}/><b>{Number(node.params.guidance||0).toFixed(1)}</b></InlineControl></Setting>:
                id==='transparent'?<div className="is-toggle-field"><span>透明背景 <small>RGBA 输出</small></span><label className="is-switch"><input type="checkbox" checked={node.params.transparent===true} onChange={e=>updateNode(node.id,'transparent',e.target.checked)}/><span/></label></div>:
                <div className="is-muted-hint" key={id}>Graph 参数：{field.title}</div>}
              </div>
            })}</div>:
            <div className="is-empty-param">当前工作流没有暴露高级参数</div>}
        </section>

        <section className="is-panel is-workflow-summary">
          <SmallLabel extra={<Workflow size={15}/>}>工作流摘要</SmallLabel>
          <div className="is-summary-row"><span>生成模式</span><b>{intents.find(x=>x.id===workflow.intent)?.label}</b></div>
          <div className="is-summary-row"><span>使用模型</span><b>{model.label}</b></div>
          <div className="is-summary-row"><span>图像输入</span><b>{references.length} 张</b></div>
          <div className="is-summary-row"><span>LoRA</span><b>{loras.filter(x=>x.enabled).length} 个启用</b></div>
          <div className="is-summary-row"><span>蒙版</span><b>{maskDirty?'已绘制':'无'}</b></div>
          <div className="is-summary-row"><span>执行状态</span><b className="is-muted-status">{runState==='idle'?'尚未提交任务':runState==='completed'?'已生成':runState==='queued'?'排队中':runState==='running'?'生成中':runState==='submitting'?'提交中':runState==='cancelled'?'已取消':'执行失败'}</b></div>
          <button className="is-summary-graph" onClick={()=>setView('graph')}><Workflow size={16}/> 查看完整节点图 <ArrowUpRight size={14}/></button>
        </section>

        <div className="is-performance-note"><Zap size={15}/><div><strong>轻量参数视图</strong><span>仅节点视图加载 React Flow；图像预览按最长 1600 px 缩放，避免无谓的浏览器内存占用。</span></div></div>
      </aside>
    </div>:
    <div className="is-graph-layout">
      <aside className="is-panel is-node-library">
        <SmallLabel>节点组件库</SmallLabel>
        <p className="is-panel-explanation">点击添加到画布，拖动连接节点。</p>
        <div className="is-node-palette">{kinds.map(item=><button key={item.kind} onClick={()=>addNode(item.kind)}><span className={'is-palette-icon '+item.kind}><Plus size={16}/></span><span><strong>{item.label}</strong><small>{item.description}</small></span></button>)}</div>
        <button className="is-outline-add" onClick={()=>{setWorkflow(makeWorkflow(workflow.intent,modelId));setSelectedNode('sampler')}}><RotateCcw size={14}/>恢复当前模式默认流</button>
        <div className="is-muted-hint">Graph 决定流程，参数视图仅操作暴露字段。新增孤立节点不会自动执行。</div>
      </aside>
      <section className="is-panel is-graph-stage">
        <div className="is-graph-stage-head"><div><Workflow size={16}/><strong>{workflow.name} / Node Graph</strong></div><span>{workflow.nodes.length} nodes · {workflow.edges.length} links</span></div>
        <Suspense fallback={<div className="is-loading-graph">正在加载轻量节点编辑器……</div>}>
          <GraphCanvas workflow={workflow} selectedId={selectedNode} onSelect={setSelectedNode} onMove={setNodePosition} onConnect={connectNodes} onRemove={removeNodes} onInvalidConnection={()=>notify('节点类型或连接方向不兼容','warning')}/>
        </Suspense>
        <div className="is-graph-footer"><span><MousePointer2 size={14}/> 拖拽节点 · 滚轮平移 · 连线配置</span><button onClick={()=>setView('parameters')}><SlidersHorizontal size={15}/> 返回参数视图</button></div>
      </section>
      <aside className="is-panel is-node-inspector">
        <SmallLabel extra={<Settings2 size={16}/>}>节点属性</SmallLabel>
        {selectedGraphNode?<div>
          <div className="is-inspector-selected"><strong>{nodeTitle(selectedGraphNode.kind)}</strong><code>{selectedGraphNode.id}</code></div>
          <div className="is-inspector-section-title">暴露到参数视图</div>
          <p className="is-panel-explanation">勾选后，参数视图会立即显示对应控件。</p>
          <div className="is-exposure-fields">{(Object.keys(selectedGraphNode.params) as FieldId[]).concat(selectedGraphNode.kind==='references'?['images']:selectedGraphNode.kind==='mask'?['mask']:[]).map(id=>
            <label key={id}><input type="checkbox" checked={selectedGraphNode.exposed.includes(id)} onChange={()=>setWorkflow(prev=>toggleFieldExposure(prev,selectedGraphNode.id,id))}/><span>{fieldRegistry[id].title}</span></label>)}</div>
          {selectedGraphNode.kind==='model'&&<Setting label="基础模型"><select className="is-select" value={String(selectedGraphNode.params.modelId||'qwen-image-2.1')} onChange={e=>changeModel(e.target.value)}>{studioModels.map(item=><option value={item.id} key={item.id}>{item.label}</option>)}</select></Setting>}
          {selectedGraphNode.kind==='sampler'&&<div className="is-inspector-settings"><Setting label="Steps"><input className="is-small-input" type="number" min="1" max="100" value={Number(selectedGraphNode.params.steps||28)} onChange={e=>updateNode(selectedGraphNode.id,'steps',Number(e.target.value))}/></Setting><Setting label="Seed"><input className="is-small-input" type="number" min="0" max="2147483647" value={Number(selectedGraphNode.params.seed||0)} onChange={e=>updateNode(selectedGraphNode.id,'seed',Number(e.target.value))}/></Setting></div>}
          {selectedGraphNode.kind==='lora'&&<div className="is-muted-hint">LoRA Stack 默认支持 0–N 个 LoRA。打开参数视图可批量添加、禁用和调整权重。</div>}
          <button className="is-danger-quiet" onClick={()=>removeNodes([selectedGraphNode.id],[])}><Trash2 size={14}/> 删除此节点</button>
        </div>:
        <div className="is-inspector-empty"><MousePointer2 size={25}/><strong>请选择节点</strong><span>点击画布中的节点，编辑它暴露的参数。</span></div>}
        <div className="is-inspector-bottom"><CircleHelp size={15}/> 本地工作流编辑器，不代表当前 GPU 已加载模型。</div>
      </aside>
    </div>}

    <input type="file" ref={pickerRef} accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp" multiple hidden onChange={uploadImages}/>
    <input type="file" ref={graphImportRef} accept=".json,application/json" hidden onChange={importWorkflow}/>
  </div>;
}
