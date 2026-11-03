/** The graph owns execution structure; the parameter view only exposes fields.
 * No image data or React Flow objects live in this serializable document.
 */
export type StudioIntent = 'create' | 'reference' | 'inpaint';
export type NodeKind = 'model' | 'prompt' | 'references' | 'mask' | 'lora' | 'sampler' | 'vae' | 'output';
export type FieldId =
  | 'modelId' | 'checkpoint' | 'prompt' | 'negativePrompt' | 'images' | 'mask'
  | 'loras' | 'steps' | 'seed' | 'aspect' | 'guidance' | 'transparent';
export type FieldValue = string | number | boolean | LoRAEntry[];

export interface LoRAEntry {
  id: string;
  name: string;
  strength: number;
  enabled: boolean;
}
export interface StudioNode {
  id: string;
  kind: NodeKind;
  x: number;
  y: number;
  params: Partial<Record<FieldId, FieldValue>>;
  exposed: FieldId[];
}
export interface StudioEdge {
  id: string;
  source: string;
  target: string;
}
export interface StudioWorkflow {
  format: 'lumacarve.studio.workflow.v1';
  name: string;
  intent: StudioIntent;
  nodes: StudioNode[];
  edges: StudioEdge[];
}
export interface StudioModel {
  id: string;
  label: string;
  subtitle: string;
  intents: readonly StudioIntent[];
  maxReferences: number;
  supportsMask: boolean;
  supportsAlpha: boolean;
  status: string;
}
export interface StudioField {
  id: FieldId;
  title: string;
  group: string;
  placement: 'primary' | 'advanced';
  widget: 'textarea' | 'text' | 'number' | 'select' | 'image-list' | 'mask' | 'lora-list' | 'switch' | 'range';
}
export const studioModels: readonly StudioModel[] = [
  { id: 'anima-base-1', label: 'Anima Base 1.0', subtitle: '本地 CUDA 文字生成 · 首个适配器', intents: ['create'], maxReferences: 0, supportsMask: false, supportsAlpha: false, status: '需安装权重后启用' },
  { id: 'qwen-image-2.1', label: 'Qwen-Image-2.1', subtitle: '统一生成与编辑 · 7B', intents: ['create','reference','inpaint'], maxReferences: 10, supportsMask: true, supportsAlpha: true, status: '适配规划中' },
  { id: 'moss-image', label: 'MOSS-Image', subtitle: '模型适配计划', intents: ['create'], maxReferences: 0, supportsMask: false, supportsAlpha: false, status: '适配规划中' },
  { id: 'krea-2-raw', label: 'Krea 2 RAW', subtitle: '模型适配计划', intents: ['create'], maxReferences: 0, supportsMask: false, supportsAlpha: false, status: '适配规划中' },
];
export function getStudioModel(id: string): StudioModel {
  return studioModels.find(model => model.id === id) || studioModels[0];
}
export const fieldRegistry: Record<FieldId, StudioField> = {
  modelId: { id: 'modelId', title: '基础模型', group: '模型', placement: 'primary', widget: 'select' },
  checkpoint: { id: 'checkpoint', title: '模型快照', group: '模型', placement: 'primary', widget: 'select' },
  prompt: { id: 'prompt', title: '创作指令', group: '创作指令', placement: 'primary', widget: 'textarea' },
  negativePrompt: { id: 'negativePrompt', title: '排除内容', group: '创作指令', placement: 'primary', widget: 'textarea' },
  images: { id: 'images', title: '参考图', group: '输入素材', placement: 'primary', widget: 'image-list' },
  mask: { id: 'mask', title: '局部重绘蒙版', group: '输入素材', placement: 'primary', widget: 'mask' },
  loras: { id: 'loras', title: 'LoRA 堆栈', group: 'LoRA', placement: 'primary', widget: 'lora-list' },
  steps: { id: 'steps', title: '采样步数', group: '生成参数', placement: 'advanced', widget: 'range' },
  seed: { id: 'seed', title: '随机种子', group: '生成参数', placement: 'advanced', widget: 'number' },
  aspect: { id: 'aspect', title: '画幅比例', group: '画面', placement: 'advanced', widget: 'select' },
  guidance: { id: 'guidance', title: '引导强度', group: '生成参数', placement: 'advanced', widget: 'range' },
  transparent: { id: 'transparent', title: '透明背景', group: '画面', placement: 'advanced', widget: 'switch' },
};
export const kinds: ReadonlyArray<{ kind: NodeKind; label: string; description: string }> = [
  { kind: 'model', label: '模型加载', description: '基础模型单实例' },
  { kind: 'prompt', label: '文本编码', description: '提示词与条件' },
  { kind: 'references', label: '参考图输入', description: '多图参考' },
  { kind: 'mask', label: '蒙版输入', description: '局部编辑' },
  { kind: 'lora', label: 'LoRA Stack', description: '0—N 个 LoRA' },
  { kind: 'sampler', label: '扩散采样', description: '采样器与随机种子' },
  { kind: 'vae', label: 'VAE 解码', description: '潜空间转换' },
  { kind: 'output', label: '输出图片', description: 'PNG / RGBA' },
];
export function nodeTitle(kind: NodeKind): string {
  return kinds.find(k => k.kind === kind)?.label || kind;
}

function makeNode(kind: NodeKind, id: string, x: number, y: number, modelId: string): StudioNode {
  const common = { id, kind, x, y };
  switch (kind) {
    case 'model': return { ...common, params: { modelId, checkpoint: '' }, exposed: ['modelId', 'checkpoint'] };
    case 'prompt': return { ...common, params: { prompt: '', negativePrompt: '' }, exposed: ['prompt','negativePrompt'] };
    case 'references': return { ...common, params: {}, exposed: ['images'] };
    case 'mask': return { ...common, params: {}, exposed: ['mask'] };
    case 'lora': return { ...common, params: { loras: [] }, exposed: ['loras'] };
    case 'sampler': return { ...common, params: { steps: 28, seed: 8492014, aspect: '1:1', guidance: 4 }, exposed: ['steps','seed','aspect','guidance'] };
    case 'vae': return { ...common, params: {}, exposed: [] };
    case 'output': return { ...common, params: { transparent: false }, exposed: modelId === 'anima-base-1' ? [] : ['transparent'] };
  }
}
function edge(source: string, target: string): StudioEdge {
  return { id: 'edge-' + source + '-' + target, source, target };
}
export function makeWorkflow(intent: StudioIntent = 'create', modelId = 'anima-base-1'): StudioWorkflow {
  const nodes: StudioNode[] = [
    makeNode('model','model',20,140,modelId),
    makeNode('lora','lora',240,140,modelId),
    makeNode('prompt','prompt',20,380,modelId),
    makeNode('sampler','sampler',490,140,modelId),
    makeNode('vae','vae',745,140,modelId),
    makeNode('output','output',995,140,modelId),
  ];
  const edges = [
    edge('model','lora'), edge('lora','sampler'), edge('prompt','sampler'),
    edge('sampler','vae'), edge('vae','output'),
  ];
  if (intent !== 'create') {
    nodes.push(makeNode('references','references',245,380,modelId));
    edges.push(edge('references','sampler'));
  }
  if (intent === 'inpaint') {
    nodes.push(makeNode('mask','mask',470,380,modelId));
    edges.push(edge('mask','sampler'));
  }
  const title = intent === 'create' ? '文字生成' : intent === 'reference' ? '参考图创作' : '局部编辑';
  return { format: 'lumacarve.studio.workflow.v1', name: title, intent, nodes, edges };
}
export function getModelId(workflow: StudioWorkflow): string {
  const value = workflow.nodes.find(n => n.kind === 'model')?.params.modelId;
  return typeof value === 'string' ? value : 'anima-base-1';
}
export function getField(workflow: StudioWorkflow, id: FieldId): {node: StudioNode; value: FieldValue | undefined} | undefined {
  const node = workflow.nodes.find(n => n.exposed.includes(id));
  return node ? { node, value: node.params[id] } : undefined;
}
export function visibleFields(workflow: StudioWorkflow, placement: 'primary'|'advanced'): Array<{node:StudioNode; field:StudioField}> {
  return workflow.nodes.flatMap(node => node.exposed.filter(id => fieldRegistry[id].placement === placement).map(id => ({node, field: fieldRegistry[id]})));
}
export function updateNodeValue(workflow: StudioWorkflow, nodeId: string, field: FieldId, value: FieldValue): StudioWorkflow {
  return { ...workflow, nodes: workflow.nodes.map(node => node.id === nodeId ? { ...node, params: {...node.params, [field]: value} } : node) };
}
export function toggleFieldExposure(workflow: StudioWorkflow, nodeId: string, field: FieldId): StudioWorkflow {
  return { ...workflow, nodes: workflow.nodes.map(node => {
    if (node.id !== nodeId || !(field in node.params) && field !== 'mask' && field !== 'images') return node;
    return {...node, exposed: node.exposed.includes(field) ? node.exposed.filter(x=>x!==field) : [...node.exposed,field]};
  }) };
}
export function appendGraphNode(workflow: StudioWorkflow, kind: NodeKind): StudioWorkflow {
  const id = kind + '-' + Date.now().toString(36) + '-' + Math.floor(Math.random()*10000).toString(36);
  const count = workflow.nodes.length;
  const x = 150 + (count % 4) * 230;
  const y = 580 + Math.floor(count / 4) * 140;
  return {...workflow,nodes:[...workflow.nodes,makeNode(kind,id,x,y,getModelId(workflow))]};
}
export function removeGraphNode(workflow: StudioWorkflow, id: string): StudioWorkflow {
  return {...workflow,nodes:workflow.nodes.filter(n=>n.id!==id),edges:workflow.edges.filter(e=>e.source!==id&&e.target!==id)};
}
const allowedTargets: Partial<Record<NodeKind,readonly NodeKind[]>> = {
  model: ['lora','sampler'],
  prompt: ['sampler'],
  references: ['sampler'],
  mask: ['sampler'],
  lora: ['lora','sampler'],
  sampler: ['vae'],
  vae: ['output'],
};
export function canConnect(workflow: StudioWorkflow, source: string, target: string): boolean {
  const a=workflow.nodes.find(n=>n.id===source);
  const b=workflow.nodes.find(n=>n.id===target);
  if(!a||!b||a.id===b.id||workflow.edges.some(e=>e.source===source&&e.target===target)) return false;
  if(!allowedTargets[a.kind]?.includes(b.kind)) return false;
  const children=new Map<string,string[]>();
  for (const edge of workflow.edges) children.set(edge.source,[...(children.get(edge.source)||[]),edge.target]);
  const stack=[target];const visited=new Set<string>();
  while(stack.length){const at=stack.pop()!;if(at===source)return false;if(visited.has(at))continue;visited.add(at);stack.push(...(children.get(at)||[]));}
  return true;
}
export function connectGraphNodes(workflow: StudioWorkflow, source: string, target: string): StudioWorkflow {
  return canConnect(workflow,source,target) ? {...workflow,edges:[...workflow.edges,edge(source,target)]} : workflow;
}
export function validateImport(data: unknown): StudioWorkflow {
  if (!data || typeof data !== 'object') throw new Error('文件不是工作流对象');
  const candidate=data as Partial<StudioWorkflow>;
  if(candidate.format!=='lumacarve.studio.workflow.v1'|| !Array.isArray(candidate.nodes)||!Array.isArray(candidate.edges)) throw new Error('不支持的工作流格式');
  if(candidate.nodes.length>200||candidate.edges.length>500) throw new Error('工作流规模超过编辑器限制');
  const validKinds = new Set<NodeKind>(kinds.map(k=>k.kind));
  const ids=new Set<string>();
  const nodes=candidate.nodes.map(n=>{
    if(!n||typeof n.id!=='string'||n.id.length>128||ids.has(n.id)||!validKinds.has(n.kind)||!Number.isFinite(n.x)||!Number.isFinite(n.y))throw new Error('节点存在不合法字段或重复 ID');
    if(!n.params||typeof n.params!=='object'||!Array.isArray(n.exposed))throw new Error('节点参数不合法');
    const validFields=Object.keys(fieldRegistry) as FieldId[];
    const params: Partial<Record<FieldId,FieldValue>>={};
    for(const k of validFields){
      const v=n.params[k];
      if(typeof v==='string'&&v.length<20000 || typeof v==='number'&&Number.isFinite(v) || typeof v==='boolean')params[k]=v;
      else if(k==='loras'&&Array.isArray(v)&&v.length<=1000&&v.every(item=>item&&typeof item.id==='string'&&typeof item.name==='string'&&item.name.length<300&&typeof item.strength==='number'&&Number.isFinite(item.strength)&&typeof item.enabled==='boolean'))params.loras=v;
    }
    ids.add(n.id);
    return { id:n.id,kind:n.kind,x:Math.max(-10000,Math.min(10000,n.x)),y:Math.max(-10000,Math.min(10000,n.y)),params,exposed:n.exposed.filter((f):f is FieldId=>typeof f==='string' && validFields.includes(f)).slice(0,30) } as StudioNode;
  });
  const edges=candidate.edges.map(e=>{
    if(!e||typeof e.source!=='string'||typeof e.target!=='string'||!ids.has(e.source)||!ids.has(e.target)||e.source===e.target)throw new Error('连接包含缺失的节点');
    return edge(e.source,e.target);
  });
  const intent:StudioIntent= candidate.intent==='reference'||candidate.intent==='inpaint'?candidate.intent:'create';
  const name=typeof candidate.name==='string'?candidate.name.slice(0,100):'导入工作流';
  const workflow:StudioWorkflow={format:'lumacarve.studio.workflow.v1',name,intent,nodes,edges:[]};
  for(const item of edges){if(!canConnect(workflow,item.source,item.target))throw new Error('存在不允许的连接或循环');workflow.edges.push(item);}
  return workflow;
}
