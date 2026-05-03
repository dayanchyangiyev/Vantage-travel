import { motion } from 'motion/react';
import { 
  ArrowLeft,
  MoreHorizontal,
} from 'lucide-react';
import { SavedTrip, TripPlan } from '../types/trip';

export default function Dashboard({
  plan,
  savedTrip,
  onBack,
}: {
  plan: TripPlan;
  savedTrip: SavedTrip | null;
  onBack: () => void;
}) {
  return (
    <div className="max-w-6xl mx-auto px-6 py-20 bg-white">
      {/* Navigation Header */}
      <nav className="flex justify-between items-center mb-24">
        <button
          onClick={onBack}
          className="flex items-center gap-3 text-xs uppercase tracking-[0.3em] font-medium text-zinc-400 hover:text-zinc-950 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Parameters
        </button>
        <div className="text-[10px] uppercase tracking-[0.4em] font-bold text-zinc-950">Vantage / Exploration</div>
        <button className="text-zinc-300 hover:text-zinc-950 transition-colors">
          <MoreHorizontal className="w-5 h-5" />
        </button>
      </nav>

      <header className="mb-32">
        <h1 className="text-7xl font-light tracking-tighter text-zinc-950 mb-6">
          Architectural <br />Summary.
        </h1>
        <div className="w-24 h-px bg-zinc-950" />
        {savedTrip && (
          <div className="mt-10 border border-zinc-100 bg-zinc-50/70 p-6">
            <p className="text-[10px] uppercase tracking-[0.25em] font-semibold text-zinc-400 mb-5">
              Saved Travel Preferences
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
              <div>
                <span className="block text-zinc-400 text-[11px] uppercase tracking-wider mb-1">Origin Country</span>
                <span className="text-zinc-900">{savedTrip.origin_country}</span>
              </div>
              <div>
                <span className="block text-zinc-400 text-[11px] uppercase tracking-wider mb-1">Departure City</span>
                <span className="text-zinc-900">{savedTrip.origin_city || '—'}</span>
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
                <span className="block text-zinc-400 text-[11px] uppercase tracking-wider mb-1">Budget</span>
                <span className="text-zinc-900 uppercase">{savedTrip.budget_profile}</span>
              </div>
              <div>
                <span className="block text-zinc-400 text-[11px] uppercase tracking-wider mb-1">Interests</span>
                <span className="text-zinc-900">
                  {(savedTrip.interests || []).length
                    ? savedTrip.interests.join(', ')
                    : 'None selected'}
                </span>
              </div>
            </div>
          </div>
        )}
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-y-24 gap-x-12">
        {/* Timing Column */}
        <section className="lg:col-span-3 space-y-20 border-r border-zinc-100 pr-12">
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

          {/* Transit Logistics */}
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

          {/* Points of Interest */}
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
        </section>

        {/* Financial Column */}
        <aside className="space-y-16 pl-6">
          <div className="space-y-8">
            <label className="text-[10px] uppercase tracking-widest font-bold text-zinc-300">Fiscal Projection</label>
            <div className="space-y-10">
              {[
                { label: 'Baseline', value: plan.budget.min },
                { label: 'Standard', value: plan.budget.medium },
                { label: 'Comfort', value: plan.budget.comfortable },
                { label: 'Premium', value: plan.budget.luxury },
              ].map((item, i) => (
                <div key={i} className="group">
                  <div className="text-[10px] uppercase tracking-widest text-zinc-300 mb-1">{item.label}</div>
                  <div className="text-3xl font-light tracking-tighter text-zinc-950 group-hover:translate-x-2 transition-transform duration-500">{item.value}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-6 pt-12 border-t border-zinc-100">
             <div className="text-[11px] leading-relaxed text-zinc-400 font-light italic">
               {plan.budget.foodInfo}
             </div>
          </div>

          {/* Temporal Data */}
          <div className="space-y-8 pt-12 border-t border-zinc-100">
            <label className="text-[10px] uppercase tracking-widest font-bold text-zinc-300">Occurrences</label>
            <div className="space-y-8">
              {plan.events.map((event, i) => (
                <div key={i} className="space-y-2">
                  <div className="text-[10px] font-bold text-zinc-950">{event.date}</div>
                  <div className="text-xs text-zinc-500 font-light leading-snug">{event.name} — {event.description}</div>
                </div>
              ))}
            </div>
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
