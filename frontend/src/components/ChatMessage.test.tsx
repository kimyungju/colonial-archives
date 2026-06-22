import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ChatMessage from "./ChatMessage";
import { useAppStore } from "../stores/useAppStore";
import type { ChatMessage as ChatMessageType } from "../types";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

beforeEach(() => {
  mockFetch.mockReset();
  mockFetch.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve([]),
  });

  useAppStore.setState({
    isPdfModalOpen: false,
    pdfModalProps: null,
  });
});

describe("ChatMessage", () => {
  it("does not open the PDF modal for unresolved archive citations without a document id", async () => {
    const message: ChatMessageType = {
      role: "assistant",
      content: "Opium revenues are recorded [archive:1].",
      citations: [
        {
          type: "archive",
          id: 1,
          doc_id: "",
          pages: [],
          text_span: "Entity: opium revenues.",
          confidence: 0.8,
        },
      ],
      source_type: "archive",
    };

    render(<ChatMessage message={message} />);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/graph/search?q=opium+revenues&limit=1",
        expect.objectContaining({ method: "GET" }),
      );
    });
    expect(screen.queryByRole("button", { name: "[1]" })).not.toBeInTheDocument();
    expect(screen.getByText("Entity: opium revenues.")).toBeInTheDocument();
    expect(useAppStore.getState().isPdfModalOpen).toBe(false);
  });

  it("resolves entity-only archive citations to clickable PDF sources", async () => {
    const user = userEvent.setup();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            canonical_id: "india_financial_consultations",
            name: "India Financial Consultations",
            main_categories: ["Economic and Financial"],
            sub_category: null,
            attributes: {},
            highlighted: false,
            evidence_doc_id: "Trocki Opium",
            evidence_page: 259,
            evidence_text_span: "India Financial Consultations",
            evidence_confidence: 0.86,
          },
        ]),
    });
    const message: ChatMessageType = {
      role: "assistant",
      content: "Financial records include India Financial Consultations [archive:1].",
      citations: [
        {
          type: "archive",
          id: 1,
          doc_id: "",
          pages: [],
          text_span: "Entity: India Financial Consultations.",
          confidence: 0.8,
        },
      ],
      source_type: "archive",
    };

    render(<ChatMessage message={message} />);

    const inlineCitationButton = await screen.findByRole("button", { name: "[1]" });
    expect(screen.getByText("Trocki Opium")).toBeInTheDocument();
    expect(screen.getByText("p.259")).toBeInTheDocument();

    await user.click(inlineCitationButton);

    expect(useAppStore.getState().pdfModalProps).toEqual({
      docId: "Trocki Opium",
      page: 259,
    });
  });

  it("opens the PDF modal for archive citations with a document id", async () => {
    const user = userEvent.setup();
    const message: ChatMessageType = {
      role: "assistant",
      content: "Revenue account [archive:1].",
      citations: [
        {
          type: "archive",
          id: 1,
          doc_id: "CO 273:550:8",
          pages: [4],
          text_span: "Revenue account.",
          confidence: 0.9,
        },
      ],
      source_type: "archive",
    };

    render(<ChatMessage message={message} />);

    await user.click(screen.getAllByRole("button", { name: "[1]" })[0]);

    expect(useAppStore.getState().pdfModalProps).toEqual({
      docId: "CO 273:550:8",
      page: 4,
    });
  });
});
