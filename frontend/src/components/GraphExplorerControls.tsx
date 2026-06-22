import { useState, type FormEvent } from "react";

import type { GraphNode } from "../types";

export interface CommunityControl {
  readonly name: string;
  readonly color: string;
  readonly count: number;
  readonly hidden: boolean;
  readonly focused: boolean;
}

interface GraphExplorerControlsProps {
  readonly communities: readonly CommunityControl[];
  readonly mode: "overview" | "subgraph";
  readonly visibleEntities: number;
  readonly totalEntities: number;
  readonly visibleEdges: number;
  readonly isLoadingSubgraph: boolean;
  readonly subgraphError: string | null;
  readonly onSearch: (query: string) => Promise<readonly GraphNode[]>;
  readonly onSelectSearchResult: (node: GraphNode) => void;
  readonly onToggleCategory: (category: string) => void;
  readonly onFocusCategory: (category: string | null) => void;
  readonly onResetOverview: () => void;
}

export default function GraphExplorerControls({
  communities,
  mode,
  visibleEntities,
  totalEntities,
  visibleEdges,
  isLoadingSubgraph,
  subgraphError,
  onSearch,
  onSelectSearchResult,
  onToggleCategory,
  onFocusCategory,
  onResetOverview,
}: GraphExplorerControlsProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<readonly GraphNode[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  async function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      return;
    }
    setIsSearching(true);
    setSearchError(null);
    try {
      setResults(await onSearch(trimmed));
    } catch (err) {
      if (err instanceof Error) {
        setSearchError(err.message);
      } else {
        setSearchError("Search failed");
      }
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  }

  return (
    <div className="pointer-events-none absolute inset-x-3 top-3 z-10 flex max-w-[460px] flex-col gap-3 sm:left-3 sm:right-auto">
      <div className="pointer-events-auto rounded-lg border border-stone-700/70 bg-stone-950/88 p-3 shadow-[0_18px_50px_rgba(0,0,0,0.28)] backdrop-blur-md">
        <form onSubmit={submitSearch} className="flex gap-2">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search entities"
            className="min-w-0 flex-1 rounded-md border border-stone-700 bg-stone-900 px-3 py-2 text-sm text-stone-100 outline-none transition-colors placeholder:text-stone-600 focus:border-ink-400"
          />
          <button
            type="submit"
            disabled={isSearching}
            className="rounded-md bg-ink-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-ink-500 disabled:cursor-wait disabled:bg-stone-700"
          >
            {isSearching ? "Searching" : "Search"}
          </button>
        </form>

        {(results.length > 0 || searchError) && (
          <div className="mt-2 max-h-56 overflow-y-auto rounded-md border border-stone-800 bg-stone-900/95">
            {searchError && (
              <p className="px-3 py-2 text-xs text-red-300">{searchError}</p>
            )}
            {results.map((node) => (
              <button
                key={node.canonical_id}
                type="button"
                onClick={() => {
                  onSelectSearchResult(node);
                  setResults([]);
                  setQuery(node.name);
                }}
                className="block w-full border-b border-stone-800 px-3 py-2 text-left last:border-b-0 hover:bg-stone-800 focus:bg-stone-800 focus:outline-none"
              >
                <span className="block truncate text-sm text-stone-100">
                  {node.name}
                </span>
                <span className="block truncate font-mono text-[11px] text-stone-500">
                  {node.canonical_id}
                </span>
              </button>
            ))}
          </div>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-stone-400">
          <span className="rounded border border-stone-800 px-2 py-1 font-mono">
            {visibleEntities}/{totalEntities} entities
          </span>
          <span className="rounded border border-stone-800 px-2 py-1 font-mono">
            {visibleEdges} links
          </span>
          {mode === "subgraph" && (
            <button
              type="button"
              onClick={onResetOverview}
              className="rounded border border-ink-500/60 px-2 py-1 text-ink-300 transition-colors hover:border-ink-400 hover:text-ink-200"
            >
              Back to all nodes
            </button>
          )}
          {isLoadingSubgraph && <span>Loading neighborhood</span>}
          {subgraphError && <span className="text-red-300">{subgraphError}</span>}
        </div>
      </div>

      {mode === "overview" && (
        <div className="pointer-events-auto max-h-[42vh] overflow-y-auto rounded-lg border border-stone-700/70 bg-stone-950/86 p-3 backdrop-blur-md">
          <div className="mb-2 flex items-center justify-between gap-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-400">
              Communities
            </h2>
            <button
              type="button"
              onClick={() => onFocusCategory(null)}
              className="text-xs text-stone-500 transition-colors hover:text-stone-200"
            >
              All
            </button>
          </div>
          <div className="space-y-1.5">
            {communities.map((community) => (
              <div
                key={community.name}
                className={`grid grid-cols-[1fr_auto_auto] items-center gap-2 rounded-md px-2 py-1.5 ${
                  community.focused ? "bg-stone-800" : "bg-transparent"
                }`}
              >
                <button
                  type="button"
                  onClick={() =>
                    onFocusCategory(community.focused ? null : community.name)
                  }
                  className={`flex min-w-0 items-center gap-2 text-left text-xs ${
                    community.hidden ? "opacity-35" : "opacity-100"
                  }`}
                >
                  <span
                    className="h-3 w-3 shrink-0 rounded-full"
                    style={{ backgroundColor: community.color }}
                  />
                  <span className="truncate text-stone-200">
                    {community.name}
                  </span>
                </button>
                <span className="font-mono text-[11px] text-stone-500">
                  {community.count}
                </span>
                <button
                  type="button"
                  onClick={() => onToggleCategory(community.name)}
                  className="rounded border border-stone-700 px-1.5 py-0.5 text-[11px] text-stone-400 transition-colors hover:border-stone-500 hover:text-stone-100"
                >
                  {community.hidden ? "Show" : "Hide"}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
