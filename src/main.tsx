import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { App } from './App';
import { AdminDashboard } from './components/AdminDashboard';
import { AdminQueryLogsDetail } from './components/AdminQueryLogsDetail';
import './globals.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        {/* Jalur utama untuk User Chatbot */}
        <Route path="/" element={<App />} />
        
        {/* Jalur khusus untuk System Admin */}
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/admin/logs" element={<AdminQueryLogsDetail />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);