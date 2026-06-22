import type { Citation, GraphNode } from "../types";

export type ArchivePdfTarget = {
  readonly docId: string;
  readonly page: number;
};

export function getArchivePdfTarget(citation: Citation): ArchivePdfTarget | null {
  if (citation.type !== "archive") return null;

  const docId = citation.doc_id.trim();
  const page = citation.pages.find((candidate) => (
    Number.isInteger(candidate) && candidate > 0
  ));

  if (docId.length === 0 || page === undefined) return null;

  return { docId, page };
}

export function getArchivePdfTargetFromGraphNode(
  node: Pick<GraphNode, "evidence_doc_id" | "evidence_page">,
): ArchivePdfTarget | null {
  const docId = node.evidence_doc_id?.trim() ?? "";
  const page = node.evidence_page;

  if (
    docId.length === 0 ||
    typeof page !== "number" ||
    !Number.isInteger(page) ||
    page <= 0
  ) {
    return null;
  }

  return { docId, page };
}

export function extractEntityNameFromCitationText(textSpan: string): string | null {
  const entityMatch = /^\s*Entity:\s*(.+?)\s*$/i.exec(textSpan);
  if (!entityMatch) return null;

  const rawEntity = entityMatch[1].trim();
  const entityWithTrailingMetadata = /^(.*?)\.\s*(?:[\w -]+:\s*.+)?$/.exec(rawEntity);
  const entityName = (entityWithTrailingMetadata?.[1] ?? rawEntity)
    .replace(/\.$/, "")
    .trim();

  return entityName.length > 0 ? entityName : null;
}
