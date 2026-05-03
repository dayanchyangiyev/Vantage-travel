import React, { useState } from 'react';
import { motion } from 'motion/react';
import { ArrowLeft, Loader2 } from 'lucide-react';

interface RegisterProps {
  onBack: () => void;
  onSuccess: () => void;
  onNavigateLogin: () => void;
}

export default function Register({ onBack, onSuccess, onNavigateLogin }: RegisterProps) {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const response = await fetch('http://127.0.0.1:8000/api/accounts/register/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(Object.values(data).join(' ') || 'Registration failed');
      }

      onSuccess(); // Registration successful, navigate to login
    } catch (err: any) {
      setError(err.message || 'Something went wrong');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md mx-auto">
      <button
        onClick={onBack}
        className="flex items-center gap-2 text-zinc-400 hover:text-zinc-900 transition-colors mb-12 text-sm tracking-widest uppercase font-medium"
      >
        <ArrowLeft className="w-4 h-4" />
        Back
      </button>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white/50 backdrop-blur-xl border border-zinc-200 p-8 shadow-2xl"
      >
        <h2 className="text-3xl font-light tracking-tight text-zinc-900 mb-2">Create Account.</h2>
        <p className="text-zinc-500 mb-8 font-light">Join Vantage Travel today.</p>

        {error && (
          <div className="mb-6 p-4 bg-red-50 text-red-600 text-sm border border-red-100">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-xs uppercase tracking-[0.2em] font-medium text-zinc-500 mb-2">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full px-0 py-3 bg-transparent border-b border-zinc-200 focus:border-zinc-900 focus:ring-0 outline-none transition-colors font-light"
              placeholder="Choose a username"
            />
          </div>

          <div>
            <label className="block text-xs uppercase tracking-[0.2em] font-medium text-zinc-500 mb-2">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-0 py-3 bg-transparent border-b border-zinc-200 focus:border-zinc-900 focus:ring-0 outline-none transition-colors font-light"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className="block text-xs uppercase tracking-[0.2em] font-medium text-zinc-500 mb-2">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="w-full px-0 py-3 bg-transparent border-b border-zinc-200 focus:border-zinc-900 focus:ring-0 outline-none transition-colors font-light"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-4 bg-zinc-950 text-white font-light tracking-wide hover:bg-zinc-800 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Create Account'}
          </button>
        </form>

        <div className="mt-8 text-center">
          <p className="text-sm text-zinc-500 font-light">
            Already have an account?{' '}
            <button
              onClick={onNavigateLogin}
              className="text-zinc-900 hover:underline underline-offset-4"
            >
              Sign In
            </button>
          </p>
        </div>
      </motion.div>
    </div>
  );
}
