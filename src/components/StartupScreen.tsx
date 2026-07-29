import React from 'react';

/**
 * Tampilan ringan yang muncul saat bundle halaman chat sedang dimuat.
 * Tidak melakukan request API dan tidak memuat gambar besar.
 */
export const StartupScreen: React.FC = () => {
  return (
    <div className="relative flex min-h-screen w-full overflow-hidden bg-black text-white">
      <div className="absolute left-0 top-0 h-full w-[76px] border-r border-white/[0.04] bg-transparent" />

      <div className="absolute left-6 top-7 flex h-10 w-10 items-center justify-center">
        <img
          src="/icon.png"
          alt="Lapis AI"
          className="h-8 w-8 object-contain"
        />
      </div>

      <main className="flex min-h-screen w-full items-center justify-center px-6 pl-[92px]">
        <div className="w-full max-w-[930px] -translate-y-2">
          <div className="mx-auto mb-8 h-12 w-[min(72%,620px)] animate-pulse rounded-2xl bg-white/[0.055]" />

          <div className="relative h-[190px] w-full overflow-hidden rounded-[30px] border border-white/[0.09] bg-[#111216] shadow-[0_24px_90px_rgba(0,0,0,0.5)]">
            <div className="absolute left-7 top-7 h-5 w-52 animate-pulse rounded-full bg-white/[0.07]" />
            <div className="absolute bottom-5 left-5 h-11 w-32 animate-pulse rounded-full bg-white/[0.065]" />
            <div className="absolute bottom-5 right-5 h-11 w-24 animate-pulse rounded-full bg-white/[0.07]" />
          </div>

          <div className="mt-10 grid grid-cols-1 gap-5 md:grid-cols-3">
            {[0, 1, 2].map((item) => (
              <div
                key={item}
                className="h-32 animate-pulse rounded-[24px] border border-white/[0.035] bg-white/[0.045]"
              />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
};
