import { getNodeColor } from "../constants/graphColors";
import type { GraphNode, GraphPayload } from "../types";
import {
  communityFor,
  degreeMap,
  entityNodeId,
  nodeSize,
  visibleByCategory,
} from "./graphModelBasics";
import type {
  ExplorerEdge,
  ExplorerModel,
  ExplorerNode,
  SubgraphOptions,
} from "./graphModelTypes";
import { SUBGRAPH_NODE_LIMIT } from "./graphModelTypes";

function sortedGraphNodes(
  nodes: readonly GraphNode[],
  degreeById: ReadonlyMap<string, number>,
  centerNode: string,
): GraphNode[] {
  return [...nodes].sort((left, right) => {
    if (left.canonical_id === centerNode) return -1;
    if (right.canonical_id === centerNode) return 1;
    const degreeDelta =
      (degreeById.get(right.canonical_id) ?? 0) -
      (degreeById.get(left.canonical_id) ?? 0);
    if (degreeDelta !== 0) return degreeDelta;
    return left.name.localeCompare(right.name);
  });
}

export function buildSubgraphModel(
  payload: GraphPayload,
  options: SubgraphOptions,
): ExplorerModel {
  const degreeById = degreeMap(payload.edges);
  const visibleNodes = sortedGraphNodes(
    payload.nodes.filter((node) => visibleByCategory(node, options)),
    degreeById,
    payload.center_node,
  ).slice(0, SUBGRAPH_NODE_LIMIT);
  const visibleIds = new Set(visibleNodes.map((node) => node.canonical_id));
  const nodes = visibleNodes.map((node, index) => {
    const isCenter = node.canonical_id === payload.center_node;
    const offsetIndex = Math.max(index - 1, 0);
    const angle =
      (Math.PI * 2 * offsetIndex) / Math.max(visibleNodes.length - 1, 1);
    const ring = 128 + Math.floor(offsetIndex / 16) * 72;
    const connectionCount = degreeById.get(node.canonical_id) ?? 0;
    return {
      id: entityNodeId(node.canonical_id),
      kind: "entity",
      label: node.name,
      entityId: node.canonical_id,
      community: communityFor(node.main_categories),
      mainCategories: node.main_categories,
      subCategory: node.sub_category,
      connectionCount,
      entityIds: [node.canonical_id],
      x: isCenter ? 0 : Math.cos(angle) * ring,
      y: isCenter ? 0 : Math.sin(angle) * ring,
      size: isCenter ? 22 : nodeSize(connectionCount, 4, 14),
      color: getNodeColor(node.main_categories),
      forceLabel: false,
      overviewNode: null,
      graphNode: node,
    } satisfies ExplorerNode;
  });
  const edges = payload.edges
    .filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target))
    .map(
      (edge) =>
        ({
          id: `relationship:${edge.id}`,
          kind: "relationship",
          source: entityNodeId(edge.source),
          target: entityNodeId(edge.target),
          label: edge.type,
          size: edge.highlighted ? 1.05 : 0.45,
          color: edge.highlighted ? "#8A6832" : "#57534E",
        }) satisfies ExplorerEdge,
    );

  return {
    mode: "subgraph",
    nodes,
    edges,
    stats: {
      communities: new Set(nodes.map((node) => node.community)).size,
      totalEntities: payload.nodes.length,
      visibleEntities: nodes.length,
      visibleEdges: edges.length,
    },
  };
}
