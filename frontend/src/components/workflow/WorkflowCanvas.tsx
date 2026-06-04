"use client";
import { useCallback, useRef, useState, type DragEvent } from "react";
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  addEdge,
  type Node,
  type Edge,
  type OnConnect,
  type OnInit,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { AgentNode } from "./nodes/AgentNode";
import { ToolNode } from "./nodes/ToolNode";
import { TriggerNode } from "./nodes/TriggerNode";
import { OutputNode } from "./nodes/OutputNode";
import { Toolbar } from "./Toolbar";
import type { WorkflowNode, WorkflowEdge } from "@/lib/api";

// ─── Node type registry ─────────────────────────────────────────────────────

const nodeTypes = {
  agentNode: AgentNode,
  toolNode: ToolNode,
  triggerNode: TriggerNode,
  outputNode: OutputNode,
} as const;

// ─── Type helpers ────────────────────────────────────────────────────────────

type FlowNodeType = keyof typeof nodeTypes;

function wfTypeToFlowType(wfType: WorkflowNode["type"]): FlowNodeType {
  const map: Record<WorkflowNode["type"], FlowNodeType> = {
    agent: "agentNode",
    tool: "toolNode",
    trigger: "triggerNode",
    output: "outputNode",
  };
  return map[wfType];
}

function flowTypeToWfType(flowType: string): WorkflowNode["type"] {
  const map: Record<string, WorkflowNode["type"]> = {
    agentNode: "agent",
    toolNode: "tool",
    triggerNode: "trigger",
    outputNode: "output",
  };
  return map[flowType] ?? "agent";
}

// ─── Convert between API types and React Flow types ─────────────────────────

function toFlowNode(n: WorkflowNode): Node {
  return {
    id: n.id,
    type: wfTypeToFlowType(n.type),
    position: n.position,
    data: { ...n.data, label: n.data.label ?? n.type },
  };
}

function toWorkflowNode(n: Node): WorkflowNode {
  return {
    id: n.id,
    type: flowTypeToWfType(n.type ?? "agentNode"),
    position: { x: n.position.x, y: n.position.y },
    data: n.data as Record<string, unknown>,
  };
}

function toFlowEdge(e: WorkflowEdge): Edge {
  return { id: e.id, source: e.source, target: e.target };
}

function toWorkflowEdge(e: Edge): WorkflowEdge {
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle ?? undefined,
    targetHandle: e.targetHandle ?? undefined,
  };
}

// ─── Props ───────────────────────────────────────────────────────────────────

export interface WorkflowCanvasProps {
  /** Saved nodes to initialise the canvas. */
  initialNodes?: WorkflowNode[];
  /** Saved edges to initialise the canvas. */
  initialEdges?: WorkflowEdge[];
  /** Called when the user clicks save. Returns serialisable data for the API. */
  onSave?: (nodes: WorkflowNode[], edges: WorkflowEdge[]) => void;
  /** When true, canvas is read-only (no edits, no toolbar, no save). */
  readOnly?: boolean;
  /** Called when a node is selected/deselected. Returns the node id or null. */
  onNodeSelect?: (nodeId: string | null) => void;
}

// ─── Component ───────────────────────────────────────────────────────────────

export function WorkflowCanvas({ initialNodes, initialEdges, onSave, readOnly = false, onNodeSelect }: WorkflowCanvasProps) {
  const rfInstanceRef = useRef<ReactFlowInstance | null>(null);
  const [isInitialised, setIsInitialised] = useState(false);

  const [nodes, setNodes, onNodesChange] = useNodesState(
    initialNodes?.map(toFlowNode) ?? [],
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState(
    initialEdges?.map(toFlowEdge) ?? [],
  );

  // ── Connection handler ──────────────────────────────────────────────────

  const onConnect: OnConnect = useCallback(
    (connection) => {
      setEdges((eds) => addEdge(connection, eds));
    },
    [setEdges],
  );

  // ── Drag-and-drop ───────────────────────────────────────────────────────

  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault();

      const type = event.dataTransfer.getData("application/reactflow");
      if (!type || !rfInstanceRef.current) return;

      const position = rfInstanceRef.current.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const flowType = wfTypeToFlowType(type as WorkflowNode["type"]);
      const newId = `${type}-${Date.now()}`;

      const newNode: Node = {
        id: newId,
        type: flowType,
        position,
        data: { label: type },
      };

      setNodes((nds) => nds.concat(newNode));
    },
    [setNodes],
  );

  // ── Save handler ────────────────────────────────────────────────────────

  const handleSave = useCallback(() => {
    if (!onSave) return;
    const wfNodes = nodes.map(toWorkflowNode);
    const wfEdges = edges.map(toWorkflowEdge);
    onSave(wfNodes, wfEdges);
  }, [nodes, edges, onSave]);

  // ── Node click handler ──────────────────────────────────────────────────

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      onNodeSelect?.(node.id);
    },
    [onNodeSelect],
  );

  const onPaneClick = useCallback(() => {
    onNodeSelect?.(null);
  }, [onNodeSelect]);

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar — hidden in read-only mode */}
      {!readOnly && <Toolbar />}

      {/* Save button — hidden in read-only mode */}
      {!readOnly && onSave && (
        <div className="flex items-center gap-2 px-4 py-1.5 bg-gray-900/40 border-b border-gray-700/30">
          <button
            onClick={handleSave}
            className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded-md transition-colors"
          >
            Save
          </button>
        </div>
      )}

      {/* Canvas */}
      <div className="flex-1 relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onDragOver={!readOnly ? onDragOver : undefined}
          onDrop={!readOnly ? onDrop : undefined}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          onInit={useCallback<OnInit>((instance) => {
            rfInstanceRef.current = instance;
            setIsInitialised(true);
          }, [])}
          nodeTypes={nodeTypes}
          nodesDraggable={!readOnly}
          nodesConnectable={!readOnly}
          deleteKeyCode={!readOnly ? "Delete" : null}
          fitView
          colorMode="dark"
          className="bg-gray-950"
        >
          <Controls
            className="!bg-gray-800 !border-gray-700 !rounded-lg"
          />
          <MiniMap
            nodeColor={(node) => {
              const t = (node.type ?? "").replace("Node", "");
              const colors: Record<string, string> = {
                agent: "#818cf8",
                tool: "#34d399",
                trigger: "#fbbf24",
                output: "#9ca3af",
              };
              return colors[t] ?? "#6b7280";
            }}
            maskColor="rgba(0,0,0,0.65)"
            style={{
              background: "#111827",
              border: "1px solid #374151",
              borderRadius: "8px",
            }}
          />
          <Background
            variant={BackgroundVariant.Dots}
            gap={20}
            size={1}
            color="#374151"
          />
        </ReactFlow>
      </div>
    </div>
  );
}
