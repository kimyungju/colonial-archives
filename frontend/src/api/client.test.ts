import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient } from "./client";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

beforeEach(() => {
  mockFetch.mockReset();
});

describe("apiClient", () => {
  it("postQuery sends POST with correct body", async () => {
    const mockResponse = {
      answer: "Test answer",
      source_type: "archive",
      citations: [],
      graph: null,
    };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const result = await apiClient.postQuery({
      question: "Who governed the Straits?",
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/query",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: "Who governed the Straits?" }),
      })
    );
    expect(result.answer).toBe("Test answer");
  });

  it("postQuery includes filter_categories when provided", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          answer: "",
          source_type: "archive",
          citations: [],
          graph: null,
        }),
    });

    await apiClient.postQuery({
      question: "Trade routes?",
      filter_categories: ["Economic and Financial"],
    });

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.filter_categories).toEqual(["Economic and Financial"]);
  });

  it("getSignedUrl sends GET with query params", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({ url: "https://signed.url", expires_in: 900 }),
    });

    const result = await apiClient.getSignedUrl("doc_042", 5);

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/document/signed_url?doc_id=doc_042&page=5",
      expect.objectContaining({ method: "GET" })
    );
    expect(result.url).toBe("https://signed.url");
  });

  it("searchGraph sends GET with query params", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([]),
    });

    await apiClient.searchGraph("Raffles", 10);

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/graph/search?q=Raffles&limit=10",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("searchGraph includes categories when provided", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([]),
    });

    await apiClient.searchGraph("Raffles", 20, ["Defence and Military"]);

    const url = mockFetch.mock.calls[0][0];
    expect(url).toContain("categories=Defence+and+Military");
  });

  it("throws on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: "Internal error" }),
    });

    await expect(apiClient.postQuery({ question: "test" })).rejects.toThrow(
      "API error 500"
    );
  });
});

describe("apiClient timeout", () => {
  it("postQuery aborts after the timeout and surfaces a clear error", async () => {
    vi.useFakeTimers();
    try {
      const mockFetch = vi.fn();
      vi.stubGlobal("fetch", mockFetch);

      let abortSignal: AbortSignal | undefined;
      mockFetch.mockImplementation((_url: string, init: RequestInit) => {
        abortSignal = init.signal as AbortSignal;
        return new Promise((_resolve, reject) => {
          if (abortSignal) {
            abortSignal.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError")),
            );
          }
        });
      });

      const promise = apiClient.postQuery({ question: "anything" });
      // Attach the rejection assertion BEFORE advancing timers so the
      // rejection isn't briefly unhandled (which vitest flags as an
      // unhandled error even when the assertion later catches it).
      const assertion = expect(promise).rejects.toThrow(/timed out/i);

      await vi.advanceTimersByTimeAsync(91_000);
      await assertion;
    } finally {
      vi.useRealTimers();
    }
  });

  it("caller-provided AbortSignal cancels the request before the timeout", async () => {
    const mockFetch = vi.fn();
    vi.stubGlobal("fetch", mockFetch);

    mockFetch.mockImplementation((_url: string, init: RequestInit) => {
      return new Promise((_resolve, reject) => {
        (init.signal as AbortSignal).addEventListener("abort", () =>
          reject(new DOMException("Aborted", "AbortError")),
        );
      });
    });

    const controller = new AbortController();
    const promise = apiClient.postQuery(
      { question: "anything" },
      { signal: controller.signal },
    );

    controller.abort();

    await expect(promise).rejects.toThrow();
    await expect(promise).rejects.not.toThrow(/timed out/i);
  });

  it("already-aborted signal rejects without making a fetch call", async () => {
    const mockFetch = vi.fn();
    vi.stubGlobal("fetch", mockFetch);

    mockFetch.mockImplementation((_url: string, init: RequestInit) => {
      return new Promise((_resolve, reject) => {
        if ((init.signal as AbortSignal).aborted) {
          reject(new DOMException("Aborted", "AbortError"));
          return;
        }
        (init.signal as AbortSignal).addEventListener("abort", () =>
          reject(new DOMException("Aborted", "AbortError")),
        );
      });
    });

    const controller = new AbortController();
    controller.abort();

    const promise = apiClient.postQuery(
      { question: "anything" },
      { signal: controller.signal },
    );

    await expect(promise).rejects.toThrow();
  });
});
