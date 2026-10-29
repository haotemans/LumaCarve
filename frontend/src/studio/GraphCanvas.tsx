import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import {
  Background, BackgroundVariant, Controls, Handle, MiniMap, Position,
  ReactFlow, useNodesState,
} from '@xyflow/react';
import type { Connection, Edge, Node, NodeProps } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import type { StudioNode, StudioWorkflow } from './workflow';
import { canConnect, nodeTitle } from './workflow';

type GraphNode = Node<{ kind: StudioNode['kind']; fieldCount: number }, 'studio'>;

const GraphBlock = memo(function GraphBlock({data, selected}: NodeProps<GraphNode>) {
  const kind = data.kind;
  return <div className={'st-graph-block st-node-'+kind+(selected?' is-selected':'')}>
    <Handle type="target" position={Position.Left} className="st-port st-port-input"/>
    <div className="st-graph-node-label">{nodeTitle(kind)}</div>
    <div className="st-graph-node-detail">{kind==='lora'?'多 LoRA 共享模型':kind==='references'?'多图片条件':kind==='mask'?'局部选区':kind==='sampler'?'采样与随机种子':kind==='output'?'输出图片':'流程组件'}</div>
    <div className="st-graph-node-foot"><span>{kind.toUpperCase()}</span><span>暴露 {data.fieldCount} 项</span></div>
    <Handle type="source" position={Position.Right} className="st-port st-port-output"/>
  </div>;
});
const nodeTypes = { studio: GraphBlock };

type Props = {
  workflow: StudioWorkflow;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onMove: (id: string, x: number, y: number) => void;
  onConnect: (source: string, target: string) => void;
  onRemove: (nodeIds: string[], edgeIds: string[]) => void;
  onInvalidConnection: () => void;
};

function convertNodes(items: StudioNode[]): GraphNode[] {
  return items.map(n=>({
    id:n.id, type:'studio', position:{x:n.x,y:n.y},
    data:{kind:n.kind,fieldCount:n.exposed.length},
  }));
}

export default function GraphCanvas({
  workflow, selectedId, onSelect, onMove, onConnect, onRemove, onInvalidConnection,
}:Props) {
  const [nodes,setNodes,onNodesChange]=useNodesState<GraphNode>(convertNodes(workflow.nodes));
  const edges:Edge[]=useMemo(()=>workflow.edges.map(e=>({
    id:e.id, source:e.source,target:e.target,type:'smoothstep',
    animated:false, style:{stroke:'#7b89c4',strokeWidth:2},
  })),[workflow.edges]);

  useEffect(()=>{setNodes(convertNodes(workflow.nodes));},[workflow.nodes,setNodes]);
  const connect=useCallback((params:Connection)=>{
    if(params.source&&params.target){
      if(canConnect(workflow,params.source,params.target))onConnect(params.source,params.target);
      else onInvalidConnection();
    }
  },[workflow,onConnect,onInvalidConnection]);
  const [ready,setReady]=useState(false);
  useEffect(()=>{setReady(true)},[]);

  return <div className="st-reactflow" aria-label="图像工作流节点编辑器">
    {ready&&<ReactFlow<GraphNode,Edge>
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodesChange={onNodesChange}
      onConnect={connect}
      onNodeClick={(_,node)=>onSelect(node.id)}
      onPaneClick={()=>onSelect(null)}
      onNodeDragStop={(_,node)=>onMove(node.id,node.position.x,node.position.y)}
      onNodesDelete={deleted=>onRemove(deleted.map(n=>n.id),[])}
      onEdgesDelete={deleted=>onRemove([],deleted.map(e=>e.id))}
      isValidConnection={connection=>canConnect(workflow,connection.source||'',connection.target||'')}
      nodesDraggable
      elementsSelectable
      nodesConnectable
      fitView
      fitViewOptions={{padding:.15}}
      minZoom={.25}
      maxZoom={1.8}
      deleteKeyCode={['Backspace','Delete']}
      panOnScroll
      selectionOnDrag
      colorMode="light"
      proOptions={{hideAttribution:true}}
    >
      <Background variant={BackgroundVariant.Dots} color="#c6cede" size={1.1} gap={22}/>
      <Controls position="bottom-left" showInteractive={false}/>
      <MiniMap position="bottom-right" pannable zoomable nodeColor={node=>
        node.id===selectedId?'#6866f5':'#bac4e1'
      } style={{background:'#ffffffd9',border:'1px solid #fff',borderRadius:'12px'}}/>
    </ReactFlow>}
  </div>;
}
