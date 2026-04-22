/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Plane, ChevronRight, ArrowLeft, MoreHorizontal } from 'lucide-react';
import { TripInput, TripPlan } from './types/trip';
import { generateTripPlan } from './lib/gemini';
import TripForm from './components/TripForm';
import Dashboard from './components/Dashboard';

export default function App() {
  const [step, setStep] = useState<'landing' | 'form' | 'loading' | 'dashboard'>('landing');
  const [tripPlan, setTripPlan] = useState<TripPlan | null>(null);

  const handleStartTrip = (input: TripInput) => {
    setStep('loading');
    generateTripPlan(input).then((plan) => {
      setTripPlan(plan);
      setStep('dashboard');
    }).catch(err => {
      console.error(err);
      setStep('form');
    });
  };

  return (
    <div className="min-h-screen bg-white text-zinc-950 font-sans">
      <AnimatePresence mode="wait">
        {step === 'landing' && (
          <motion.div
            key="landing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex flex-col items-center justify-center min-h-screen px-6 text-center"
          >
            <motion.div
              initial={{ y: 10, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.1 }}
              className="text-[10px] uppercase tracking-[0.3em] font-medium text-zinc-400 mb-6"
            >
              VANTAGE TRAVEL
            </motion.div>

            <motion.h1
              initial={{ y: 10, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.2 }}
              className="text-6xl md:text-8xl font-light tracking-tight mb-10 text-zinc-900"
            >
              Travel Made <br />
              <span className="font-normal">Essential.</span>
            </motion.h1>

            <motion.div
              initial={{ y: 10, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.3 }}
              className="w-px h-24 bg-zinc-200 mb-10"
            />

            <motion.button
              id="start-planning-btn"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.4 }}
              onClick={() => setStep('form')}
              className="flex items-center gap-6 px-10 py-4 bg-zinc-950 text-white rounded-none font-light tracking-wide transition-all hover:bg-zinc-800"
            >
              Start Planning
              <ChevronRight className="w-4 h-4" />
            </motion.button>
          </motion.div>
        )}

        {step === 'form' && (
          <motion.div
            key="form"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="max-w-4xl mx-auto px-6 py-24"
          >
            <button
               onClick={() => setStep('landing')}
               className="flex items-center gap-2 text-zinc-400 hover:text-zinc-900 transition-colors mb-16 text-sm tracking-widest uppercase font-medium"
            >
              <ArrowLeft className="w-4 h-4" />
              Index
            </button>
            <TripForm onSubmit={handleStartTrip} />
          </motion.div>
        )}

        {step === 'loading' && (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 flex flex-col items-center justify-center bg-white"
          >
            <motion.div
              animate={{ scaleX: [0, 1, 0] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
              className="w-48 h-[1px] bg-zinc-900 mb-6"
            />
            <h2 className="text-xs uppercase tracking-[0.4em] font-light text-zinc-400">Processing Requirements</h2>
          </motion.div>
        )}

        {step === 'dashboard' && tripPlan && (
          <motion.div
            key="dashboard"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <Dashboard plan={tripPlan} onBack={() => setStep('form')} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
