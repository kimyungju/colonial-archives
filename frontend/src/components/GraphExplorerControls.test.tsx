import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import GraphExplorerControls from "./GraphExplorerControls";

function renderControls(mode: "overview" | "subgraph") {
  const onResetOverview = vi.fn();
  render(
    <GraphExplorerControls
      communities={[]}
      mode={mode}
      visibleEntities={12}
      totalEntities={20}
      visibleEdges={30}
      isLoadingSubgraph={false}
      subgraphError={null}
      onSearch={() => Promise.resolve([])}
      onSelectSearchResult={vi.fn()}
      onToggleCategory={vi.fn()}
      onFocusCategory={vi.fn()}
      onResetOverview={onResetOverview}
    />,
  );
  return { onResetOverview };
}

describe("GraphExplorerControls", () => {
  it("shows the all-nodes action only for subgraphs", () => {
    renderControls("overview");

    expect(
      screen.queryByRole("button", { name: "Back to all nodes" }),
    ).not.toBeInTheDocument();
  });

  it("returns to the overview when the all-nodes action is clicked", async () => {
    const user = userEvent.setup();
    const { onResetOverview } = renderControls("subgraph");

    await user.click(screen.getByRole("button", { name: "Back to all nodes" }));

    expect(onResetOverview).toHaveBeenCalledOnce();
  });
});
