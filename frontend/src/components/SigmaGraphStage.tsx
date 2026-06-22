import { useEffect, useMemo } from "react";
import {
  ControlsContainer,
  FullScreenControl,
  SigmaContainer,
  useCamera,
  useLoadGraph,
  useRegisterEvents,
  useSetSettings,
  ZoomControl,
} from "@react-sigma/core";
import "@react-sigma/core/lib/style.css";
import "./SigmaGraphStage.css";
import { MultiDirectedGraph } from "graphology";

import type { ExplorerModel } from "../graph/graphModel";
import { drawGraphNodeHover } from "../graph/sigmaHoverLabel";
import { createSigmaGraph } from "../graph/sigmaGraph";
import type {
  ExplorerGraph,
  SigmaEdgeAttributes,
  SigmaNodeAttributes,
} from "../graph/sigmaGraph";

interface SigmaGraphStageProps {
  readonly model: ExplorerModel;
  readonly selectedNodeId: string | null;
  readonly hoveredNodeId: string | null;
  readonly onHoverNode: (nodeId: string | null) => void;
  readonly onNodeClick: (nodeId: string) => void;
  readonly onStageClick: () => void;
  readonly onResetOverview: () => void;
}

interface SigmaGraphInnerProps extends SigmaGraphStageProps {
  readonly graph: ExplorerGraph;
  readonly activeNeighborIds: ReadonlySet<string>;
}

function GraphLoader({
  graph,
  model,
  selectedNodeId,
}: Pick<SigmaGraphInnerProps, "graph" | "model" | "selectedNodeId">) {
  const loadGraph = useLoadGraph<
    SigmaNodeAttributes,
    SigmaEdgeAttributes
  >();
  const { reset, gotoNode } = useCamera({
    duration: 450,
    easing: "quadraticInOut",
  });

  useEffect(() => {
    loadGraph(graph);
    if (
      model.mode === "overview" &&
      selectedNodeId &&
      graph.hasNode(selectedNodeId)
    ) {
      gotoNode(selectedNodeId, { duration: 450, easing: "quadraticInOut" });
      return;
    }
    reset({ duration: model.mode === "subgraph" ? 500 : 300, easing: "quadraticInOut" });
  }, [gotoNode, graph, loadGraph, model.mode, reset, selectedNodeId]);

  return null;
}

function GraphEvents({
  onHoverNode,
  onNodeClick,
  onStageClick,
}: Pick<
  SigmaGraphInnerProps,
  "onHoverNode" | "onNodeClick" | "onStageClick"
>) {
  const registerEvents = useRegisterEvents<
    SigmaNodeAttributes,
    SigmaEdgeAttributes
  >();

  useEffect(() => {
    registerEvents({
      enterNode: (event) => onHoverNode(event.node),
      leaveNode: () => onHoverNode(null),
      clickNode: (event) => onNodeClick(event.node),
      clickStage: () => onStageClick(),
    });
  }, [onHoverNode, onNodeClick, onStageClick, registerEvents]);

  return null;
}

function GraphReducers({
  model,
  hoveredNodeId,
  selectedNodeId,
  activeNeighborIds,
}: Pick<
  SigmaGraphInnerProps,
  "model" | "hoveredNodeId" | "selectedNodeId" | "activeNeighborIds"
>) {
  const setSettings = useSetSettings<
    SigmaNodeAttributes,
    SigmaEdgeAttributes
  >();

  useEffect(() => {
    const activeNodeId =
      hoveredNodeId ?? (model.mode === "overview" ? selectedNodeId : null);
    setSettings({
      nodeReducer: (node, data) => {
        if (!activeNodeId) {
          if (node !== selectedNodeId) return data;
          return {
            ...data,
            color: "#D4AD6A",
            forceLabel: model.mode === "overview",
            size: data.size * 1.1,
          };
        }
        if (node === activeNodeId) {
          return {
            ...data,
            color: "#D4AD6A",
            forceLabel: true,
            size: data.size * 1.22,
          };
        }
        if (activeNeighborIds.has(node)) {
          return {
            ...data,
            forceLabel: data.kind === "community",
            size: data.size * 1.04,
          };
        }
        return {
          ...data,
          color: "#44403C",
          forceLabel: false,
          label: data.kind === "community" ? data.label : "",
        };
      },
      edgeReducer: (_edge, data) => {
        if (!activeNodeId) return data;
        const isIncident =
          data.sourceNode === activeNodeId || data.targetNode === activeNodeId;
        if (isIncident) {
          return {
            ...data,
            color:
              data.kind === "community-membership" ? "#9F6B2E" : "#D4AD6A",
            size: data.size * 1.45,
          };
        }
        return { ...data, hidden: true };
      },
    });
  }, [activeNeighborIds, hoveredNodeId, model.mode, selectedNodeId, setSettings]);

  return null;
}

function SigmaGraphInner(props: SigmaGraphInnerProps) {
  return (
    <>
      <GraphLoader
        graph={props.graph}
        model={props.model}
        selectedNodeId={props.selectedNodeId}
      />
      <GraphEvents
        onHoverNode={props.onHoverNode}
        onNodeClick={props.onNodeClick}
        onStageClick={props.onStageClick}
      />
      <GraphReducers
        model={props.model}
        hoveredNodeId={props.hoveredNodeId}
        selectedNodeId={props.selectedNodeId}
        activeNeighborIds={props.activeNeighborIds}
      />
      <ControlsContainer position="bottom-right">
        {props.model.mode === "subgraph" && (
          <div className="react-sigma-control">
            <button
              type="button"
              title="Back to all nodes"
              aria-label="Back to all nodes"
              onClick={props.onResetOverview}
              className="sigma-overview-control"
            >
              All
            </button>
          </div>
        )}
        <ZoomControl />
        <FullScreenControl />
      </ControlsContainer>
    </>
  );
}

function activeNeighbors(
  model: ExplorerModel,
  activeNodeId: string | null,
): ReadonlySet<string> {
  const neighbors = new Set<string>();
  if (!activeNodeId) return neighbors;
  for (const edge of model.edges) {
    if (edge.source === activeNodeId) neighbors.add(edge.target);
    if (edge.target === activeNodeId) neighbors.add(edge.source);
  }
  return neighbors;
}

export default function SigmaGraphStage(props: SigmaGraphStageProps) {
  const graph = useMemo(() => createSigmaGraph(props.model), [props.model]);
  const activeNodeId = props.hoveredNodeId ?? props.selectedNodeId;
  const activeNeighborIds = useMemo(
    () => activeNeighbors(props.model, activeNodeId),
    [activeNodeId, props.model],
  );

  return (
    <SigmaContainer<SigmaNodeAttributes, SigmaEdgeAttributes>
      className="sigma-graph-stage h-full w-full"
      graph={MultiDirectedGraph}
      settings={{
        allowInvalidContainer: true,
        defaultEdgeType: "line",
        defaultNodeType: "circle",
        edgeLabelColor: { color: "#57534E" },
        edgeLabelFont: "IBM Plex Mono, ui-monospace, monospace",
        edgeLabelSize: 10,
        hideEdgesOnMove: true,
        hideLabelsOnMove: true,
        labelColor: { color: "#F5F5F4" },
        labelDensity: 0.04,
        labelFont: "Plus Jakarta Sans, system-ui, sans-serif",
        labelRenderedSizeThreshold: 30,
        labelSize: 11,
        maxCameraRatio: 4,
        minCameraRatio: 0.05,
        defaultDrawNodeHover: drawGraphNodeHover,
        renderEdgeLabels: false,
        stagePadding: 72,
      }}
      style={{ background: "#1C1917", height: "100%", width: "100%" }}
    >
      <SigmaGraphInner
        {...props}
        graph={graph}
        activeNeighborIds={activeNeighborIds}
      />
    </SigmaContainer>
  );
}
