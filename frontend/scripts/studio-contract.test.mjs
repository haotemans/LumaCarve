import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { readFileSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { createServer } from 'vite';

let server;
let workflow;
let api;
before(async () => {
  server = await createServer({ server:{ middlewareMode:true }, appType:'custom', logLevel:'silent' });
  workflow = await server.ssrLoadModule('/src/features/image-studio/workflow.ts');
  api = await server.ssrLoadModule('/src/features/image-studio/api.ts');
});
after(async () => { if(server) await server.close(); });

test('default Anima generation remains exact backend workflow v1 format', () => {
  const graph = workflow.makeWorkflow('create','anima-base-1');
  assert.equal(graph.format,'lumacarve.studio.workflow.v1');
  assert.equal(graph.intent,'create');
  assert.equal(workflow.getModelId(graph),'anima-base-1');
  assert.deepEqual(graph.nodes.map(n=>n.kind),['model','lora','prompt','sampler','vae','output']);
  assert.deepEqual(graph.edges.map(e=>[e.source,e.target]),[
    ['model','lora'],['lora','sampler'],['prompt','sampler'],['sampler','vae'],['vae','output'],
  ]);
  assert.deepEqual(workflow.validateImport(JSON.parse(JSON.stringify(graph))),graph);
});

test('Vue parameter edits write into the same backend Graph JSON', () => {
  const base=workflow.makeWorkflow('create','anima-base-1');
  const prompt=base.nodes.find(n=>n.kind==='prompt');
  const sampler=base.nodes.find(n=>n.kind==='sampler');
  const lora=base.nodes.find(n=>n.kind==='lora');
  let graph=workflow.updateNodeValue(base,prompt.id,'prompt','original sample');
  graph=workflow.updateNodeValue(graph,sampler.id,'steps',36);
  graph=workflow.updateNodeValue(graph,lora.id,'loras',[
    {id:'x',name:'style-alpha',strength:0.85,enabled:true},
    {id:'y',name:'style-beta',strength:1.2,enabled:false},
  ]);
  const roundtrip=workflow.validateImport(JSON.parse(JSON.stringify(graph)));
  assert.equal(roundtrip.nodes.find(n=>n.kind==='prompt').params.prompt,'original sample');
  assert.equal(roundtrip.nodes.find(n=>n.kind==='sampler').params.steps,36);
  assert.equal(roundtrip.nodes.find(n=>n.kind==='lora').params.loras.length,2);
});

test('submit action sends real job request, not an image mock', async () => {
  const original=globalThis.fetch;
  let capture;
  globalThis.fetch=async (url,options)=>{
    capture={url,options};
    return {ok:true,status:202,json:async()=>({id:'job123',state:'queued',result:null,error:null})};
  };
  try {
    const graph=workflow.makeWorkflow();
    const result=await api.submitImageJob(graph);
    assert.equal(result.state,'queued');
    assert.equal(capture.url,'http://127.0.0.1:8000/api/v1/jobs');
    const body=JSON.parse(capture.options.body);
    assert.equal(body.workflow.format,'lumacarve.studio.workflow.v1');
    assert.equal(body.priority,'interactive');
  } finally { globalThis.fetch=original; }
});

test('React runtime and TSX sources are absent after full migration', () => {
  const root=resolve('src');
  const files=[];
  function collect(dir) { for(const entry of readdirSync(dir,{withFileTypes:true})) {
    const path=join(dir,entry.name);
    if(entry.isDirectory())collect(path);else files.push(path);
  }}
  collect(root);
  assert.equal(files.filter(file=>/\.(jsx|tsx)$/.test(file)).length,0);
  const manifest=JSON.parse(readFileSync('package.json','utf8'));
  assert.equal(manifest.dependencies.react,undefined);
  assert.equal(manifest.dependencies['@xyflow/react'],undefined);
  assert.equal(typeof manifest.dependencies.vue,'string');
  assert.equal(typeof manifest.dependencies.pinia,'string');
});
