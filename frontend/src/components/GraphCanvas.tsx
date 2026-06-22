import { useCallback, useEffect, useMemo, useState } from "react";

import { apiClient } from "../api/client";
import {
  CATEGORY_COLORS,
  DEFAULT_NODE_COLOR,
} from "../constants/graphColors";
import {
  buildCommunityOverviewModel,
  buildSubgraphModel,
  entityNodeId,
  explorerNodeToGraphNode,
} from "../graph/graphModel";
import type { ExplorerModel } from "../graph/graphModel";
import { useAppStore } from "../stores/useAppStore";
import type { GraphNode, GraphOverviewPayload } from "../types";
import {
  EmptyGraphState,
  ErrorGraphState,
  LoadingGraphState,
} from "./GraphCanvasStates";
import GraphExplorerControls from "./GraphExplorerControls";
import type { CommunityControl } from "./GraphExplorerControls";
import SigmaGraphStage from "./SigmaGraphStage";

const MAX_OVERVIEW_RETRIES = 5;
const OVERVIEW_RETRY_DELAY_MS = 3_000;
const UNCATEGORIZED = "Uncategorized";

function toErrorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Unknown error";
}

function firstCategory(categories: readonly string[]): string {
  return categories[0] ?? UNCATEGORIZED;
}

function buildCommunityControls(
  overviewData: GraphOverviewPayload | null,
  hiddenCategories: ReadonlySet<string>,
  focusedCategory: string | null,
): readonly CommunityControl[] {
  const counts = new Map<string, number>();
  for (const node of overviewData?.nodes ?? []) {
    const category = firstCategory(node.main_categories);
    counts.set(category, (counts.get(category) ?? 0) + 1);
  }

  const names = new Set<string>([
    ...Object.keys(CATEGORY_COLORS),
    ...counts.keys(),
  ]);

  return [...names]
    .map((name) => ({
      name,
      color: CATEGORY_COLORS[name] ?? DEFAULT_NODE_COLOR,
      count: counts.get(name) ?? 0,
      hidden: hiddenCategories.has(name),
      focused: focusedCategory === name,
    }))
    .sort(
      (left, right) =>
        right.count - left.count || left.name.localeCompare(right.name),
    );
}

function findNode(model: ExplorerModel, nodeId: string) {
  return model.nodes.find((node) => node.id === nodeId) ?? null;
}

export default function GraphCanvas() {
  const graphData = useAppStore((state) => state.graphData);
  const overviewData = useAppStore((state) => state.overviewData);
  const isOverviewMode = useAppStore((state) => state.isOverviewMode);
  const hiddenCategories = useAppStore((state) => state.hiddenCategories);
  const selectedNode = useAppStore((state) => state.selectedNode);
  const selectNode = useAppStore((state) => state.selectNode);
  const setGraphData = useAppStore((state) => state.setGraphData);
  const setOverviewData = useAppStore((state) => state.setOverviewData);
  const setOverviewMode = useAppStore((state) => state.setOverviewMode);
  const toggleCategory = useAppStore((state) => state.toggleCategory);

  const [overviewError, setOverviewError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [fetchToken, setFetchToken] = useState(0);
  const [focusedCategory, setFocusedCategory] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [visualSelectionId, setVisualSelectionId] = useState<string | null>(null);
  const [isLoadingSubgraph, setIsLoadingSubgraph] = useState(false);
  const [subgraphError, setSubgraphError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timeoutId: number | null = null;

    async function fetchOverview(attempt: number): Promise<void> {
      try {
        const data = await apiClient.getOverview();
        if (cancelled) return;
        setOverviewData(data);
        setOverviewError(null);
        setRetryCount(0);
      } catch (err) {
        if (cancelled) return;
        const message = toErrorMessage(err);
        console.warn(
          `[GraphCanvas] Overview fetch failed (attempt ${attempt + 1}/${MAX_OVERVIEW_RETRIES + 1}): ${message}`,
        );
        if (attempt < MAX_OVERVIEW_RETRIES) {
          setRetryCount(attempt + 1);
          timeoutId = window.setTimeout(() => {
            void fetchOverview(attempt + 1);
          }, OVERVIEW_RETRY_DELAY_MS);
          return;
        }
        setOverviewError(message);
        setRetryCount(0);
      }
    }

    void fetchOverview(0);
    return () => {
      cancelled = true;
      if (timeoutId !== null) window.clearTimeout(timeoutId);
    };
  }, [fetchToken, setOverviewData]);

  const model = useMemo(() => {
    if (!isOverviewMode && graphData) {
      return buildSubgraphModel(graphData, { hiddenCategories });
    }
    if (!overviewData) return null;
    return buildCommunityOverviewModel(overviewData, {
      hiddenCategories,
      focusedCategory,
    });
  }, [focusedCategory, graphData, hiddenCategories, isOverviewMode, overviewData]);

  const communities = useMemo(
    () => buildCommunityControls(overviewData, hiddenCategories, focusedCategory),
    [focusedCategory, hiddenCategories, overviewData],
  );

  const selectedNodeId = selectedNode
    ? entityNodeId(selectedNode.canonical_id)
    : visualSelectionId;

  const loadEntitySubgraph = useCallback(
    async (entityId: string, fallbackNode: GraphNode | null): Promise<void> => {
      setIsLoadingSubgraph(true);
      setSubgraphError(null);
      setVisualSelectionId(entityNodeId(entityId));
      if (fallbackNode) selectNode(fallbackNode);

      try {
        const payload = await apiClient.getSubgraph(entityId);
        const nextSelected =
          payload.nodes.find((node) => node.canonical_id === entityId) ??
          fallbackNode;
        setGraphData(payload);
        setOverviewMode(false);
        setFocusedCategory(null);
        if (nextSelected) selectNode(nextSelected);
      } catch (err) {
        setSubgraphError(toErrorMessage(err));
      } finally {
        setIsLoadingSubgraph(false);
      }
    },
    [selectNode, setGraphData, setOverviewMode],
  );

  const handleNodeClick = useCallback(
    (nodeId: string) => {
      if (!model) return;
      const node = findNode(model, nodeId);
      if (!node) return;
      setVisualSelectionId(nodeId);

      if (node.kind === "community") {
        selectNode(null);
        setFocusedCategory((current) =>
          current === node.community ? null : node.community,
        );
        return;
      }

      const graphNode = explorerNodeToGraphNode(node);
      if (!node.entityId || !graphNode) return;
      void loadEntitySubgraph(node.entityId, graphNode);
    },
    [loadEntitySubgraph, model, selectNode],
  );

  const handleStageClick = useCallback(() => {
    setVisualSelectionId(null);
    setHoveredNodeId(null);
    selectNode(null);
  }, [selectNode]);

  const handleResetOverview = useCallback(() => {
    setGraphData(null);
    setOverviewMode(true);
    setFocusedCategory(null);
    setVisualSelectionId(null);
    setSubgraphError(null);
    selectNode(null);
  }, [selectNode, setGraphData, setOverviewMode]);

  const handleSearch = useCallback(
    (query: string) => apiClient.searchGraph(query, 8),
    [],
  );

  const handleSearchResult = useCallback(
    (node: GraphNode) => {
      void loadEntitySubgraph(node.canonical_id, node);
    },
    [loadEntitySubgraph],
  );

  if (!overviewData && !overviewError) {
    return <LoadingGraphState retryCount={retryCount} />;
  }

  if (!overviewData && overviewError) {
    return (
      <ErrorGraphState
        message={overviewError}
        onRetry={() => {
          setOverviewError(null);
          setFetchToken((token) => token + 1);
        }}
      />
    );
  }

  if (!model || model.nodes.length === 0) {
    return <EmptyGraphState onClearFocus={() => setFocusedCategory(null)} />;
  }

  return (
    <div className="relative h-full w-full overflow-hidden bg-stone-900">
      <div
        className={`absolute inset-y-0 left-0 transition-[right] duration-200 ease-in-out ${
          selectedNode ? "right-0 md:right-[300px]" : "right-0"
        }`}
      >
        <SigmaGraphStage
          model={model}
          selectedNodeId={selectedNodeId}
          hoveredNodeId={hoveredNodeId}
          onHoverNode={setHoveredNodeId}
          onNodeClick={handleNodeClick}
          onStageClick={handleStageClick}
          onResetOverview={handleResetOverview}
        />
      </div>
      <GraphExplorerControls
        communities={communities}
        mode={model.mode}
        visibleEntities={model.stats.visibleEntities}
        totalEntities={model.stats.totalEntities}
        visibleEdges={model.stats.visibleEdges}
        isLoadingSubgraph={isLoadingSubgraph}
        subgraphError={subgraphError}
        onSearch={handleSearch}
        onSelectSearchResult={handleSearchResult}
        onToggleCategory={toggleCategory}
        onFocusCategory={setFocusedCategory}
        onResetOverview={handleResetOverview}
      />
    </div>
  );
}
