import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import type { ExplorerModel } from "../graph/graphModel";
import SigmaGraphStage from "./SigmaGraphStage";

vi.mock("@react-sigma/core", () => ({
  ControlsContainer: ({ children }: { readonly children: ReactNode }) => (
    <div>{children}</div>
  ),
  FullScreenControl: () => <button type="button">Fullscreen</button>,
  SigmaContainer: ({
    children,
    className,
  }: {
    readonly children: ReactNode;
    readonly className?: string;
  }) => <div className={className}>{children}</div>,
  ZoomControl: () => <button type="button">Zoom</button>,
  useCamera: () => ({
    gotoNode: vi.fn(),
    reset: vi.fn(),
  }),
  useLoadGraph: () => vi.fn(),
  useRegisterEvents: () => vi.fn(),
  useSetSettings: () => vi.fn(),
}));

const subgraphModel: ExplorerModel = {
  mode: "subgraph",
  nodes: [
    {
      id: "entity:singapore",
      kind: "entity",
      label: "Singapore",
      entityId: "singapore",
      community: "General and Establishment",
      mainCategories: ["General and Establishment"],
      subCategory: null,
      connectionCount: 1,
      entityIds: ["singapore"],
      x: 0,
      y: 0,
      size: 10,
      color: "#3B82F6",
      forceLabel: true,
      overviewNode: null,
      graphNode: null,
    },
  ],
  edges: [],
  stats: {
    communities: 0,
    totalEntities: 1,
    visibleEntities: 1,
    visibleEdges: 0,
  },
};

describe("SigmaGraphStage", () => {
  it("scopes Sigma control styling to the graph stage", () => {
    render(
      <SigmaGraphStage
        model={subgraphModel}
        selectedNodeId={null}
        hoveredNodeId={null}
        onHoverNode={vi.fn()}
        onNodeClick={vi.fn()}
        onStageClick={vi.fn()}
        onResetOverview={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Back to all nodes" }).closest(".sigma-graph-stage"),
    ).not.toBeNull();
  });

  it("returns to all nodes from the graph control", async () => {
    const user = userEvent.setup();
    const onResetOverview = vi.fn();
    render(
      <SigmaGraphStage
        model={subgraphModel}
        selectedNodeId={null}
        hoveredNodeId={null}
        onHoverNode={vi.fn()}
        onNodeClick={vi.fn()}
        onStageClick={vi.fn()}
        onResetOverview={onResetOverview}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Back to all nodes" }));

    expect(onResetOverview).toHaveBeenCalledOnce();
  });
});
