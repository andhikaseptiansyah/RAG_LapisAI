import React, { useEffect } from 'react';
import {
  useLocation,
  useNavigate,
} from 'react-router-dom';

export const Intro: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const timer = window.setTimeout(() => {
      navigate('/login', {
        replace: true,
        state: {
          from:
            (location.state as { from?: Location })
              ?.from ?? null,
        },
      });
    }, 2800);

    return () => {
      window.clearTimeout(timer);
    };
  }, [location.state, navigate]);

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-black">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.08),transparent_42%)]" />

      <div className="relative flex flex-col items-center justify-center">
        <img
          src="/animation.gif"
          alt="Lapis AI Introduction"
          className="h-40 w-40 object-contain sm:h-52 sm:w-52 md:h-64 md:w-64"
          draggable={false}
        />
      </div>
    </main>
  );
};