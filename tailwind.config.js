/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        "primary": "#adc6ff", "on-primary": "#002e6a", "primary-container": "#4d8eff", "on-primary-container": "#00285d",
        "secondary": "#c0c1ff", "secondary-container": "#3131c0", "tertiary": "#ffb786",
        "background": "#0b0d13",
        "on-background": "#e2e2eb", "surface": "#111319", "on-surface": "#e2e2eb",
        "surface-variant": "#33343b", "on-surface-variant": "#c2c6d6",
        "surface-container-lowest": "#0c0e14", "surface-container-low": "#191b22",
        "surface-container": "#1e1f26", "surface-container-high": "#282a30",
        "outline": "#8c909f", "outline-variant": "#424754", "error": "#ffb4ab",
      },
      backgroundImage: {
        'welcome-gradient': 'linear-gradient(180deg, #1a1c23 0%, #2a2d39 100%)',
        'body-gradient-subtle': 'radial-gradient(circle at center, rgba(28,36,60,0.8) 0%, rgba(11,13,19,1) 100%)',
      },
      fontFamily: {
        "headline": ["'Google Sans'", "sans-serif"],
        "body": ["Inter", "sans-serif"],
        "mono": ["JetBrains Mono", "monospace"],
      },
      keyframes: {
        typing: {
          '0%, 80%, 100%': { transform: 'scale(0)', opacity: '0.3' },
          '40%': { transform: 'scale(1)', opacity: '1' },
        },
        'pulse-mic': {
          '0%': { boxShadow: '0 0 0 0 rgba(255, 180, 171, 0.4)' },
          '70%': { boxShadow: '0 0 0 10px rgba(255, 180, 171, 0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(255, 180, 171, 0)' },
        },
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' }
        }
      },
      animation: {
        typing: 'typing 1.4s infinite ease-in-out both',
        'pulse-mic': 'pulse-mic 1.5s infinite',
        fadeIn: 'fadeIn 0.3s ease-out'
      }
    }
  },
  plugins: [
    require('@tailwindcss/typography'),
    require('@tailwindcss/forms'),
    require('@tailwindcss/container-queries')
  ],
}