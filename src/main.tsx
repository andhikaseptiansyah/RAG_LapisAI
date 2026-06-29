import React from 'react';
import ReactDOM from 'react-dom/client';
import {
  BrowserRouter,
  Routes,
  Route,
} from 'react-router-dom';

import { App } from './App';
import { AdminDashboard } from './components/AdminDashboard';
import { AdminQueryLogsDetail } from './components/AdminQueryLogsDetail';
import { AdminUploadFile } from './components/AdminUploadFile';

import './globals.css';

ReactDOM.createRoot(
  document.getElementById('root')!
).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        {/* Jalur admin */}
        <Route
          path="/admin"
          element={<AdminDashboard />}
        />

        <Route
          path="/admin/logs"
          element={<AdminQueryLogsDetail />}
        />

        <Route
          path="/admin/upload"
          element={<AdminUploadFile />}
        />

        {/* Jalur user dan conversation search */}
        <Route
          path="/*"
          element={<App />}
        />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);