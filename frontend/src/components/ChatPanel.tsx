import { useEffect, useRef, useState } from 'react';
import {
  Sparkles, Send, Plus, Square, History, Loader2, AlertTriangle, Check, X, Lock,
} from 'lucide-react';
import {
  ChatSession, ChatSessionListItem, ChatTripContext,
  endChatSession, getChatSession, listChatSessions, sendChatMessage, startChatSession,
} from '../lib/chat';

const SUGGESTIONS = [
  'What are the must-see places at my destination?',
  'Book my selected hotel',
  'Find current events during my dates',
  'Save my selected flight and hotel',
];

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('en-GB', {
      day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return '';
  }
}

export default function ChatPanel({
  token,
  context,
  isAuthenticated,
  onLogin,
}: {
  token: string | null;
  context: ChatTripContext;
  isAuthenticated: boolean;
  onLogin: () => void;
}) {
  const [session, setSession] = useState<ChatSession | null>(null);
  const [history, setHistory] = useState<ChatSessionListItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isBusy, setIsBusy] = useState(false); // start / end / load
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const loadHistory = async () => {
    if (!token) return;
    try {
      setHistory(await listChatSessions(token));
    } catch {
      // history is non-critical; ignore failures
    }
  };

  useEffect(() => {
    if (isAuthenticated && token) loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, token]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [session?.messages.length, isSending]);

  const handleStart = async () => {
    if (!token) return;
    setError(null);
    setIsBusy(true);
    try {
      const fresh = await startChatSession(token, context);
      setSession(fresh);
      setShowHistory(false);
      loadHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start the conversation.');
    } finally {
      setIsBusy(false);
    }
  };

  const handleResume = async (id: number) => {
    if (!token) return;
    setError(null);
    setIsBusy(true);
    try {
      setSession(await getChatSession(token, id));
      setShowHistory(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not open the conversation.');
    } finally {
      setIsBusy(false);
    }
  };

  const handleEnd = async () => {
    if (!token || !session) return;
    setError(null);
    setIsBusy(true);
    try {
      const ended = await endChatSession(token, session.id);
      setSession(ended);
      loadHistory();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not end the conversation.');
    } finally {
      setIsBusy(false);
    }
  };

  const handleSend = async (text?: string) => {
    const content = (text ?? input).trim();
    if (!token || !session || !content || isSending) return;
    setError(null);
    setInput('');
    setIsSending(true);
    try {
      const updated = await sendChatMessage(token, session.id, content, context);
      setSession(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The assistant could not respond.');
      setInput(content); // restore so the user can retry
    } finally {
      setIsSending(false);
    }
  };

  // --- Not signed in -------------------------------------------------------
  if (!isAuthenticated) {
    return (
      <section className="mt-28 border border-zinc-200 bg-zinc-50/60 p-10 text-center">
        <Sparkles className="mx-auto mb-4 h-6 w-6 text-zinc-400" strokeWidth={1.5} />
        <h2 className="text-2xl font-light tracking-tight text-zinc-900">AI Travel Concierge</h2>
        <p className="mx-auto mt-3 max-w-md text-sm font-light text-zinc-500">
          Sign in to chat with your concierge — it knows your trip, can search the web in
          real time, and can book or save options for you.
        </p>
        <button
          onClick={onLogin}
          className="mt-6 bg-zinc-950 px-6 py-3 text-[11px] uppercase tracking-[0.25em] font-medium text-white transition-colors hover:bg-zinc-800"
        >
          Sign in to chat
        </button>
      </section>
    );
  }

  const ended = session?.status === 'ended';

  return (
    <section className="mt-28">
      <div className="mb-8 flex items-baseline justify-between">
        <h2 className="flex items-center gap-3 text-4xl font-light tracking-tight text-zinc-950">
          <Sparkles className="h-7 w-7 text-zinc-400" strokeWidth={1.25} />
          Concierge.
        </h2>
        <span className="text-[10px] uppercase tracking-[0.3em] font-bold text-zinc-300">
          Powered by AI
        </span>
      </div>

      <div className="border border-zinc-200 bg-white">
        {/* Toolbar */}
        <div className="flex items-center justify-between border-b border-zinc-100 px-5 py-3">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] font-semibold text-zinc-400">
            {session ? (
              <>
                <span className={`h-2 w-2 rounded-full ${ended ? 'bg-zinc-300' : 'bg-emerald-500'}`} />
                {ended ? 'Session ended' : 'Session active'}
                <span className="text-zinc-300">·</span>
                <span className="normal-case tracking-normal text-zinc-500">{session.title}</span>
              </>
            ) : (
              <span>No active session</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setShowHistory((s) => !s); loadHistory(); }}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] uppercase tracking-widest font-medium text-zinc-400 transition-colors hover:text-zinc-950"
            >
              <History className="h-3.5 w-3.5" /> History
            </button>
            {session && !ended && (
              <button
                onClick={handleEnd}
                disabled={isBusy}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] uppercase tracking-widest font-medium text-zinc-400 transition-colors hover:text-red-500 disabled:opacity-40"
              >
                <Square className="h-3 w-3" /> End
              </button>
            )}
            <button
              onClick={handleStart}
              disabled={isBusy}
              className="flex items-center gap-1.5 bg-zinc-950 px-3 py-1.5 text-[10px] uppercase tracking-widest font-medium text-white transition-colors hover:bg-zinc-800 disabled:opacity-40"
            >
              <Plus className="h-3.5 w-3.5" /> New
            </button>
          </div>
        </div>

        {/* History dropdown */}
        {showHistory && (
          <div className="border-b border-zinc-100 bg-zinc-50/70">
            <div className="flex items-center justify-between px-5 py-2.5">
              <span className="text-[10px] uppercase tracking-[0.2em] font-semibold text-zinc-400">
                Past conversations
              </span>
              <button onClick={() => setShowHistory(false)} className="text-zinc-300 hover:text-zinc-900">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="max-h-56 overflow-y-auto">
              {history.length === 0 ? (
                <p className="px-5 pb-4 text-xs font-light text-zinc-400">No conversations yet.</p>
              ) : (
                history.map((h) => (
                  <button
                    key={h.id}
                    onClick={() => handleResume(h.id)}
                    className="flex w-full items-center justify-between border-t border-zinc-100 px-5 py-3 text-left transition-colors hover:bg-white"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm text-zinc-800">{h.title}</div>
                      <div className="text-[11px] text-zinc-400">
                        {h.message_count} message(s) · {formatTime(h.updated_at)}
                      </div>
                    </div>
                    <span className={`ml-3 shrink-0 text-[9px] uppercase tracking-widest font-bold ${
                      h.status === 'ended' ? 'text-zinc-300' : 'text-emerald-500'
                    }`}>
                      {h.status}
                    </span>
                  </button>
                ))
              )}
            </div>
          </div>
        )}

        {/* Transcript */}
        <div ref={scrollRef} className="h-[460px] overflow-y-auto px-5 py-6">
          {!session ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <Sparkles className="mb-4 h-8 w-8 text-zinc-300" strokeWidth={1.25} />
              <p className="max-w-sm text-sm font-light text-zinc-500">
                Start a session to chat with your concierge. It remembers your trip,
                searches the web live, and can book or save options for you.
              </p>
              <button
                onClick={handleStart}
                disabled={isBusy}
                className="mt-6 flex items-center gap-2 bg-zinc-950 px-6 py-3 text-[11px] uppercase tracking-[0.25em] font-medium text-white transition-colors hover:bg-zinc-800 disabled:opacity-40"
              >
                {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                Start session
              </button>
            </div>
          ) : (
            <div className="space-y-5">
              {session.summary && (
                <div className="border-l-2 border-zinc-200 bg-zinc-50/70 px-4 py-3">
                  <div className="mb-1 text-[9px] uppercase tracking-[0.2em] font-bold text-zinc-400">
                    Earlier conversation
                  </div>
                  <p className="text-xs font-light leading-relaxed text-zinc-500">{session.summary}</p>
                </div>
              )}

              {session.messages.length === 0 && (
                <p className="py-8 text-center text-sm font-light text-zinc-400">
                  Say hello, or pick a prompt below to get started.
                </p>
              )}

              {session.messages.map((m) => (
                <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[82%] ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
                    <div className="mb-1 text-[9px] uppercase tracking-[0.2em] font-bold text-zinc-300">
                      {m.role === 'user' ? 'You' : 'Concierge'}
                    </div>
                    <div className={`whitespace-pre-wrap px-4 py-3 text-sm leading-relaxed ${
                      m.role === 'user'
                        ? 'bg-zinc-950 font-light text-white'
                        : 'border border-zinc-200 bg-white font-light text-zinc-800'
                    }`}>
                      {m.content}
                    </div>
                    {m.actions?.length > 0 && (
                      <div className="mt-2 space-y-1.5">
                        {m.actions.map((a, i) => (
                          <div
                            key={i}
                            className={`flex items-center gap-2 px-3 py-2 text-[11px] ${
                              a.ok ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
                            }`}
                          >
                            {a.ok ? <Check className="h-3.5 w-3.5 shrink-0" /> : <AlertTriangle className="h-3.5 w-3.5 shrink-0" />}
                            <span>{a.message}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {isSending && (
                <div className="flex justify-start">
                  <div className="flex items-center gap-2 border border-zinc-200 bg-white px-4 py-3 text-sm font-light text-zinc-400">
                    <Loader2 className="h-4 w-4 animate-spin" /> Thinking…
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {error && (
          <div className="flex items-center gap-2 border-t border-red-100 bg-red-50 px-5 py-3 text-xs text-red-500">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" /> {error}
          </div>
        )}

        {/* Suggestions + composer */}
        {session && (
          <div className="border-t border-zinc-100">
            {session.messages.length === 0 && !ended && (
              <div className="flex flex-wrap gap-2 px-5 pt-4">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => handleSend(s)}
                    disabled={isSending}
                    className="border border-zinc-200 px-3 py-1.5 text-[11px] text-zinc-500 transition-colors hover:border-zinc-400 hover:text-zinc-900 disabled:opacity-40"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
            <div className="flex items-end gap-3 p-4">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                rows={1}
                placeholder={ended ? 'Send a message to resume this conversation…' : 'Ask your concierge anything…'}
                className="max-h-32 flex-1 resize-none bg-transparent px-2 py-2 text-sm font-light text-zinc-800 placeholder:text-zinc-300 focus:outline-none"
              />
              <button
                onClick={() => handleSend()}
                disabled={isSending || !input.trim()}
                className="flex items-center gap-2 bg-zinc-950 px-5 py-2.5 text-[11px] uppercase tracking-[0.2em] font-medium text-white transition-colors hover:bg-zinc-800 disabled:opacity-30"
              >
                {isSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                Send
              </button>
            </div>
          </div>
        )}
      </div>

      <p className="mt-3 flex items-center justify-center gap-1.5 text-[10px] font-light text-zinc-300">
        <Lock className="h-3 w-3" /> Conversations are saved to your account and summarized when ended.
      </p>
    </section>
  );
}
