import React, { useEffect, useState } from 'react';

interface IntroAnimationProps {
  onFinish: () => void;
}

export const IntroAnimation: React.FC<IntroAnimationProps> = ({ onFinish }) => {
  const [phase, setPhase] = useState<'playing' | 'gifLeaving' | 'backgroundLeaving'>('playing');

  useEffect(() => {
    const hideGif = setTimeout(() => {
      setPhase('gifLeaving');
    }, 2600);

    const hideBackground = setTimeout(() => {
      setPhase('backgroundLeaving');
    }, 3300);

    const finishIntro = setTimeout(() => {
      onFinish();
    }, 4200);

    return () => {
      clearTimeout(hideBackground);
      clearTimeout(hideGif);
      clearTimeout(finishIntro);
    };
  }, [onFinish]);

  return (
    <div className="fixed inset-0 z-[9999] overflow-hidden pointer-events-none">
      <style>
        {`
          @keyframes lapisTextReveal {
            0% {
              opacity: 0;
              transform: translateY(14px) scale(0.96);
              filter: blur(8px);
              letter-spacing: 0.18em;
            }

            60% {
              opacity: 1;
              transform: translateY(0) scale(1.025);
              filter: blur(0);
              letter-spacing: 0.09em;
            }

            100% {
              opacity: 1;
              transform: translateY(0) scale(1);
              filter: blur(0);
              letter-spacing: 0.08em;
            }
          }

          @keyframes lapisTextGlow {
            0%, 100% {
              text-shadow:
                0 0 12px rgba(255, 255, 255, 0.32),
                0 0 28px rgba(77, 142, 255, 0.24);
            }

            50% {
              text-shadow:
                0 0 18px rgba(255, 255, 255, 0.52),
                0 0 44px rgba(77, 142, 255, 0.38);
            }
          }
        `}
      </style>

      <div
        className={`absolute inset-0 bg-[#000000] transition-opacity duration-700 ease-in-out ${
          phase === 'backgroundLeaving' ? 'opacity-0' : 'opacity-100'
        }`}
      />

      <div
        className={`absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center transition-all duration-700 ease-[cubic-bezier(0.22,1,0.36,1)] ${
          phase === 'playing'
            ? 'opacity-100 scale-100 blur-0'
            : 'opacity-0 scale-90 blur-md'
        }`}
      >
        <img
          src="/icon.gif"
          alt="Lapis"
          className="h-52 w-52 object-contain md:h-72 md:w-72"
        />

        <h1
          className="mt-0 bg-gradient-to-r from-white via-primary to-white bg-clip-text text-center text-[42px] font-black uppercase leading-none tracking-[0.08em] text-transparent md:text-[72px]"
          style={{
            fontFamily:
              '"Montserrat", "Poppins", "Inter", "Arial Black", system-ui, sans-serif',
            animation:
              'lapisTextReveal 900ms cubic-bezier(0.22, 1, 0.36, 1) both, lapisTextGlow 2.6s ease-in-out infinite',
          }}
        >
          Lapis AI
        </h1>
      </div>
    </div>
  );
};