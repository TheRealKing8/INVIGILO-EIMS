/**
 * AiAssistantFab — floating action button + chat panel.
 *
 * Mounted once on every dashboard page (via DashboardShell). Bottom-right
 * pill, expands into a chat panel that calls the AI assistant endpoint.
 *
 * The panel keeps a rolling history (newest at the bottom) and offers
 * tap-to-fill suggestion chips. The assistant is fed live DB data on
 * the server, so the reply is grounded in real cycle state.
 */
"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { Icon } from "@/components/ui/icon";
import { postAiChat, type AiChatContext, type AiChatReply } from "@/lib/api";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  suggestions: string[];
  context: AiChatContext | null;
  /** A small timestamp shown only on hover, for parity with chat UIs. */
  at: number;
};

const WELCOME: ChatMessage = {
  id: "welcome",
  role: "assistant",
  text: "Hi — I'm INVIGILO's assistant. I'm connected to your live database, so ask me about the current cycle, conflicts, sessions, invigilators, or incidents.",
  suggestions: ["Status of the current cycle", "What conflicts are open?", "Show the latest run"],
  context: null,
  at: 0,
};

function rid(): string {
  return Math.random().toString(36).slice(2, 10);
}

/** Tiny inline-markdown renderer: **bold** and `code` plus newlines.
 * Deliberately not a full markdown lib — the assistant's replies are
 * short and we want zero extra deps. */
function renderInline(text: string): React.ReactNode {
  // Split on ** and ` tokens while keeping them in the output.
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) {
      return <strong key={i}>{p.slice(2, -2)}</strong>;
    }
    if (p.startsWith("`") && p.endsWith("`")) {
      return (
        <code
          key={i}
          className="rounded bg-ink-100 px-1.5 py-0.5 text-[12px] font-mono text-ink-900"
        >
          {p.slice(1, -1)}
        </code>
      );
    }
    return <span key={i}>{p}</span>;
  });
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isAssistant = message.role === "assistant";
  return (
    <div
      className={
        isAssistant
          ? "flex items-end gap-2"
          : "flex items-end justify-end gap-2"
      }
    >
      {isAssistant ? (
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-700 text-white">
          <Icon name="sparkle" className="h-3.5 w-3.5" />
        </span>
      ) : null}
      <div
        className={
          isAssistant
            ? "max-w-[80%] rounded-2xl rounded-bl-md bg-ink-100/70 px-3.5 py-2.5 text-sm text-ink-900"
            : "max-w-[80%] rounded-2xl rounded-br-md bg-brand-700 px-3.5 py-2.5 text-sm text-white"
        }
      >
        <div className="whitespace-pre-wrap leading-relaxed">
          {renderInline(message.text)}
        </div>
        {isAssistant && message.suggestions.length > 0 ? (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {message.suggestions.map((s) => (
              <SuggestionChip key={s} label={s} />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function SuggestionChip({ label }: { label: string }) {
  // The chip is rendered inside MessageBubble's list — the actual
  // click handler is attached via the data-suggestion attribute on
  // the panel so we don't need to thread the callback down.
  return (
    <button
      type="button"
      data-suggestion={label}
      className="rounded-full bg-surface px-2.5 py-1 text-[11px] font-semibold text-brand-700 ring-1 ring-inset ring-brand-200 transition hover:bg-brand-50"
    >
      {label}
    </button>
  );
}

export function AiAssistantFab() {
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState<ChatMessage[]>([WELCOME]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Keep the latest messages at the bottom whenever they change.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [history, pending]);

  // Wire suggestion-chip clicks via event delegation on the scroll area.
  // We stash the latest ask() in a ref so the effect only depends on
  // the open flag, not on `ask` itself (which closes over state that
  // changes every render).
  const askRef = useRef<((message: string) => Promise<void>) | null>(null);
  useEffect(() => {
    if (!open) return;
    const el = scrollRef.current;
    if (!el) return;
    function onClick(ev: Event) {
      const target = ev.target as HTMLElement | null;
      const suggestion = target?.closest<HTMLElement>("[data-suggestion]")?.dataset.suggestion;
      if (suggestion) {
        void askRef.current?.(suggestion);
      }
    }
    el.addEventListener("click", onClick);
    return () => el.removeEventListener("click", onClick);
  }, [open]);

  // Focus the input when the panel opens.
  useEffect(() => {
    if (open) {
      // Small delay so the panel finishes mounting before we steal focus.
      const t = setTimeout(() => inputRef.current?.focus(), 50);
      return () => clearTimeout(t);
    }
  }, [open]);

  async function ask(message: string) {
    const trimmed = message.trim();
    if (!trimmed || pending) return;

    const userMsg: ChatMessage = {
      id: rid(),
      role: "user",
      text: trimmed,
      suggestions: [],
      context: null,
      at: Date.now(),
    };
    setHistory((h) => [...h, userMsg]);
    setDraft("");
    setPending(true);
    setError(null);

    try {
      const reply: AiChatReply = await postAiChat(trimmed);
      const assistantMsg: ChatMessage = {
        id: rid(),
        role: "assistant",
        text: reply.reply,
        suggestions: reply.suggestions ?? [],
        context: reply.context ?? null,
        at: Date.now(),
      };
      setHistory((h) => [...h, assistantMsg]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      const fallback: ChatMessage = {
        id: rid(),
        role: "assistant",
        text:
          "I couldn't reach the assistant service. Please check your connection and try again.",
        suggestions: [],
        context: null,
        at: Date.now(),
      };
      setHistory((h) => [...h, fallback]);
    } finally {
      setPending(false);
      inputRef.current?.focus();
    }
  }

  // Keep the ref pointed at the latest ask() so the click handler
  // installed in the open-flag effect can call the freshest closure.
  useEffect(() => {
    askRef.current = ask;
  });

  function onSubmit(ev: FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    void ask(draft);
  }

  return (
    <>
      {/* Floating action button ------------------------------------- */}
      <button
        type="button"
        aria-label={open ? "Close AI assistant" : "Open AI assistant"}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-brand-700 text-white shadow-lg shadow-brand-900/30 ring-1 ring-inset ring-brand-800 transition hover:bg-brand-800 active:scale-95"
      >
        {open ? (
          <Icon name="x" className="h-5 w-5" />
        ) : (
          <Icon name="sparkle" className="h-5 w-5" />
        )}
      </button>

      {/* Chat panel ------------------------------------------------- */}
      {open ? (
        <div
          role="dialog"
          aria-label="AI assistant"
          className="fixed bottom-24 right-6 z-40 flex w-[min(92vw,380px)] flex-col overflow-hidden rounded-3xl bg-surface shadow-2xl shadow-ink-900/20 ring-1 ring-ink-200"
          style={{ maxHeight: "min(80vh, 640px)" }}
        >
          {/* Header */}
          <div className="flex items-center justify-between gap-3 border-b border-ink-100 bg-surface-dark px-4 py-3 text-white">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-500/30 text-brand-100 ring-1 ring-inset ring-brand-500/40">
                <Icon name="sparkle" className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-semibold">INVIGILO assistant</p>
                <p className="text-[11px] text-brand-200/80">Live · fed from your database</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close"
              className="flex h-8 w-8 items-center justify-center rounded-full bg-white/5 text-brand-100 ring-1 ring-inset ring-white/10 transition hover:bg-white/10"
            >
              <Icon name="x" className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Messages */}
          <div
            ref={scrollRef}
            className="flex-1 space-y-3 overflow-y-auto bg-background px-4 py-4"
          >
            {history.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}
            {pending ? (
              <div className="flex items-end gap-2">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-700 text-white">
                  <Icon name="sparkle" className="h-3.5 w-3.5" />
                </span>
                <div className="rounded-2xl rounded-bl-md bg-ink-100/70 px-3.5 py-2.5 text-sm text-ink-500">
                  <span className="inline-flex items-center gap-1">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-400" />
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-400 [animation-delay:120ms]" />
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-400 [animation-delay:240ms]" />
                  </span>
                </div>
              </div>
            ) : null}
            {error ? (
              <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700 ring-1 ring-inset ring-rose-200">
                {error}
              </p>
            ) : null}
          </div>

          {/* Composer */}
          <form
            onSubmit={onSubmit}
            className="flex items-end gap-2 border-t border-ink-100 bg-surface px-3 py-3"
          >
            <textarea
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void ask(draft);
                }
              }}
              placeholder="Ask about the current cycle…"
              rows={1}
              maxLength={500}
              disabled={pending}
              className="min-h-[40px] max-h-32 flex-1 resize-none rounded-2xl border border-ink-200 bg-background px-3 py-2 text-sm text-ink-900 placeholder:text-ink-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200 disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={pending || !draft.trim()}
              aria-label="Send"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-700 text-white transition hover:bg-brand-800 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Icon name="arrow-up-right" className="h-4 w-4" />
            </button>
          </form>
          <p className="border-t border-ink-100 bg-surface px-4 py-2 text-[10px] uppercase tracking-[0.14em] text-ink-400">
            Press Enter to send · Shift+Enter for newline
          </p>
        </div>
      ) : null}
    </>
  );
}
