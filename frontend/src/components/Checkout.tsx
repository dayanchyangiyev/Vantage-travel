import { useId, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  ArrowLeft, Plane, BedDouble, CreditCard, Check, Lock, ShieldCheck,
  Loader2, User, CalendarCheck,
} from 'lucide-react';
import { FlightOption, HotelOption } from '../types/trip';
import { BookingTripContext } from './BookingSearch';

// ---------------------------------------------------------------------------
// This is a MOCK checkout — no real charge is ever made. It collects realistic
// traveler + card details, validates them client-side, simulates processing,
// and issues a booking reference. For a university demo only.
// ---------------------------------------------------------------------------

type Stage = 'details' | 'payment' | 'processing' | 'confirmed';

const COUNTRIES = [
  'United States', 'United Kingdom', 'Romania', 'Germany', 'France', 'Italy',
  'Spain', 'Turkey', 'Netherlands', 'Canada', 'Australia', 'Japan', 'India',
  'Brazil', 'Mexico', 'United Arab Emirates', 'Other',
];

// ---------------------------------------------------------------------------
// Validation + formatting helpers
// ---------------------------------------------------------------------------
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const NAME_RE = /^[A-Za-zÀ-ÿ' -]{2,}$/;

function onlyDigits(s: string): string {
  return s.replace(/\D/g, '');
}

function detectBrand(num: string): 'visa' | 'mastercard' | 'amex' | 'discover' | null {
  const n = onlyDigits(num);
  if (/^4/.test(n)) return 'visa';
  if (/^3[47]/.test(n)) return 'amex';
  if (/^(5[1-5]|2[2-7])/.test(n)) return 'mastercard';
  if (/^6(011|5)/.test(n)) return 'discover';
  return null;
}

function formatCardNumber(value: string, brand: ReturnType<typeof detectBrand>): string {
  const n = onlyDigits(value).slice(0, brand === 'amex' ? 15 : 16);
  if (brand === 'amex') {
    return n.replace(/^(\d{0,4})(\d{0,6})(\d{0,5}).*/, (_, a, b, c) =>
      [a, b, c].filter(Boolean).join(' ')
    );
  }
  return n.replace(/(\d{4})(?=\d)/g, '$1 ').trim();
}

function luhnValid(num: string): boolean {
  const n = onlyDigits(num);
  if (n.length < 13) return false;
  let sum = 0;
  let dbl = false;
  for (let i = n.length - 1; i >= 0; i--) {
    let d = parseInt(n[i], 10);
    if (dbl) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    sum += d;
    dbl = !dbl;
  }
  return sum % 10 === 0;
}

function formatExpiry(value: string): string {
  const n = onlyDigits(value).slice(0, 4);
  if (n.length <= 2) return n;
  return `${n.slice(0, 2)}/${n.slice(2)}`;
}

function expiryInFuture(value: string): boolean {
  const m = value.match(/^(\d{2})\/(\d{2})$/);
  if (!m) return false;
  const month = parseInt(m[1], 10);
  const year = 2000 + parseInt(m[2], 10);
  if (month < 1 || month > 12) return false;
  const end = new Date(year, month, 0, 23, 59, 59); // last day of month
  return end.getTime() >= Date.now();
}

function ageFromDob(dob: string): number | null {
  if (!dob) return null;
  const d = new Date(dob);
  if (Number.isNaN(d.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  const m = now.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < d.getDate())) age--;
  return age;
}

function makeBookingRef(): string {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let s = '';
  for (let i = 0; i < 6; i++) s += chars[Math.floor(Math.random() * chars.length)];
  return `VTG-${s}`;
}

// ---------------------------------------------------------------------------
// Small field components
// ---------------------------------------------------------------------------
const fieldBase =
  'w-full bg-white border px-3 py-2.5 text-sm outline-none transition-colors rounded-none';

function TextField({
  label, value, onChange, onBlur, error, placeholder, type = 'text',
  maxLength, inputMode, autoComplete, hint,
}: {
  label: string; value: string; onChange: (v: string) => void; onBlur?: () => void;
  error?: string; placeholder?: string; type?: string; maxLength?: number;
  inputMode?: 'text' | 'numeric' | 'email' | 'tel'; autoComplete?: string; hint?: string;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[10px] uppercase tracking-[0.2em] font-semibold text-zinc-500">{label}</label>
      <input
        id={id}
        type={type}
        value={value}
        placeholder={placeholder}
        maxLength={maxLength}
        inputMode={inputMode}
        autoComplete={autoComplete}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        className={`${fieldBase} ${error ? 'border-red-300 focus:border-red-500' : 'border-zinc-200 focus:border-zinc-950'}`}
      />
      {error ? (
        <span className="text-[10px] text-red-500">{error}</span>
      ) : hint ? (
        <span className="text-[10px] text-zinc-400">{hint}</span>
      ) : null}
    </div>
  );
}

function SelectField({
  label, value, onChange, error, options, placeholder,
}: {
  label: string; value: string; onChange: (v: string) => void; error?: string;
  options: string[]; placeholder?: string;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[10px] uppercase tracking-[0.2em] font-semibold text-zinc-500">{label}</label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`${fieldBase} ${error ? 'border-red-300' : 'border-zinc-200 focus:border-zinc-950'} ${value ? 'text-zinc-900' : 'text-zinc-400'}`}
      >
        <option value="">{placeholder || 'Select…'}</option>
        {options.map((o) => (
          <option key={o} value={o} className="text-zinc-900">{o}</option>
        ))}
      </select>
      {error && <span className="text-[10px] text-red-500">{error}</span>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Checkout
// ---------------------------------------------------------------------------
interface CheckoutProps {
  trip: BookingTripContext;
  selectedFlight: FlightOption | null;
  selectedHotel: HotelOption | null;
  customerEmail?: string;
  onBack: () => void;
}

export default function Checkout({
  trip, selectedFlight, selectedHotel, customerEmail, onBack,
}: CheckoutProps) {
  const [stage, setStage] = useState<Stage>('details');
  const [bookingRef, setBookingRef] = useState<string>('');

  // Traveler details
  const [title, setTitle] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [dob, setDob] = useState('');
  const [gender, setGender] = useState('');
  const [nationality, setNationality] = useState('');
  const [email, setEmail] = useState(customerEmail || '');
  const [phone, setPhone] = useState('');
  const [passport, setPassport] = useState('');
  const [passportExpiry, setPassportExpiry] = useState('');

  // Payment details
  const [cardNumber, setCardNumber] = useState('');
  const [cardName, setCardName] = useState('');
  const [expiry, setExpiry] = useState('');
  const [cvc, setCvc] = useState('');
  const [billingZip, setBillingZip] = useState('');

  const [errors, setErrors] = useState<Record<string, string>>({});

  const brand = useMemo(() => detectBrand(cardNumber), [cardNumber]);
  const currency = selectedFlight?.currency || selectedHotel?.currency || 'USD';
  const flightTotal = selectedFlight?.price || 0;
  const hotelTotal = selectedHotel?.price || 0;
  const taxes = Math.round((flightTotal + hotelTotal) * 0.11 * 100) / 100;
  const grandTotal = Math.round((flightTotal + hotelTotal + taxes) * 100) / 100;

  const setError = (key: string, msg?: string) =>
    setErrors((prev) => {
      const next = { ...prev };
      if (msg) next[key] = msg;
      else delete next[key];
      return next;
    });

  function validateDetails(): boolean {
    const e: Record<string, string> = {};
    if (!title) e.title = 'Required';
    if (!NAME_RE.test(firstName.trim())) e.firstName = 'Enter a valid first name';
    if (!NAME_RE.test(lastName.trim())) e.lastName = 'Enter a valid last name';
    const age = ageFromDob(dob);
    if (age === null) e.dob = 'Enter your date of birth';
    else if (age < 18) e.dob = 'Lead traveler must be 18+';
    else if (age > 120) e.dob = 'Enter a valid date of birth';
    if (!gender) e.gender = 'Required';
    if (!nationality) e.nationality = 'Required';
    if (!EMAIL_RE.test(email.trim())) e.email = 'Enter a valid email';
    if (onlyDigits(phone).length < 7) e.phone = 'Enter a valid phone number';
    if (!/^[A-Za-z0-9]{6,9}$/.test(passport.trim())) e.passport = '6–9 letters/numbers';
    if (!expiryInFuture(passportExpiry)) e.passportExpiry = 'Must be a future date (MM/YY)';
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function validatePayment(): boolean {
    const e: Record<string, string> = {};
    const digits = onlyDigits(cardNumber);
    const expectedLen = brand === 'amex' ? 15 : 16;
    if (digits.length !== expectedLen || !luhnValid(digits)) e.cardNumber = 'Enter a valid card number';
    if (!NAME_RE.test(cardName.trim())) e.cardName = 'Enter the name on the card';
    if (!expiryInFuture(expiry)) e.expiry = 'Invalid or past expiry';
    if (!/^\d{3,4}$/.test(cvc) || cvc.length !== (brand === 'amex' ? 4 : 3)) e.cvc = brand === 'amex' ? '4 digits' : '3 digits';
    if (onlyDigits(billingZip).length < 3 && billingZip.trim().length < 3) e.billingZip = 'Required';
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function goToPayment() {
    if (validateDetails()) {
      setErrors({});
      setStage('payment');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }

  function pay() {
    if (!validatePayment()) return;
    setStage('processing');
    // Simulate gateway latency, then issue a confirmation.
    window.setTimeout(() => {
      setBookingRef(makeBookingRef());
      setStage('confirmed');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }, 2200);
  }

  const money = (n: number) => `$${n.toFixed(2)}`;
  const maskedCard = onlyDigits(cardNumber).slice(-4);

  // ---- Order summary card (shared across stages) ----
  const OrderSummary = (
    <div className="border border-zinc-200 bg-white">
      <div className="px-5 py-4 border-b border-zinc-100">
        <span className="text-[10px] uppercase tracking-[0.25em] font-bold text-zinc-400">Order Summary</span>
        <div className="mt-1 text-sm text-zinc-900">{trip.destinationCity}, {trip.destinationCountry}</div>
        <div className="text-[11px] text-zinc-400">{trip.startDate} → {trip.endDate} · {trip.travelers} traveler(s)</div>
      </div>
      <div className="divide-y divide-zinc-100">
        {selectedFlight && (
          <div className="flex items-start gap-3 px-5 py-4">
            <Plane className="w-4 h-4 text-zinc-400 mt-0.5" strokeWidth={1.5} />
            <div className="flex-1">
              <div className="text-sm text-zinc-900">{selectedFlight.airline}</div>
              <div className="text-[11px] text-zinc-400">
                {selectedFlight.origin}–{selectedFlight.destination} · {selectedFlight.stops <= 0 ? 'Direct' : `${selectedFlight.stops} stop(s)`}
              </div>
            </div>
            <div className="text-sm tabular-nums">{money(flightTotal)}</div>
          </div>
        )}
        {selectedHotel && (
          <div className="flex items-start gap-3 px-5 py-4">
            <BedDouble className="w-4 h-4 text-zinc-400 mt-0.5" strokeWidth={1.5} />
            <div className="flex-1">
              <div className="text-sm text-zinc-900">{selectedHotel.name}</div>
              <div className="text-[11px] text-zinc-400">{selectedHotel.stars}★ · {selectedHotel.nights} night(s)</div>
            </div>
            <div className="text-sm tabular-nums">{money(hotelTotal)}</div>
          </div>
        )}
        <div className="flex items-center justify-between px-5 py-3 text-[11px] text-zinc-400">
          <span>Taxes &amp; fees</span><span className="tabular-nums">{money(taxes)}</span>
        </div>
      </div>
      <div className="flex items-center justify-between px-5 py-4 border-t border-zinc-200 bg-zinc-50">
        <span className="text-[10px] uppercase tracking-[0.25em] font-bold text-zinc-500">Total · {currency}</span>
        <span className="text-2xl font-light tabular-nums">{money(grandTotal)}</span>
      </div>
    </div>
  );

  // ---- Stepper ----
  const steps: { key: Stage; label: string }[] = [
    { key: 'details', label: 'Traveler' },
    { key: 'payment', label: 'Payment' },
    { key: 'confirmed', label: 'Confirmation' },
  ];
  const activeIndex = stage === 'processing' ? 1 : steps.findIndex((s) => s.key === stage);

  return (
    <div className="max-w-5xl mx-auto px-6 py-16">
      <button
        onClick={onBack}
        className="flex items-center gap-3 text-xs uppercase tracking-[0.3em] font-medium text-zinc-400 hover:text-zinc-950 transition-colors mb-10"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Summary
      </button>

      <div className="flex items-center gap-3 mb-2">
        <Lock className="w-5 h-5 text-zinc-900" strokeWidth={1.5} />
        <h2 className="text-3xl font-light tracking-tight">Secure Checkout</h2>
      </div>
      <p className="text-[11px] text-zinc-400 mb-10">
        Demo environment — no real payment is processed. Do not enter a real card.
      </p>

      {/* Stepper */}
      <div className="flex items-center gap-2 mb-12">
        {steps.map((s, i) => (
          <div key={s.key} className="flex items-center gap-2 flex-1">
            <div className={`flex items-center justify-center w-7 h-7 rounded-full text-[11px] font-medium ${
              i < activeIndex ? 'bg-emerald-600 text-white'
              : i === activeIndex ? 'bg-zinc-950 text-white'
              : 'bg-zinc-100 text-zinc-400'
            }`}>
              {i < activeIndex ? <Check className="w-3.5 h-3.5" /> : i + 1}
            </div>
            <span className={`text-[10px] uppercase tracking-widest font-semibold ${i === activeIndex ? 'text-zinc-900' : 'text-zinc-400'}`}>
              {s.label}
            </span>
            {i < steps.length - 1 && <div className={`h-px flex-1 ${i < activeIndex ? 'bg-emerald-300' : 'bg-zinc-100'}`} />}
          </div>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {/* ---------------- CONFIRMATION ---------------- */}
        {stage === 'confirmed' ? (
          <motion.div
            key="confirmed"
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="max-w-xl mx-auto text-center"
          >
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-50 mb-6">
              <CalendarCheck className="w-8 h-8 text-emerald-600" strokeWidth={1.5} />
            </div>
            <h3 className="text-3xl font-light tracking-tight mb-2">Booking Confirmed</h3>
            <p className="text-sm text-zinc-500 mb-8">
              A confirmation has been sent to <span className="text-zinc-900">{email}</span>.
            </p>
            <div className="border border-zinc-200 text-left">
              <div className="flex items-center justify-between px-5 py-4 bg-zinc-950 text-white">
                <span className="text-[10px] uppercase tracking-[0.25em] font-bold text-zinc-300">Booking Reference</span>
                <span className="text-lg font-medium tracking-widest tabular-nums">{bookingRef}</span>
              </div>
              <div className="px-5 py-4 space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-zinc-400">Lead traveler</span><span>{title} {firstName} {lastName}</span></div>
                <div className="flex justify-between"><span className="text-zinc-400">Trip</span><span>{trip.destinationCity}, {trip.destinationCountry}</span></div>
                <div className="flex justify-between"><span className="text-zinc-400">Dates</span><span>{trip.startDate} → {trip.endDate}</span></div>
                {selectedFlight && <div className="flex justify-between"><span className="text-zinc-400">Flight</span><span>{selectedFlight.airline}</span></div>}
                {selectedHotel && <div className="flex justify-between"><span className="text-zinc-400">Hotel</span><span className="truncate ml-4">{selectedHotel.name}</span></div>}
                <div className="flex justify-between"><span className="text-zinc-400">Paid · {currency}</span><span className="font-semibold">{money(grandTotal)}</span></div>
                <div className="flex justify-between"><span className="text-zinc-400">Card</span><span>{brand ? brand.toUpperCase() : 'CARD'} •••• {maskedCard}</span></div>
              </div>
            </div>
            <button
              onClick={onBack}
              className="mt-8 px-8 py-4 bg-zinc-950 text-white text-xs uppercase tracking-[0.3em] font-medium hover:bg-zinc-800 transition-colors"
            >
              Return to Dashboard
            </button>
          </motion.div>
        ) : stage === 'processing' ? (
          /* ---------------- PROCESSING ---------------- */
          <motion.div
            key="processing"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="py-24 flex flex-col items-center text-center"
          >
            <Loader2 className="w-10 h-10 text-zinc-900 animate-spin mb-6" strokeWidth={1.5} />
            <p className="text-sm uppercase tracking-[0.3em] text-zinc-500">Processing payment…</p>
            <p className="mt-2 text-[11px] text-zinc-400">Authorizing {money(grandTotal)} {currency} · do not close this window</p>
          </motion.div>
        ) : (
          /* ---------------- DETAILS / PAYMENT ---------------- */
          <motion.div
            key="form"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="grid grid-cols-1 lg:grid-cols-3 gap-10"
          >
            <div className="lg:col-span-2 space-y-8">
              {stage === 'details' ? (
                <>
                  <div className="flex items-center gap-2">
                    <User className="w-4 h-4 text-zinc-500" strokeWidth={1.5} />
                    <h3 className="text-sm uppercase tracking-[0.2em] font-semibold text-zinc-700">Lead Traveler Details</h3>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
                    <div className="col-span-2 md:col-span-1">
                      <SelectField label="Title" value={title} onChange={(v) => { setTitle(v); setError('title'); }} options={['Mr', 'Ms', 'Mx', 'Dr']} error={errors.title} />
                    </div>
                    <div className="col-span-2 md:col-span-2">
                      <TextField label="First name" value={firstName} onChange={(v) => { setFirstName(v); setError('firstName'); }} error={errors.firstName} placeholder="As on passport" autoComplete="given-name" />
                    </div>
                    <div className="col-span-2 md:col-span-3">
                      <TextField label="Last name" value={lastName} onChange={(v) => { setLastName(v); setError('lastName'); }} error={errors.lastName} placeholder="As on passport" autoComplete="family-name" />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <TextField label="Date of birth" type="date" value={dob} onChange={(v) => { setDob(v); setError('dob'); }} error={errors.dob} />
                    <SelectField label="Gender" value={gender} onChange={(v) => { setGender(v); setError('gender'); }} options={['Female', 'Male', 'Other', 'Prefer not to say']} error={errors.gender} />
                    <SelectField label="Nationality" value={nationality} onChange={(v) => { setNationality(v); setError('nationality'); }} options={COUNTRIES} error={errors.nationality} />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <TextField label="Email" type="email" inputMode="email" value={email} onChange={(v) => { setEmail(v); setError('email'); }} error={errors.email} placeholder="you@example.com" autoComplete="email" />
                    <TextField label="Phone" inputMode="tel" value={phone} onChange={(v) => { setPhone(v); setError('phone'); }} error={errors.phone} placeholder="+1 555 000 1234" autoComplete="tel" />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <TextField label="Passport number" value={passport} onChange={(v) => { setPassport(v.toUpperCase()); setError('passport'); }} error={errors.passport} placeholder="X1234567" maxLength={9} />
                    <TextField label="Passport expiry (MM/YY)" inputMode="numeric" value={passportExpiry} onChange={(v) => { setPassportExpiry(formatExpiry(v)); setError('passportExpiry'); }} error={errors.passportExpiry} placeholder="08/30" maxLength={5} />
                  </div>

                  <div className="pt-4 flex justify-end">
                    <button onClick={goToPayment} className="px-8 py-4 bg-zinc-950 text-white text-xs uppercase tracking-[0.3em] font-medium hover:bg-zinc-800 transition-colors">
                      Continue to Payment
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-2">
                    <CreditCard className="w-4 h-4 text-zinc-500" strokeWidth={1.5} />
                    <h3 className="text-sm uppercase tracking-[0.2em] font-semibold text-zinc-700">Payment Details</h3>
                  </div>

                  <div className="relative">
                    <TextField
                      label="Card number" inputMode="numeric" value={cardNumber}
                      onChange={(v) => { setCardNumber(formatCardNumber(v, detectBrand(v))); setError('cardNumber'); }}
                      error={errors.cardNumber} placeholder="4242 4242 4242 4242"
                      autoComplete="cc-number" maxLength={brand === 'amex' ? 17 : 19}
                    />
                    {brand && (
                      <span className="absolute right-3 top-8 text-[10px] uppercase tracking-widest font-bold text-zinc-400">{brand}</span>
                    )}
                  </div>
                  <TextField label="Name on card" value={cardName} onChange={(v) => { setCardName(v); setError('cardName'); }} error={errors.cardName} placeholder="Full name" autoComplete="cc-name" />
                  <div className="grid grid-cols-2 gap-4">
                    <TextField label="Expiry (MM/YY)" inputMode="numeric" value={expiry} onChange={(v) => { setExpiry(formatExpiry(v)); setError('expiry'); }} error={errors.expiry} placeholder="12/28" maxLength={5} autoComplete="cc-exp" />
                    <TextField label="CVC" inputMode="numeric" value={cvc} onChange={(v) => { setCvc(onlyDigits(v).slice(0, brand === 'amex' ? 4 : 3)); setError('cvc'); }} error={errors.cvc} placeholder={brand === 'amex' ? '1234' : '123'} maxLength={4} autoComplete="cc-csc" />
                  </div>
                  <TextField label="Billing postal code" value={billingZip} onChange={(v) => { setBillingZip(v); setError('billingZip'); }} error={errors.billingZip} placeholder="10001" maxLength={10} autoComplete="postal-code" />

                  <div className="flex items-center gap-2 text-[11px] text-zinc-400 pt-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-600" />
                    Your details are validated locally and never sent to a real gateway.
                  </div>

                  <div className="pt-4 flex items-center justify-between">
                    <button onClick={() => { setStage('details'); setErrors({}); }} className="text-xs uppercase tracking-widest font-medium text-zinc-400 hover:text-zinc-900 transition-colors">
                      ← Edit details
                    </button>
                    <button onClick={pay} className="flex items-center gap-2 px-8 py-4 bg-zinc-950 text-white text-xs uppercase tracking-[0.3em] font-medium hover:bg-zinc-800 transition-colors">
                      <Lock className="w-3.5 h-3.5" />
                      Pay {money(grandTotal)}
                    </button>
                  </div>
                </>
              )}
            </div>

            <div className="lg:col-span-1">{OrderSummary}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
