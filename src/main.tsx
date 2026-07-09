import React from 'react';
import ReactDOM from 'react-dom/client';
import {
  BrowserRouter,
  Route,
  Routes,
} from 'react-router-dom';

import { App } from './App';
import { AdminDashboard } from './components/AdminDashboard';
import { AdminQueryLogsDetail } from './components/AdminQueryLogsDetail';
import { AdminUploadFile } from './components/AdminUploadFile';
import { Intro } from './components/Intro';
import { Login } from './components/Login';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AuthProvider } from './hooks/useAuth';

import './globals.css';

ReactDOM.createRoot(
  document.getElementById('root')!
).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
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
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
