import React, { lazy, Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from 'react-router-dom';

import { AppErrorBoundary } from './components/AppErrorBoundary';
import { Login } from './components/Login';
import { ProtectedRoute } from './components/ProtectedRoute';
import { StartupScreen } from './components/StartupScreen';
import { AuthProvider } from './hooks/useAuth';

import './globals.css';

// Halaman chat cukup besar. Muat setelah router dan autentikasi siap,
// sambil menampilkan shell ringan yang menyerupai halaman asli.
const App = lazy(() =>
  import('./App').then((module) => ({
    default: module.App,
  }))
);

const AdminDashboard = lazy(() =>
  import('./components/AdminDashboard').then((module) => ({
    default: module.AdminDashboard,
  }))
);

const AdminQueryLogsDetail = lazy(() =>
  import('./components/AdminQueryLogsDetail').then((module) => ({
    default: module.AdminQueryLogsDetail,
  }))
);

const AdminUploadFile = lazy(() =>
  import('./components/AdminUploadFile').then((module) => ({
    default: module.AdminUploadFile,
  }))
);

const AdminPageFallback: React.FC = () => (
  <div
    role="status"
    aria-live="polite"
    className="grid min-h-screen place-items-center bg-black text-sm text-white/60"
  >
    Loading admin page...
  </div>
);

const renderAdminPage = (page: React.ReactNode): React.ReactNode => (
  <ProtectedRoute requireAdmin>
    <Suspense fallback={<AdminPageFallback />}>{page}</Suspense>
  </ProtectedRoute>
);

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Elemen #root tidak ditemukan.');
}

ReactDOM.createRoot(rootElement).render(
  <AppErrorBoundary>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route
            path="/intro"
            element={<Navigate to="/login" replace />}
          />

          <Route path="/login" element={<Login />} />

          <Route
            path="/admin"
            element={renderAdminPage(<AdminDashboard />)}
          />

          <Route
            path="/admin/logs"
            element={renderAdminPage(<AdminQueryLogsDetail />)}
          />

          <Route
            path="/admin/upload"
            element={renderAdminPage(<AdminUploadFile />)}
          />

          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <Suspense fallback={<StartupScreen />}>
                  <App />
                </Suspense>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </AppErrorBoundary>
);
