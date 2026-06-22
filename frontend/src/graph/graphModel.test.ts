import { describe, expect, it } from "vitest";
import type { GraphEdge, GraphOverviewPayload, GraphPayload } from "../types";
import {
  buildCommunityOverviewModel,
  buildSubgraphModel,
  getNodeNeighborSummaries,
} from "./graphModel";

const edge = (
  id: string,
  source: string,
  target: string,
  type = "RELATED_TO",
): GraphEdge => ({
  id,
  source,
  target,
  type,
  attributes: {},
  highlighted: false,
});

const overview: GraphOverviewPayload = {
  nodes: [
    {
      canonical_id: "singapore",
      name: "Singapore",
      main_categories: ["General and Establishment"],
      sub_category: null,
      connection_count: 50,
      evidence_doc_id: null,
      evidence_page: null,
    },
    {
      canonical_id: "opium",
      name: "Opium Revenue",
      main_categories: ["Economic and Financial"],
      sub_category: null,
      connection_count: 24,
      evidence_doc_id: null,
      evidence_page: null,
    },
    {
      canonical_id: "school",
      name: "School Inspectors",
      main_categories: ["Social Services"],
      sub_category: null,
      connection_count: 8,
      evidence_doc_id: null,
      evidence_page: null,
    },
    {
      canonical_id: "fort",
      name: "Fort Canning",
      main_categories: ["Defence and Military"],
      sub_category: null,
      connection_count: 7,
      evidence_doc_id: null,
      evidence_page: null,
    },
  ],
  edges: [
    edge("e1", "singapore", "opium", "TRADE"),
    edge("e2", "singapore", "school", "ADMINISTERED"),
    edge("e3", "fort", "singapore", "DEFENDED"),
  ],
};

describe("buildCommunityOverviewModel", () => {
  it("creates category community hubs before entity nodes", () => {
    const model = buildCommunityOverviewModel(overview, {
      hiddenCategories: new Set<string>(),
      focusedCategory: null,
    });

    expect(model.mode).toBe("overview");
    expect(model.nodes[0]?.kind).toBe("community");
    expect(model.nodes.some((node) => node.id === "entity:singapore")).toBe(true);
    expect(model.nodes.some((node) => node.id === "community:General and Establishment")).toBe(true);
    expect(model.stats.visibleEntities).toBe(4);
  });

  it("filters hidden categories and keeps aggregated community edges", () => {
    const model = buildCommunityOverviewModel(overview, {
      hiddenCategories: new Set<string>(["Defence and Military"]),
      focusedCategory: null,
    });

    expect(model.nodes.some((node) => node.id === "entity:fort")).toBe(false);
    expect(model.nodes.some((node) => node.id === "community:Defence and Military")).toBe(false);
    expect(model.edges.some((modelEdge) => modelEdge.kind === "community-link")).toBe(true);
  });

  it("focuses a single community when requested", () => {
    const model = buildCommunityOverviewModel(overview, {
      hiddenCategories: new Set<string>(),
      focusedCategory: "Economic and Financial",
    });

    expect(model.nodes.some((node) => node.id === "entity:opium")).toBe(true);
    expect(model.nodes.some((node) => node.id === "entity:singapore")).toBe(false);
    expect(model.stats.communities).toBe(1);
  });
});

describe("buildSubgraphModel", () => {
  it("lays out an on-demand entity subgraph around the center node", () => {
    const payload: GraphPayload = {
      center_node: "singapore",
      nodes: [
        {
          canonical_id: "singapore",
          name: "Singapore",
          main_categories: ["General and Establishment"],
          sub_category: null,
          attributes: {},
          highlighted: true,
          evidence_doc_id: null,
          evidence_page: null,
          evidence_text_span: null,
          evidence_confidence: null,
        },
        {
          canonical_id: "opium",
          name: "Opium Revenue",
          main_categories: ["Economic and Financial"],
          sub_category: null,
          attributes: {},
          highlighted: false,
          evidence_doc_id: null,
          evidence_page: null,
          evidence_text_span: null,
          evidence_confidence: null,
        },
      ],
      edges: [edge("e1", "singapore", "opium", "TRADE")],
    };

    const model = buildSubgraphModel(payload, {
      hiddenCategories: new Set<string>(),
    });

    expect(model.mode).toBe("subgraph");
    expect(model.nodes.find((node) => node.id === "entity:singapore")?.forceLabel).toBe(false);
    expect(model.edges).toHaveLength(1);
  });
});

describe("getNodeNeighborSummaries", () => {
  it("returns neighbors sorted by relationship type and name", () => {
    const neighbors = getNodeNeighborSummaries("singapore", overview.nodes, overview.edges);

    expect(neighbors.map((neighbor) => neighbor.name)).toEqual([
      "School Inspectors",
      "Fort Canning",
      "Opium Revenue",
    ]);
  });
});
