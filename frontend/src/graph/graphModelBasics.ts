import { CATEGORY_COLORS, DEFAULT_NODE_COLOR } from "../constants/graphColors";
import type { GraphEdge, GraphNode } from "../types";
import type {
  CommunityOverviewOptions,
  ExplorerNode,
  NeighborNode,
  NeighborSummary,
  SubgraphOptions,
} from "./graphModelTypes";
import { COMMUNITY_PREFIX, ENTITY_PREFIX, UNCATEGORIZED } from "./graphModelTypes";

export function communityFor(categories: readonly string[]): string {
  return categories[0] ?? UNCATEGORIZED;
}

export function communityNodeId(category: string): string {
  return `${COMMUNITY_PREFIX}${category}`;
}

export function entityNodeId(canonicalId: string): string {
  return `${ENTITY_PREFIX}${canonicalId}`;
}

export function visibleByCategory(
  node: { readonly main_categories: readonly string[] },
  options: CommunityOverviewOptions | SubgraphOptions,
): boolean {
  const category = communityFor(node.main_categories);
  if (options.hiddenCategories.has(category)) return false;
  if ("focusedCategory" in options && options.focusedCategory !== null) {
    return category === options.focusedCategory;
  }
  return true;
}

export function nodeSize(
  connectionCount: number,
  base: number,
  max: number,
): number {
  return Math.min(max, base + Math.log2(connectionCount + 1) * 4);
}

export function degreeMap(edges: readonly GraphEdge[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const edge of edges) {
    counts.set(edge.source, (counts.get(edge.source) ?? 0) + 1);
    counts.set(edge.target, (counts.get(edge.target) ?? 0) + 1);
  }
  return counts;
}

export function explorerNodeToGraphNode(node: ExplorerNode): GraphNode | null {
  if (node.kind !== "entity" || node.entityId === null) return null;
  if (node.graphNode) return node.graphNode;
  if (!node.overviewNode) return null;
  return {
    canonical_id: node.overviewNode.canonical_id,
    name: node.overviewNode.name,
    main_categories: node.overviewNode.main_categories,
    sub_category: node.overviewNode.sub_category,
    attributes: {},
    highlighted: true,
    evidence_doc_id: node.overviewNode.evidence_doc_id,
    evidence_page: node.overviewNode.evidence_page,
    evidence_text_span: null,
    evidence_confidence: null,
  };
}

export function getNodeNeighborSummaries(
  canonicalId: string,
  nodes: readonly NeighborNode[],
  edges: readonly GraphEdge[],
): NeighborSummary[] {
  const nodesById = new Map(nodes.map((node) => [node.canonical_id, node]));
  const summaries: NeighborSummary[] = [];
  for (const edge of edges) {
    const isOutgoing = edge.source === canonicalId;
    const isIncoming = edge.target === canonicalId;
    if (!isOutgoing && !isIncoming) continue;
    const neighborId = isOutgoing ? edge.target : edge.source;
    const neighbor = nodesById.get(neighborId);
    if (!neighbor) continue;
    summaries.push({
      canonicalId: neighbor.canonical_id,
      name: neighbor.name,
      relationship: edge.type,
      direction: isOutgoing ? "outgoing" : "incoming",
      mainCategories: neighbor.main_categories,
    });
  }
  return summaries.sort(
    (left, right) =>
      left.relationship.localeCompare(right.relationship) ||
      left.name.localeCompare(right.name),
  );
}

export function categoryColor(category: string): string {
  return CATEGORY_COLORS[category] ?? DEFAULT_NODE_COLOR;
}
