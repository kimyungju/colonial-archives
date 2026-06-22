import type { Citation } from "../types";
import { useAppStore } from "../stores/useAppStore";
import { getArchivePdfTarget } from "../utils/citationTraceability";

interface Props {
  citation: Citation;
}

export default function CitationBadge({ citation }: Props) {
  const openPdfModal = useAppStore((s) => s.openPdfModal);

  if (citation.type === "archive") {
    const pdfTarget = getArchivePdfTarget(citation);
    if (!pdfTarget) {
      return (
        <span
          className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded text-xs font-medium bg-stone-700/30 text-stone-400 font-mono"
          title={citation.text_span}
        >
          {citation.text_span || "Graph evidence"}
        </span>
      );
    }

    return (
      <button
        className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded text-xs font-medium bg-ink-500/20 text-ink-400 hover:bg-ink-500/30 transition-colors cursor-pointer font-mono"
        title={citation.text_span}
        onClick={() => openPdfModal(pdfTarget.docId, pdfTarget.page)}
      >
        {pdfTarget.docId}:p{pdfTarget.page}
      </button>
    );
  }

  return (
    <a
      href={citation.url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center px-1.5 py-0.5 mx-0.5 rounded text-xs font-medium bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 transition-colors"
      title={citation.title}
    >
      {citation.title}
    </a>
  );
}
