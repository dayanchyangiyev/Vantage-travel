import { useMemo, useState } from 'react';
import { ArrowLeft, MoreHorizontal, AlertTriangle, RefreshCw } from 'lucide-react';
import { motion } from 'motion/react';
import { DynamicTierQuote, SavedTrip, TripPlan } from '../types/trip';

type TierKey = 'cheapest' | 'affordable' | 'moderate' | 'luxury';

function daysBetween(startDate: string, endDate: string): number {
  const start = new Date(startDate);
  const end = new Date(endDate);
  const diffMs = end.getTime() - start.getTime();
  const days = Math.round(diffMs / (1000 * 60 * 60 * 24));
  return days > 0 ? days : 0;
}

// ---------------------------------------------------------------------------
// Skeleton — animated loading placeholder
// ---------------------------------------------------------------------------
function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`relative overflow-hidden bg-zinc-100 rounded-none ${className}`}
    >
      <motion.div
        className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/60 to-transparent"
        animate={{ translateX: ['−100%', '200%'] }}
        transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// PricingError — shown when pricing API fails
// ---------------------------------------------------------------------------
function PricingError({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="border border-red-100 bg-red-50 p-5 space-y-3">
      <div className="flex items-center gap-2 text-red-500">
        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
        <span className="text-[10px] uppercase tracking-[0.2em] font-semibold">Pricing Unavailable</span>
      </div>
      <p className="text-xs text-red-400 font-light leading-relaxed">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-medium text-red-400 hover:text-red-600 transition-colors"
        >
          <RefreshCw className="w-3 h-3" />
          Retry
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TierCardSkeleton — loading placeholder for a single tier card
// ---------------------------------------------------------------------------
function TierCardSkeleton() {
  return (
    <div className="w-full p-5 border border-zinc-100 space-y-3">
      <Skeleton className="h-2 w-16" />
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-3 w-20" />
      <Skeleton className="h-3 w-20" />
      <Skeleton className="h-3 w-14" />
      <Skeleton className="h-4 w-28 mt-2" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// TripPlanSkeleton — loading placeholder for Gemini content sections
// ---------------------------------------------------------------------------
function TripPlanSkeleton() {
  return (
    <div className="space-y-20">
      {/* Best time to travel */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
        <div className="space-y-4">
          <Skeleton className="h-2 w-24" />
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-3 w-32" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-4/5" />
        </div>
        <div className="flex items-end justify-end">
          <div className="space-y-2 text-right">
            <Skeleton className="h-2 w-20 ml-auto" />
            <Skeleton className="h-12 w-32 ml-auto" />
          </div>
        </div>
      </div>
      {/* Transit protocols */}
      <div className="space-y-6 pt-20 border-t border-zinc-50">
        <Skeleton className="h-2 w-28" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-zinc-100 border border-zinc-100">
          {[0, 1].map((i) => (
            <div key={i} className="bg-white p-8 space-y-4">
              <div className="flex justify-between">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-5 w-16" />
              </div>
              <Skeleton className="h-2 w-full" />
              <Skeleton className="h-2 w-4/5" />
              <Skeleton className="h-2 w-3/5" />
            </div>
          ))}
        </div>
      </div>
      {/* Places */}
      <div className="space-y-8 pt-20 border-t border-zinc-50">
        <Skeleton className="h-2 w-36" />
        {[0, 1, 2].map((i) => (
          <div key={i} className="space-y-3">
            <div className="flex items-baseline gap-6">
              <Skeleton className="h-3 w-6" />
              <Skeleton className="h-6 w-48" />
            </div>
            <Skeleton className="h-2 w-full ml-12" />
            <Skeleton className="h-2 w-4/5 ml-12" />
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Dashboard component
// ---------------------------------------------------------------------------
export default function Dashboard({
  plan,
  savedTrip,
  pricingSnapshot,
  isPricingLoading,
  pricingError,
  onBack,
}: {
  plan: TripPlan | null;
  savedTrip: SavedTrip | null;
  pricingSnapshot: DynamicTierQuote | null;
  isPricingLoading: boolean;
  pricingError: string | null;
  onBack: () => void;
}) {
  const initialTier = (savedTrip?.budget_profile || 'moderate') as TierKey;
  const [selectedTier, setSelectedTier] = useState<TierKey>(initialTier);

  const effectivePricingSnapshot = useMemo(() => {
    if (pricingSnapshot?.tiers) return pricingSnapshot;
    if (savedTrip?.pricing_snapshot && 'tiers' in savedTrip.pricing_snapshot) {
      return savedTrip.pricing_snapshot as DynamicTierQuote;
    }
    return null;
  }, [pricingSnapshot, savedTrip]);

  const stayDays = useMemo(() => {
    if (effectivePricingSnapshot?.trip_duration_days) {
      return effectivePricingSnapshot.trip_duration_days;
    }
    if (!savedTrip) return 0;
    return daysBetween(savedTrip.start_date, savedTrip.end_date);
  }, [effectivePricingSnapshot, savedTrip]);

  const selectedPricing = effectivePricingSnapshot?.tiers?.[selectedTier];

  return (
    <div className="max-w-6xl mx-auto px-6 py-20 bg-white">
      <nav className="flex justify-between items-center mb-24">
        <button
          onClick={onBack}
          className="flex items-center gap-3 text-xs uppercase tracking-[0.3em] font-medium text-zinc-400 hover:text-zinc-950 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Select Trip
        </button>
        <div className="text-[10px] uppercase tracking-[0.4em] font-bold text-zinc-950">Vantage / Exploration</div>
        <button className="text-zinc-300 hover:text-zinc-950 transition-colors">
          <MoreHorizontal className="w-5 h-5" />
        </button>
      </nav>

      <header className="mb-28">
        <h1 className="text-7xl font-light tracking-tighter text-zinc-950 mb-6">
          Summary.
        </h1>
        <div className="w-24 h-px bg-zinc-950" />

        {/* Saved preferences panel */}
        {savedTrip && (
          <div className="mt-10 border border-zinc-100 bg-zinc-50/70 p-6">
            <p className="text-[10px] uppercase tracking-[0.25em] font-semibold text-zinc-400 mb-5">
              Saved Travel Preferences
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
              <div>
                <span className="block text-zinc-400 text-[11px] uppercase tracking-wider mb-1">Departure</span>
                <span className="text-zinc-900">{savedTrip.origin_country}</span>
              </div>
              <div>
                <span className="block text-zinc-400 text-[11px] uppercase tracking-wider mb-1">Destination</span>
                <span className="text-zinc-900">{savedTrip.destination}</span>
              </div>
              <div>
                <span className="block text-zinc-400 text-[11px] uppercase tracking-wider mb-1">Travelers</span>
                <span className="text-zinc-900">{savedTrip.travelers}</span>
              </div>
              <div>
                <span className="block text-zinc-400 text-[11px] uppercase tracking-wider mb-1">Dates</span>
                <span className="text-zinc-900">{savedTrip.start_date} → {savedTrip.end_date}</span>
              </div>
              <div>
                <span className="block text-zinc-400 text-[11px] uppercase tracking-wider mb-1">Interests</span>
                <span className="text-zinc-900">
                  {(savedTrip.interests || []).length ? savedTrip.interests.join(', ') : 'None selected'}
                </span>
              </div>
              <div>
                <span className="block text-zinc-400 text-[11px] uppercase tracking-wider mb-1">Duration</span>
                <span className="text-zinc-900">{stayDays} day(s)</span>
              </div>
            </div>
          </div>
        )}

        {/* Selected category budget panel — loading / error / data */}
        <div className="mt-6 border border-zinc-100 bg-white p-6 min-h-[96px]">
          <p className="text-[10px] uppercase tracking-[0.25em] font-semibold text-zinc-400 mb-4">
            Selected Category Budget
          </p>
          {isPricingLoading && !effectivePricingSnapshot ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="space-y-2">
                  <Skeleton className="h-2 w-16" />
                  <Skeleton className="h-4 w-20" />
                </div>
              ))}
            </div>
          ) : pricingError && !effectivePricingSnapshot ? (
            <p className="text-xs text-red-400 flex items-center gap-2">
              <AlertTriangle className="w-3 h-3" />
              {pricingError}
            </p>
          ) : selectedPricing ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 text-sm"
            >
              <div>
                <span className="block text-zinc-400 text-[11px] uppercase tracking-wider mb-1">Category</span>
                <span className="text-zinc-900 uppercase">{selectedTier}</span>
              </div>
              <div>
                <span className="block text-zinc-400 text-[11px] uppercase tracking-wider mb-1">Flight Cost</span>
                <span className="text-zinc-900">${selectedPricing.flight_cost.toFixed(0)}</span>
              </div>
              <div>
                <span className="block text-zinc-400 text-[11px] uppercase tracking-wider mb-1">Hotel / Day</span>
                <span className="text-zinc-900">${selectedPricing.hotel_daily_cost.toFixed(0)}</span>
              </div>
              <div>
                <span className="block text-zinc-400 text-[11px] uppercase tracking-wider mb-1">Living / Day</span>
                <span className="text-zinc-900">${selectedPricing.local_daily_cost.toFixed(0)}</span>
              </div>
              <div>
                <span className="block text-zinc-400 text-[11px] uppercase tracking-wider mb-1">Final Value</span>
                <span className="text-zinc-900 font-semibold">${selectedPricing.total_trip_cost.toFixed(0)}</span>
              </div>
            </motion.div>
          ) : (
            <p className="text-xs text-zinc-400">No pricing data available.</p>
          )}
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-y-24 gap-x-12">

        {/* ── Left column: Gemini trip plan content ── */}
        <section className="lg:col-span-3 space-y-20 border-r border-zinc-100 pr-12">
          {plan ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-20"
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
                <div className="space-y-6">
                  <label className="text-[10px] uppercase tracking-widest font-bold text-zinc-300">Optimal Sequence</label>
                  <div className="space-y-2">
                    <h3 className="text-4xl font-light tracking-tight">{plan.bestTimeToTravel.period}</h3>
                    <div className="flex items-center gap-2 text-sm text-zinc-400">
                      <span className="w-2 h-2 rounded-full bg-zinc-950" />
                      {plan.bestTimeToTravel.weather}
                    </div>
                  </div>
                  <p className="text-sm font-light leading-relaxed text-zinc-500 max-w-sm">
                    {plan.bestTimeToTravel.reason}
                  </p>
                </div>
                <div className="flex items-end md:justify-end">
                  <div className="text-left md:text-right">
                    <label className="text-[10px] uppercase tracking-widest font-bold text-zinc-300 block mb-2">Crowd Density</label>
                    <div className="text-5xl font-light tracking-tighter uppercase">{plan.bestTimeToTravel.touristDensity}</div>
                  </div>
                </div>
              </div>

              <div className="space-y-8 pt-20 border-t border-zinc-50">
                <label className="text-[10px] uppercase tracking-widest font-bold text-zinc-300">Transit Protocols</label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-zinc-100 border border-zinc-100">
                  {plan.tickets.map((ticket, idx) => (
                    <div key={idx} className="bg-white p-8 space-y-6">
                      <div className="flex justify-between items-start">
                        <div className="text-xs uppercase tracking-widest font-bold">{ticket.company}</div>
                        <div className="text-xl font-light tracking-tight">{ticket.price}</div>
                      </div>
                      <ul className="space-y-2">
                        {ticket.pros.map((pro, i) => (
                          <li key={i} className="text-[11px] text-zinc-400 flex items-center gap-3">
                            <div className="w-1 h-1 bg-zinc-200 rounded-full" />
                            {pro}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-8 pt-20 border-t border-zinc-50">
                <label className="text-[10px] uppercase tracking-widest font-bold text-zinc-300">Curated Interest Points</label>
                <div className="space-y-12">
                  {plan.places.map((place, idx) => (
                    <div key={idx} className="group cursor-default">
                      <div className="flex items-baseline gap-6 mb-4">
                        <span className="text-xs font-bold text-zinc-300">0{idx + 1}</span>
                        <h4 className="text-2xl font-light tracking-tight group-hover:pl-4 transition-all duration-500">{place.name}</h4>
                        <span className="text-[10px] uppercase tracking-widest text-zinc-200 font-bold">{place.type}</span>
                      </div>
                      <p className="text-sm font-light text-zinc-500 max-w-xl pl-12 leading-relaxed">
                        {place.description}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          ) : (
            <TripPlanSkeleton />
          )}
        </section>

        {/* ── Right column: pricing tier cards ── */}
        <aside className="lg:col-span-2 space-y-12 lg:-ml-4">
          <div className="space-y-6">
            <label className="text-[10px] uppercase tracking-widest font-bold text-zinc-300">Travel Categories</label>

            {isPricingLoading && !effectivePricingSnapshot ? (
              /* Loading skeletons for all 4 tier cards */
              <div className="space-y-4">
                {[0, 1, 2, 3].map((i) => (
                  <TierCardSkeleton key={i} />
                ))}
              </div>
            ) : pricingError && !effectivePricingSnapshot ? (
              /* Error state */
              <PricingError
                message={pricingError}
              />
            ) : effectivePricingSnapshot ? (
              /* Live pricing data */
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-4"
              >
                {(['cheapest', 'affordable', 'moderate', 'luxury'] as const).map((tier) => {
                  const entry = effectivePricingSnapshot.tiers[tier];
                  const selected = selectedTier === tier;
                  return (
                    <button
                      key={tier}
                      onClick={() => setSelectedTier(tier)}
                      className={`w-full text-left p-5 border transition-all ${
                        selected
                          ? 'border-zinc-900 bg-zinc-950 text-white'
                          : 'border-zinc-200 bg-zinc-50 hover:border-zinc-400'
                      }`}
                    >
                      <div className={`text-[10px] uppercase tracking-[0.2em] mb-3 ${selected ? 'text-zinc-300' : 'text-zinc-500'}`}>
                        {tier}
                      </div>
                      <div className="text-sm mb-1">Flight: ${entry.flight_cost.toFixed(0)}</div>
                      <div className="text-sm mb-1">Hotel/day: ${entry.hotel_daily_cost.toFixed(0)}</div>
                      <div className="text-sm mb-1">Living/day: ${entry.local_daily_cost.toFixed(0)}</div>
                      <div className="text-sm mb-1">Stay: {effectivePricingSnapshot.trip_duration_days} day(s)</div>
                      <div className="text-base mt-3 font-semibold">Final: ${entry.total_trip_cost.toFixed(0)}</div>
                    </button>
                  );
                })}
              </motion.div>
            ) : (
              <div className="text-sm text-zinc-500 border border-zinc-200 bg-zinc-50 p-4">
                Pricing categories are not available.
              </div>
            )}
          </div>

          <div className="space-y-6 pt-12 border-t border-zinc-100">
            {plan ? (
              <div className="text-[11px] leading-relaxed text-zinc-400 font-light italic">
                {plan.budget.foodInfo}
              </div>
            ) : (
              <div className="space-y-2">
                <Skeleton className="h-2 w-full" />
                <Skeleton className="h-2 w-4/5" />
                <Skeleton className="h-2 w-3/5" />
              </div>
            )}
          </div>

          <div className="space-y-8 pt-12 border-t border-zinc-100">
            <label className="text-[10px] uppercase tracking-widest font-bold text-zinc-300">Occurrences</label>
            {plan ? (
              <div className="space-y-8">
                {plan.events.map((event, i) => (
                  <div key={i} className="space-y-2">
                    <div className="text-[10px] font-bold text-zinc-950">{event.date}</div>
                    <div className="text-xs text-zinc-500 font-light leading-snug">{event.name} — {event.description}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-6">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="space-y-2">
                    <Skeleton className="h-2 w-16" />
                    <Skeleton className="h-2 w-full" />
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>
      </div>

      <footer className="mt-48 pt-20 border-t border-zinc-100 flex justify-between items-center text-[10px] uppercase tracking-[0.3em] font-bold text-zinc-300">
        <div>© 2026 Vantage Travel</div>
        <div className="flex gap-12">
          <span>Terms</span>
          <span>Privacy</span>
          <span>Legal</span>
        </div>
      </footer>
    </div>
  );
}
