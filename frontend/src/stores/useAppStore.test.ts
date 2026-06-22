import { describe, it, expect, beforeEach } from "vitest";
import { useAppStore } from "./useAppStore";

// Reset store between tests
beforeEach(() => {
  useAppStore.setState({
    messages: [],
    isQuerying: false,
    queryError: null,
    filterCategories: [],
    graphData: null,
    selectedNode: null,
    overviewData: null,
    isOverviewMode: true,
    hiddenCategories: new Set<string>(),
    splitRatio: 0.65,
    isSidebarOpen: false,
    isPdfModalOpen: false,
    pdfModalProps: null,
    chatInput: "",
  });
});

describe("useAppStore", () => {
  it("has correct initial state", () => {
    const state = useAppStore.getState();
    expect(state.messages).toEqual([]);
    expect(state.isQuerying).toBe(false);
    expect(state.splitRatio).toBe(0.65);
    expect(state.graphData).toBeNull();
    expect(state.filterCategories).toEqual([]);
  });

  it("selectNode opens sidebar", () => {
    const node = {
      canonical_id: "e1",
      name: "Raffles",
      main_categories: ["General and Establishment"],
      sub_category: null,
      attributes: {},
      highlighted: false,
    };
    useAppStore.getState().selectNode(node);
    const state = useAppStore.getState();
    expect(state.selectedNode).toEqual(node);
    expect(state.isSidebarOpen).toBe(true);
  });

  it("selectNode(null) closes sidebar", () => {
    useAppStore.getState().selectNode(null);
    const state = useAppStore.getState();
    expect(state.selectedNode).toBeNull();
    expect(state.isSidebarOpen).toBe(false);
  });

  it("openPdfModal sets modal props", () => {
    useAppStore.getState().openPdfModal("doc_042", 5);
    const state = useAppStore.getState();
    expect(state.isPdfModalOpen).toBe(true);
    expect(state.pdfModalProps).toEqual({ docId: "doc_042", page: 5 });
  });

  it("openPdfModal ignores blank document ids", () => {
    useAppStore.getState().openPdfModal("", 1);
    const state = useAppStore.getState();
    expect(state.isPdfModalOpen).toBe(false);
    expect(state.pdfModalProps).toBeNull();
  });

  it("closePdfModal clears modal", () => {
    useAppStore.getState().openPdfModal("doc_042", 5);
    useAppStore.getState().closePdfModal();
    const state = useAppStore.getState();
    expect(state.isPdfModalOpen).toBe(false);
    expect(state.pdfModalProps).toBeNull();
  });

  it("setSplitRatio clamps between 0.3 and 0.7", () => {
    useAppStore.getState().setSplitRatio(0.1);
    expect(useAppStore.getState().splitRatio).toBe(0.3);

    useAppStore.getState().setSplitRatio(0.9);
    expect(useAppStore.getState().splitRatio).toBe(0.7);

    useAppStore.getState().setSplitRatio(0.5);
    expect(useAppStore.getState().splitRatio).toBe(0.5);
  });

  it("setFilterCategories replaces categories", () => {
    useAppStore
      .getState()
      .setFilterCategories(["Economic and Financial", "Social Services"]);
    expect(useAppStore.getState().filterCategories).toEqual([
      "Economic and Financial",
      "Social Services",
    ]);
  });

  it("setChatInput updates input text", () => {
    useAppStore.getState().setChatInput("Tell me about Raffles");
    expect(useAppStore.getState().chatInput).toBe("Tell me about Raffles");
  });

  it("toggleCategory adds and removes categories", () => {
    const { toggleCategory } = useAppStore.getState();
    toggleCategory("Defence and Military");
    expect(useAppStore.getState().hiddenCategories.has("Defence and Military")).toBe(true);
    toggleCategory("Defence and Military");
    expect(useAppStore.getState().hiddenCategories.has("Defence and Military")).toBe(false);
  });

  it("setOverviewMode switches between overview and query mode", () => {
    const { setOverviewMode } = useAppStore.getState();
    setOverviewMode(true);
    expect(useAppStore.getState().isOverviewMode).toBe(true);
    setOverviewMode(false);
    expect(useAppStore.getState().isOverviewMode).toBe(false);
  });
});
