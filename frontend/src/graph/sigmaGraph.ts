import { MultiDirectedGraph } from "graphology";
import type {
  ExplorerEdgeKind,
  ExplorerModel,
  ExplorerNodeKind,
} from "./graphModel";

type AttributeValue = string | number | boolean | null;

export interface SigmaNodeAttributes {
  readonly [name: string]: AttributeValue;
  readonly x: number;
  readonly y: number;
  readonly size: number;
  readonly label: string;
  readonly color: string;
  readonly forceLabel: boolean;
  readonly kind: ExplorerNodeKind;
  readonly entityId: string | null;
  readonly community: string;
  readonly connectionCount: number;
}

export interface SigmaEdgeAttributes {
  readonly [name: string]: AttributeValue;
  readonly label: string;
  readonly size: number;
  readonly color: string;
  readonly kind: ExplorerEdgeKind;
  readonly sourceNode: string;
  readonly targetNode: string;
}

export type ExplorerGraph = MultiDirectedGraph<
  SigmaNodeAttributes,
  SigmaEdgeAttributes
>;

export function createSigmaGraph(model: ExplorerModel): ExplorerGraph {
  const graph = new MultiDirectedGraph<
    SigmaNodeAttributes,
    SigmaEdgeAttributes
  >();

  for (const node of model.nodes) {
    graph.addNode(node.id, {
      x: node.x,
      y: node.y,
      size: node.size,
      label: node.label,
      color: node.color,
      forceLabel: node.forceLabel,
      kind: node.kind,
      entityId: node.entityId,
      community: node.community,
      connectionCount: node.connectionCount,
    });
  }

  for (const edge of model.edges) {
    if (!graph.hasNode(edge.source) || !graph.hasNode(edge.target)) continue;
    graph.addDirectedEdgeWithKey(edge.id, edge.source, edge.target, {
      label: edge.label,
      size: edge.size,
      color: edge.color,
      kind: edge.kind,
      sourceNode: edge.source,
      targetNode: edge.target,
    });
  }

  return graph;
}
