import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AdminSidebar } from './AdminSidebar';
import { AdminHeader } from './AdminHeader';
import {
  getQueryLogsDashboard,
  type QueryLog,
  type QueryLogPerformance,
  type QueryLogStatus,
  type QueryRange,
} from '../services/queryLogService';
import { getFriendlyApiErrorMessage } from '../services/api';

const queryRangeLabels: Record<QueryRange, string> = {
  daily: 'Harian',
  weekly: 'Mingguan',
  monthly: 'Bulanan',
  yearly: 'Tahunan',
};

const getStatusStyle = (status: QueryLogStatus) => {
  switch (status) {
    case 'ANSWERED':
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    case 'NEED_REVIEW':
      return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    case 'NOT_FOUND':
      return 'bg-error-container/20 text-error border-error/30';
    case 'ERROR':
      return 'bg-error-container/20 text-error border-error/30';
    default:
      return 'bg-surface-variant text-on-surface-variant border-outline-variant';
  }
};

const formatLogTime = (timestamp: string): string => {
  const normalized = timestamp?.includes('T')
    ? timestamp
    : timestamp?.replace(' ', 'T');
  const date = new Date(normalized);

  if (Number.isNaN(date.getTime())) {
    return timestamp?.split(' ')[1] ?? '-';
  }

  return date.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

const formatLogDateTime = (timestamp: string): string => {
  const normalized = timestamp?.includes('T')
    ? timestamp
    : timestamp?.replace(' ', 'T');
  const date = new Date(normalized);

  if (Number.isNaN(date.getTime())) {
    return timestamp || '-';
  }

  return date.toLocaleString([], {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

const formatPercent = (value: number): string => {
  return `${Math.round((Number.isFinite(value) ? value : 0) * 100)}%`;
};

const parseResponseTimeSeconds = (value: string): number => {
  const numeric = Number(String(value ?? '').replace('s', ''));
  return Number.isFinite(numeric) ? numeric : 0;
};

const emptyPerformance: QueryLogPerformance = {
  totalQueries: 0,
  answered: 0,
  notFound: 0,
  needReview: 0,
  errors: 0,
  averageConfidence: 0,
  averageResponseTime: 0,
};

export const AdminQueryLogsDetail: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedQueryId, setSelectedQueryId] = useState<string | null>(null);
  const [queryPage, setQueryPage] = useState(1);
  const [queryRange, setQueryRange] = useState<QueryRange>('daily');
  const [queryLogs, setQueryLogs] = useState<QueryLog[]>([]);
  const [performance, setPerformance] = useState<QueryLogPerformance>(emptyPerformance);
  const [totalLogs, setTotalLogs] = useState(0);
  const [totalQueryPages, setTotalQueryPages] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const queriesPerPage = 25;

  const loadQueryLogs = useCallback(async (signal?: AbortSignal) => {
    setIsLoading(true);
    setErrorMessage('');

    try {
      const response = await getQueryLogsDashboard(
        {
          range: queryRange,
          page: queryPage,
          limit: queriesPerPage,
        },
        signal
      );

      const logs = Array.isArray(response.logs) ? response.logs : [];
      setQueryLogs(logs);
      setPerformance(response.performance ?? emptyPerformance);
      setTotalLogs(Number(response.total ?? logs.length));
      setTotalQueryPages(Math.max(Number(response.totalPages ?? 1), 1));

      setSelectedQueryId((currentId) => {
        if (currentId && logs.some((log) => log.queryId === currentId)) {
          return currentId;
        }

        return logs[0]?.queryId ?? null;
      });
    } catch (error) {
      if (signal?.aborted) {
        return;
      }

      setErrorMessage(getFriendlyApiErrorMessage(error));
      setQueryLogs([]);
      setPerformance(emptyPerformance);
      setTotalLogs(0);
      setTotalQueryPages(1);
      setSelectedQueryId(null);
    } finally {
      if (!signal?.aborted) {
        setIsLoading(false);
      }
    }
  }, [queryPage, queryRange]);

  useEffect(() => {
    const controller = new AbortController();
    void loadQueryLogs(controller.signal);

    return () => controller.abort();
  }, [loadQueryLogs]);

  const selectedLog = useMemo(() => {
    return (
      queryLogs.find((log) => log.queryId === selectedQueryId) ??
      queryLogs[0] ??
      null
    );
  }, [queryLogs, selectedQueryId]);

  const safeQueryPage = Math.min(queryPage, totalQueryPages);
  const queryStartNumber = totalLogs === 0 ? 0 : (safeQueryPage - 1) * queriesPerPage + 1;
  const queryEndNumber = Math.min(safeQueryPage * queriesPerPage, totalLogs);

  const handleQueryRangeChange = (range: QueryRange) => {
    setQueryRange(range);
    setQueryPage(1);
    setSelectedQueryId(null);
  };

  const rangeDropdown = (
    <div className="w-full sm:w-[180px]">
      <label className="block font-mono text-[10px] text-outline uppercase tracking-wider mb-1.5">
        Periode
      </label>

      <div className="relative">
        <select
          value={queryRange}
          onChange={(event) => handleQueryRangeChange(event.target.value as QueryRange)}
          className="w-full appearance-none bg-[#0b0d13] border border-outline-variant/50 rounded-xl py-2.5 pl-3 pr-10 font-mono text-xs text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/60 transition-all cursor-pointer"
        >
          {(Object.keys(queryRangeLabels) as QueryRange[]).map((range) => (
            <option key={range} value={range} className="bg-[#0b0d13] text-on-surface">
              {queryRangeLabels[range]}
            </option>
          ))}
        </select>

        <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-outline">
          <span className="material-symbols-outlined text-[18px]">expand_more</span>
        </span>
      </div>
    </div>
  );

  const computedAverageResponseTime = useMemo(() => {
    if (queryLogs.length === 0) return performance.averageResponseTime || 0;

    const average = queryLogs.reduce(
      (sum, log) => sum + parseResponseTimeSeconds(log.responseTime),
      0
    ) / queryLogs.length;

    return Number.isFinite(average) ? average : 0;
  }, [performance.averageResponseTime, queryLogs]);

  const performanceSummary = useMemo(() => {
    const avgConfidence = Math.round((performance.averageConfidence || 0) * 100);
    const avgResponseTime = computedAverageResponseTime.toFixed(2);

    return [
      {
        label: 'Total Queries',
        value: String(performance.totalQueries ?? totalLogs),
        helper: `Pertanyaan pada periode ${queryRangeLabels[queryRange]}`,
        icon: 'manage_search',
        tone: 'text-primary',
      },
      {
        label: 'Answered',
        value: String(performance.answered ?? 0),
        helper: 'Query berhasil dijawab dengan sumber',
        icon: 'check_circle',
        tone: 'text-emerald-400',
      },
      {
        label: 'Not Found',
        value: String(performance.notFound ?? 0),
        helper: 'Tidak ada konteks relevan',
        icon: 'error',
        tone: 'text-error',
      },
      {
        label: 'Avg Confidence',
        value: `${avgConfidence}%`,
        helper: 'Rata-rata keyakinan jawaban',
        icon: 'verified',
        tone: 'text-primary',
      },
      {
        label: 'Avg Response',
        value: `${avgResponseTime}s`,
        helper: 'Rata-rata waktu respons sistem',
        icon: 'speed',
        tone: 'text-tertiary',
      },
    ];
  }, [computedAverageResponseTime, performance, queryRange, totalLogs]);

  return (
    <div className="bg-background text-on-surface font-body overflow-hidden flex h-screen w-full relative">
      <AdminSidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <main className="flex-1 flex flex-col h-full relative min-w-0">
        <AdminHeader onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

        <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-4 md:p-8 pb-12">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
            <div>
              <p className="font-mono text-[10px] md:text-xs uppercase tracking-wider text-outline mb-2">
                Admin Monitoring
              </p>
              <h1 className="font-headline text-2xl md:text-3xl font-bold text-on-surface">
                Query Logs Detail
              </h1>
              <p className="text-on-surface-variant text-sm md:text-base mt-2 max-w-3xl">
                Halaman ini menampilkan riwayat pertanyaan real dari backend, dokumen yang diambil sistem, skor keyakinan, status jawaban, dan jawaban yang dihasilkan sistem.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void loadQueryLogs()}
                disabled={isLoading}
                className="px-4 py-2 rounded-xl border border-outline-variant/50 text-xs md:text-sm text-on-surface-variant hover:text-primary hover:border-primary/50 disabled:opacity-50 transition-colors"
              >
                {isLoading ? 'Loading...' : 'Refresh'}
              </button>

              <div className="flex items-center gap-2 px-3 py-2 bg-primary/10 text-primary border border-primary/20 rounded-full font-mono text-[10px] md:text-xs w-fit">
                <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                Live Query Trace
              </div>
            </div>
          </div>

          {errorMessage && (
            <div className="mb-6 p-4 rounded-xl border border-error/30 bg-error-container/20 text-error text-sm">
              {errorMessage}
            </div>
          )}

          <section className="h-auto lg:h-[50vh] min-h-[520px] bg-surface-container-low border border-outline-variant rounded-2xl p-4 md:p-6 shadow-sm mb-6 flex flex-col">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
              <div>
                <h2 className="font-headline text-lg md:text-xl font-bold">Query Logs</h2>
                <p className="text-outline text-xs md:text-sm mt-1">
                  Klik salah satu log untuk melihat detail lengkapnya.
                </p>
              </div>

              <div className="flex flex-col sm:flex-row sm:items-end gap-3">
                {rangeDropdown}

                <span className="flex items-center gap-1.5 px-2 py-1 bg-emerald-500/10 text-emerald-400 text-[10px] md:text-xs rounded-md border border-emerald-500/20 font-mono w-fit sm:mb-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  Backend API
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 min-h-0 flex-1">
              <div className="xl:col-span-7 min-h-0">
                <div className="h-full min-h-[260px] overflow-y-auto custom-scrollbar bg-[#0b0d13] border border-outline-variant/50 rounded-xl">
                  <table className="w-full text-left border-collapse min-w-[720px]">
                    <thead className="sticky top-0 bg-[#0b0d13] text-outline font-mono text-[10px] md:text-xs uppercase tracking-wider border-b border-outline-variant/40">
                      <tr>
                        <th className="px-4 py-3 font-medium">Time</th>
                        <th className="px-4 py-3 font-medium">Question</th>
                        <th className="px-4 py-3 font-medium">Sources</th>
                        <th className="px-4 py-3 font-medium">Confidence</th>
                        <th className="px-4 py-3 font-medium">Status</th>
                      </tr>
                    </thead>

                    <tbody className="divide-y divide-outline-variant/30 font-mono text-[11px] md:text-[13px]">
                      {isLoading && queryLogs.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="px-4 py-10 text-center text-on-surface-variant">
                            Loading query logs dari backend...
                          </td>
                        </tr>
                      ) : queryLogs.length > 0 ? (
                        queryLogs.map((log) => (
                          <tr
                            key={log.queryId}
                            onClick={() => setSelectedQueryId(log.queryId)}
                            className={`cursor-pointer transition-colors ${
                              selectedQueryId === log.queryId
                                ? 'bg-primary/10'
                                : 'hover:bg-surface-container-high/30'
                            }`}
                          >
                            <td className="px-4 py-4 text-on-surface-variant whitespace-nowrap">
                              {formatLogTime(log.timestamp)}
                            </td>
                            <td className="px-4 py-4 text-on-surface max-w-[280px]">
                              <span className="block truncate">&quot;{log.userQuestion}&quot;</span>
                              <span className="block text-outline text-[10px] mt-1">{log.queryId}</span>
                            </td>
                            <td className="px-4 py-4 text-on-surface-variant whitespace-nowrap">
                              {log.retrievedDocuments.length > 0
                                ? `${log.retrievedDocuments.length} sources`
                                : 'No source'}
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap">
                              <span className="text-primary font-semibold">
                                {formatPercent(log.confidenceScore)}
                              </span>
                            </td>
                            <td className="px-4 py-4 whitespace-nowrap">
                              <span className={`px-2 py-1 rounded-md border text-[10px] ${getStatusStyle(log.status)}`}>
                                {log.status}
                              </span>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={5} className="px-4 py-10 text-center text-on-surface-variant">
                            Belum ada query log real. Jalankan chat dulu agar log tersimpan.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-3 px-3 py-3 bg-[#0b0d13] border border-outline-variant/50 rounded-xl">
                  <p className="font-mono text-[10px] md:text-xs text-outline">
                    Showing {queryStartNumber}-{queryEndNumber} of {totalLogs} chats
                  </p>

                  {totalQueryPages > 1 && (
                    <div className="flex items-center gap-2 overflow-x-auto custom-scrollbar pb-1 sm:pb-0">
                      {Array.from({ length: totalQueryPages }, (_, index) => index + 1).map((page) => (
                        <button
                          key={page}
                          type="button"
                          onClick={() => setQueryPage(page)}
                          className={`w-8 h-8 rounded-lg border font-mono text-xs transition-all shrink-0 ${
                            safeQueryPage === page
                              ? 'bg-primary text-on-primary-container border-primary'
                              : 'bg-surface-container-high text-on-surface-variant border-outline-variant/50 hover:text-primary hover:border-primary/50'
                          }`}
                        >
                          {page}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="xl:col-span-5 min-h-0">
                <div className="h-full min-h-[320px] overflow-y-auto custom-scrollbar bg-surface-container-high/30 border border-outline-variant/50 rounded-xl p-4">
                  {selectedLog ? (
                    <>
                      <div className="flex items-start justify-between gap-3 mb-4">
                        <div>
                          <p className="font-mono text-[10px] text-outline uppercase tracking-wider mb-1">
                            Selected Log
                          </p>
                          <h3 className="font-headline text-lg font-bold text-on-surface break-all">
                            {selectedLog.queryId}
                          </h3>
                          <p className="font-mono text-[10px] text-outline mt-1">
                            {formatLogDateTime(selectedLog.timestamp)}
                          </p>
                        </div>

                        <span className={`px-2 py-1 rounded-md border text-[10px] font-mono ${getStatusStyle(selectedLog.status)}`}>
                          {selectedLog.status}
                        </span>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
                        <div className="bg-[#0b0d13] border border-outline-variant/50 rounded-lg p-3">
                          <p className="text-outline font-mono text-[10px] uppercase mb-1">User</p>
                          <p className="text-sm text-on-surface">{selectedLog.userName}</p>
                        </div>

                        <div className="bg-[#0b0d13] border border-outline-variant/50 rounded-lg p-3">
                          <p className="text-outline font-mono text-[10px] uppercase mb-1">Response Time</p>
                          <p className="text-sm text-on-surface">{selectedLog.responseTime}</p>
                        </div>

                        <div className="bg-[#0b0d13] border border-outline-variant/50 rounded-lg p-3">
                          <p className="text-outline font-mono text-[10px] uppercase mb-1">Confidence</p>
                          <div className="flex items-center gap-2">
                            <div className="h-2 bg-surface-variant rounded-full overflow-hidden flex-1">
                              <div
                                className="h-full bg-primary rounded-full"
                                style={{ width: formatPercent(selectedLog.confidenceScore) }}
                              />
                            </div>
                            <span className="font-mono text-xs text-primary">
                              {formatPercent(selectedLog.confidenceScore)}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="space-y-3">
                        <div className="bg-[#0b0d13] border border-outline-variant/50 rounded-lg p-3">
                          <p className="text-outline font-mono text-[10px] uppercase mb-2">User Question</p>
                          <p className="text-sm text-on-surface leading-relaxed">&quot;{selectedLog.userQuestion}&quot;</p>
                        </div>

                        <div className="bg-[#0b0d13] border border-outline-variant/50 rounded-lg p-3">
                          <p className="text-outline font-mono text-[10px] uppercase mb-2">Retrieved Documents</p>

                          {selectedLog.retrievedDocuments.length > 0 ? (
                            <div className="space-y-2">
                              {selectedLog.retrievedDocuments.map((source) => (
                                <div
                                  key={`${source.documentName}-${source.chunkId}`}
                                  className="flex items-start justify-between gap-3 border-b border-outline-variant/30 pb-2 last:border-b-0 last:pb-0"
                                >
                                  <div>
                                    <p className="text-sm text-on-surface">{source.documentName}</p>
                                    <p className="font-mono text-[10px] text-outline">
                                      p.{source.page} • {source.chunkId}
                                    </p>
                                  </div>
                                  <span className="font-mono text-xs text-primary whitespace-nowrap">
                                    {formatPercent(source.relevanceScore)}
                                  </span>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-sm text-error">No relevant context found in vector DB.</p>
                          )}
                        </div>

                        <div className="bg-[#0b0d13] border border-outline-variant/50 rounded-lg p-3">
                          <p className="text-outline font-mono text-[10px] uppercase mb-2">Generated Answer</p>
                          <p className="text-sm text-on-surface-variant leading-relaxed whitespace-pre-wrap">
                            {selectedLog.answerGenerated || 'Belum ada jawaban tersimpan untuk log ini.'}
                          </p>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="h-full flex items-center justify-center text-center text-sm text-on-surface-variant">
                      Pilih log dari tabel, atau jalankan chat terlebih dahulu agar log muncul.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </section>

          <div className="grid grid-cols-1 2xl:grid-cols-12 gap-6">
            <section className="2xl:col-span-5 bg-surface-container-low border border-outline-variant rounded-2xl p-4 md:p-6 shadow-sm">
              <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-5">
                <div>
                  <h2 className="font-headline text-lg md:text-xl font-bold">Query Performance Summary</h2>
                  <p className="text-outline text-sm mt-1">
                    Ringkasan performa sistem berdasarkan status log, confidence score, dan response time dari backend.
                  </p>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-end gap-3">
                  {rangeDropdown}

                  <span className="font-mono text-[10px] md:text-xs px-2 md:px-3 py-1 bg-primary/10 text-primary border border-primary/20 rounded-full w-fit sm:mb-1.5">
                    Database Connected
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {performanceSummary.map((metric) => (
                  <div
                    key={metric.label}
                    className="bg-[#0b0d13] border border-outline-variant/50 rounded-xl p-4 hover:border-primary/50 transition-colors"
                  >
                    <div className="flex items-center justify-between gap-3 mb-3">
                      <p className="text-outline font-mono text-[10px] uppercase tracking-wider">
                        {metric.label}
                      </p>
                      <span className={`material-symbols-outlined text-[18px] ${metric.tone}`}>
                        {metric.icon}
                      </span>
                    </div>

                    <p className="font-headline text-2xl md:text-3xl font-bold text-on-surface mb-1">
                      {metric.value}
                    </p>
                    <p className="text-xs text-on-surface-variant leading-relaxed">
                      {metric.helper}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            <section className="2xl:col-span-7 bg-surface-container-low border border-outline-variant rounded-2xl p-4 md:p-6 shadow-sm">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-5">
                <div>
                  <h2 className="font-headline text-lg md:text-xl font-bold">Query Logs Explanation</h2>
                  <p className="text-outline text-sm mt-1">
                    Penjelasan singkat tentang cara membaca data query logs dan performa sistem RAG.
                  </p>
                </div>

                <span className="font-mono text-[10px] md:text-xs px-2 md:px-3 py-1 bg-primary/10 text-primary border border-primary/20 rounded-full w-fit">
                  Guide
                </span>
              </div>

              <div className="bg-[#0b0d13] border border-outline-variant/50 rounded-xl p-4 md:p-5 space-y-4">
                <div className="flex gap-3">
                  <span className="material-symbols-outlined text-primary text-[22px] shrink-0">manage_search</span>
                  <div>
                    <h3 className="font-headline text-base font-bold text-on-surface mb-1">
                      Fungsi Query Logs
                    </h3>
                    <p className="text-sm text-on-surface-variant leading-relaxed">
                      Query Logs digunakan untuk melihat riwayat pertanyaan user, waktu pertanyaan dikirim,
                      dokumen yang berhasil diambil sistem, confidence score, response time, dan status jawaban.
                    </p>
                  </div>
                </div>

                <div className="flex gap-3">
                  <span className="material-symbols-outlined text-emerald-400 text-[22px] shrink-0">source</span>
                  <div>
                    <h3 className="font-headline text-base font-bold text-on-surface mb-1">
                      Fungsi Retrieved Documents
                    </h3>
                    <p className="text-sm text-on-surface-variant leading-relaxed">
                      Retrieved Documents menunjukkan sumber dokumen yang dipakai chatbot untuk menjawab pertanyaan.
                      Semakin tinggi relevance score, semakin kuat hubungan dokumen tersebut dengan pertanyaan user.
                    </p>
                  </div>
                </div>

                <div className="flex gap-3">
                  <span className="material-symbols-outlined text-secondary text-[22px] shrink-0">verified</span>
                  <div>
                    <h3 className="font-headline text-base font-bold text-on-surface mb-1">
                      Fungsi Query Performance Summary
                    </h3>
                    <p className="text-sm text-on-surface-variant leading-relaxed">
                      Query Performance Summary membantu admin membaca performa sistem berdasarkan total query,
                      jumlah pertanyaan yang berhasil dijawab, query yang tidak ditemukan, rata-rata confidence,
                      dan rata-rata waktu respons pada periode harian, mingguan, bulanan, atau tahunan.
                    </p>
                  </div>
                </div>

                <div className="flex gap-3">
                  <span className="material-symbols-outlined text-amber-400 text-[22px] shrink-0">tips_and_updates</span>
                  <div>
                    <h3 className="font-headline text-base font-bold text-on-surface mb-1">
                      Cara Membaca Status
                    </h3>
                    <p className="text-sm text-on-surface-variant leading-relaxed">
                      Status ANSWERED berarti sistem menemukan konteks yang cukup. NOT_FOUND berarti sistem belum
                      menemukan dokumen yang relevan. NEED_REVIEW berarti jawaban masih perlu dicek kembali karena
                      confidence atau konteks dokumennya belum sepenuhnya kuat.
                    </p>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
};
