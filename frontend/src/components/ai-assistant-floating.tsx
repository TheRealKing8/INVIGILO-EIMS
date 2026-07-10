/**
 * AiAssistantFloating — a context-aware AI helper for the Invigilo app.
 *
 * Collapsed: a single floating pill in the bottom-right with a sparkle icon
 * and a small "Ask" label + live status dot.
 *
 * Expanded: a proper chat panel that opens from the bottom-right with
 *   - a dark emerald header (matches the sidebar/Topbar dark surfaces)
 *   - a scrollable transcript (assistant bubbles on the left, user bubbles
 *     on the right) with suggested prompts at the bottom of an empty list
 *   - a composer at the bottom with an auto-growing textarea + send button
 *
 * Stub backend: until a /api/v1/ai/chat/ endpoint exists, the assistant
 * answers locally with canned responses for the suggested prompts and a
 * generic fallback for free-form input. The hook point is marked TODO.
 *
 * Accessibility:
 *   - role="dialog" + aria-label when open
 *   - focus moves to the composer on open
 *   - Esc closes the panel
 *   - click outside closes
 *   - aria-live="polite" on the transcript for screen readers
 */
"use client";

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";

import { Icon } from "@/components/ui/icon";

type Sender = "user" | "assistant";

type Message = {
  id: string;
  sender: Sender;
  text: string;
  /** ISO timestamp; the UI formats it as a short time (HH:MM). */
  at: string;
};

type Suggestion = {
  label: string;
  prompt: string;
  reply: string;
};

const SUGGESTIONS: Suggestion[] = [
  {
    label: "Today's exams",
    prompt: "What exams are scheduled for today?",
    reply:
      "Open the Examinations tab to see the live schedule for the current period. The Overview card on the dashboard shows the next sessions with date, time, room, and invigilator count.",
  },
  {
    label: "Run allocations",
    prompt: "How do I run the allocation engine?",
    reply:
      "Go to Allocations → click 'Run engine' against the active period. The engine respects workload caps, no double-booking, and cross-department pairing. Conflicts are recorded on the run.",
  },
  {
    label: "Log an incident",
    prompt: "How do I log an incident?",
    reply:
      "On the Incidents tab, click 'Log incident' — fill in the title, body, and severity. You can also update the status (open → investigating → escalated → resolved) inline on the row.",
  },
  {
    label: "Export a report",
    prompt: "Can I export a PDF report?",
    reply:
      "Yes. Open the Reports tab, click 'New export', pick a format (PDF, Excel, or CSV) and an audience. When generation finishes, hit 'Download' on the row to pull the file.",
  },
];

const FALLBACK_REPLY =
  "I'm a local assistant for now. Try one of the suggested prompts above, or open the relevant dashboard tab for live data.";

const newId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `m-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const formatTime = (iso: string) => {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
};

export function AiAssistantFloating() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [isThinking, setIsThinking] = useState(false);

  const panelRef = useRef<HTMLDivElement | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const transcriptRef = useRef<HTMLDivElement | null>(null);
  const headingId = useId();

  const hasMessages = messages.length > 0;

  /* Focus the composer when the panel opens. */
  useEffect(() => {
    if (!isOpen) return;
    const t = window.setTimeout(() => composerRef.current?.focus(), 60);
    return () => window.clearTimeout(t);
  }, [isOpen]);

  /* Click outside closes the panel. */
  useEffect(() => {
    if (!isOpen) return;
    function onDown(e: MouseEvent) {
      if (!panelRef.current) return;
      if (!panelRef.current.contains(e.target as Node)) setIsOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [isOpen]);

  /* Esc closes the panel. */
  useEffect(() => {
    if (!isOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setIsOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [isOpen]);

  /* Keep the transcript scrolled to the bottom as messages stream in. */
  useEffect(() => {
    const el = transcriptRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, isThinking]);

  const replyFor = useCallback((input: string): string => {
    const match = SUGGESTIONS.find(
      (s) =>
        s.prompt.toLowerCase() === input.trim().toLowerCase() ||
        s.label.toLowerCase() === input.trim().toLowerCase(),
    );
    if (match) return match.reply;
    return FALLBACK_REPLY;
  }, []);

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isThinking) return;
      const userMessage: Message = {
        id: newId(),
        sender: "user",
        text: trimmed,
        at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setDraft("");
      setIsThinking(true);
      // TODO: POST /api/v1/ai/chat/ — until that endpoint exists, the
      // assistant answers locally after a brief "thinking" beat.
      window.setTimeout(() => {
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            sender: "assistant",
            text: replyFor(trimmed),
            at: new Date().toISOString(),
          },
        ]);
        setIsThinking(false);
      }, 650);
    },
    [isThinking, replyFor],
  );

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    send(draft);
  };

  const handleComposerKeyDown = (e: ReactKeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(draft);
    }
  };

  const clearTranscript = () => {
    setMessages([]);
    setDraft("");
  };

  const composerAriaLabel = useMemo(
    () => "Ask the Invigilo assistant a question",
    [],
  );

  return (
    <div className="fixed bottom-4 right-4 z-50 sm:bottom-6 sm:right-6">
      {isOpen ? (
        <div
          ref={panelRef}
          role="dialog"
          aria-labelledby={headingId}
          aria-label="Invigilo assistant"
          className="mb-3 flex h-[560px] max-h-[80vh] w-[min(380px,calc(100vw-2rem))] flex-col overflow-hidden rounded-3xl bg-surface shadow-[var(--shadow-elev)] ring-1 ring-ink-200"
        >
          {/* Header — dark emerald to match the sidebar / Topbar dark surface */}
          <div className="relative flex items-center justify-between gap-3 bg-surface-dark px-5 py-4 text-white">
            <div className="flex items-center gap-3">
              <span
                aria-hidden
                className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/10 text-white ring-1 ring-inset ring-white/10"
              >
                <Icon name="sparkle" className="h-5 w-5" />
              </span>
              <div className="min-w-0 leading-tight">
                <p id={headingId} className="text-sm font-semibold">
                  Invigilo Assistant
                </p>
                <p className="flex items-center gap-1.5 text-[11px] text-brand-200/80">
                  <span
                    aria-hidden
                    className="h-1.5 w-1.5 rounded-full bg-brand-400 pulse-ring"
                  />
                  Smart help for exam operations
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              {hasMessages ? (
                <button
                  type="button"
                  onClick={clearTranscript}
                  className="rounded-full px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-brand-200/80 transition hover:bg-white/10 hover:text-white"
                >
                  Clear
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                aria-label="Close assistant"
                className="inline-flex h-9 w-9 items-center justify-center rounded-full text-brand-100/80 transition hover:bg-white/10 hover:text-white"
              >
                <Icon name="x" className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Transcript */}
          <div
            ref={transcriptRef}
            aria-live="polite"
            className="flex-1 overflow-y-auto bg-ink-100/40 px-4 py-4"
          >
            {hasMessages ? (
              <ol className="space-y-3">
                {messages.map((m) => (
                  <li
                    key={m.id}
                    className={
                      m.sender === "user"
                        ? "flex justify-end"
                        : "flex items-end gap-2"
                    }
                  >
                    {m.sender === "assistant" ? (
                      <span
                        aria-hidden
                        className="mb-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-700 text-white ring-1 ring-inset ring-brand-800"
                      >
                        <Icon name="sparkle" className="h-3.5 w-3.5" />
                      </span>
                    ) : null}
                    <div
                      className={
                        m.sender === "user"
                          ? "max-w-[78%] rounded-2xl rounded-br-md bg-brand-700 px-3.5 py-2.5 text-sm text-white shadow-sm shadow-brand-900/20"
                          : "max-w-[78%] rounded-2xl rounded-bl-md bg-surface px-3.5 py-2.5 text-sm text-ink-900 ring-1 ring-ink-200"
                      }
                    >
                      <p className="whitespace-pre-wrap leading-relaxed">{m.text}</p>
                      <p
                        className={
                          m.sender === "user"
                            ? "mt-1 text-right text-[10px] font-medium uppercase tracking-[0.14em] text-brand-100/70"
                            : "mt-1 text-[10px] font-medium uppercase tracking-[0.14em] text-ink-400"
                        }
                      >
                        {formatTime(m.at)}
                      </p>
                    </div>
                  </li>
                ))}
                {isThinking ? (
                  <li
                    aria-label="Assistant is typing"
                    className="flex items-end gap-2"
                  >
                    <span
                      aria-hidden
                      className="mb-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-700 text-white ring-1 ring-inset ring-brand-800"
                    >
                      <Icon name="sparkle" className="h-3.5 w-3.5" />
                    </span>
                    <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-md bg-surface px-3.5 py-3 ring-1 ring-ink-200">
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-400" />
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-400 [animation-delay:120ms]" />
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-400 [animation-delay:240ms]" />
                    </div>
                  </li>
                ) : null}
              </ol>
            ) : (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <span
                  aria-hidden
                  className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-700 ring-1 ring-inset ring-brand-100"
                >
                  <Icon name="sparkle" className="h-6 w-6" />
                </span>
                <p className="mt-3 text-sm font-semibold text-ink-900">
                  Hi, I&apos;m here to help.
                </p>
                <p className="mt-1 max-w-[260px] text-xs leading-relaxed text-ink-500">
                  Ask about exams, allocations, reports, or incident handling. Or
                  start with a prompt below.
                </p>
              </div>
            )}
          </div>

          {/* Suggested prompts (shown until the user has chatted) */}
          {!hasMessages ? (
            <div className="border-t border-ink-100 bg-surface px-4 py-3">
              <p className="eyebrow mb-2 text-ink-500">Suggested</p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s.label}
                    type="button"
                    onClick={() => send(s.prompt)}
                    className="rounded-full bg-brand-50 px-3 py-1.5 text-xs font-semibold text-brand-800 ring-1 ring-inset ring-brand-100 transition hover:bg-brand-100 hover:ring-brand-200"
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {/* Composer */}
          <form
            onSubmit={handleSubmit}
            className="flex items-end gap-2 border-t border-ink-100 bg-surface px-3 py-3"
          >
            <label className="sr-only" htmlFor={`${headingId}-composer`}>
              {composerAriaLabel}
            </label>
            <textarea
              id={`${headingId}-composer`}
              ref={composerRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleComposerKeyDown}
              placeholder="Ask the assistant…"
              rows={1}
              aria-label={composerAriaLabel}
              className="min-h-[44px] max-h-32 flex-1 resize-none rounded-2xl bg-ink-100/60 px-3.5 py-2.5 text-sm text-ink-900 placeholder:text-ink-400 ring-1 ring-inset ring-ink-200 transition focus:bg-surface focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <button
              type="submit"
              disabled={!draft.trim() || isThinking}
              aria-label="Send message"
              className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-700 text-white shadow-sm shadow-brand-900/20 transition hover:bg-brand-800 active:bg-brand-900 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Icon name="arrow-up-right" className="h-4 w-4" />
            </button>
          </form>
        </div>
      ) : null}

      {/* Collapsed pill — bottom-right floating action button */}
      <button
        type="button"
        onClick={() => setIsOpen((value) => !value)}
        aria-expanded={isOpen}
        aria-label={isOpen ? "Close AI assistant" : "Open AI assistant"}
        className="group inline-flex h-12 items-center gap-2.5 rounded-full bg-brand-700 pl-3 pr-5 text-sm font-semibold text-white shadow-[var(--shadow-elev)] ring-1 ring-inset ring-brand-800/40 transition hover:bg-brand-800 active:bg-brand-900"
      >
        <span
          aria-hidden
          className="relative flex h-9 w-9 items-center justify-center rounded-full bg-white/10 ring-1 ring-inset ring-white/15"
        >
          <Icon name="sparkle" className="h-4 w-4" />
          <span
            aria-hidden
            className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-brand-400 ring-2 ring-brand-700 pulse-ring"
          />
        </span>
        <span className="hidden sm:inline">Ask Invigilo</span>
      </button>
    </div>
  );
}
