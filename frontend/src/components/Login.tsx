import React, { useState } from 'react';
import { motion } from 'motion/react';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface LoginProps {
  onBack: () => void;
  onSuccess: () => void;
  onNavigateRegister: () => void;
}

export default function Login({ onBack, onSuccess, onNavigateRegister }: LoginProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const response = await fetch('http://127.0.0.1:8000/api/accounts/login/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        throw new Error('Invalid credentials');
      }

      const data = await response.json();
      
      // Fetch user profile
      const profileResponse = await fetch('http://127.0.0.1:8000/api/accounts/profile/', {
        headers: { 'Authorization': `Bearer ${data.access}` },
      });

      if (profileResponse.ok) {
        const userData = await profileResponse.json();
        login(data.access, userData);
        onSuccess();
      } else {
        throw new Error('Failed to fetch profile');
      }
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
        <h2 className="text-3xl font-light tracking-tight text-zinc-900 mb-2">Welcome Back.</h2>
        <p className="text-zinc-500 mb-8 font-light">Enter your credentials to continue.</p>

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
              placeholder="Your username"
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
              className="w-full px-0 py-3 bg-transparent border-b border-zinc-200 focus:border-zinc-900 focus:ring-0 outline-none transition-colors font-light"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-4 bg-zinc-950 text-white font-light tracking-wide hover:bg-zinc-800 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Sign In'}
          </button>
        </form>

        <div className="mt-8 text-center">
          <p className="text-sm text-zinc-500 font-light">
            Don't have an account?{' '}
            <button
              onClick={onNavigateRegister}
              className="text-zinc-900 hover:underline underline-offset-4"
            >
              Create one
            </button>
          </p>
        </div>
      </motion.div>
    </div>
  );
}
