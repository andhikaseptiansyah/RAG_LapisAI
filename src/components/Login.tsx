import React, { useEffect, useMemo, useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';

import { useAuth } from '../hooks/useAuth';
import type { AuthUser } from '../services/authService';

interface LoginLocationState {
  from?: {
    pathname?: string;
    search?: string;
  };
}

const isAdminRole = (role: string): boolean => {
  return role === 'admin' || role === 'superadmin' || role === 'owner';
};

const resolveRedirectPath = (
  authenticatedUser: AuthUser,
  requestedPath: string
): string => {
  const role = authenticatedUser.role;
  const requestedAdminRoute = requestedPath.startsWith('/admin');

  if (!isAdminRole(role) && requestedAdminRoute) return '/';
  if (requestedPath && requestedPath !== '/login' && requestedPath !== '/') return requestedPath;

  return isAdminRole(role) ? '/admin' : '/';
};

// Komponen Toast Notification
const Toast = ({ message, onClose }: { message: string; onClose: () => void }) => (
  <motion.div
    initial={{ opacity: 0, y: -20, scale: 0.95 }}
    animate={{ opacity: 1, y: 0, scale: 1 }}
    exit={{ opacity: 0, y: -20, scale: 0.95 }}
    className="fixed top-6 right-6 z-50 flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-950/80 px-4 py-3 text-sm text-red-200 shadow-[0_4px_20px_rgba(220,38,38,0.3)] backdrop-blur-md"
  >
    <span className="material-symbols-outlined text-red-500">error</span>
    <p>{message}</p>
    <button onClick={onClose} className="ml-2 text-red-400 hover:text-white">
      <span className="material-symbols-outlined text-[18px]">close</span>
    </button>
  </motion.div>
);

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAuthenticated, isInitializing, login } = useAuth();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // State untuk Toast & Efek Animasi
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [shake, setShake] = useState(false);

  const requestedPath = useMemo(() => {
    const state = location.state as LoginLocationState | null;
    const pathname = state?.from?.pathname ?? '/';
    const search = state?.from?.search ?? '';
    return `${pathname}${search}`;
  }, [location.state]);

  useEffect(() => {
    document.documentElement.classList.add('dark');
  }, []);

  const triggerError = (message: string) => {
    setToastMessage(message);
    setShake(true);
    setTimeout(() => setShake(false), 500); // Reset shake setelah animasi selesai
    setTimeout(() => setToastMessage(null), 4000); // Hilangkan toast otomatis
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    const normalizedUsername = username.trim();

    if (!normalizedUsername || !password) {
      triggerError('Username dan password wajib diisi.');
      return;
    }

    setIsSubmitting(true);
    setToastMessage(null);

    try {
      const authenticatedUser = await login({
        username: normalizedUsername,
        password,
      });

      if (!authenticatedUser?.role) {
        throw new Error('Login berhasil, tetapi data role user tidak terbaca.');
      }

      navigate(resolveRedirectPath(authenticatedUser, requestedPath), { replace: true });
    } catch (caughtError) {
      const message = caughtError instanceof Error ? caughtError.message : 'Login gagal. Periksa kembali kredensial Anda.';
      triggerError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#030712] font-body text-slate-200">
        <motion.div animate={{ opacity: [0.5, 1, 0.5] }} transition={{ repeat: Infinity, duration: 1.5 }} className="flex flex-col items-center gap-4">
          <span className="material-symbols-outlined animate-spin text-[32px] text-blue-500">progress_activity</span>
          <span className="font-mono text-sm tracking-widest text-slate-400">INITIALIZING NODE...</span>
        </motion.div>
      </div>
    );
  }

  if (isAuthenticated && user) {
    return <Navigate to={resolveRedirectPath(user, requestedPath)} replace />;
  }

  // Interaksi Mikro: Cek apakah input valid/terisi
  const isUsernameValid = username.trim().length > 0;
  const isPasswordValid = password.length > 0;

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#030712] px-4 font-body sm:p-6">
      
      {/* CSS Khusus untuk animasi Grid Berjalan */}
      <style>{`
        @keyframes grid-scroll {
          0% { background-position: 0 0; }
          100% { background-position: 0 4rem; }
        }
        .animate-grid-scroll {
          animation: grid-scroll 3s linear infinite;
        }
      `}</style>

      {/* Toast Notification */}
      <AnimatePresence>
        {toastMessage && (
          <Toast message={toastMessage} onClose={() => setToastMessage(null)} />
        )}
      </AnimatePresence>

      {/* 3D Background Elements & Particles */}
      <div className="absolute inset-0 z-0 flex items-center justify-center overflow-hidden pointer-events-none">
        <div className="absolute -top-[20%] left-1/2 h-[40rem] w-[50rem] -translate-x-1/2 rounded-full bg-blue-700/15 blur-[120px]"></div>
        <div className="absolute -bottom-[20%] left-1/2 h-[30rem] w-[40rem] -translate-x-1/2 rounded-full bg-indigo-900/20 blur-[100px]"></div>

        {/* 3D Perspective Grid with Infinite Scroll */}
        <div 
          className="absolute inset-0 animate-grid-scroll bg-[linear-gradient(to_right,#3b82f61a_1px,transparent_1px),linear-gradient(to_bottom,#3b82f61a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_70%_60%_at_50%_50%,#000_70%,transparent_100%)]"
          style={{ transform: 'perspective(1000px) rotateX(60deg) scale(2.5) translateY(-5%)' }}
        ></div>

        {/* Floating Particles (Framer Motion) */}
        {[...Array(5)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute h-1 w-1 rounded-full bg-blue-400 shadow-[0_0_10px_2px_rgba(96,165,250,0.8)]"
            animate={{
              y: ['0vh', '-100vh'],
              x: Math.random() * 100 - 50,
              opacity: [0, 1, 0],
            }}
            transition={{
              duration: Math.random() * 5 + 5,
              repeat: Infinity,
              ease: "linear",
              delay: Math.random() * 5,
            }}
            style={{ left: `${Math.random() * 100}%`, bottom: '-10%' }}
          />
        ))}
      </div>

      {/* Main Login Container */}
      <motion.main 
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="relative z-10 flex w-full max-w-[400px] flex-col gap-8"
      >
        {/* Header Section */}
        <div className="flex flex-col items-center gap-3 text-center">
          <motion.div 
            whileHover={{ scale: 1.05, rotate: 90 }}
            transition={{ type: "spring", stiffness: 200 }}
            className="mb-2 flex h-16 w-16 cursor-pointer items-center justify-center rounded-2xl bg-black p-[1px] shadow-[0_0_20px_rgba(59,130,246,0.3)] ring-1 ring-white/10"
          >
            <div className="flex h-full w-full items-center justify-center rounded-2xl bg-black/80">
              <span className="material-symbols-outlined bg-gradient-to-br from-blue-400 to-indigo-600 bg-clip-text text-[32px] text-transparent drop-shadow-[0_0_15px_rgba(59,130,246,0.6)]">
                hub
              </span>
            </div>
          </motion.div>

          <h1 className="font-headline text-[28px] font-bold tracking-wide text-white drop-shadow-md">
            Assistant
          </h1>
          <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-blue-400/80">
            Enterprise AI Node
          </p>
        </div>

        {/* Form Section with Shake Animation on Error */}
        <motion.form 
          animate={shake ? { x: [-10, 10, -10, 10, 0] } : {}}
          transition={{ duration: 0.4 }}
          className="flex flex-col gap-5" 
          onSubmit={handleSubmit}
        >
          {/* Username Input */}
          <div className="flex flex-col gap-2">
            <label className="ml-1 font-mono text-[11px] uppercase tracking-wider text-slate-400" htmlFor="username">
              Username
            </label>
            <div className="group relative rounded-xl transition-all focus-within:shadow-[0_0_15px_rgba(59,130,246,0.2)]">
              <span className={`material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-[20px] transition-colors ${isUsernameValid ? 'text-emerald-400 drop-shadow-[0_0_5px_rgba(52,211,153,0.5)]' : 'text-slate-500 group-focus-within:text-blue-400'}`}>
                {isUsernameValid ? 'check_circle' : 'person'}
              </span>
              <input
                id="username"
                name="username"
                autoComplete="username"
                className="w-full rounded-xl border border-white/10 bg-[#0f1423]/80 py-4 pl-[44px] pr-4 text-sm text-white backdrop-blur-md transition-all placeholder:text-slate-600 hover:bg-[#141a2e]/90 focus:border-blue-500/50 focus:bg-[#0a0d17] focus:outline-none focus:ring-0"
                placeholder="Enter your ID"
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
              />
            </div>
          </div>

          {/* Password Input */}
          <div className="flex flex-col gap-2">
            <label className="ml-1 font-mono text-[11px] uppercase tracking-wider text-slate-400" htmlFor="password">
              Password
            </label>
            <div className="group relative rounded-xl transition-all focus-within:shadow-[0_0_15px_rgba(59,130,246,0.2)]">
              <span className={`material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-[20px] transition-colors ${isPasswordValid ? 'text-blue-400' : 'text-slate-500'}`}>
                lock
              </span>
              <input
                id="password"
                name="password"
                autoComplete="current-password"
                className="w-full rounded-xl border border-white/10 bg-[#0f1423]/80 py-4 pl-[44px] pr-[44px] text-sm text-white backdrop-blur-md transition-all placeholder:text-slate-600 hover:bg-[#141a2e]/90 focus:border-blue-500/50 focus:bg-[#0a0d17] focus:outline-none focus:ring-0"
                placeholder="••••••••"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              <button
                type="button"
                onClick={() => setShowPassword((prev) => !prev)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-500 transition-colors hover:text-slate-300 focus:outline-none"
              >
                <span className="material-symbols-outlined text-[20px]">
                  {showPassword ? 'visibility_off' : 'visibility'}
                </span>
              </button>
            </div>
          </div>

          {/* Main Login Button */}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="group mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 py-4 font-headline text-[15px] font-semibold text-white shadow-[0_4px_20px_rgba(59,130,246,0.4),inset_0_1px_0_rgba(255,255,255,0.2)] transition-all hover:shadow-[0_8px_25px_rgba(59,130,246,0.5)] disabled:cursor-not-allowed disabled:opacity-70"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <span className="material-symbols-outlined animate-spin text-[20px]">progress_activity</span>
                Authenticating...
              </>
            ) : (
              <>
                Log In
                <span className="material-symbols-outlined text-[20px] transition-transform group-hover:translate-x-1">arrow_forward</span>
              </>
            )}
          </motion.button>
        </motion.form>

        {/* Footer Section */}
        <div className="mt-2 flex flex-col gap-5 border-t border-white/10 pt-6">
          <div className="flex items-center justify-center gap-2 text-slate-400">
            <span className="material-symbols-outlined text-[14px] text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.5)]">
              verified_user
            </span>
            <p className="text-xs tracking-wide">Verified End-to-End Encrypted Session</p>
          </div>

          <div className="flex justify-center gap-6">
            <span className="cursor-pointer font-mono text-[10px] uppercase tracking-wider text-slate-500 transition-colors hover:text-white">Privacy</span>
            <span className="cursor-pointer font-mono text-[10px] uppercase tracking-wider text-slate-500 transition-colors hover:text-white">Terms</span>
            <span className="font-mono text-[10px] uppercase tracking-wider text-slate-600">v4.2.0</span>
          </div>
        </div>
      </motion.main>
    </div>
  );
};