import React from 'react';

import { useUiLanguage } from '../i18n/LanguageContext';

const AppErrorFallback: React.FC = () => {
  const { language } = useUiLanguage();

  return (
    <main
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        padding: 24,
        background: '#000000',
        color: '#ffffff',
        fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif',
      }}
    >
      <section style={{ maxWidth: 480, textAlign: 'center' }}>
        <h1 style={{ margin: 0, fontSize: 24 }}>
          {language === 'EN'
            ? 'Application failed to load'
            : 'Aplikasi gagal dimuat'}
        </h1>
        <p
          style={{
            margin: '12px 0 24px',
            color: 'rgba(255,255,255,0.65)',
            lineHeight: 1.6,
          }}
        >
          {language === 'EN'
            ? 'Reload the page. If the problem continues, check the browser console for the underlying error.'
            : 'Muat ulang halaman. Jika masalah berlanjut, periksa konsol browser untuk melihat penyebabnya.'}
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          style={{
            border: '1px solid rgba(255,255,255,0.18)',
            borderRadius: 12,
            padding: '11px 18px',
            background: 'rgba(255,255,255,0.08)',
            color: '#ffffff',
            cursor: 'pointer',
          }}
        >
          {language === 'EN' ? 'Reload' : 'Muat Ulang'}
        </button>
      </section>
    </main>
  );
};

type AppErrorBoundaryState = {
  hasError: boolean;
};

export class AppErrorBoundary extends React.Component<
  React.PropsWithChildren,
  AppErrorBoundaryState
> {
  state: AppErrorBoundaryState = {
    hasError: false,
  };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return {
      hasError: true,
    };
  }

  componentDidCatch(error: unknown): void {
    console.error('Lapis AI failed to render:', error);
  }

  render(): React.ReactNode {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return <AppErrorFallback />;
  }
}
