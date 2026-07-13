/**
 * AiAssistantFloating — a context-aware AI helper for the Invigilo app.
 *
 * Collapsed: a single floating pill in the bottom-right with a sparkle icon
 * and a small "Ask" label + live status dot.
 *
 * Expanded: a proper chat panel that opens from the bottom-right with
 *   - a dark emerald header (matches the sidebar/Topbar dark surfaces)
 *   - a scrollable transcript (assistant bubbles on the left, user bubbles
 *     on the right) with reply-driven suggestion chips
 *   - a per-message "What the AI saw" disclosure that renders the live
 *     context payload so the user can audit what the reply was grounded in
 *   - a composer at the bottom with an auto-growing textarea + send button
 *
 * The assistant is rule-based and live: every user message is POSTed to
 * ``/api/v1/ai/chat/`` (see ``backend/apps/ai/services.py``). The reply is
 * deterministic and cites real DB values from the active period, latest
 * run, open conflicts, and invigilator pool. The four seed chips below
 * the empty state are just hand-written prompts; once a chat starts the
 * chip set is replaced by the backend's intent-driven suggestions.
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
import { postAiChat, type AiChatContext } from "@/lib/api";

type Sender = "user" | "assistant";

type Suggestion = {
  label?: string;
  prompt: string;
};

type Message = {
  id: string;
  sender: Sender;
  text: string;
  /** ISO timestamp; the UI formats it as a short time (HH:MM). */
  at: string;
  /** Backend's intent classification, when the message is from the assistant. */
  intent?: string;
  /** Reply-driven suggestions — only present on assistant messages. */
  suggestions?: string[];
  /** Live context the assistant's reply was grounded in. */
  context?: AiChatContext;
};

/**
 * Seed prompts shown when the transcript is empty. These are the
 * highest-signal questions a fresh user will ask; the real
 * intent-driven chips come back from the backend on the first reply.
 */
const SEED_PROMPTS: Suggestion[] = [
  { prompt: "What's the status of the current cycle?" },
  { prompt: "What conflicts is the engine reporting?" },
  { prompt: "Show today's sessions" },
  { prompt: "How many invigilators are available today?" },
];

/** Friendly fallback when the backend errors out. */
const OFFLINE_REPLY =
  "The assistant is offline right now. Check your network and try again in a moment.";

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

const formatContextTime = (iso: string) => {
  try {
    return new Date(iso).toLocaleString([], {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
};

/** Render a single context field in the disclosure list. */
function contextRow(label: string, value: string | number | null): string {
  return `${label}: ${value === null || value === "" ? "—" : String(value)}`;
}

export function AiAssistantFloating() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  /** The id of the assistant message whose "What the AI saw" panel is open. */
  const [expandedContextId, setExpandedContextId] = useState<string | null>(null);

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

  const send = useCallback(
    async (text: string) => {
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
      try {
        const reply = await postAiChat(trimmed);
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            sender: "assistant",
            text: reply.reply,
            at: new Date().toISOString(),
            intent: reply.intent,
            suggestions: reply.suggestions,
            context: reply.context,
          },
        ]);
      } catch {
        // Network or 5xx — surface a friendly bubble and re-enable the composer.
        setMessages((prev) => [
          ...prev,
          {
            id: newId(),
            sender: "assistant",
            text: OFFLINE_REPLY,
            at: new Date().toISOString(),
            intent: "error",
          },
        ]);
      } finally {
        setIsThinking(false);
      }
    },
    [isThinking],
  );

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    void send(draft);
  };

  const handleComposerKeyDown = (e: ReactKeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send(draft);
    }
  };

  const clearTranscript = () => {
    setMessages([]);
    setDraft("");
    setExpandedContextId(null);
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
                  Fed live from your database
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
                    <div className="max-w-[78%]">
                      <div
                        className={
                          m.sender === "user"
                            ? "rounded-2xl rounded-br-md bg-brand-700 px-3.5 py-2.5 text-sm text-white shadow-sm shadow-brand-900/20"
                            : "rounded-2xl rounded-bl-md bg-surface px-3.5 py-2.5 text-sm text-ink-900 ring-1 ring-ink-200"
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
                          {m.sender === "assistant" && m.intent
                            ? `${formatTime(m.at)} · ${m.intent}`
                            : formatTime(m.at)}
                        </p>
                      </div>

                      {/* Reply-driven suggestion chips from the backend. */}
                      {m.sender === "assistant" &&
                      m.suggestions &&
                      m.suggestions.length > 0 ? (
                        <div className="mt-1.5 flex flex-wrap gap-1.5">
                          {m.suggestions.map((s) => (
                            <button
                              key={s}
                              type="button"
                              onClick={() => void send(s)}
                              className="rounded-full bg-brand-50 px-2.5 py-1 text-[11px] font-semibold text-brand-800 ring-1 ring-inset ring-brand-100 transition hover:bg-brand-100 hover:ring-brand-200"
                            >
                              {s}
                            </button>
                          ))}
                        </div>
                      ) : null}

                      {/* "What the AI saw" disclosure — only on assistant messages
                          that came back with a context payload. */}
                      {m.sender === "assistant" && m.context ? (
                        <div className="mt-1.5">
                          <button
                            type="button"
                            onClick={() =>
                              setExpandedContextId(
                                expandedContextId === m.id ? null : m.id,
                              )
                            }
                            className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400 transition hover:text-ink-700"
                            aria-expanded={expandedContextId === m.id}
                          >
                            {expandedContextId === m.id
                              ? "Hide context"
                              : "What the AI saw"}
                          </button>
                          {expandedContextId === m.id ? (
                            <div className="mt-1 rounded-xl bg-ink-100/70 p-2.5 text-[11px] leading-relaxed text-ink-700 ring-1 ring-inset ring-ink-200">
                              {[
                                contextRow(
                                  "Active period",
                                  m.context.active_period,
                                ),
                                contextRow(
                                  "Upcoming sessions",
                                  m.context.upcoming_session_count,
                                ),
                                contextRow(
                                  "Open conflicts",
                                  m.context.open_conflict_count,
                                ),
                                contextRow(
                                  "Open incidents",
                                  m.context.open_incident_count,
                                ),
                                contextRow(
                                  "Invigilators",
                                  m.context.invigilator_total,
                                ),
                                contextRow(
                                  "Unavailable today",
                                  m.context.invigilator_unavailable_today,
                                ),
                                contextRow(
                                  "Latest run coverage",
                                  m.context.latest_run_coverage === null
                                    ? null
                                    : `${Math.round(
                                        m.context.latest_run_coverage * 100,
                                      )}%`,
                                ),
                                `Generated at: ${formatContextTime(
                                  m.context.generated_at,
                                )}`,
                              ].map((line) => (
                                <p key={line.split(":")[0]}>{line}</p>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
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
                  Ask about exams, allocations, conflicts, or incident
                  handling. Replies cite the live state of your database.
                </p>
              </div>
            )}
          </div>

          {/* Suggested prompts (shown until the user has chatted) */}
          {!hasMessages ? (
            <div className="border-t border-ink-100 bg-surface px-4 py-3">
              <p className="eyebrow mb-2 text-ink-500">Try asking</p>
              <div className="flex flex-wrap gap-2">
                {SEED_PROMPTS.map((s) => (
                  <button
                    key={s.prompt}
                    type="button"
                    onClick={() => void send(s.prompt)}
                    className="rounded-full bg-brand-50 px-3 py-1.5 text-xs font-semibold text-brand-800 ring-1 ring-inset ring-brand-100 transition hover:bg-brand-100 hover:ring-brand-200"
                  >
                    {s.prompt}
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
