import { useState } from 'react';
import { motion } from 'motion/react';
import { TripInput } from '../types/trip';

const INTERESTS = ['Food', 'Art', 'History', 'Nature', 'Nightlife', 'Shopping', 'Adventure'];

interface TripFormProps {
  onSubmit: (input: TripInput) => void;
  initialData?: Partial<TripInput>;
}

export default function TripForm({ onSubmit, initialData }: TripFormProps) {
  const [formData, setFormData] = useState<Partial<TripInput>>({
    originCountry: initialData?.originCountry || '',
    destination: initialData?.destination || '',
    budget: initialData?.budget || 'moderate',
    travelers: initialData?.travelers || 1,
    startDate: initialData?.startDate || '',
    endDate: initialData?.endDate || '',
    interests: initialData?.interests || []
  });

  const toggleInterest = (interest: string) => {
    const current = formData.interests || [];
    if (current.includes(interest)) {
      setFormData({ ...formData, interests: current.filter(i => i !== interest) });
    } else {
      setFormData({ ...formData, interests: [...current, interest] });
    }
  };

  return (
    <div className="max-w-3xl">
      <div className="mb-20">
        <h2 className="text-xs uppercase tracking-[0.4em] font-medium text-zinc-400 mb-4">Phase 01 / Definition</h2>
        <p className="text-4xl font-light tracking-tight text-zinc-900 leading-tight">
          Specify the parameters <br />of your next journey.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-16">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
          <div className="space-y-4">
            <label className="text-[10px] uppercase tracking-widest font-semibold text-zinc-400">Origin Country</label>
            <input
              id="origin-country-input"
              type="text"
              value={formData.originCountry || ''}
              placeholder="Country of departure"
              className="w-full bg-transparent border-b border-zinc-200 py-6 text-2xl focus:border-zinc-950 outline-none transition-colors placeholder:text-zinc-200 font-light"
              onChange={(e) => setFormData({ ...formData, originCountry: e.target.value })}
            />
          </div>
          <div className="space-y-4">
            <label className="text-[10px] uppercase tracking-widest font-semibold text-zinc-400">Destination Country</label>
            <input
              id="destination-input"
              type="text"
              value={formData.destination || ''}
              placeholder="Country or city to visit"
              className="w-full bg-transparent border-b border-zinc-200 py-6 text-2xl focus:border-zinc-950 outline-none transition-colors placeholder:text-zinc-200 font-light"
              onChange={(e) => setFormData({ ...formData, destination: e.target.value })}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-16">
          <div className="space-y-4 text-sm">
            <label className="text-[10px] uppercase tracking-widest font-semibold text-zinc-400">Arrival / Departure</label>
            <div className="flex gap-4">
              <input
                id="start-date-input"
                type="date"
                value={formData.startDate || ''}
                className="bg-transparent border-b border-zinc-200 py-4 flex-1 outline-none focus:border-zinc-950 transition-colors"
                onChange={(e) => setFormData({ ...formData, startDate: e.target.value })}
              />
              <input
                id="end-date-input"
                type="date"
                value={formData.endDate || ''}
                className="bg-transparent border-b border-zinc-200 py-4 flex-1 outline-none focus:border-zinc-950 transition-colors"
                onChange={(e) => setFormData({ ...formData, endDate: e.target.value })}
              />
            </div>
          </div>

          <div className="space-y-4">
            <label className="text-[10px] uppercase tracking-widest font-semibold text-zinc-400">Group Size</label>
            <input
              id="travelers-input"
              type="number"
              min="1"
              value={formData.travelers || 1}
              placeholder="1"
              className="w-full bg-transparent border-b border-zinc-200 py-4 text-xl outline-none focus:border-zinc-950 transition-colors"
              onChange={(e) => {
                const value = Number(e.target.value);
                setFormData({ ...formData, travelers: Number.isNaN(value) ? 1 : value });
              }}
            />
          </div>
        </div>

        <div className="space-y-6">
          <label className="text-[10px] uppercase tracking-widest font-semibold text-zinc-400">Interests</label>
          <div className="flex flex-wrap gap-2">
            {INTERESTS.map((interest) => (
              <button
                key={interest}
                onClick={() => toggleInterest(interest)}
                className={`px-6 py-3 text-xs tracking-widest uppercase transition-all border ${
                  formData.interests?.includes(interest)
                    ? 'bg-zinc-950 text-white border-zinc-950'
                    : 'bg-transparent text-zinc-400 border-zinc-100 hover:border-zinc-300'
                }`}
              >
                {interest}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <label className="text-[10px] uppercase tracking-widest font-semibold text-zinc-400">Economic Profile</label>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
            {['cheapest', 'affordable', 'moderate', 'luxury'].map((lvl) => (
              <button
                key={lvl}
                onClick={() => setFormData({ ...formData, budget: lvl as any })}
                className={`py-4 text-[10px] uppercase tracking-[0.2em] transition-all border ${
                  formData.budget === lvl
                    ? 'bg-zinc-950 text-white border-zinc-950'
                    : 'bg-transparent text-zinc-400 border-zinc-100 hover:border-zinc-300'
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-24 pt-16 border-t border-zinc-100 italic font-light text-zinc-400 text-sm">
        All inputs will be stored and processed by our predictive models to architect your ideal exploration sequence.
      </div>

      <div className="mt-12">
        <button
          id="confirm-trip-btn"
          disabled={!formData.originCountry || !formData.destination || !formData.startDate || !formData.endDate}
          onClick={() => onSubmit(formData as TripInput)}
          className="w-full py-6 bg-zinc-950 text-white font-medium uppercase tracking-[0.3em] text-xs disabled:opacity-20 transition-all hover:bg-zinc-800"
        >
          Confirm Requirements
        </button>
      </div>
    </div>
  );
}
