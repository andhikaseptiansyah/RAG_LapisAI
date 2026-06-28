import React, { useEffect, useState } from 'react';

interface IntroAnimationProps {
  onFinish: () => void;
}

export const IntroAnimation: React.FC<IntroAnimationProps> = ({ onFinish }) => {
  const [phase, setPhase] = useState<'idle' | 'backgroundLeaving' | 'iconLeaving'>('idle');

  useEffect(() => {
    const hideBackground = setTimeout(() => {
      setPhase('backgroundLeaving');
    }, 2600);

    const moveIconToHeader = setTimeout(() => {
      setPhase('iconLeaving');
    }, 3200);

    const finishIntro = setTimeout(() => {
      onFinish();
    }, 4600);

    return () => {
      clearTimeout(hideBackground);
      clearTimeout(moveIconToHeader);
      clearTimeout(finishIntro);
    };
  }, [onFinish]);

  return (
    <div className="fixed inset-0 z-[9999] overflow-hidden pointer-events-none">
      <style>
        {`
          @keyframes lapisIntroMotion {
            0% {
              transform: translateY(0) scale(1) rotate(0deg);
              opacity: 0.92;
            }
            25% {
              transform: translateY(-18px) scale(1.08) rotate(8deg);
              opacity: 1;
            }
            50% {
              transform: translateY(0) scale(1.02) rotate(0deg);
              opacity: 0.96;
            }
            75% {
              transform: translateY(18px) scale(1.08) rotate(-8deg);
              opacity: 1;
            }
            100% {
              transform: translateY(0) scale(1) rotate(0deg);
              opacity: 0.92;
            }
          }
        `}
      </style>

      <div
        className={`absolute inset-0 bg-[#000000] transition-opacity duration-700 ease-in-out ${
          phase === 'idle' ? 'opacity-100' : 'opacity-0'
        }`}
      ></div>

      <div
        style={{
          transform:
            phase === 'iconLeaving'
              ? 'translate(calc(-50% - 28px), calc(-50% - min(24.5vh, 195px))) scale(0.2)'
              : 'translate(-50%, -50%) scale(1)',
          opacity: phase === 'iconLeaving' ? 0 : 1,
          filter: phase === 'iconLeaving' ? 'blur(3px)' : 'blur(0)',
          transition:
            'transform 1200ms cubic-bezier(0.16, 1, 0.3, 1), opacity 900ms ease-in-out 300ms, filter 900ms ease-in-out 300ms',
        }}
        className="absolute left-1/2 top-1/2"
      >
        <img
          src="/icon.png"
          alt="Lapis"
          style={{
            animation: phase === 'idle' ? 'lapisIntroMotion 1.8s ease-in-out infinite' : 'none',
          }}
          className="h-44 w-44 md:h-64 md:w-64 object-contain"
        />
      </div>
    </div>
  );
};
