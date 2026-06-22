import type { GraphNode, OverviewNode } from "../types";

export const COMMUNITY_PREFIX = "community:";
export const ENTITY_PREFIX = "entity:";
export const UNCATEGORIZED = "Uncategorized";
export const OVERVIEW_ENTITIES_PER_COMMUNITY = 18;
export const FOCUSED_ENTITIES_PER_COMMUNITY = 60;
export const SUBGRAPH_NODE_LIMIT = 180;

export type ExplorerMode = "overview" | "subgraph";
export type ExplorerNodeKind = "community" | "entity";
export type ExplorerEdgeKind =
  | "community-link"
  | "community-membership"
  | "relationship";

export interface ExplorerNode {
  readonly id: string;
  readonly kind: ExplorerNodeKind;
  readonly label: string;
  readonly entityId: string | null;
  readonly community: string;
  readonly mainCategories: readonly string[];
  readonly subCategory: string | null;
  readonly connectionCount: number;
  readonly entityIds: readonly string[];
  readonly x: number;
  readonly y: number;
  readonly size: number;
  readonly color: string;
  readonly forceLabel: boolean;
  readonly overviewNode: OverviewNode | null;
  readonly graphNode: GraphNode | null;
}

export interface ExplorerEdge {
  readonly id: string;
  readonly kind: ExplorerEdgeKind;
  readonly source: string;
  readonly target: string;
  readonly label: string;
  readonly size: number;
  readonly color: string;
}

export interface ExplorerStats {
  readonly communities: number;
  readonly totalEntities: number;
  readonly visibleEntities: number;
  readonly visibleEdges: number;
}

export interface ExplorerModel {
  readonly mode: ExplorerMode;
  readonly nodes: readonly ExplorerNode[];
  readonly edges: readonly ExplorerEdge[];
  readonly stats: ExplorerStats;
}

export interface CommunityOverviewOptions {
  readonly hiddenCategories: ReadonlySet<string>;
  readonly focusedCategory: string | null;
}

export interface SubgraphOptions {
  readonly hiddenCategories: ReadonlySet<string>;
}

export interface NeighborSummary {
  readonly canonicalId: string;
  readonly name: string;
  readonly relationship: string;
  readonly direction: "incoming" | "outgoing";
  readonly mainCategories: readonly string[];
}

export type NeighborNode = Pick<
  OverviewNode,
  "canonical_id" | "main_categories" | "name" | "sub_category"
>;
