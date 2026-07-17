import React, { lazy, Suspense } from 'react';
import ReactDOM from 'react-dom/client';
import {
  BrowserRouter,
  Route,
  Routes,
} from 'react-router-dom';

import { AuthProvider } from './hooks/useAuth';

import './globals.css';

const App = lazy(() => import('./App').then(m => ({ default: m.App })));
const Intro = lazy(() => import('./components/Intro').then(m => ({ default: m.Intro })));
const Login = lazy(() => import('./components/Login').then(m => ({ default: m.Login })));
const AdminDashboard = lazy(() => import('./components/AdminDashboard').then(m => ({ default: m.AdminDashboard })));
const AdminQueryLogsDetail = lazy(() => import('./components/AdminQueryLogsDetail').then(m => ({ default: m.AdminQueryLogsDetail })));
const AdminUploadFile = lazy(() => import('./components/AdminUploadFile').then(m => ({ default: m.AdminUploadFile })));
const ProtectedRoute = lazy(() => import('./components/ProtectedRoute').then(m => ({ default: m.ProtectedRoute })));

const Loading = () => null;

ReactDOM.createRoot(
  document.getElementById('root')!
).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route path="/intro" element={<Intro />} />
            <Route path="/login" element={<Login />} />

            <Route
              path="/admin"
              element={
                <ProtectedRoute requireAdmin>
                  <AdminDashboard />
                </ProtectedRoute>
              }
            />

            <Route
              path="/admin/logs"
              element={
                <ProtectedRoute requireAdmin>
                  <AdminQueryLogsDetail />
                </ProtectedRoute>
              }
            />

            <Route
              path="/admin/upload"
              element={
                <ProtectedRoute requireAdmin>
                  <AdminUploadFile />
                </ProtectedRoute>
              }
            />

            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <App />
                </ProtectedRoute>
              }
            />
          </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
