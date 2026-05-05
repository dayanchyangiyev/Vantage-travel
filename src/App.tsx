/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronRight, ArrowLeft, User as UserIcon, LogOut } from "lucide-react";
import { DynamicTierQuote, SavedTrip, TripInput, TripPlan } from "./types/trip";
import { generateTripPlan } from "./lib/gemini";
import { fetchCurrentTrip, saveTrip } from "./lib/trips";
import { fetchDynamicTierQuote } from "./lib/dynamicPricing";
import TripForm from "./components/TripForm";
import Dashboard from "./components/Dashboard";
import Login from "./components/Login";
import Register from "./components/Register";
import { useAuth } from "./context/AuthContext";

type Step = "landing" | "login" | "register" | "form" | "loading" | "dashboard";

export default function App() {
  const [step, setStep] = useState<Step>("landing");
  const [tripPlan, setTripPlan] = useState<TripPlan | null>(null);
  const [savedTrip, setSavedTrip] = useState<SavedTrip | null>(null);
  const [livePricingSnapshot, setLivePricingSnapshot] = useState<DynamicTierQuote | null>(null);
  const [isLoadingSavedTrip, setIsLoadingSavedTrip] = useState(false);
  const { isAuthenticated, token, user, logout } = useAuth();

  useEffect(() => {
    let isCancelled = false;

    async function loadSavedTrip() {
      if (!isAuthenticated || !token) {
        setSavedTrip(null);
        return;
      }

      setIsLoadingSavedTrip(true);
      try {
        const trip = await fetchCurrentTrip(token);
        if (isCancelled) {
          return;
        }

        setSavedTrip(trip);
        setLivePricingSnapshot(
          trip?.pricing_snapshot && "tiers" in trip.pricing_snapshot
            ? (trip.pricing_snapshot as DynamicTierQuote)
            : null
        );
        if (trip?.engine_output && Object.keys(trip.engine_output).length > 0) {
          setTripPlan(trip.engine_output);
          setStep("dashboard");
        }
      } catch (error) {
        console.error("Failed to load saved trip", error);
      } finally {
        if (!isCancelled) {
          setIsLoadingSavedTrip(false);
        }
      }
    }

    loadSavedTrip();
    return () => {
      isCancelled = true;
    };
  }, [isAuthenticated, token]);

  const initialTripInput = useMemo<Partial<TripInput> | undefined>(() => {
    if (!savedTrip) {
      return undefined;
    }

    return {
      originCountry: savedTrip.origin_country,
      destination: savedTrip.destination,
      travelers: savedTrip.travelers,
      startDate: savedTrip.start_date,
      endDate: savedTrip.end_date,
      budget: savedTrip.budget_profile,
      interests: savedTrip.interests || [],
    };
  }, [savedTrip]);

  const handleStartTrip = async (input: TripInput) => {
    setStep("loading");
    try {
      const destinationParts = (input.destination || "")
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean);
      const destinationCity = destinationParts[0] || input.destination;
      const destinationCountry =
        destinationParts[destinationParts.length - 1] || input.destination;

      let pricingSnapshot: DynamicTierQuote | null = null;
      try {
        pricingSnapshot = await fetchDynamicTierQuote({
          originCity: input.originCountry,
          destinationCity,
          destinationCountry,
          departureDate: input.startDate,
          returnDate: input.endDate,
          adults: input.travelers,
          currency: "USD",
        });
        setLivePricingSnapshot(pricingSnapshot);
      } catch (pricingError) {
        console.error("Failed to fetch pricing snapshot", pricingError);
        setLivePricingSnapshot(null);
      }

      const plan = await generateTripPlan(input);
      setTripPlan(plan);

      if (isAuthenticated && token) {
        try {
          const persistedTrip = await saveTrip(
            token,
            { ...input, pricingSnapshot },
            plan
          );
          setSavedTrip(persistedTrip);
        } catch (saveError) {
          console.error("Trip generated but failed to save", saveError);
        }
      }

      setStep("dashboard");
    } catch (err) {
      console.error(err);
      setStep("form");
    }
  };

  const handleLogout = () => {
    logout();
    setTripPlan(null);
    setSavedTrip(null);
    setLivePricingSnapshot(null);
    setStep("landing");
  };

  const hasSavedPlan = !!(savedTrip && tripPlan);

  return (
    <div className="min-h-screen bg-white text-zinc-950 font-sans">
      <AnimatePresence mode="wait">
        {step === "landing" && (
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
              className="absolute top-8 right-8 flex gap-4"
            >
              {isAuthenticated ? (
                <div className="flex items-center gap-4">
                  <span className="text-sm font-medium text-zinc-600 flex items-center gap-2">
                    <UserIcon className="w-4 h-4" />
                    {user?.username}
                  </span>
                  <button
                    onClick={handleLogout}
                    className="text-xs uppercase tracking-widest font-medium text-zinc-400 hover:text-zinc-900 transition-colors flex items-center gap-2"
                  >
                    <LogOut className="w-4 h-4" />
                    Logout
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setStep("login")}
                  className="text-xs uppercase tracking-widest font-medium text-zinc-500 hover:text-zinc-900 transition-colors"
                >
                  Sign In
                </button>
              )}
            </motion.div>

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

            <div className="flex flex-col sm:flex-row gap-4 items-center">
              <motion.button
                id="start-planning-btn"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.4 }}
                onClick={() => setStep("form")}
                className="flex items-center gap-6 px-10 py-4 bg-zinc-950 text-white rounded-none font-light tracking-wide transition-all hover:bg-zinc-800"
              >
                Search New Trip
                <ChevronRight className="w-4 h-4" />
              </motion.button>

              {hasSavedPlan && (
                <motion.button
                  id="continue-previous-trip-btn"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.45 }}
                  onClick={() => setStep("dashboard")}
                  className="flex items-center gap-6 px-10 py-4 border border-zinc-300 text-zinc-900 rounded-none font-light tracking-wide transition-all hover:border-zinc-900"
                >
                  Continue Previous Trip
                  <ChevronRight className="w-4 h-4" />
                </motion.button>
              )}
            </div>

            {isAuthenticated && isLoadingSavedTrip && (
              <p className="mt-5 text-xs tracking-widest uppercase text-zinc-400">
                Loading your saved preferences...
              </p>
            )}
          </motion.div>
        )}

        {step === "form" && (
          <motion.div
            key="form"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="max-w-4xl mx-auto px-6 py-24"
          >
            <button
              onClick={() => setStep("landing")}
              className="flex items-center gap-2 text-zinc-400 hover:text-zinc-900 transition-colors mb-16 text-sm tracking-widest uppercase font-medium"
            >
              <ArrowLeft className="w-4 h-4" />
              Index
            </button>
            <TripForm
              key={savedTrip?.id ?? "new-trip"}
              onSubmit={handleStartTrip}
              initialData={initialTripInput}
            />
          </motion.div>
        )}

        {step === "loading" && (
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
            <h2 className="text-xs uppercase tracking-[0.4em] font-light text-zinc-400">
              Processing Requirements
            </h2>
          </motion.div>
        )}

        {step === "login" && (
          <motion.div
            key="login"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center justify-center min-h-screen px-6 py-24"
          >
            <Login
              onBack={() => setStep("landing")}
              onSuccess={() => setStep("landing")}
              onNavigateRegister={() => setStep("register")}
            />
          </motion.div>
        )}

        {step === "register" && (
          <motion.div
            key="register"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center justify-center min-h-screen px-6 py-24"
          >
            <Register
              onBack={() => setStep("landing")}
              onSuccess={() => setStep("login")}
              onNavigateLogin={() => setStep("login")}
            />
          </motion.div>
        )}

        {step === "dashboard" && tripPlan && (
          <motion.div key="dashboard" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <Dashboard
              plan={tripPlan}
              savedTrip={savedTrip}
              pricingSnapshot={livePricingSnapshot}
              onBack={() => setStep(isAuthenticated ? "landing" : "form")}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
