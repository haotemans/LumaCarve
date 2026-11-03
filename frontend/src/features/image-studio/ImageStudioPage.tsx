import { useEffect, useRef, useState } from 'react';
import type { ChangeEvent, PointerEvent as ReactPointerEvent } from 'react';
import {
  ArrowDownToLine, ArrowLeftRight, ArrowUpRight, Brush, Check, CheckCircle2,
  ChevronDown, CircleHelp, Copy, Download, Eye, FileImage, FolderOpen,
  Image as ImageIcon, ImagePlus, Layers3, Maximize, MoreHorizontal,
  MousePointer2, PenTool, Plus, RotateCcw, Settings2, Shuffle, SlidersHorizontal,
  Sparkles, Trash2, Upload, Workflow, X, Zap,
} from 'lucide-react';
import type { SharedProps } from '../../App';
import {
  getField, getModelId, getStudioModel, makeWorkflow, studioModels,
  updateNodeValue, validateImport, visibleFields,
} from './workflow';
import type { FieldId, FieldValue, LoRAEntry, StudioIntent, StudioWorkflow } from './workflow';
import {
  cancelImageJob, getImageJob, outputFromJob, submitImageJob,
} from './api';
import type { GeneratedImage, JobState } from './api';
import RuntimeStatusPanel from './RuntimeStatusPanel';

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
  const [advanced,setAdvanced]=useState(true);
  const [references,setReferences]=useState<RefImage[]>([]);
  const [selectedRef,setSelectedRef]=useState<string|null>(null);
  const [brushSize,setBrushSize]=useState(38);
  const [erase,setErase]=useState(false);
  const [maskDirty,setMaskDirty]=useState(false);
  const [drawing,setDrawing]=useState(false);
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
    notify('已导出参数预设 JSON（不包含参考图和蒙版）','success');
  }
  async function importWorkflow(event:ChangeEvent<HTMLInputElement>){
    const file=event.target.files?.[0];event.target.value='';
    if(!file)return;
    if(file.size>2*1024*1024){notify('工作流 JSON 超过 2MB 安全限制','warning');return;}
    try{
      const data=validateImport(JSON.parse(await file.text()));
      setWorkflow(data);
      notify('已导入参数预设；参考图片需重新选择','success');
    }catch(error){notify('导入失败：'+(error instanceof Error?error.message:'文件格式错误'),'warning');}
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
  const modelOutputs=generatedImages.filter(item=>item.modelId===modelId);
  const visibleOutput=modelOutputs.find(item=>item.outputId===selectedOutputId)||modelOutputs.at(-1);
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
        <span className="is-workspace-tag"><SlidersHorizontal size={14}/> 轻量参数工作台</span>
        <button className="is-action-icon" title="导入参数预设 JSON" aria-label="导入参数预设" onClick={()=>graphImportRef.current?.click()}><FolderOpen size={17}/></button>
        <button className="is-action-icon" title="导出参数预设 JSON" aria-label="导出参数预设" onClick={exportWorkflow}><Download size={17}/></button>
        <button className="is-action-icon" title="恢复默认生成参数" aria-label="恢复默认生成参数" onClick={()=>{
          setWorkflow(makeWorkflow(workflow.intent,modelId));
          setCompare(false);
          notify('已恢复当前模型的默认参数','info');
        }}><RotateCcw size={17}/></button>
      </div>
    </div>

    <div className="is-mode-bar">
      <div className="is-mode-tabs" role="group" aria-label="创作类型">
        {intents.map(intent=><button key={intent.id} title={intent.help} disabled={!model.intents.includes(intent.id)} className={workflow.intent===intent.id?'active':''} onClick={()=>changeIntent(intent.id)}>
          {intent.id==='create'?<Sparkles size={15}/>:intent.id==='reference'?<ImageIcon size={15}/>:<Brush size={15}/>}
          {intent.label}
        </button>)}
      </div>
      <div className="is-workflow-context"><span>参数直达</span><span className="is-separator">/</span><span>生成由本地服务执行</span><span className="is-separator">/</span><span className="is-context-status">GPU 指标按需显示</span></div>
    </div>

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
          <div className="is-canvas-top"><div className="is-preview-title"><span className="is-preview-dot"/><strong>{previewSource?'原图预览':'创作画布'}</strong><small>{previewSource?'REFERENCE IMAGE':visibleOutput?'GENERATED PNG':'EMPTY CANVAS'}</small></div><div className="is-canvas-actions">
            {previewSource&&visibleOutput&&<button className={'is-icon-label'+(compare?' active':'')} onClick={()=>setCompare(v=>!v)} title="查看已生成图片对照"><ArrowLeftRight size={14}/>对比</button>}
            <span className="is-canvas-size">{activeRef?activeRef.width+' × '+activeRef.height:visibleOutput?visibleOutput.width+' × '+visibleOutput.height:String(getValue('aspect')||'1:1')}</span>
          </div></div>
          <div className="is-canvas-backdrop">
            <div className="is-preview-frame" style={{aspectRatio:previewRatio}}>
              {previewSource?<img className="is-main-image" src={activeRef!.url} alt={activeRef!.name}/>:
              visibleOutput?<img className="is-main-image" src={visibleOutput.imageUrl} alt="Anima 实际生成图片"/>:
              <div className="is-empty-canvas">
                <span className="is-empty-canvas-symbol"><ImageIcon size={34} strokeWidth={1.35}/></span>
                <strong>{activeJobId?'正在生成图像':'开始你的第一张作品'}</strong>
                <small>{activeJobId?'任务状态将自动更新，结果会在此展示':'输入创作指令并点击「开始生成」'}</small>
              </div>}
              {previewSource&&compare&&visibleOutput&&<div className="is-compare-placeholder"><img className="is-main-image" src={visibleOutput.imageUrl} alt="已生成结果对比"/><span>生成结果</span></div>}
              {masked&&previewSource&&<canvas key={activeRef?.id+'-'+workflow.intent} ref={canvasRef} className={'is-mask-canvas'+(drawing?' drawing':'')} style={{opacity:.62}} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={pointerUp} aria-label="局部编辑蒙版绘制画布"/>}
              <span className="is-preview-caption">{previewSource?(masked?'蒙版编辑 · 本地画布':'参考原图 · 本地预览'):visibleOutput?'实际生成结果 · Seed '+visibleOutput.seed:'暂无生成结果'}</span>
            </div>
          </div>
          <div className="is-canvas-bottom">
            {modelOutputs.length>0?
              <div className="is-canvas-filmstrip">{modelOutputs.map(item=><button key={item.outputId} className={item.outputId===visibleOutput?.outputId?'active':''} onClick={()=>setSelectedOutputId(item.outputId)} title={'实际生成图片 · Seed '+item.seed}><img src={item.imageUrl} alt={'生成图像 '+item.outputId}/></button>)}</div>:
              <span className="is-canvas-no-history">暂无生成记录</span>}
            <span>{modelOutputs.length?modelOutputs.length+' 张真实生成结果':'输出将保存在本地工作区'}</span>
          </div>
        </section>

        {showPrompt&&<section className="is-panel is-prompt-panel">
          <div className="is-prompt-head"><div><Sparkles size={17}/><strong>{needsImage?'图像编辑指令':'画面描述'}</strong></div><span>修改后自动用于下次生成</span></div>
          <textarea aria-label="创作指令" value={String(getValue('prompt')||'')} onChange={e=>updateField('prompt',e.target.value)} placeholder={needsImage?'描述要修改的内容，例如：保留人物身份，将衣服替换为第二张参考图中的外套，并保持背景一致':'描述想生成的画面、主体、光影、构图与风格……'} rows={3}/>
          {showField('negativePrompt')&&<div className="is-negative-prompt"><label htmlFor="studio-negative">排除内容 · Negative prompt</label><textarea id="studio-negative" aria-label="排除内容" rows={2} value={String(getValue('negativePrompt')||'')} onChange={e=>updateField('negativePrompt',e.target.value)} placeholder="排除不想出现的元素（实际支持程度由模型适配器决定）"/></div>}
          <div className="is-prompt-footer"><span><CheckCircle2 size={14}/> 参数已同步至生成配置</span><div className="is-generation-actions"><span aria-live="polite">{runState==='queued'?'任务排队中':runState==='running'?'正在生成图片':runState==='submitting'?'正在提交任务':''}</span>
            {activeJobId&&<button className="is-cancel-generation" onClick={()=>void requestCancel()} type="button">取消任务</button>}
            <button className="is-generate-button" onClick={()=>void requestRun()} disabled={Boolean(activeJobId)||runState==='submitting'}><Zap size={16}/>{activeJobId?'生成中':runState==='submitting'?'提交中':needsImage?'开始编辑':'开始生成'}<ArrowUpRight size={15}/></button></div></div>
        </section>}
        {!showPrompt&&<section className="is-panel is-prompt-disabled">当前导入预设未包含可编辑的创作指令，请换用默认生成配置。</section>}
      </div>

      <aside className="is-column is-settings-column">
        <section className="is-panel is-params-panel">
          <SmallLabel extra={<span className="is-soft-tag">常用设置</span>}>生成参数</SmallLabel>
          <p className="is-panel-explanation">调整参数后立即用于下一次生成。使用预设也不会创建多份配置。</p>
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
                <div className="is-muted-hint" key={id}>当前预设字段：{field.title}</div>}
              </div>
            })}</div>:
            <div className="is-empty-param">当前工作流没有暴露高级参数</div>}
        </section>

        <RuntimeStatusPanel/>

        <section className="is-panel is-workflow-summary">
          <SmallLabel extra={<Workflow size={15}/>}>工作流摘要</SmallLabel>
          <div className="is-summary-row"><span>生成模式</span><b>{intents.find(x=>x.id===workflow.intent)?.label}</b></div>
          <div className="is-summary-row"><span>使用模型</span><b>{model.label}</b></div>
          <div className="is-summary-row"><span>图像输入</span><b>{references.length} 张</b></div>
          <div className="is-summary-row"><span>LoRA</span><b>{loras.filter(x=>x.enabled).length} 个启用</b></div>
          <div className="is-summary-row"><span>蒙版</span><b>{maskDirty?'已绘制':'无'}</b></div>
          <div className="is-summary-row"><span>执行状态</span><b className="is-muted-status">{runState==='idle'?'尚未提交任务':runState==='completed'?'已生成':runState==='queued'?'排队中':runState==='running'?'生成中':runState==='submitting'?'提交中':runState==='cancelled'?'已取消':'执行失败'}</b></div>
        </section>

        <div className="is-performance-note"><Zap size={15}/><div><strong>轻量创作界面</strong><span>不加载可视化节点编辑器或 GPU 监控；参考图预览限制为最长 1600 px。</span></div></div>
      </aside>
    </div>

    <input type="file" ref={pickerRef} accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp" multiple hidden onChange={uploadImages}/>
    <input type="file" ref={graphImportRef} accept=".json,application/json" hidden onChange={importWorkflow}/>
  </div>;
}
