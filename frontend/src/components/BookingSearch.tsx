import { useCallback, useEffect, useState } from 'react';
import { motion } from 'motion/react';
import {
  ArrowLeft, Plane, BedDouble, Search, AlertTriangle, Check,
  Star, Clock, RefreshCw,
} from 'lucide-react';
import {
  CategorizedFlightOptions, CategorizedHotelOptions, FlightOption, HotelOption, TierKey,
} from '../types/trip';
import { searchFlights, searchHotels } from '../lib/search';

const TIERS: TierKey[] = ['cheapest', 'affordable', 'moderate', 'luxury'];

const TIER_LABEL: Record<TierKey, string> = {
  cheapest: 'Cheapest',
  affordable: 'Affordable',
  moderate: 'Moderate',
  luxury: 'Luxury',
};

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------
function formatDuration(minutes: number): string {
  if (!minutes) return '—';
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

function formatClock(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

function stopsLabel(stops: number): string {
  if (stops <= 0) return 'Direct';
  return stops === 1 ? '1 stop' : `${stops} stops`;
}

// ---------------------------------------------------------------------------
// Shared field components
// ---------------------------------------------------------------------------
function Field({
  label, children,
}: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-2 min-w-0">
      <span className="text-[9px] uppercase tracking-[0.2em] font-semibold text-zinc-400">{label}</span>
      {children}
    </label>
  );
}

const inputClass =
  'bg-transparent border-b border-zinc-200 py-2 text-sm outline-none focus:border-zinc-950 transition-colors w-full';

// ---------------------------------------------------------------------------
// Option cards
// ---------------------------------------------------------------------------
function FlightCard({
  option, selected, onSelect,
}: { option: FlightOption; selected: boolean; onSelect: () => void }) {
  return (
    <button
      onClick={onSelect}
      className={`group relative w-full text-left p-5 border transition-all ${
        selected ? 'border-zinc-900 bg-zinc-950 text-white' : 'border-zinc-200 bg-white hover:border-zinc-400'
      }`}
    >
      {selected && (
        <span className="absolute top-3 right-3 flex items-center gap-1 text-[9px] uppercase tracking-widest">
          <Check className="w-3 h-3" /> Selected
        </span>
      )}
      <div className="flex items-center gap-2 mb-3">
        <Plane className={`w-4 h-4 ${selected ? 'text-zinc-300' : 'text-zinc-400'}`} strokeWidth={1.5} />
        <span className="text-sm font-medium truncate">{option.airline}</span>
      </div>
      <div className="text-2xl font-light tracking-tight mb-3">
        ${option.price.toFixed(0)}
        <span className={`ml-1 text-[10px] uppercase tracking-widest ${selected ? 'text-zinc-400' : 'text-zinc-300'}`}>
          {option.currency}
        </span>
      </div>
      <div className={`flex items-center justify-between text-[11px] ${selected ? 'text-zinc-300' : 'text-zinc-500'}`}>
        <span>{formatClock(option.departure_time)} → {formatClock(option.arrival_time)}</span>
        <span>{option.origin}–{option.destination}</span>
      </div>
      <div className={`mt-2 flex items-center gap-3 text-[10px] uppercase tracking-wider ${selected ? 'text-zinc-400' : 'text-zinc-400'}`}>
        <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{formatDuration(option.duration_minutes)}</span>
        <span>·</span>
        <span>{stopsLabel(option.stops)}</span>
      </div>
    </button>
  );
}

function HotelCard({
  option, selected, onSelect,
}: { option: HotelOption; selected: boolean; onSelect: () => void }) {
  const perNight = option.nights > 0 ? option.price / option.nights : option.price;
  return (
    <button
      onClick={onSelect}
      className={`group relative w-full text-left border transition-all overflow-hidden ${
        selected ? 'border-zinc-900 bg-zinc-950 text-white' : 'border-zinc-200 bg-white hover:border-zinc-400'
      }`}
    >
      {option.thumbnail ? (
        <div className="h-28 w-full overflow-hidden bg-zinc-100">
          <img src={option.thumbnail} alt={option.name} className="h-full w-full object-cover" loading="lazy" />
        </div>
      ) : (
        <div className="h-28 w-full flex items-center justify-center bg-zinc-100">
          <BedDouble className="w-6 h-6 text-zinc-300" strokeWidth={1.25} />
        </div>
      )}
      <div className="p-5">
        {selected && (
          <span className="absolute top-3 right-3 flex items-center gap-1 text-[9px] uppercase tracking-widest bg-zinc-950/80 px-2 py-1">
            <Check className="w-3 h-3" /> Selected
          </span>
        )}
        <div className="flex items-center gap-1 mb-1">
          {Array.from({ length: Math.min(option.stars, 5) }).map((_, i) => (
            <Star key={i} className={`w-3 h-3 ${selected ? 'text-amber-300' : 'text-amber-400'}`} fill="currentColor" strokeWidth={0} />
          ))}
          {option.rating > 0 && (
            <span className={`ml-1 text-[10px] tabular-nums ${selected ? 'text-zinc-300' : 'text-zinc-400'}`}>
              {option.rating.toFixed(1)}
            </span>
          )}
        </div>
        <div className="text-sm font-medium leading-snug mb-2 truncate">{option.name}</div>
        <div className="text-2xl font-light tracking-tight">
          ${option.price.toFixed(0)}
          <span className={`ml-1 text-[10px] uppercase tracking-widest ${selected ? 'text-zinc-400' : 'text-zinc-300'}`}>
            total · {option.nights}n
          </span>
        </div>
        <div className={`mt-1 text-[11px] ${selected ? 'text-zinc-300' : 'text-zinc-500'}`}>
          ${perNight.toFixed(0)}/night · {option.board_name}
        </div>
        <div className="mt-2">
          <span className={`text-[9px] uppercase tracking-widest font-semibold ${
            option.refundable ? (selected ? 'text-emerald-300' : 'text-emerald-600') : (selected ? 'text-zinc-500' : 'text-zinc-400')
          }`}>
            {option.refundable ? 'Refundable' : 'Non-refundable'}
          </span>
        </div>
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// BookingSearch — flight OR hotel search with tiered, selectable options
// ---------------------------------------------------------------------------
export interface BookingTripContext {
  origin: string;
  destinationCity: string;
  destinationCountry: string;
  startDate: string;
  endDate: string;
  travelers: number;
}

interface BookingSearchProps {
  mode: 'flight' | 'hotel';
  variant?: 'embedded' | 'full';
  trip: BookingTripContext;
  selectedFlightId?: string | null;
  selectedHotelId?: string | null;
  onSelectFlight?: (option: FlightOption) => void;
  onSelectHotel?: (option: HotelOption) => void;
  onBack?: () => void;
  autoSearch?: boolean;
}

export default function BookingSearch({
  mode, variant = 'embedded', trip,
  selectedFlightId, selectedHotelId, onSelectFlight, onSelectHotel,
  onBack, autoSearch = true,
}: BookingSearchProps) {
  const isFlight = mode === 'flight';

  // Editable search fields, prefilled from the trip context.
  const [origin, setOrigin] = useState(trip.origin);
  const [destinationCity, setDestinationCity] = useState(trip.destinationCity);
  const [destinationCountry, setDestinationCountry] = useState(trip.destinationCountry);
  const [startDate, setStartDate] = useState(trip.startDate);
  const [endDate, setEndDate] = useState(trip.endDate);
  const [travelers, setTravelers] = useState(trip.travelers || 1);

  const [flights, setFlights] = useState<CategorizedFlightOptions | null>(null);
  const [hotels, setHotels] = useState<CategorizedHotelOptions | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runSearch = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      if (isFlight) {
        const result = await searchFlights({
          originCity: origin,
          destinationCity,
          departureDate: startDate,
          returnDate: endDate,
          adults: travelers,
        });
        setFlights(result);
      } else {
        const result = await searchHotels({
          destinationCity,
          destinationCountry,
          checkIn: startDate,
          checkOut: endDate,
          adults: travelers,
        });
        setHotels(result);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Search failed.');
    } finally {
      setIsLoading(false);
    }
  }, [isFlight, origin, destinationCity, destinationCountry, startDate, endDate, travelers]);

  // Auto-run once on mount when the prefilled fields are usable.
  useEffect(() => {
    const ready = isFlight
      ? origin && destinationCity && startDate && endDate
      : destinationCity && startDate && endDate;
    if (autoSearch && ready) {
      runSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const result = isFlight ? flights : hotels;
  const perTier = variant === 'embedded' ? 2 : 3;

  return (
    <div className={variant === 'full' ? 'max-w-6xl mx-auto px-6 py-16' : ''}>
      {variant === 'full' && (
        <button
          onClick={onBack}
          className="flex items-center gap-3 text-xs uppercase tracking-[0.3em] font-medium text-zinc-400 hover:text-zinc-950 transition-colors mb-12"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Summary
        </button>
      )}

      {variant === 'full' && (
        <div className="flex items-center gap-3 mb-6">
          {isFlight
            ? <Plane className="w-5 h-5 text-zinc-900" strokeWidth={1.5} />
            : <BedDouble className="w-5 h-5 text-zinc-900" strokeWidth={1.5} />}
          <h3 className="text-3xl font-light tracking-tight">
            {isFlight ? 'Flight Search' : 'Hotel Search'}
          </h3>
        </div>
      )}

      {/* Search bar */}
      <div className="border border-zinc-100 bg-zinc-50/60 p-5 mb-8">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-5 items-end">
          {isFlight ? (
            <>
              <Field label="From">
                <input className={inputClass} value={origin} onChange={(e) => setOrigin(e.target.value)} placeholder="City or IATA" />
              </Field>
              <Field label="To">
                <input className={inputClass} value={destinationCity} onChange={(e) => setDestinationCity(e.target.value)} placeholder="City or IATA" />
              </Field>
            </>
          ) : (
            <>
              <Field label="City">
                <input className={inputClass} value={destinationCity} onChange={(e) => setDestinationCity(e.target.value)} placeholder="Destination city" />
              </Field>
              <Field label="Country">
                <input className={inputClass} value={destinationCountry} onChange={(e) => setDestinationCountry(e.target.value)} placeholder="Country" />
              </Field>
            </>
          )}
          <Field label={isFlight ? 'Depart' : 'Check-in'}>
            <input type="date" className={inputClass} value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </Field>
          <Field label={isFlight ? 'Return' : 'Check-out'}>
            <input type="date" className={inputClass} value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </Field>
          <div className="flex items-end gap-3">
            <Field label={isFlight ? 'Travelers' : 'Guests'}>
              <input
                type="number" min={1} className={`${inputClass} w-16`} value={travelers}
                onChange={(e) => setTravelers(Math.max(1, Number(e.target.value) || 1))}
              />
            </Field>
            <button
              onClick={runSearch}
              disabled={isLoading}
              className="flex items-center gap-2 px-5 py-2.5 bg-zinc-950 text-white text-[11px] uppercase tracking-widest font-medium hover:bg-zinc-800 transition-colors disabled:opacity-40"
            >
              {isLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
              Search
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      {error ? (
        <div className="border border-red-100 bg-red-50 p-5 flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs text-red-500 font-medium uppercase tracking-widest mb-1">Search unavailable</p>
            <p className="text-xs text-red-400 font-light">{error}</p>
          </div>
        </div>
      ) : isLoading && !result ? (
        <div className="py-16 text-center text-xs uppercase tracking-[0.3em] text-zinc-400">
          Searching {isFlight ? 'flights' : 'hotels'}…
        </div>
      ) : result ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-10">
          {TIERS.map((tier) => {
            const options = (result.tiers[tier] || []).slice(0, perTier);
            return (
              <div key={tier} className="space-y-4">
                <div className="flex items-baseline gap-3">
                  <span className="text-[10px] uppercase tracking-[0.3em] font-bold text-zinc-300">{TIER_LABEL[tier]}</span>
                  <span className="h-px flex-1 bg-zinc-100" />
                </div>
                {options.length ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {options.map((option) =>
                      isFlight ? (
                        <FlightCard
                          key={option.id}
                          option={option as FlightOption}
                          selected={selectedFlightId === option.id}
                          onSelect={() => onSelectFlight?.(option as FlightOption)}
                        />
                      ) : (
                        <HotelCard
                          key={option.id}
                          option={option as HotelOption}
                          selected={selectedHotelId === option.id}
                          onSelect={() => onSelectHotel?.(option as HotelOption)}
                        />
                      )
                    )}
                  </div>
                ) : (
                  <p className="text-[11px] text-zinc-400 font-light">No options in this range.</p>
                )}
              </div>
            );
          })}
        </motion.div>
      ) : (
        <div className="py-12 text-center text-xs uppercase tracking-[0.3em] text-zinc-300">
          Enter details and search.
        </div>
      )}
    </div>
  );
}
