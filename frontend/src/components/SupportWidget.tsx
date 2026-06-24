import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Headset, X, Send, Loader2, Check, ShieldCheck, AlertTriangle, ShieldAlert,
} from 'lucide-react';
import {
  SupportSession, SupportOperation,
  confirmOperation, declineOperation, sendSupportMessage, startSupportSession,
} from '../lib/support';

interface LocalMessage { role: 'user' | 'assistant'; content: string; id: string | number; }

export default function SupportWidget({
  token, isAuthenticated, onLogin,
}: { token: string | null; isAuthenticated: boolean; onLogin: () => void }) {
  const [open, setOpen] = useState(false);
  const [showBubble, setShowBubble] = useState(false);
  const [session, setSession] = useState<SupportSession | null>(null);
  const [messages, setMessages] = useState<LocalMessage[]>([]);
  const [pendingOp, setPendingOp] = useState<SupportOperation | null>(null);
  const [input, setInput] = useState('');
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Pop the "Need support?" bubble 10s after load (until opened/dismissed).
  useEffect(() => {
    const t = window.setTimeout(() => setShowBubble(true), 10000);
    return () => window.clearTimeout(t);
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && typeof el.scrollTo === 'function') {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    }
  }, [messages.length, isBusy, pendingOp]);

  const openWidget = async () => {
    setShowBubble(false);
    setOpen(true);
    if (!isAuthenticated || !token || session) return;
    setError(null);
    setIsBusy(true);
    try {
      const fresh = await startSupportSession(token);
      setSession(fresh);
      setMessages([{
        role: 'assistant', id: 'welcome',
        content: "Hi! I'm your Vantage support agent. I can help with your trips and "
          + "bookings — and if needed, arrange a refund or change. What's going on?",
      }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start support.');
    } finally {
      setIsBusy(false);
    }
  };

  const send = async (text?: string) => {
    const content = (text ?? input).trim();
    if (!token || !session || !content || isBusy) return;
    setError(null);
    setInput('');
    setMessages((m) => [...m, { role: 'user', content, id: `u-${Date.now()}` }]);
    setIsBusy(true);
    try {
      const updated = await sendSupportMessage(token, session.id, content);
      setSession(updated);
      const last = updated.messages[updated.messages.length - 1];
      if (last && last.role === 'assistant') {
        setMessages((m) => [...m, { role: 'assistant', content: last.content, id: last.id }]);
      }
      setPendingOp(updated.pending_operation ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The agent could not respond.');
    } finally {
      setIsBusy(false);
    }
  };

  const resolveOperation = async (confirm: boolean) => {
    if (!token || !pendingOp) return;
    setIsBusy(true);
    setError(null);
    try {
      const op = confirm
        ? await confirmOperation(token, pendingOp.id)
        : await declineOperation(token, pendingOp.id);
      const note = op.result?.message
        || (confirm ? 'Operation completed.' : "Okay, I won't make that change.");
      setMessages((m) => [...m, { role: 'assistant', content: note, id: `op-${op.id}` }]);
      setPendingOp(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update the operation.');
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <>
      {/* Floating launcher */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
        <AnimatePresence>
          {showBubble && !open && (
            <motion.button
              initial={{ opacity: 0, y: 8, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              onClick={openWidget}
              className="max-w-[220px] border border-zinc-200 bg-white px-4 py-3 text-left shadow-lg"
            >
              <div className="text-[9px] uppercase tracking-[0.2em] font-bold text-zinc-300">Vantage Support</div>
              <div className="mt-1 text-sm font-light text-zinc-800">Need support? I'm here to help. 👋</div>
            </motion.button>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0, y: 16, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 16, scale: 0.98 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              className="flex h-[560px] w-[min(92vw,380px)] flex-col border border-zinc-200 bg-white shadow-2xl"
            >
              {/* Header */}
              <div className="flex items-center justify-between border-b border-zinc-100 bg-zinc-950 px-4 py-3 text-white">
                <div className="flex items-center gap-2">
                  <Headset className="h-4 w-4 text-zinc-300" strokeWidth={1.5} />
                  <span className="text-sm font-medium">Customer Support</span>
                  {session && (
                    <span className={`ml-1 text-[8px] uppercase tracking-[0.15em] font-bold px-1.5 py-0.5 ${
                      session.mode === 'individual' ? 'bg-amber-400/20 text-amber-300' : 'bg-white/15 text-zinc-300'
                    }`}>
                      {session.mode === 'individual' ? 'Agent' : 'Assist'}
                    </span>
                  )}
                </div>
                <button onClick={() => setOpen(false)} className="text-zinc-400 hover:text-white">
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Body */}
              {!isAuthenticated ? (
                <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
                  <ShieldAlert className="mb-3 h-7 w-7 text-zinc-300" strokeWidth={1.25} />
                  <p className="text-sm font-light text-zinc-500">
                    Sign in to chat with support — it works with your bookings and can arrange
                    refunds or changes.
                  </p>
                  <button
                    onClick={onLogin}
                    className="mt-5 bg-zinc-950 px-5 py-2.5 text-[11px] uppercase tracking-[0.25em] font-medium text-white hover:bg-zinc-800"
                  >
                    Sign in
                  </button>
                </div>
              ) : (
                <>
                  <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
                    {messages.map((m) => (
                      <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[85%] whitespace-pre-wrap px-3 py-2 text-[13px] leading-relaxed ${
                          m.role === 'user'
                            ? 'bg-zinc-950 font-light text-white'
                            : 'border border-zinc-200 bg-white font-light text-zinc-800'
                        }`}>
                          {m.content}
                        </div>
                      </div>
                    ))}

                    {/* Policy-gated confirmation card */}
                    {pendingOp && pendingOp.status === 'awaiting_confirmation' && (
                      <div className="border border-amber-200 bg-amber-50 p-3">
                        <div className="mb-1 flex items-center gap-1.5 text-[10px] uppercase tracking-widest font-bold text-amber-700">
                          <ShieldCheck className="h-3.5 w-3.5" /> Confirm {pendingOp.kind}
                        </div>
                        <p className="text-[12px] text-amber-800">
                          {pendingOp.kind === 'refund' ? 'Refund' : 'Change'} booking{' '}
                          <span className="font-semibold">{pendingOp.booking_reference}</span>?
                          This needs your explicit confirmation.
                        </p>
                        {pendingOp.policy_basis && (
                          <p className="mt-1 text-[10px] text-amber-600">Policy: {pendingOp.policy_basis}</p>
                        )}
                        <div className="mt-3 flex gap-2">
                          <button
                            onClick={() => resolveOperation(true)}
                            disabled={isBusy}
                            className="flex items-center gap-1.5 bg-zinc-950 px-3 py-1.5 text-[10px] uppercase tracking-widest font-medium text-white hover:bg-zinc-800 disabled:opacity-40"
                          >
                            <Check className="h-3 w-3" /> Confirm
                          </button>
                          <button
                            onClick={() => resolveOperation(false)}
                            disabled={isBusy}
                            className="border border-zinc-300 px-3 py-1.5 text-[10px] uppercase tracking-widest font-medium text-zinc-600 hover:border-zinc-900 hover:text-zinc-900 disabled:opacity-40"
                          >
                            Decline
                          </button>
                        </div>
                      </div>
                    )}

                    {isBusy && (
                      <div className="flex justify-start">
                        <div className="flex items-center gap-2 border border-zinc-200 bg-white px-3 py-2 text-[13px] font-light text-zinc-400">
                          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Working…
                        </div>
                      </div>
                    )}
                  </div>

                  {error && (
                    <div className="flex items-center gap-2 border-t border-red-100 bg-red-50 px-4 py-2 text-[11px] text-red-500">
                      <AlertTriangle className="h-3.5 w-3.5 shrink-0" /> {error}
                    </div>
                  )}

                  <div className="flex items-end gap-2 border-t border-zinc-100 p-3">
                    <textarea
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
                      }}
                      rows={1}
                      placeholder="Describe your issue…"
                      className="max-h-24 flex-1 resize-none bg-transparent px-2 py-1.5 text-[13px] font-light text-zinc-800 placeholder:text-zinc-300 focus:outline-none"
                    />
                    <button
                      onClick={() => send()}
                      disabled={isBusy || !input.trim()}
                      aria-label="Send message"
                      className="flex items-center justify-center bg-zinc-950 p-2.5 text-white hover:bg-zinc-800 disabled:opacity-30"
                    >
                      <Send className="h-4 w-4" />
                    </button>
                  </div>
                </>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* The button itself */}
        {!open && (
          <button
            onClick={openWidget}
            aria-label="Open customer support"
            className="flex h-14 w-14 items-center justify-center rounded-full bg-zinc-950 text-white shadow-xl transition-transform hover:scale-105 hover:bg-zinc-800"
          >
            <Headset className="h-6 w-6" strokeWidth={1.5} />
          </button>
        )}
      </div>
    </>
  );
}
