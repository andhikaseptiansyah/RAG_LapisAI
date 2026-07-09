import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminSidebar } from './AdminSidebar';
import { AdminHeader } from './AdminHeader';
import { useDashboard } from '../hooks/useDashboard';
import type { ChatRange } from '../services/dashboardService';
import type { DocumentType, RepositoryDocument } from '../services/documentService';

const rangeLabels: Record<ChatRange, string> = {
  daily: 'Harian',
  weekly: 'Mingguan',
  monthly: 'Bulanan',
  yearly: 'Tahunan',
};

const getDocumentIcon = (type: DocumentType) => {
  switch (type) {
    case 'PDF':
      return 'picture_as_pdf';
    case 'DOCX':
      return 'article';
    case 'TXT':
      return 'text_snippet';
    default:
      return 'description';
  }
};

const getDocumentIconStyle = (type: DocumentType) => {
  switch (type) {
    case 'PDF':
      return 'text-error bg-error/10';
    case 'DOCX':
      return 'text-primary bg-primary/10';
    case 'TXT':
      return 'text-secondary bg-secondary/10';
    default:
      return 'text-outline bg-surface-variant';
  }
};

const getIndexedStatusStyle = (status: RepositoryDocument['indexedStatus']) => {
  switch (status) {
    case 'Indexed':
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    case 'Re-indexed':
      return 'bg-primary/10 text-primary border-primary/20';
    case 'Pending':
      return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    default:
      return 'bg-surface-variant text-on-surface-variant border-outline-variant';
  }
};

const formatDate = (value: string) => {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString([], {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
  });
};

export const AdminDashboard: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const {
    summary,
    chatSummary,
    analytics,
    documents,
    range,
    documentSearch,
    documentPage,
    isLoading,
    error,
    setRange,
    setDocumentSearch,
    setDocumentPage,
    loadDashboard,
  } = useDashboard({ initialRange: 'daily', initialDocumentLimit: 5 });

  const chatChartMax = useMemo(() => {
    return Math.max(...analytics.map((item) => item.totalChats), 1);
  }, [analytics]);

  const summaryCards = [
    {
      label: 'Total Documents',
      value: summary?.totalDocuments ?? 0,
      helper: 'Dokumen tersimpan di database',
      icon: 'folder_open',
      tone: 'text-primary',
    },
    {
      label: 'Total Chunks',
      value: summary?.totalChunks ?? 0,
      helper: 'Chunks hasil indexing',
      icon: 'database',
      tone: 'text-secondary',
    },
    {
      label: 'Total Chats',
      value: summary?.totalChats ?? 0,
      helper: 'Percakapan dari query log',
      icon: 'forum',
      tone: 'text-tertiary',
    },
    {
      label: 'Avg Response',
      value: `${summary?.averageResponseTime ?? 0}s`,
      helper: 'Rata-rata waktu jawab',
      icon: 'speed',
      tone: 'text-emerald-400',
    },
  ];

  return (
    <div className="bg-background text-on-surface font-body overflow-hidden flex h-screen w-full relative">
      <AdminSidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <main className="flex-1 flex flex-col h-full relative min-w-0">
        <AdminHeader onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

        <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-4 md:p-8 pb-12">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
            <div>
              <p className="font-mono text-[10px] md:text-xs uppercase tracking-wider text-outline mb-2">
                Database Connected Admin
              </p>
              <h1 className="font-headline text-2xl md:text-3xl font-bold text-on-surface">
                Admin Dashboard
              </h1>
              <p className="text-on-surface-variant text-sm md:text-base mt-2 max-w-3xl">
                Dashboard ini mengambil dokumen, chat analytics, dan summary dari API backend, bukan dari dummy data frontend.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <select
                value={range}
                onChange={(event) => setRange(event.target.value as ChatRange)}
                className="bg-[#0b0d13] border border-outline-variant/50 rounded-xl py-2.5 px-3 font-mono text-xs text-on-surface focus:outline-none focus:border-primary transition-all"
              >
                {(Object.keys(rangeLabels) as ChatRange[]).map((item) => (
                  <option key={item} value={item} className="bg-[#0b0d13] text-on-surface">
                    {rangeLabels[item]}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => void loadDashboard()}
                disabled={isLoading}
                className="px-4 py-2.5 rounded-xl border border-outline-variant text-sm text-on-surface-variant hover:text-primary hover:border-primary/50 disabled:opacity-50 transition-colors"
              >
                Refresh
              </button>
              <Link
                to="/admin/upload"
                className="px-4 py-2.5 rounded-xl bg-primary text-on-primary text-sm font-semibold transition-colors"
              >
                Upload Docs
              </Link>
            </div>
          </div>

          {error && (
            <div className="mb-6 p-4 rounded-xl border border-error/30 bg-error-container/20 text-error text-sm">
              {error}
            </div>
          )}

          <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-6">
            {summaryCards.map((card) => (
              <div key={card.label} className="bg-surface-container-low border border-outline-variant rounded-2xl p-5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs text-outline font-mono uppercase tracking-wider">{card.label}</p>
                    <p className="text-2xl font-headline font-bold mt-3">{card.value}</p>
                  </div>
                  <span className={`material-symbols-outlined text-[28px] ${card.tone}`}>{card.icon}</span>
                </div>
                <p className="text-xs text-on-surface-variant mt-3">{card.helper}</p>
              </div>
            ))}
          </section>

          <section className="grid grid-cols-1 xl:grid-cols-[1fr_0.85fr] gap-6">
            <div className="bg-surface-container-low border border-outline-variant rounded-2xl p-4 md:p-6">
              <div className="flex items-center justify-between gap-4 mb-5">
                <div>
                  <h2 className="font-headline text-lg font-bold">Chat Analytics</h2>
                  <p className="text-xs text-outline mt-1">
                    {chatSummary
                      ? `${chatSummary.totalChatCount} chats · peak ${chatSummary.peakLabel}`
                      : 'Belum ada data chat.'}
                  </p>
                </div>
                {isLoading && <span className="text-xs text-outline font-mono">Loading...</span>}
              </div>

              <div className="h-[320px] flex items-end gap-3 border-l border-b border-outline-variant/60 p-4">
                {analytics.length > 0 ? (
                  analytics.map((item) => (
                    <div key={item.label} className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                      <div
                        className="w-full max-w-[52px] rounded-t-xl bg-primary/80 min-h-[8px] transition-all"
                        style={{ height: `${Math.max((item.totalChats / chatChartMax) * 100, 4)}%` }}
                        title={`${item.totalChats} chats`}
                      />
                      <span className="text-[10px] text-outline font-mono text-center">{item.label}</span>
                    </div>
                  ))
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-sm text-outline text-center">
                    Belum ada query log untuk periode ini.
                  </div>
                )}
              </div>
            </div>

            <div className="bg-surface-container-low border border-outline-variant rounded-2xl overflow-hidden">
              <div className="p-4 md:p-5 border-b border-outline-variant flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h2 className="font-headline text-lg font-bold">Document Repository</h2>
                  <p className="text-xs text-outline mt-1">Dokumen dari tabel documents.</p>
                </div>
                <input
                  value={documentSearch}
                  onChange={(event) => setDocumentSearch(event.target.value)}
                  placeholder="Search document..."
                  className="bg-[#0b0d13] border border-outline-variant/50 rounded-xl py-2.5 px-3 text-sm text-on-surface focus:outline-none focus:border-primary transition-all"
                />
              </div>

              <div className="divide-y divide-outline-variant/40">
                {documents.length > 0 ? (
                  documents.map((document) => (
                    <div key={document.id} className="p-4 flex items-start justify-between gap-4">
                      <div className="flex items-start gap-3 min-w-0">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${getDocumentIconStyle(document.type)}`}>
                          <span className="material-symbols-outlined text-[22px]">{getDocumentIcon(document.type)}</span>
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-on-surface truncate">{document.filename}</p>
                          <p className="text-xs text-outline font-mono mt-1">
                            {document.size} · {document.chunks} chunks · {formatDate(document.uploadDate)}
                          </p>
                        </div>
                      </div>
                      <span className={`shrink-0 inline-flex items-center px-2.5 py-1 rounded-full border font-mono text-[10px] ${getIndexedStatusStyle(document.indexedStatus)}`}>
                        {document.indexedStatus}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="p-8 text-center text-sm text-outline">
                    Belum ada dokumen di database.
                  </div>
                )}
              </div>

              <div className="p-4 border-t border-outline-variant flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => setDocumentPage(documentPage - 1)}
                  disabled={documentPage <= 1}
                  className="px-3 py-2 rounded-lg border border-outline-variant text-xs text-on-surface-variant disabled:opacity-40"
                >
                  Prev
                </button>
                <span className="text-xs text-outline font-mono">Page {documentPage}</span>
                <button
                  type="button"
                  onClick={() => setDocumentPage(documentPage + 1)}
                  disabled={documents.length < 5}
                  className="px-3 py-2 rounded-lg border border-outline-variant text-xs text-on-surface-variant disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
};
