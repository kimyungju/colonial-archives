import { describe, expect, it } from "vitest";
import type { Citation } from "../types";
import {
  extractEntityNameFromCitationText,
  getArchivePdfTarget,
  getArchivePdfTargetFromGraphNode,
} from "./citationTraceability";

describe("getArchivePdfTarget", () => {
  it("returns null for archive citations without a document id", () => {
    const citation: Citation = {
      type: "archive",
      id: 1,
      doc_id: "",
      pages: [],
      text_span: "Entity: opium revenues.",
      confidence: 0.8,
    };

    expect(getArchivePdfTarget(citation)).toBeNull();
  });

  it("returns a normalized PDF target for archive citations with a page", () => {
    const citation: Citation = {
      type: "archive",
      id: 2,
      doc_id: " CO 273:550:8 ",
      pages: [4],
      text_span: "Revenue account.",
      confidence: 0.9,
    };

    expect(getArchivePdfTarget(citation)).toEqual({
      docId: "CO 273:550:8",
      page: 4,
    });
  });

  it("returns null for web citations", () => {
    const citation: Citation = {
      type: "web",
      id: 3,
      title: "Reference",
      url: "https://example.com",
    };

    expect(getArchivePdfTarget(citation)).toBeNull();
  });
});

describe("getArchivePdfTargetFromGraphNode", () => {
  it("returns a PDF target for graph nodes with evidence", () => {
    expect(
      getArchivePdfTargetFromGraphNode({
        evidence_doc_id: " Trocki Opium ",
        evidence_page: 259,
      }),
    ).toEqual({
      docId: "Trocki Opium",
      page: 259,
    });
  });

  it("returns null for graph nodes without usable evidence", () => {
    expect(
      getArchivePdfTargetFromGraphNode({
        evidence_doc_id: "",
        evidence_page: 259,
      }),
    ).toBeNull();
    expect(
      getArchivePdfTargetFromGraphNode({
        evidence_doc_id: "Trocki Opium",
        evidence_page: 0,
      }),
    ).toBeNull();
  });
});

describe("extractEntityNameFromCitationText", () => {
  it("extracts the entity name from graph-only citation text", () => {
    expect(
      extractEntityNameFromCitationText("Entity: India Financial Consultations."),
    ).toBe("India Financial Consultations");
  });

  it("drops trailing entity metadata from graph-only citation text", () => {
    expect(
      extractEntityNameFromCitationText(
        "Entity: Singapore national accounts 1987. year: 1987",
      ),
    ).toBe("Singapore national accounts 1987");
  });

  it("keeps abbreviations inside entity names", () => {
    expect(
      extractEntityNameFromCitationText("Entity: Captain S. W. Kirby."),
    ).toBe("Captain S. W. Kirby");
  });

  it("returns null for ordinary archive text", () => {
    expect(extractEntityNameFromCitationText("Revenue account.")).toBeNull();
  });
});
