interface LoadingGraphStateProps {
  readonly retryCount: number;
}

interface ErrorGraphStateProps {
  readonly message: string;
  readonly onRetry: () => void;
}

interface EmptyGraphStateProps {
  readonly onClearFocus: () => void;
}

export function LoadingGraphState({ retryCount }: LoadingGraphStateProps) {
  return (
    <div className="flex h-full items-center justify-center bg-stone-900">
      <div className="text-center animate-fade-in">
        <div className="relative mx-auto mb-6 h-24 w-24">
          <div className="absolute inset-0 animate-ping rounded-full border border-stone-700/40 [animation-duration:3s]" />
          <div className="absolute inset-3 animate-ping rounded-full border border-stone-600/30 [animation-delay:0.5s] [animation-duration:2.5s]" />
          <div className="absolute inset-6 animate-ping rounded-full border border-stone-500/20 [animation-delay:1s] [animation-duration:2s]" />
          <div className="absolute inset-[2.25rem] rounded-full bg-ink-500/20" />
        </div>
        <p className="font-display text-sm text-stone-400">
          Loading knowledge graph&hellip;
        </p>
        <p className="mt-1 text-xs text-stone-600">
          {retryCount > 0
            ? `Waking up database... attempt ${retryCount + 1} of 6`
            : "Connecting to archive database"}
        </p>
      </div>
    </div>
  );
}

export function ErrorGraphState({ message, onRetry }: ErrorGraphStateProps) {
  return (
    <div className="flex h-full items-center justify-center bg-stone-900">
      <div className="max-w-sm text-center animate-fade-in">
        <p className="mb-1 font-display text-base text-stone-300">
          Could not load knowledge graph
        </p>
        <p className="mb-4 text-xs text-stone-500">{message}</p>
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md border border-stone-700 bg-stone-800 px-4 py-2 text-sm text-stone-300 transition-colors hover:bg-stone-700 hover:text-stone-100"
        >
          Retry connection
        </button>
      </div>
    </div>
  );
}

export function EmptyGraphState({ onClearFocus }: EmptyGraphStateProps) {
  return (
    <div className="flex h-full items-center justify-center bg-stone-900">
      <div className="text-center">
        <p className="font-display text-base text-stone-300">
          No graph nodes match the current filters
        </p>
        <button
          type="button"
          onClick={onClearFocus}
          className="mt-3 rounded-md border border-stone-700 px-3 py-1.5 text-sm text-stone-300 transition-colors hover:border-stone-500 hover:text-stone-100"
        >
          Clear community focus
        </button>
      </div>
    </div>
  );
}
