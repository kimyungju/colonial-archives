import { describe, expect, it } from "vitest";
import { createSigmaGraph } from "./sigmaGraph";
import type { ExplorerModel } from "./graphModel";

const model: ExplorerModel = {
  mode: "overview",
  nodes: [
    {
      id: "community:General and Establishment",
      kind: "community",
      label: "General and Establishment",
      entityId: null,
      community: "General and Establishment",
      mainCategories: ["General and Establishment"],
      subCategory: null,
      connectionCount: 12,
      entityIds: ["singapore"],
      x: 0,
      y: 0,
      size: 24,
      color: "#3B82F6",
      forceLabel: true,
      overviewNode: null,
      graphNode: null,
    },
    {
      id: "entity:singapore",
      kind: "entity",
      label: "Singapore",
      entityId: "singapore",
      community: "General and Establishment",
      mainCategories: ["General and Establishment"],
      subCategory: null,
      connectionCount: 12,
      entityIds: ["singapore"],
      x: 10,
      y: 10,
      size: 12,
      color: "#3B82F6",
      forceLabel: true,
      overviewNode: null,
      graphNode: null,
    },
  ],
  edges: [
    {
      id: "membership:General and Establishment:singapore",
      kind: "community-membership",
      source: "community:General and Establishment",
      target: "entity:singapore",
      label: "contains",
      size: 0.8,
      color: "#3B82F6",
    },
  ],
  stats: {
    communities: 1,
    totalEntities: 1,
    visibleEntities: 1,
    visibleEdges: 1,
  },
};

describe("createSigmaGraph", () => {
  it("loads explorer nodes and edges into graphology attributes", () => {
    const graph = createSigmaGraph(model);

    expect(graph.order).toBe(2);
    expect(graph.size).toBe(1);
    expect(graph.getNodeAttribute("entity:singapore", "label")).toBe("Singapore");
    expect(graph.getEdgeAttribute(
      "membership:General and Establishment:singapore",
      "kind",
    )).toBe("community-membership");
  });
});
