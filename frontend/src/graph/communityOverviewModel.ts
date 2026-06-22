import { getNodeColor } from "../constants/graphColors";
import type { GraphOverviewPayload, OverviewNode } from "../types";
import {
  categoryColor,
  communityFor,
  communityNodeId,
  entityNodeId,
  nodeSize,
  visibleByCategory,
} from "./graphModelBasics";
import type {
  CommunityOverviewOptions,
  ExplorerEdge,
  ExplorerModel,
  ExplorerNode,
} from "./graphModelTypes";
import {
  FOCUSED_ENTITIES_PER_COMMUNITY,
  OVERVIEW_ENTITIES_PER_COMMUNITY,
  UNCATEGORIZED,
} from "./graphModelTypes";

function sortedOverviewNodes(nodes: readonly OverviewNode[]): OverviewNode[] {
  return [...nodes].sort((left, right) => {
    if (right.connection_count !== left.connection_count) {
      return right.connection_count - left.connection_count;
    }
    return left.name.localeCompare(right.name);
  });
}

export function buildCommunityOverviewModel(
  payload: GraphOverviewPayload,
  options: CommunityOverviewOptions,
): ExplorerModel {
  const grouped = new Map<string, OverviewNode[]>();
  const visibleNodes = payload.nodes.filter((node) =>
    visibleByCategory(node, options),
  );

  for (const node of sortedOverviewNodes(visibleNodes)) {
    const community = communityFor(node.main_categories);
    const nodes = grouped.get(community) ?? [];
    nodes.push(node);
    grouped.set(community, nodes);
  }

  const communities = [...grouped.entries()].sort(
    ([leftName, leftNodes], [rightName, rightNodes]) =>
      rightNodes.length - leftNodes.length || leftName.localeCompare(rightName),
  );

  const nodes: ExplorerNode[] = [];
  const edges: ExplorerEdge[] = [];
  const entityCommunity = new Map<string, string>();
  const visibleEntityIds = new Set<string>();
  const radius = communities.length > 2 ? 440 : 300;
  const entityLimit =
    options.focusedCategory === null
      ? OVERVIEW_ENTITIES_PER_COMMUNITY
      : FOCUSED_ENTITIES_PER_COMMUNITY;

  communities.forEach(([community, communityNodes], index) => {
    const angle = (Math.PI * 2 * index) / Math.max(communities.length, 1);
    const hubX = Math.cos(angle) * radius;
    const hubY = Math.sin(angle) * radius;
    const color = categoryColor(community);
    const representativeNodes = communityNodes.slice(0, entityLimit);

    for (const node of communityNodes) {
      entityCommunity.set(node.canonical_id, community);
    }

    nodes.push({
      id: communityNodeId(community),
      kind: "community",
      label: community,
      entityId: null,
      community,
      mainCategories: community === UNCATEGORIZED ? [] : [community],
      subCategory: null,
      connectionCount: communityNodes.reduce(
        (total, node) => total + node.connection_count,
        0,
      ),
      entityIds: communityNodes.map((node) => node.canonical_id),
      x: hubX,
      y: hubY,
      size: Math.min(28, 16 + Math.sqrt(communityNodes.length) * 0.35),
      color,
      forceLabel: true,
      overviewNode: null,
      graphNode: null,
    });

    representativeNodes.forEach((node, localIndex) => {
      const localAngle =
        (Math.PI * 2 * localIndex) / Math.max(representativeNodes.length, 1);
      const localRadius = 68 + Math.floor(localIndex / 12) * 42;
      const nodeId = entityNodeId(node.canonical_id);
      visibleEntityIds.add(node.canonical_id);
      nodes.push({
        id: nodeId,
        kind: "entity",
        label: node.name,
        entityId: node.canonical_id,
        community,
        mainCategories: node.main_categories,
        subCategory: node.sub_category,
        connectionCount: node.connection_count,
        entityIds: [node.canonical_id],
        x: hubX + Math.cos(localAngle) * localRadius,
        y: hubY + Math.sin(localAngle) * localRadius,
        size: nodeSize(node.connection_count, 3, 8),
        color: getNodeColor(node.main_categories),
        forceLabel: false,
        overviewNode: node,
        graphNode: null,
      });
      edges.push({
        id: `membership:${community}:${node.canonical_id}`,
        kind: "community-membership",
        source: communityNodeId(community),
        target: nodeId,
        label: "contains",
        size: 0.35,
        color: "#57534E",
      });
    });
  });

  const communityLinkCounts = new Map<string, number>();
  for (const edge of payload.edges) {
    const sourceCommunity = entityCommunity.get(edge.source);
    const targetCommunity = entityCommunity.get(edge.target);
    if (!sourceCommunity || !targetCommunity) continue;

    if (visibleEntityIds.has(edge.source) && visibleEntityIds.has(edge.target)) {
      edges.push({
        id: `relationship:${edge.id}`,
        kind: "relationship",
        source: entityNodeId(edge.source),
        target: entityNodeId(edge.target),
        label: edge.type,
        size: 0.45,
        color: "#57534E",
      });
    }

    if (sourceCommunity === targetCommunity) continue;
    const key = `${sourceCommunity}->${targetCommunity}`;
    communityLinkCounts.set(key, (communityLinkCounts.get(key) ?? 0) + 1);
  }

  for (const [key, count] of communityLinkCounts) {
    const [sourceCommunity, targetCommunity] = key.split("->");
    if (!sourceCommunity || !targetCommunity) continue;
    edges.push({
      id: `community-link:${key}`,
      kind: "community-link",
      source: communityNodeId(sourceCommunity),
      target: communityNodeId(targetCommunity),
      label: `${count} relationships`,
      size: Math.min(1.4, 0.35 + Math.log2(count + 1) * 0.18),
      color: "#78716C",
    });
  }

  return {
    mode: "overview",
    nodes,
    edges,
    stats: {
      communities: communities.length,
      totalEntities: payload.nodes.length,
      visibleEntities: visibleNodes.length,
      visibleEdges: edges.length,
    },
  };
}
