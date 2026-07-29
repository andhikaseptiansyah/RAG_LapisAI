import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],

  server: {
    // Jangan otomatis pindah ke 5174/5175 saat server lama masih aktif.
    // Dengan strictPort, terminal langsung memberi tahu bahwa 5173 harus dibersihkan.
    port: 5173,
    strictPort: true,

    warmup: {
      clientFiles: [
        './src/main.tsx',
        './src/globals.css',
        './src/components/Login.tsx',
        './src/components/ProtectedRoute.tsx',
        './src/components/StartupScreen.tsx',
        './src/App.tsx',
      ],
    },
  },

  optimizeDeps: {
    include: [
      'react',
      'react-dom/client',
      'react-router-dom',
      'dompurify',
      'marked',
    ],
  },
});
