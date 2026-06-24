import { useCallback, useEffect, useState } from 'react';
import { motion } from 'motion/react';
import {
  ArrowLeft, Plane, BedDouble, RefreshCw, AlertTriangle, CalendarCheck,
  ShieldCheck, Ticket,
} from 'lucide-react';
import { BookingRecord, listBookings } from '../lib/search';

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('en-GB', {
      day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function BookingCard({ booking }: { booking: BookingRecord }) {
  const isFlight = booking.kind === 'flight';
  const Icon = isFlight ? Plane : BedDouble;
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="border border-zinc-200 bg-white"
    >
      <div className="flex items-stretch">
        <div className="flex w-16 shrink-0 items-center justify-center border-r border-zinc-100 bg-zinc-50/60">
          <Icon className="h-6 w-6 text-zinc-400" strokeWidth={1.25} />
        </div>
        <div className="flex-1 p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-[9px] uppercase tracking-[0.2em] font-bold text-zinc-300">
                {isFlight ? 'Flight ticket' : 'Hotel reservation'}
              </div>
              <div className="mt-1 truncate text-sm font-medium text-zinc-900">
                {booking.title || (isFlight ? 'Flight' : 'Hotel')}
              </div>
            </div>
            <span className={`shrink-0 rounded-none px-2 py-1 text-[9px] uppercase tracking-widest font-bold ${
              booking.status.toUpperCase() === 'CANCELLED'
                ? 'bg-red-50 text-red-500'
                : 'bg-emerald-50 text-emerald-600'
            }`}>
              {booking.status}
            </span>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
            <div>
              <div className="text-[9px] uppercase tracking-widest text-zinc-400">Reference</div>
              <div className="mt-0.5 text-sm tabular-nums tracking-wide text-zinc-900">{booking.reference}</div>
            </div>
            <div>
              <div className="text-[9px] uppercase tracking-widest text-zinc-400">Paid</div>
              <div className="mt-0.5 text-sm tabular-nums text-zinc-900">
                {booking.price != null ? `$${Number(booking.price).toFixed(0)} ${booking.currency || ''}`.trim() : '—'}
              </div>
            </div>
            <div>
              <div className="text-[9px] uppercase tracking-widest text-zinc-400">Booked</div>
              <div className="mt-0.5 text-[13px] text-zinc-600">{formatDate(booking.created_at)}</div>
            </div>
            <div className="flex items-end">
              <span className="inline-flex items-center gap-1.5 text-[10px] text-zinc-400">
                <ShieldCheck className={`h-3.5 w-3.5 ${booking.is_real ? 'text-emerald-600' : 'text-zinc-300'}`} />
                {booking.is_real ? 'Supplier-confirmed' : 'Demo ticket'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export default function Bookings({
  token, onBack,
}: { token: string | null; onBack: () => void }) {
  const [bookings, setBookings] = useState<BookingRecord[] | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) {
      setError('Sign in to view your bookings.');
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      setBookings(await listBookings(token));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load your bookings.');
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const flights = (bookings || []).filter((b) => b.kind === 'flight');
  const hotels = (bookings || []).filter((b) => b.kind === 'hotel');

  return (
    <div className="max-w-5xl mx-auto px-6 py-16 bg-white">
      <button
        onClick={onBack}
        className="flex items-center gap-3 text-xs uppercase tracking-[0.3em] font-medium text-zinc-400 hover:text-zinc-950 transition-colors mb-12"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Dashboard
      </button>

      <div className="mb-10 flex items-end justify-between">
        <div className="flex items-center gap-3">
          <Ticket className="h-6 w-6 text-zinc-900" strokeWidth={1.5} />
          <h2 className="text-4xl font-light tracking-tight text-zinc-950">Bookings.</h2>
        </div>
        <button
          onClick={load}
          disabled={isLoading}
          className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-medium text-zinc-400 hover:text-zinc-950 transition-colors disabled:opacity-40"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error ? (
        <div className="border border-red-100 bg-red-50 p-5 flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
          <p className="text-xs text-red-400 font-light">{error}</p>
        </div>
      ) : isLoading && !bookings ? (
        <div className="py-20 text-center text-xs uppercase tracking-[0.3em] text-zinc-400">
          Loading your bookings…
        </div>
      ) : bookings && bookings.length === 0 ? (
        <div className="border border-zinc-200 bg-zinc-50/60 py-20 text-center">
          <CalendarCheck className="mx-auto mb-4 h-8 w-8 text-zinc-300" strokeWidth={1.25} />
          <p className="text-sm font-light text-zinc-500">No bookings yet.</p>
          <p className="mt-1 text-xs text-zinc-400">Book a flight or hotel from the dashboard to see it here.</p>
        </div>
      ) : (
        <div className="space-y-12">
          {flights.length > 0 && (
            <section className="space-y-4">
              <div className="flex items-baseline gap-3">
                <span className="text-[10px] uppercase tracking-[0.3em] font-bold text-zinc-300">Flights</span>
                <span className="h-px flex-1 bg-zinc-100" />
              </div>
              {flights.map((b) => <BookingCard key={b.id} booking={b} />)}
            </section>
          )}
          {hotels.length > 0 && (
            <section className="space-y-4">
              <div className="flex items-baseline gap-3">
                <span className="text-[10px] uppercase tracking-[0.3em] font-bold text-zinc-300">Hotels</span>
                <span className="h-px flex-1 bg-zinc-100" />
              </div>
              {hotels.map((b) => <BookingCard key={b.id} booking={b} />)}
            </section>
          )}
        </div>
      )}
    </div>
  );
}
