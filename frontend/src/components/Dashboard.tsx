import { useMemo, useState } from 'react';
import {
  ArrowLeft, MoreHorizontal, AlertTriangle, RefreshCw, Sun, Cloud, CloudRain, Droplets,
  Plane, BedDouble, ChevronRight, Check,
} from 'lucide-react';
import { motion } from 'motion/react';
import { DynamicTierQuote, FlightOption, HotelOption, SavedTrip, TripPlan, WeatherSummary } from '../types/trip';
import BookingSearch, { BookingTripContext } from './BookingSearch';

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
// WeatherSkeleton — loading placeholder for the weather widget
// ---------------------------------------------------------------------------
function WeatherSkeleton() {
  return (
    <div className="border border-zinc-200 bg-white">
      <div className="flex items-stretch border-b border-zinc-100">
        <div className="w-20 border-r border-zinc-100 flex items-center justify-center p-5">
          <Skeleton className="h-8 w-8" />
        </div>
        <div className="flex-1 p-5 space-y-3">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-9 w-24" />
        </div>
      </div>
      <div className="grid grid-cols-2 divide-x divide-zinc-100">
        <div className="p-4"><Skeleton className="h-6 w-16" /></div>
        <div className="p-4"><Skeleton className="h-6 w-16" /></div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// WeatherWidget — general weather summary for the destination
// ---------------------------------------------------------------------------
function getWeatherIcon(condition: string) {
  const c = condition.toLowerCase();
  if (c.includes('rain') || c.includes('shower') || c.includes('drizzle')) return CloudRain;
  if (c.includes('cloud') || c.includes('overcast')) return Cloud;
  if (c.includes('sun') || c.includes('clear')) return Sun;
  return Cloud;
}

function WeatherWidget({ summary }: { summary: WeatherSummary }) {
  const Icon = getWeatherIcon(summary.condition);
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      className="border border-zinc-200 bg-white"
    >
      {/* Hero — icon panel + condition + big temperature */}
      <div className="flex items-stretch border-b border-zinc-100">
        <div className="flex w-20 shrink-0 items-center justify-center border-r border-zinc-100 bg-zinc-50/60">
          <Icon className="w-9 h-9 text-zinc-400" strokeWidth={1.25} />
        </div>
        <div className="flex-1 p-5">
          <div className="flex items-start justify-between gap-2">
            <span className="text-xs font-light leading-tight text-zinc-500">{summary.condition}</span>
            <span className="shrink-0 text-[9px] font-bold uppercase tracking-[0.2em] text-zinc-300">
              {summary.is_forecast ? 'Forecast' : 'Reference'}
            </span>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-4xl font-extralight leading-none tabular-nums text-zinc-900">
              {Math.round(summary.high_c)}°
            </span>
            <span className="text-sm font-light tabular-nums text-zinc-400">
              / {Math.round(summary.low_c)}° low
            </span>
          </div>
          <div className="mt-1.5 text-[10px] font-light tabular-nums text-zinc-300">
            {Math.round(summary.high_f)}°F – {Math.round(summary.low_f)}°F
          </div>
        </div>
      </div>

      {/* Stat strip — humidity + rain */}
      <div className="grid grid-cols-2 divide-x divide-zinc-100">
        <div className="flex items-center gap-3 p-4">
          <Droplets className="w-4 h-4 shrink-0 text-zinc-300" strokeWidth={1.5} />
          <div className="leading-none">
            <div className="text-sm tabular-nums text-zinc-800">{summary.humidity_pct}%</div>
            <div className="mt-1 text-[9px] font-bold uppercase tracking-widest text-zinc-300">Humidity</div>
          </div>
        </div>
        <div className="flex items-center gap-3 p-4">
          <CloudRain className="w-4 h-4 shrink-0 text-zinc-300" strokeWidth={1.5} />
          <div className="leading-none">
            <div className="text-sm tabular-nums text-zinc-800">{summary.precipitation_pct}%</div>
            <div className="mt-1 text-[9px] font-bold uppercase tracking-widest text-zinc-300">Rain</div>
          </div>
        </div>
      </div>

      {/* Date label footnote */}
      <div className="border-t border-zinc-100 px-5 py-3">
        <p className="text-[10px] font-light leading-snug text-zinc-400">{summary.date_label}</p>
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Main Dashboard component
// ---------------------------------------------------------------------------
function formatDateRange(startDate: string, endDate: string): string {
  const fmt = (d: string) =>
    new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  const fmtYear = (d: string) =>
    new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  return `${fmt(startDate)} – ${fmtYear(endDate)}`;
}

export default function Dashboard({
  plan,
  savedTrip,
  currentTripDates,
  pricingSnapshot,
  isPricingLoading,
  pricingError,
  weatherSummary,
  weatherError,
  isWeatherLoading,
  isAuthenticated,
  bookingContext,
  selectedFlight,
  selectedHotel,
  onSelectFlight,
  onSelectHotel,
  onOpenFlightSearch,
  onOpenHotelSearch,
  onBack,
  onLogin,
  onRegister,
}: {
  plan: TripPlan | null;
  savedTrip: SavedTrip | null;
  currentTripDates: { startDate: string; endDate: string } | null;
  pricingSnapshot: DynamicTierQuote | null;
  isPricingLoading: boolean;
  pricingError: string | null;
  weatherSummary: WeatherSummary | null;
  weatherError: string | null;
  isWeatherLoading: boolean;
  isAuthenticated: boolean;
  bookingContext: BookingTripContext | null;
  selectedFlight: FlightOption | null;
  selectedHotel: HotelOption | null;
  onSelectFlight: (option: FlightOption) => void;
  onSelectHotel: (option: HotelOption) => void;
  onOpenFlightSearch: () => void;
  onOpenHotelSearch: () => void;
  onBack: () => void;
  onLogin: () => void;
  onRegister: () => void;
}) {
  const [bookingTab, setBookingTab] = useState<'flight' | 'hotel'>('flight');
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
        <div className="flex items-center gap-6">
          {!isAuthenticated && plan && (
            <div className="flex gap-4">
              <button
                onClick={onLogin}
                className="text-xs uppercase tracking-widest font-medium text-zinc-500 hover:text-zinc-900 transition-colors"
              >
                Sign In
              </button>
              <button
                onClick={onRegister}
                className="text-xs uppercase tracking-widest font-medium text-white bg-zinc-950 hover:bg-zinc-800 px-4 py-2 transition-colors"
              >
                Save Trip
              </button>
            </div>
          )}
          <button className="text-zinc-300 hover:text-zinc-950 transition-colors">
            <MoreHorizontal className="w-5 h-5" />
          </button>
        </div>
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

      {/* ── Flights & Stays: search bars + selectable options ── */}
      {bookingContext && (
        <section className="mb-28">
          <div className="flex items-baseline justify-between mb-8">
            <h2 className="text-4xl font-light tracking-tight text-zinc-950">Flights &amp; Stays.</h2>
            <span className="text-[10px] uppercase tracking-[0.3em] font-bold text-zinc-300">Choose &amp; Save</span>
          </div>

          {/* Current selection summary */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-zinc-100 border border-zinc-100 mb-10">
            <div className="bg-white p-5">
              <div className="flex items-center gap-2 mb-3">
                <Plane className="w-4 h-4 text-zinc-400" strokeWidth={1.5} />
                <span className="text-[10px] uppercase tracking-[0.25em] font-semibold text-zinc-400">Selected Flight</span>
              </div>
              {selectedFlight ? (
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-zinc-900">{selectedFlight.airline}</div>
                    <div className="text-[11px] text-zinc-400">
                      {selectedFlight.origin}–{selectedFlight.destination} · {selectedFlight.stops <= 0 ? 'Direct' : `${selectedFlight.stops} stop(s)`}
                    </div>
                  </div>
                  <div className="text-xl font-light flex items-center gap-2">
                    <Check className="w-4 h-4 text-emerald-600" />
                    ${selectedFlight.price.toFixed(0)}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-zinc-400 font-light">No flight selected yet.</p>
              )}
            </div>
            <div className="bg-white p-5">
              <div className="flex items-center gap-2 mb-3">
                <BedDouble className="w-4 h-4 text-zinc-400" strokeWidth={1.5} />
                <span className="text-[10px] uppercase tracking-[0.25em] font-semibold text-zinc-400">Selected Hotel</span>
              </div>
              {selectedHotel ? (
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-zinc-900 truncate">{selectedHotel.name}</div>
                    <div className="text-[11px] text-zinc-400">
                      {selectedHotel.stars}★ · {selectedHotel.nights} night(s)
                    </div>
                  </div>
                  <div className="text-xl font-light flex items-center gap-2">
                    <Check className="w-4 h-4 text-emerald-600" />
                    ${selectedHotel.price.toFixed(0)}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-zinc-400 font-light">No hotel selected yet.</p>
              )}
            </div>
          </div>

          {/* Tabs: separate flight vs hotel search */}
          <div className="flex items-center justify-between border-b border-zinc-100 mb-8">
            <div className="flex">
              <button
                onClick={() => setBookingTab('flight')}
                className={`flex items-center gap-2 px-5 py-3 text-xs uppercase tracking-widest font-medium transition-colors border-b-2 -mb-px ${
                  bookingTab === 'flight' ? 'border-zinc-950 text-zinc-950' : 'border-transparent text-zinc-400 hover:text-zinc-700'
                }`}
              >
                <Plane className="w-4 h-4" /> Flights
              </button>
              <button
                onClick={() => setBookingTab('hotel')}
                className={`flex items-center gap-2 px-5 py-3 text-xs uppercase tracking-widest font-medium transition-colors border-b-2 -mb-px ${
                  bookingTab === 'hotel' ? 'border-zinc-950 text-zinc-950' : 'border-transparent text-zinc-400 hover:text-zinc-700'
                }`}
              >
                <BedDouble className="w-4 h-4" /> Hotels
              </button>
            </div>
            <button
              onClick={bookingTab === 'flight' ? onOpenFlightSearch : onOpenHotelSearch}
              className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-medium text-zinc-400 hover:text-zinc-950 transition-colors"
            >
              Full {bookingTab === 'flight' ? 'flight' : 'hotel'} search
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {bookingTab === 'flight' ? (
            <BookingSearch
              mode="flight"
              variant="embedded"
              trip={bookingContext}
              selectedFlightId={selectedFlight?.id ?? null}
              onSelectFlight={onSelectFlight}
            />
          ) : (
            <BookingSearch
              mode="hotel"
              variant="embedded"
              trip={bookingContext}
              selectedHotelId={selectedHotel?.id ?? null}
              onSelectHotel={onSelectHotel}
            />
          )}
        </section>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-y-24 gap-x-12">

        {/* ── Left column: Gemini trip plan content ── */}
        <section className="lg:col-span-3 space-y-20 border-r border-zinc-100 pr-12">
          {plan ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-20"
            >
              <div className="space-y-6">
                <div className="space-y-6">
                  <label className="text-[10px] uppercase tracking-widest font-bold text-zinc-300">Optimal Sequence</label>
                  <div className="space-y-2">
                    <h3 className="text-4xl font-light tracking-tight">
                      {currentTripDates
                        ? formatDateRange(currentTripDates.startDate, currentTripDates.endDate)
                        : savedTrip
                          ? formatDateRange(savedTrip.start_date, savedTrip.end_date)
                          : plan.bestTimeToTravel.period}
                    </h3>
                    <div className="flex items-center gap-2 text-sm text-zinc-400">
                      <span className="w-2 h-2 rounded-full bg-zinc-950" />
                      {weatherSummary
                        ? `${weatherSummary.low_c}°C – ${weatherSummary.high_c}°C · ${weatherSummary.condition}`
                        : plan.bestTimeToTravel.weather}
                    </div>
                  </div>
                  <p className="text-sm font-light leading-relaxed text-zinc-500 max-w-sm">
                    {plan.bestTimeToTravel.reason}
                  </p>
                </div>
              </div>

              <div className="space-y-8">
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
                      className={`w-full flex flex-col items-center justify-center text-center p-6 border transition-all ${
                        selected
                          ? 'border-zinc-900 bg-zinc-950 text-white'
                          : 'border-zinc-200 bg-zinc-50 hover:border-zinc-400'
                      }`}
                    >
                      <div className={`text-[11px] uppercase tracking-[0.25em] font-medium mb-4 ${selected ? 'text-zinc-300' : 'text-zinc-500'}`}>
                        {tier}
                      </div>
                      <div className="text-sm font-light mb-1">Flight: ${entry.flight_cost.toFixed(0)}</div>
                      <div className="text-sm font-light mb-1">Hotel/day: ${entry.hotel_daily_cost.toFixed(0)}</div>
                      <div className="text-sm font-light mb-1">Living/day: ${entry.local_daily_cost.toFixed(0)}</div>
                      <div className="text-sm font-light mb-1">Stay: {effectivePricingSnapshot.trip_duration_days} day(s)</div>
                      <div className="text-lg mt-4 font-semibold tracking-wide">Final: ${entry.total_trip_cost.toFixed(0)}</div>
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

          <div className="space-y-6 pt-12 border-t border-zinc-100">
            <label className="text-[10px] uppercase tracking-widest font-bold text-zinc-300">Weather at Destination</label>
            {isWeatherLoading ? (
              <WeatherSkeleton />
            ) : weatherSummary ? (
              <WeatherWidget summary={weatherSummary} />
            ) : (
              <p className="text-[11px] text-zinc-400 font-light">
                {weatherError ?? 'Weather data unavailable.'}
              </p>
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
