import type {
  QueryRequest,
  QueryResponse,
  SignedUrlResponse,
  PageTextResponse,
  GraphNode,
  GraphPayload,
  GraphOverviewPayload,
} from "../types";

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

const DEFAULT_TIMEOUT_MS = 60_000;
const QUERY_TIMEOUT_MS = 90_000;

async function request<T>(
  url: string,
  init?: RequestInit,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  // Compose timeout abort with any caller-provided signal so component
  // unmount / superseded-request cancellation still works. We do NOT
  // rely on AbortSignal.any (ES2024, not yet universally available).
  const callerSignal = init?.signal;
  let onCallerAbort: (() => void) | null = null;
  if (callerSignal) {
    if (callerSignal.aborted) {
      controller.abort();
    } else {
      onCallerAbort = () => controller.abort();
      callerSignal.addEventListener("abort", onCallerAbort, { once: true });
    }
  }

  try {
    const res = await fetch(url, { ...init, signal: controller.signal });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(
        `API error ${res.status}: ${body.detail ?? res.statusText}`,
      );
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      // Distinguish caller-cancelled from timeout-cancelled. If the
      // caller's signal triggered, surface that (so React StrictMode /
      // navigation aborts don't look like timeouts).
      if (callerSignal?.aborted) {
        throw err;
      }
      throw new Error(`Request timed out after ${timeoutMs / 1000}s`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
    if (callerSignal && onCallerAbort) {
      callerSignal.removeEventListener("abort", onCallerAbort);
    }
  }
}

export const apiClient = {
  // postQuery accepts an optional AbortSignal so callers (e.g. a
  // useEffect cleanup or a "supersede previous query" handler in
  // useAppStore.sendQuery) can cancel an in-flight request without
  // waiting for the 90s hard timeout. The wrapper composes this
  // signal with its own timeout controller — see request().
  postQuery(
    req: QueryRequest,
    options?: { signal?: AbortSignal },
  ): Promise<QueryResponse> {
    return request<QueryResponse>(
      `${API_BASE}/query`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
        signal: options?.signal,
      },
      QUERY_TIMEOUT_MS,
    );
  },

  getSignedUrl(docId: string, page: number): Promise<SignedUrlResponse> {
    return request<SignedUrlResponse>(
      `${API_BASE}/document/signed_url?doc_id=${encodeURIComponent(docId)}&page=${page}`,
      { method: "GET" }
    );
  },

  searchGraph(
    query: string,
    limit = 20,
    categories?: string[]
  ): Promise<GraphNode[]> {
    const params = new URLSearchParams({ q: query, limit: String(limit) });
    if (categories?.length) {
      categories.forEach((c) => params.append("categories", c));
    }
    return request<GraphNode[]>(`${API_BASE}/graph/search?${params}`, {
      method: "GET",
    });
  },

  listDocuments(): Promise<{ documents: string[] }> {
    return request<{ documents: string[] }>(`${API_BASE}/admin/documents`, {
      method: "GET",
    });
  },

  getPageText(docId: string, page: number): Promise<PageTextResponse> {
    return request<PageTextResponse>(
      `${API_BASE}/document/${encodeURIComponent(docId)}/pages/${page}/text`,
      { method: "GET" }
    );
  },

  getOverview(): Promise<GraphOverviewPayload> {
    return request<GraphOverviewPayload>(`${API_BASE}/graph/overview`, {
      method: "GET",
    });
  },

  getSubgraph(entityCanonicalId: string, categories?: string[]): Promise<GraphPayload> {
    const params = new URLSearchParams();
    if (categories?.length) {
      categories.forEach((category) => params.append("categories", category));
    }
    const query = params.toString();
    return request<GraphPayload>(
      `${API_BASE}/graph/${encodeURIComponent(entityCanonicalId)}${query ? `?${query}` : ""}`,
      { method: "GET" },
    );
  },

  getDocumentText(
    docId: string,
    pageStart?: number,
    pageEnd?: number,
  ): Promise<{ doc_id: string; total_pages: number; pages: Array<{ page_number: number; text: string; confidence: number }> }> {
    const params = new URLSearchParams();
    if (pageStart !== undefined) params.set("page_start", String(pageStart));
    if (pageEnd !== undefined) params.set("page_end", String(pageEnd));
    const qs = params.toString();
    const url = `${API_BASE}/document/${encodeURIComponent(docId)}/text${qs ? `?${qs}` : ""}`;
    return request(url);
  },

  getOcrQuality(docId: string): Promise<{
    doc_id: string;
    total_pages: number;
    avg_confidence: number;
    flagged_pages: { page: number; confidence: number }[];
    flagged_count: number;
  }> {
    return request(`${API_BASE}/admin/documents/${encodeURIComponent(docId)}/ocr`, {
      method: "GET",
    });
  },
};
