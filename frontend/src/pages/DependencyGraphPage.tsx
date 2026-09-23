import { useState, useCallback } from 'react';
import { Search, Filter, Maximize } from 'lucide-react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  useNodesState,
  useEdgesState,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { api } from '../services/api';
import type { DependencyAnalysis, ComponentNode } from '../types/api';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorAlert } from '../components/ErrorAlert';
import { EmptyState } from '../components/EmptyState';
import { shortId } from '../utils/helpers';

const TYPE_COLORS: Record<string, string> = {
  module: 'var(--color-sg-node-module)',
  class: 'var(--color-sg-node-class)',
  function: 'var(--color-sg-node-function)',
  method: 'var(--color-sg-node-method)',
};

function getNodeColor(type: string) {
  return TYPE_COLORS[type] || 'var(--color-sg-text-muted)';
}

function getEdgeStyle(type: string) {
  switch (type) {
    case 'imports':
      return { stroke: 'var(--color-sg-node-module)', strokeWidth: 1.5, strokeDasharray: '4 4' };
    case 'calls':
      return { stroke: 'var(--color-sg-node-function)', strokeWidth: 1.5 };
    case 'contains':
      return { stroke: 'var(--color-sg-text-muted)', strokeWidth: 1, strokeDasharray: '2 2' };
    default:
      return { stroke: 'var(--color-sg-border)', strokeWidth: 1 };
  }
}

export default function DependencyGraphPage() {
  const [path, setPath] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<DependencyAnalysis | null>(null);
  const [selectedNodeData, setSelectedNodeData] = useState<ComponentNode | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const handleAnalyze = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!path.trim()) return;

    setIsLoading(true);
    setError(null);
    setData(null);
    setSelectedNodeData(null);
    
    try {
      const result = await api.analyzeDependencies(path.trim());
      setData(result);

      const ySpacing = 120;
      const xSpacing = 260;

      const typeGroups: Record<string, ComponentNode[]> = {
        module: [],
        class: [],
        function: [],
        method: [],
      };

      result.nodes.forEach(n => {
        if (typeGroups[n.component_type]) {
          typeGroups[n.component_type].push(n);
        } else {
          typeGroups['module'].push(n);
        }
      });

      const newNodes: Node[] = [];
      let yIndex = 0;
      for (const type of ['module', 'class', 'function', 'method']) {
        const group = typeGroups[type];
        if (group.length > 0) {
          group.forEach((node, xIndex) => {
            const color = getNodeColor(node.component_type);
            newNodes.push({
              id: node.component_id,
              position: { x: xIndex * xSpacing, y: yIndex * ySpacing },
              data: { 
                label: shortId(node.name),
                fullData: node 
              },
              style: {
                background: 'var(--color-sg-panel)',
                border: '1px solid var(--color-sg-border)',
                borderLeft: `4px solid ${color}`,
                borderRadius: '4px',
                padding: '8px 12px',
                fontSize: '12px',
                fontWeight: 500,
                width: 200,
                color: 'var(--color-sg-text)',
                fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
              },
            });
          });
          yIndex++;
        }
      }

      const newEdges: Edge[] = result.edges.map(e => ({
        id: `${e.source}-${e.target}-${e.dependency_type}`,
        source: e.source,
        target: e.target,
        animated: e.dependency_type === 'calls',
        style: getEdgeStyle(e.dependency_type),
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 15,
          height: 15,
          color: getEdgeStyle(e.dependency_type).stroke,
        },
      }));

      setNodes(newNodes);
      setEdges(newEdges);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    if (node.data && node.data.fullData) {
      setSelectedNodeData(node.data.fullData as ComponentNode);
    }
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNodeData(null);
  }, []);

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] gap-4 w-full">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between flex-shrink-0">
        <div>
          <h1 className="sg-heading text-xl mb-1">Dependency Graph</h1>
          <p className="text-sm text-[#8b8d98]">Interactive visualization of repository structure.</p>
        </div>

        <form onSubmit={handleAnalyze} className="flex gap-2 w-full sm:w-auto">
          <input 
            type="text" 
            value={path} 
            onChange={(e) => setPath(e.target.value)}
            placeholder="Repository path..."
            className="sg-input w-full sm:w-64" 
          />
          <button type="submit" disabled={isLoading || !path.trim()} className="sg-btn sg-btn-primary">
            <Search size={14} /> Analyze
          </button>
        </form>
      </div>

      {error && <ErrorAlert message={error} onRetry={handleAnalyze} />}

      {/* Main Graph Area */}
      <div className="flex-1 flex gap-4 min-h-0">
        
        {/* Graph Viewer */}
        <div className="flex-1 sg-panel overflow-hidden relative flex flex-col">
          
          {/* Internal Toolbar */}
          {data && (
             <div className="absolute top-4 left-4 z-10 flex gap-2">
                <div className="sg-panel flex items-center px-3 py-1.5 text-xs text-[#e4e4e7] gap-2 shadow-sm bg-[#1a1d24]/90 backdrop-blur">
                  <Filter size={12} className="text-[#8b8d98]" />
                  <span>{nodes.length} Nodes</span>
                  <span className="text-[#5c5e6a]">|</span>
                  <span>{edges.length} Edges</span>
                </div>
             </div>
          )}

          {isLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <LoadingSpinner message="Mapping dependency graph..." />
            </div>
          ) : !data ? (
            <div className="flex-1 flex items-center justify-center">
              <EmptyState title="No graph loaded" description="Analyze a repository to view its dependency structure." />
            </div>
          ) : (
            <div className="flex-1 w-full h-full">
              <ReactFlow
                nodes={nodes} 
                edges={edges}
                onNodesChange={onNodesChange} 
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                onPaneClick={onPaneClick}
                fitView
                attributionPosition="bottom-right"
              >
                <Background color="var(--color-sg-border)" gap={24} size={1} />
                <Controls showInteractive={false} />
                <MiniMap
                  nodeStrokeColor={(n) => {
                    const dataNode = data.nodes.find(d => d.component_id === n.id);
                    return dataNode ? getNodeColor(dataNode.component_type) : '#333';
                  }}
                  nodeColor="var(--color-sg-panel)"
                  nodeBorderRadius={4}
                  maskColor="rgba(17, 19, 24, 0.7)"
                  style={{ backgroundColor: 'var(--color-sg-elevated)' }}
                />
              </ReactFlow>
            </div>
          )}
        </div>

        {/* Right Inspector Panel */}
        {data && (
          <div className="w-80 sg-panel flex flex-col overflow-hidden flex-shrink-0">
            <div className="p-4 border-b border-[#2a2e38] bg-[#22262e]">
              <h3 className="font-semibold text-[#e4e4e7] text-sm">Inspector</h3>
            </div>
            
            <div className="flex-1 overflow-y-auto p-4">
              {selectedNodeData ? (
                <div className="space-y-6">
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[#5c5e6a] tracking-wider mb-1">Component</div>
                    <div className="font-mono text-sm text-[#3b82f6] break-all">{selectedNodeData.component_id}</div>
                  </div>
                  
                  <div>
                    <div className="text-[10px] uppercase font-bold text-[#5c5e6a] tracking-wider mb-1">Type</div>
                    <div className="flex items-center gap-2">
                       <span className="w-2 h-2 rounded-full" style={{ backgroundColor: getNodeColor(selectedNodeData.component_type) }} />
                       <span className="capitalize text-[#e4e4e7] text-sm">{selectedNodeData.component_type}</span>
                    </div>
                  </div>

                  {selectedNodeData.file_path && (
                    <div>
                      <div className="text-[10px] uppercase font-bold text-[#5c5e6a] tracking-wider mb-1">Location</div>
                      <div className="font-mono text-xs text-[#8b8d98] break-all">
                        {selectedNodeData.file_path}
                        {selectedNodeData.line_number && `:${selectedNodeData.line_number}`}
                      </div>
                    </div>
                  )}

                  <div className="pt-4 border-t border-[#2a2e38]">
                    <div className="text-[10px] uppercase font-bold text-[#5c5e6a] tracking-wider mb-2">Relationships</div>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-[#8b8d98]">Inbound (Dependents)</span>
                        <span className="text-[#e4e4e7] font-mono">{edges.filter(e => e.target === selectedNodeData.component_id).length}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-[#8b8d98]">Outbound (Dependencies)</span>
                        <span className="text-[#e4e4e7] font-mono">{edges.filter(e => e.source === selectedNodeData.component_id).length}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center text-[#5c5e6a]">
                  <Maximize size={24} className="mb-2 opacity-50" />
                  <p className="text-sm">Select a node in the graph to inspect its details.</p>
                </div>
              )}
            </div>

            {/* Legend */}
            <div className="p-4 border-t border-[#2a2e38] bg-[#1a1d24]">
              <div className="text-[10px] uppercase font-bold text-[#5c5e6a] tracking-wider mb-3">Legend</div>
              <div className="grid grid-cols-2 gap-2 text-xs text-[#8b8d98]">
                <div className="flex items-center gap-2"><div className="w-2 h-2" style={{ backgroundColor: 'var(--color-sg-node-module)' }} />Module</div>
                <div className="flex items-center gap-2"><div className="w-2 h-2" style={{ backgroundColor: 'var(--color-sg-node-class)' }} />Class</div>
                <div className="flex items-center gap-2"><div className="w-2 h-2" style={{ backgroundColor: 'var(--color-sg-node-function)' }} />Function</div>
                <div className="flex items-center gap-2"><div className="w-2 h-2" style={{ backgroundColor: 'var(--color-sg-node-method)' }} />Method</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
