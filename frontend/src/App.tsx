/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronRight, ArrowLeft, User as UserIcon, LogOut } from "lucide-react";
import { DynamicTierQuote, FlightOption, HotelOption, SavedTrip, TripInput, TripPlan, WeatherSummary } from "./types/trip";
import { generateTripPlan } from "./lib/gemini";
import { fetchCurrentTrip, saveTrip } from "./lib/trips";
import { fetchDynamicTierQuote } from "./lib/dynamicPricing";
import { fetchWeatherSummary } from "./lib/weather";
import { saveSelection } from "./lib/search";
import TripForm from "./components/TripForm";
import Dashboard from "./components/Dashboard";
import BookingSearch, { BookingTripContext } from "./components/BookingSearch";
import Checkout from "./components/Checkout";
import Bookings from "./components/Bookings";
import Login from "./components/Login";
import Register from "./components/Register";
import { useAuth } from "./context/AuthContext";

type Step = "landing" | "login" | "register" | "form" | "dashboard" | "flight-search" | "hotel-search" | "checkout" | "bookings";

function splitDestination(destination: string): { city: string; country: string } {
  const parts = (destination || "").split(",").map((p) => p.trim()).filter(Boolean);
  return {
    city: parts[0] || destination,
    country: parts[parts.length - 1] || destination,
  };
}

export default function App() {
  const [step, setStep] = useState<Step>("landing");
  const [currentTripInput, setCurrentTripInput] = useState<TripInput | null>(null);
  const [tripPlan, setTripPlan] = useState<TripPlan | null>(null);
  const [savedTrip, setSavedTrip] = useState<SavedTrip | null>(null);
  const [livePricingSnapshot, setLivePricingSnapshot] = useState<DynamicTierQuote | null>(null);
  const [weatherSummary, setWeatherSummary] = useState<WeatherSummary | null>(null);
  const [weatherError, setWeatherError] = useState<string | null>(null);
  const [currentTripDates, setCurrentTripDates] = useState<{ startDate: string; endDate: string } | null>(null);
  const [isLoadingSavedTrip, setIsLoadingSavedTrip] = useState(false);
  const [isPricingLoading, setIsPricingLoading] = useState(false);
  const [isWeatherLoading, setIsWeatherLoading] = useState(false);
  const [pricingError, setPricingError] = useState<string | null>(null);
  const [selectedFlight, setSelectedFlight] = useState<FlightOption | null>(null);
  const [selectedHotel, setSelectedHotel] = useState<HotelOption | null>(null);
  const { isAuthenticated, token, user, logout } = useAuth();

  useEffect(() => {
    let isCancelled = false;

    async function loadSavedTrip() {
      if (!isAuthenticated || !token) {
        // We only clear savedTrip if we are resetting the state, not handled here.
        return;
      }

      // If we already have a trip plan in memory (e.g. user just created one anonymously),
      // we shouldn't overwrite it with their old saved trip.
      if (tripPlan) {
        return;
      }

      setIsLoadingSavedTrip(true);
      try {
        const trip = await fetchCurrentTrip(token);
        if (isCancelled) {
          return;
        }

        setSavedTrip(trip);
        setSelectedFlight(trip?.selected_flight ?? null);
        setSelectedHotel(trip?.selected_hotel ?? null);
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
  // We only run loadSavedTrip when auth state changes, and we do not want it to re-run
  // just because tripPlan changes, so we intentionally exclude tripPlan from deps.
  // eslint-disable-next-line react-hooks/exhaustive-deps
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

  const bookingContext = useMemo<BookingTripContext | null>(() => {
    const origin = currentTripInput?.originCountry || savedTrip?.origin_country || "";
    const destination = currentTripInput?.destination || savedTrip?.destination || "";
    const startDate = currentTripInput?.startDate || savedTrip?.start_date || "";
    const endDate = currentTripInput?.endDate || savedTrip?.end_date || "";
    const travelers = currentTripInput?.travelers || savedTrip?.travelers || 1;
    if (!destination || !startDate || !endDate) {
      return null;
    }
    const { city, country } = splitDestination(destination);
    return {
      origin,
      destinationCity: city,
      destinationCountry: country,
      startDate,
      endDate,
      travelers,
    };
  }, [currentTripInput, savedTrip]);

  const handleSelectFlight = (option: FlightOption) => {
    setSelectedFlight(option);
    if (isAuthenticated && token && savedTrip) {
      saveSelection(token, savedTrip.id, { selected_flight: option }).catch((e) =>
        console.error("Failed to save flight selection", e)
      );
    }
  };

  const handleSelectHotel = (option: HotelOption) => {
    setSelectedHotel(option);
    if (isAuthenticated && token && savedTrip) {
      saveSelection(token, savedTrip.id, { selected_hotel: option }).catch((e) =>
        console.error("Failed to save hotel selection", e)
      );
    }
  };

  const handleStartTrip = async (input: TripInput) => {
    // Save input in case user decides to sign in / register later
    setCurrentTripInput(input);

    // Go to dashboard immediately — no full-screen loading step
    setTripPlan(null);
    setSelectedFlight(null);
    setSelectedHotel(null);
    setLivePricingSnapshot(null);
    setWeatherSummary(null);
    setWeatherError(null);
    setPricingError(null);
    setIsPricingLoading(true);
    setIsWeatherLoading(true);
    setCurrentTripDates({ startDate: input.startDate, endDate: input.endDate });
    setStep("dashboard");

    const destinationParts = (input.destination || "")
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean);
    const destinationCity = destinationParts[0] || input.destination;
    const destinationCountry = destinationParts[destinationParts.length - 1] || input.destination;

    // Run pricing, Gemini, and weather in parallel — dashboard shows skeletons while they load
    const [pricingResult, planResult, weatherResult] = await Promise.allSettled([
      fetchDynamicTierQuote({
        originCity: input.originCountry,
        destinationCity,
        destinationCountry,
        departureDate: input.startDate,
        returnDate: input.endDate,
        adults: input.travelers,
        currency: "USD",
      }),
      generateTripPlan(input),
      fetchWeatherSummary({
        destinationCity,
        destinationCountry,
        startDate: input.startDate,
        endDate: input.endDate,
      }),
    ]);

    // Handle pricing result
    let pricingSnapshot: DynamicTierQuote | null = null;
    if (pricingResult.status === "fulfilled") {
      pricingSnapshot = pricingResult.value;
      setLivePricingSnapshot(pricingSnapshot);
      setPricingError(null);
    } else {
      const msg = pricingResult.reason?.message || "Could not retrieve pricing data. Please try again later.";
      setPricingError(msg);
      console.error("Pricing fetch failed:", pricingResult.reason);
    }
    setIsPricingLoading(false);

    // Handle weather result
    if (weatherResult.status === "fulfilled") {
      setWeatherSummary(weatherResult.value);
      setWeatherError(null);
    } else {
      const msg = weatherResult.reason?.message || "Weather data unavailable.";
      setWeatherError(msg);
      console.error("Weather fetch failed:", weatherResult.reason);
    }
    setIsWeatherLoading(false);

    // Handle Gemini plan result
    if (planResult.status === "fulfilled") {
      const plan = planResult.value;
      setTripPlan(plan);

      // Save the trip in the background if authenticated
      if (isAuthenticated && token) {
        try {
          const persistedTrip = await saveTrip(
            token,
            { ...input, pricingSnapshot },
            plan
          );
          setSavedTrip(persistedTrip);
        } catch (saveError) {
          console.error("Trip generated but failed to save:", saveError);
        }
      }
    } else {
      console.error("Trip plan generation failed:", planResult.reason);
      // Plan stays null — dashboard shows skeletons with no data
      // User can go back and retry
    }
  };

  const handleLogout = () => {
    logout();
    setCurrentTripInput(null);
    setTripPlan(null);
    setSavedTrip(null);
    setLivePricingSnapshot(null);
    setWeatherSummary(null);
    setWeatherError(null);
    setCurrentTripDates(null);
    setSelectedFlight(null);
    setSelectedHotel(null);
    setIsPricingLoading(false);
    setIsWeatherLoading(false);
    setPricingError(null);
    setStep("landing");
  };

  const handleAuthSuccess = async () => {
    const activeToken = localStorage.getItem('access_token');
    
    if (activeToken && tripPlan && currentTripInput) {
      try {
        const persistedTrip = await saveTrip(
          activeToken,
          { ...currentTripInput, pricingSnapshot: livePricingSnapshot },
          tripPlan
        );
        setSavedTrip(persistedTrip);
        setStep("dashboard");
      } catch (error) {
        console.error("Failed to save generated trip to new account:", error);
        setStep("dashboard");
      }
    } else {
      setStep(tripPlan ? "dashboard" : "landing");
    }
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


        {step === "login" && (
          <motion.div
            key="login"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex items-center justify-center min-h-screen px-6 py-24"
          >
            <Login
              onBack={() => setStep(tripPlan ? "dashboard" : "landing")}
              onSuccess={handleAuthSuccess}
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
              onBack={() => setStep(tripPlan ? "dashboard" : "landing")}
              onSuccess={() => setStep("login")}
              onNavigateLogin={() => setStep("login")}
            />
          </motion.div>
        )}

        {step === "dashboard" && (
          <motion.div key="dashboard" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <Dashboard
              isAuthenticated={isAuthenticated}
              token={token}
              onLogin={() => setStep("login")}
              onRegister={() => setStep("register")}
              plan={tripPlan}
              savedTrip={savedTrip}
              currentTripDates={currentTripDates}
              pricingSnapshot={livePricingSnapshot}
              isPricingLoading={isPricingLoading}
              pricingError={pricingError}
              weatherSummary={weatherSummary}
              weatherError={weatherError}
              isWeatherLoading={isWeatherLoading}
              bookingContext={bookingContext}
              selectedFlight={selectedFlight}
              selectedHotel={selectedHotel}
              onSelectFlight={handleSelectFlight}
              onSelectHotel={handleSelectHotel}
              onOpenFlightSearch={() => setStep("flight-search")}
              onOpenHotelSearch={() => setStep("hotel-search")}
              onOpenCheckout={() => setStep("checkout")}
              onOpenBookings={() => setStep("bookings")}
              onBack={() => setStep(isAuthenticated ? "landing" : "form")}
            />
          </motion.div>
        )}

        {step === "flight-search" && bookingContext && (
          <motion.div key="flight-search" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <BookingSearch
              mode="flight"
              variant="full"
              trip={bookingContext}
              selectedFlightId={selectedFlight?.id ?? null}
              onSelectFlight={handleSelectFlight}
              onBack={() => setStep("dashboard")}
            />
          </motion.div>
        )}

        {step === "hotel-search" && bookingContext && (
          <motion.div key="hotel-search" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <BookingSearch
              mode="hotel"
              variant="full"
              trip={bookingContext}
              selectedHotelId={selectedHotel?.id ?? null}
              onSelectHotel={handleSelectHotel}
              onBack={() => setStep("dashboard")}
            />
          </motion.div>
        )}

        {step === "checkout" && bookingContext && (
          <motion.div key="checkout" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <Checkout
              trip={bookingContext}
              selectedFlight={selectedFlight}
              selectedHotel={selectedHotel}
              customerEmail={user?.email}
              token={token}
              onViewBookings={() => setStep("bookings")}
              onBack={() => setStep("dashboard")}
            />
          </motion.div>
        )}

        {step === "bookings" && (
          <motion.div key="bookings" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <Bookings token={token} onBack={() => setStep("dashboard")} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
