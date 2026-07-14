import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AdminSidebar } from './AdminSidebar';
import { AdminHeader } from './AdminHeader';
import {
  getQueryLogsDashboard,
  type QueryLog,
  type QueryLogPerformance,
  type RetrievedSource,
  type QueryLogStatus,
  type QueryRange,
} from '../services/queryLogService';
import { getFriendlyApiErrorMessage } from '../services/api';

const queryRangeLabels: Record<QueryRange, string> = {
  daily: 'Today',
  weekly: 'This Week',
  monthly: 'This Month',
  yearly: 'This Year',
};

const queryRangeOptions: QueryRange[] = ['daily', 'weekly', 'monthly', 'yearly'];

const getStatusStyle = (status: QueryLogStatus): string => {
  switch (status) {
    case 'ANSWERED':
      return 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400';
    case 'NEED_REVIEW':
      return 'border-amber-500/20 bg-amber-500/10 text-amber-400';
    case 'NOT_FOUND':
      return 'border-rose-500/20 bg-rose-500/10 text-rose-400';
    case 'ERROR':
      return 'border-rose-500/20 bg-rose-500/10 text-rose-400';
    default:
      return 'border-slate-700 bg-slate-800 text-slate-300';
  }
};

const normalizeTimestamp = (timestamp: string): string => {
  return timestamp?.includes('T') ? timestamp : timestamp?.replace(' ', 'T');
};

const parseTimestampToDate = (timestamp: string): Date | null => {
  if (!timestamp) return null;
  const date = new Date(normalizeTimestamp(timestamp));
  return Number.isNaN(date.getTime()) ? null : date;
};

const formatLogTime = (timestamp: string): string => {
  const date = parseTimestampToDate(timestamp);
  if (!date) return timestamp?.split(' ')[1] ?? '-';
  return date.toLocaleTimeString('en-US', {
    timeZone: 'Asia/Jakarta',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

const formatLogDateTime = (timestamp: string): string => {
  const date = parseTimestampToDate(timestamp);
  if (!date) return timestamp || '-';
  return date.toLocaleString('en-US', {
    timeZone: 'Asia/Jakarta',
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

const getJakartaDateKey = (date: Date): string => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Jakarta',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date);
  const year = parts.find((part) => part.type === 'year')?.value ?? '0000';
  const month = parts.find((part) => part.type === 'month')?.value ?? '01';
  const day = parts.find((part) => part.type === 'day')?.value ?? '01';
  return `${year}-${month}-${day}`;
};

const parseDateKeyAsUtcDate = (dateKey: string): Date => {
  const [year, month, day] = dateKey.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, day));
};

const getWeekStartKey = (dateKey: string): string => {
  const date = parseDateKeyAsUtcDate(dateKey);
  const day = date.getUTCDay();
  const diffToMonday = day === 0 ? -6 : 1 - day;
  date.setUTCDate(date.getUTCDate() + diffToMonday);
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const dayOfMonth = String(date.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${dayOfMonth}`;
};

const getLogDateKey = (log: QueryLog): string | null => {
  const date = parseTimestampToDate(log.timestamp);
  return date ? getJakartaDateKey(date) : null;
};

const filterLogsByRange = (logs: QueryLog[], range: QueryRange): QueryLog[] => {
  const todayKey = getJakartaDateKey(new Date());
  const currentWeekStart = getWeekStartKey(todayKey);
  const currentMonthKey = todayKey.slice(0, 7);
  const currentYearKey = todayKey.slice(0, 4);

  return logs.filter((log) => {
    const logDateKey = getLogDateKey(log);
    if (!logDateKey) return false;
    switch (range) {
      case 'daily': return logDateKey === todayKey;
      case 'weekly': return getWeekStartKey(logDateKey) === currentWeekStart;
      case 'monthly': return logDateKey.slice(0, 7) === currentMonthKey;
      case 'yearly': return logDateKey.slice(0, 4) === currentYearKey;
      default: return true;
    }
  });
};

const formatPercent = (value: number): string => {
  return `${Math.round((Number.isFinite(value) ? value : 0) * 100)}%`;
};

const formatSourceLocation = (source: RetrievedSource): string => {
  const labels: string[] = [];

  if (source.page?.trim()) {
    labels.push(`Halaman ${source.page}`);
  }
  if (source.section?.trim()) {
    labels.push(`Bagian: ${source.section}`);
  }
  if (source.paragraphStart !== undefined) {
    const end = source.paragraphEnd ?? source.paragraphStart;
    labels.push(
      end === source.paragraphStart
        ? `Paragraf ${source.paragraphStart}`
        : `Paragraf ${source.paragraphStart}-${end}`
    );
  }
  if (source.lineStart !== undefined) {
    const end = source.lineEnd ?? source.lineStart;
    labels.push(
      end === source.lineStart
        ? `Baris ${source.lineStart}`
        : `Baris ${source.lineStart}-${end}`
    );
  }

  return labels.join(' • ') || 'Lokasi sumber tidak tersedia';
};

const normalizeConfidenceScore = (value: unknown): number => {
  const numeric = Number(value ?? 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return 0;
  return numeric > 1 ? numeric / 100 : numeric;
};

const parseResponseTimeSeconds = (value: unknown): number => {
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0;
  const text = String(value ?? '').trim().toLowerCase();
  if (!text) return 0;
  const numeric = Number(text.replace(',', '.').replace(/[^0-9.-]/g, ''));
  if (!Number.isFinite(numeric)) return 0;
  if (text.includes('ms')) return numeric / 1000;
  return numeric;
};

const calculatePerformanceFromLogs = (logs: QueryLog[]): QueryLogPerformance => {
  const totalQueries = logs.length;
  const answered = logs.filter((log) => log.status === 'ANSWERED').length;
  const notFound = logs.filter((log) => log.status === 'NOT_FOUND').length;
  const needReview = logs.filter((log) => log.status === 'NEED_REVIEW').length;
  const errors = logs.filter((log) => log.status === 'ERROR').length;

  const confidenceValues = logs
    .map((log) => normalizeConfidenceScore(log.confidenceScore))
    .filter((value) => Number.isFinite(value) && value > 0);

  const responseTimeValues = logs
    .map((log) => parseResponseTimeSeconds(log.responseTime))
    .filter((value) => Number.isFinite(value) && value > 0);

  const averageConfidence = confidenceValues.length > 0
    ? confidenceValues.reduce((sum, value) => sum + value, 0) / confidenceValues.length
    : 0;

  const averageResponseTime = responseTimeValues.length > 0
    ? responseTimeValues.reduce((sum, value) => sum + value, 0) / responseTimeValues.length
    : 0;

  return { totalQueries, answered, notFound, needReview, errors, averageConfidence, averageResponseTime };
};

type MetricTone = 'cyan' | 'green' | 'pink' | 'yellow' | 'purple';

type PerformanceMetric = {
  label: string;
  value: string;
  icon: string;
  tone: MetricTone;
  decoIcon: string;
};

// Pemetaan gaya gradient dan warna teks seperti referensi gambar
const metricStyles: Record<MetricTone, { bg: string, text: string }> = {
  cyan: {
    bg: 'bg-[linear-gradient(135deg,#7bf5dc_0%,#31c8e6_100%)]',
    text: 'text-slate-900',
  },
  yellow: {
    bg: 'bg-[linear-gradient(135deg,#ffe47c_0%,#ff9915_100%)]',
    text: 'text-slate-900',
  },
  green: {
    bg: 'bg-[linear-gradient(135deg,#95f8c3_0%,#46d787_100%)]',
    text: 'text-slate-900',
  },
  pink: {
    bg: 'bg-[linear-gradient(135deg,#ffb7cc_0%,#fa4e74_100%)]',
    text: 'text-slate-900',
  },
  purple: {
    bg: 'bg-[linear-gradient(135deg,#dcbbf9_0%,#9862ed_100%)]',
    text: 'text-slate-900',
  },
};

const AdminQueryLogsDetail: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedQueryId, setSelectedQueryId] = useState<string | null>(null);
  const [queryPage, setQueryPage] = useState(1);
  const [queryRange, setQueryRange] = useState<QueryRange>('daily');
  const [allQueryLogs, setAllQueryLogs] = useState<QueryLog[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const queriesPerPage = 8;

  const loadQueryLogs = useCallback(async (signal?: AbortSignal) => {
    setIsLoading(true);
    setErrorMessage('');
    try {
      const response = await getQueryLogsDashboard({ range: 'yearly', page: 1, limit: 5000 }, signal);
      const logs = Array.isArray(response.logs) ? response.logs : [];
      const sortedLogs = [...logs].sort((a, b) => {
        const first = parseTimestampToDate(a.timestamp)?.getTime() ?? 0;
        const second = parseTimestampToDate(b.timestamp)?.getTime() ?? 0;
        return second - first;
      });
      setAllQueryLogs(sortedLogs);
    } catch (error) {
      if (signal?.aborted) return;
      setErrorMessage(getFriendlyApiErrorMessage(error));
      setAllQueryLogs([]);
      setSelectedQueryId(null);
    } finally {
      if (!signal?.aborted) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadQueryLogs(controller.signal);
    return () => controller.abort();
  }, [loadQueryLogs]);

  const filteredQueryLogs = useMemo(() => filterLogsByRange(allQueryLogs, queryRange), [allQueryLogs, queryRange]);
  const performance = useMemo(() => calculatePerformanceFromLogs(filteredQueryLogs), [filteredQueryLogs]);

  const totalLogs = filteredQueryLogs.length;
  const totalQueryPages = Math.max(Math.ceil(totalLogs / queriesPerPage), 1);
  const safeQueryPage = Math.min(queryPage, totalQueryPages);

  const queryLogs = useMemo(() => {
    const startIndex = (safeQueryPage - 1) * queriesPerPage;
    return filteredQueryLogs.slice(startIndex, startIndex + queriesPerPage);
  }, [filteredQueryLogs, safeQueryPage]);

  useEffect(() => {
    setSelectedQueryId((currentId) => {
      if (currentId && filteredQueryLogs.some((log) => log.queryId === currentId)) return currentId;
      return queryLogs[0]?.queryId ?? null;
    });
  }, [filteredQueryLogs, queryLogs]);

  const selectedLog = useMemo(() => {
    return filteredQueryLogs.find((log) => log.queryId === selectedQueryId) ?? queryLogs[0] ?? null;
  }, [filteredQueryLogs, queryLogs, selectedQueryId]);

  const queryStartNumber = totalLogs === 0 ? 0 : (safeQueryPage - 1) * queriesPerPage + 1;
  const queryEndNumber = Math.min(safeQueryPage * queriesPerPage, totalLogs);

  const handleQueryRangeChange = (range: QueryRange) => {
    setQueryRange(range);
    setQueryPage(1);
    setSelectedQueryId(null);
  };

  // Metrik dikonfigurasi mengikuti palet warna gambar referensi
  const performanceSummary = useMemo<PerformanceMetric[]>(() => [
    { label: 'Total Queries', value: String(performance.totalQueries ?? totalLogs), icon: 'folder', decoIcon: 'folder', tone: 'cyan' },
    { label: 'Answered', value: String(performance.answered ?? 0), icon: 'check_circle', decoIcon: 'fact_check', tone: 'green' },
    { label: 'Not Found', value: String(performance.notFound ?? 0), icon: 'error', decoIcon: 'folder_off', tone: 'pink' },
    { label: 'Avg Confidence', value: `${Math.round((performance.averageConfidence || 0) * 100)}%`, icon: 'bar_chart', decoIcon: 'insert_chart', tone: 'yellow' },
    { label: 'Avg Response', value: `${(performance.averageResponseTime || 0).toFixed(2)}s`, icon: 'speed', decoIcon: 'speed', tone: 'purple' },
  ], [performance, totalLogs]);

  return (
    <div className="bg-slate-950 text-slate-200 font-sans flex h-screen w-full selection:bg-blue-500/30 overflow-hidden">
      
      <style dangerouslySetInnerHTML={{__html: `
        .sleek-scroll::-webkit-scrollbar { width: 6px; height: 6px; }
        .sleek-scroll::-webkit-scrollbar-track { background: transparent; }
        .sleek-scroll::-webkit-scrollbar-thumb { background: #334155; border-radius: 10px; }
        .sleek-scroll::-webkit-scrollbar-thumb:hover { background: #475569; }
      `}} />

      <AdminSidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <main className="flex-1 flex flex-col h-full overflow-y-auto sleek-scroll relative">
        <AdminHeader onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

        <div className="p-4 md:p-6 lg:p-8 pb-12 w-full max-w-[1720px] mx-auto space-y-6 md:space-y-8">
          
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-semibold tracking-tight text-white">
                Query Logs
              </h1>
              <p className="text-sm text-slate-400 mt-1.5 max-w-2xl">
                Monitor pertanyaan pengguna, dokumen sumber yang diambil, dan performa respon sistem.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void loadQueryLogs()}
                disabled={isLoading}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-800 bg-slate-900 text-sm font-medium text-slate-300 hover:bg-slate-800 hover:text-white disabled:opacity-50 transition-colors shadow-sm"
              >
                <span className="material-symbols-outlined text-[18px]">refresh</span>
                {isLoading ? 'Refreshing...' : 'Refresh'}
              </button>
            </div>
          </div>

          {errorMessage && (
            <div className="p-4 rounded-lg border border-rose-500/20 bg-rose-500/10 text-rose-400 text-sm">
              {errorMessage}
            </div>
          )}

          {/* DESAIN CARD METRICS BARU MENGIKUTI GAMBAR */}
          <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {performanceSummary.map((metric) => {
              const style = metricStyles[metric.tone];
              
              return (
                <div 
                  key={metric.label} 
                  className={`relative overflow-hidden rounded-[24px] p-5 md:p-6 shadow-md transition-transform hover:-translate-y-1 ${style.bg}`}
                >
                  {/* Top: Header Card (Icon + Title) */}
                  <div className={`flex items-center gap-2 ${style.text} opacity-90`}>
                    <span className="material-symbols-outlined text-[18px] font-bold">{metric.icon}</span>
                    <p className="text-sm font-bold">{metric.label}</p>
                  </div>
                  
                  {/* Bottom: Besar Value */}
                  <div className={`mt-6 ${style.text}`}>
                    <h4 className="text-4xl md:text-5xl font-black tracking-tight drop-shadow-sm">
                      {metric.value}
                    </h4>
                  </div>

                  {/* Dekorasi Pojok Kanan Bawah */}
                  <div className={`absolute -bottom-4 -right-2 text-[90px] opacity-15 rotate-[-5deg] ${style.text} mix-blend-color-burn pointer-events-none`}>
                    <span className="material-symbols-outlined !text-[90px]">{metric.decoIcon}</span>
                  </div>
                </div>
              );
            })}
          </section>

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-2 md:p-3 rounded-xl shadow-sm">
            <div className="inline-flex flex-wrap rounded-lg bg-slate-950 p-1">
              {queryRangeOptions.map((range) => {
                const isActive = queryRange === range;
                return (
                  <button
                    key={range}
                    type="button"
                    onClick={() => handleQueryRangeChange(range)}
                    className={`px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${
                      isActive ? 'bg-slate-800 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                    }`}
                  >
                    {queryRangeLabels[range]}
                  </button>
                );
              })}
            </div>
            <span className="text-xs font-medium text-slate-400 px-2">Total: {totalLogs} logs</span>
          </div>

          <section className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start relative">
            
            <div className="lg:col-span-5 flex flex-col gap-4">
              <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden shadow-sm flex flex-col">
                <div className="flex-1 divide-y divide-slate-800/50">
                  {isLoading && queryLogs.length === 0 ? (
                    <div className="p-8 text-center text-sm text-slate-500">Memuat log pertanyaan...</div>
                  ) : queryLogs.length > 0 ? (
                    queryLogs.map((log) => {
                      const isSelected = selectedQueryId === log.queryId;
                      return (
                        <button
                          key={log.queryId}
                          type="button"
                          onClick={() => setSelectedQueryId(log.queryId)}
                          className={`w-full text-left p-4 transition-colors relative ${
                            isSelected ? 'bg-blue-500/10' : 'hover:bg-slate-800/50'
                          }`}
                        >
                          {isSelected && <div className="absolute left-0 top-0 bottom-0 w-1 bg-blue-500" />}
                          <div className="flex items-start justify-between gap-3 mb-2">
                            <p className="text-sm font-medium text-slate-200 line-clamp-2">"{log.userQuestion}"</p>
                            <span className={`shrink-0 px-2 py-0.5 rounded-md text-[10px] font-medium border ${getStatusStyle(log.status)}`}>
                              {log.status}
                            </span>
                          </div>
                          <div className="flex items-center justify-between text-xs text-slate-500">
                            <span>{formatLogTime(log.timestamp)}</span>
                            <span>{formatPercent(log.confidenceScore)} confidence</span>
                          </div>
                        </button>
                      );
                    })
                  ) : (
                    <div className="p-8 text-center text-sm text-slate-500">Tidak ada log untuk periode ini.</div>
                  )}
                </div>

                <div className="p-4 border-t border-slate-800 bg-slate-900/80 flex items-center justify-between text-xs text-slate-400">
                  <span>Menampilkan {queryStartNumber}-{queryEndNumber} dari {totalLogs} log</span>
                  
                  {totalQueryPages > 1 && (
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => setQueryPage(p => Math.max(1, p - 1))}
                        disabled={safeQueryPage === 1}
                        className="px-3 py-1.5 rounded border border-slate-700 hover:bg-slate-800 disabled:opacity-50 disabled:hover:bg-transparent transition-colors flex items-center"
                      >
                        Prev
                      </button>
                      
                      <span className="font-medium text-slate-300">
                        {safeQueryPage} / {totalQueryPages}
                      </span>
                      
                      <button
                        onClick={() => setQueryPage(p => Math.min(totalQueryPages, p + 1))}
                        disabled={safeQueryPage === totalQueryPages}
                        className="px-3 py-1.5 rounded border border-slate-700 hover:bg-slate-800 disabled:opacity-50 disabled:hover:bg-transparent transition-colors flex items-center"
                      >
                        Next
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="lg:col-span-7 sticky top-6 rounded-xl border border-slate-800 bg-slate-900 shadow-sm max-h-[calc(100vh-3rem)] overflow-y-auto sleek-scroll flex flex-col">
              {selectedLog ? (
                <>
                  <div className="p-5 md:p-6 border-b border-slate-800 sticky top-0 bg-slate-900/95 backdrop-blur z-10">
                    <div className="flex flex-wrap items-center gap-3 mb-1.5">
                      <h2 className="text-lg font-semibold text-white">Detail Log</h2>
                      <span className={`px-2.5 py-0.5 rounded-md text-[11px] font-medium border ${getStatusStyle(selectedLog.status)}`}>
                        {selectedLog.status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 font-mono truncate">ID: {selectedLog.queryId} • {formatLogDateTime(selectedLog.timestamp)}</p>
                  </div>

                  <div className="p-5 md:p-6 space-y-6">
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3 md:gap-4">
                      <div className="p-3.5 md:p-4 rounded-lg bg-slate-950 border border-slate-800">
                        <p className="text-xs font-medium text-slate-500 mb-1">User</p>
                        <p className="text-sm font-medium text-slate-200 truncate">{selectedLog.userName}</p>
                      </div>
                      <div className="p-3.5 md:p-4 rounded-lg bg-slate-950 border border-slate-800">
                        <p className="text-xs font-medium text-slate-500 mb-1">Waktu Respon</p>
                        <p className="text-sm font-medium text-slate-200">{selectedLog.responseTime}</p>
                      </div>
                      <div className="p-3.5 md:p-4 rounded-lg bg-slate-950 border border-slate-800 hidden md:block">
                        <p className="text-xs font-medium text-slate-500 mb-1">Confidence</p>
                        <p className="text-sm font-medium text-slate-200">{formatPercent(selectedLog.confidenceScore)}</p>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div>
                        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                          <span className="material-symbols-outlined text-[16px]">help</span> Pertanyaan User
                        </h3>
                        <div className="p-4 rounded-lg bg-slate-800/30 border border-slate-800 text-sm text-slate-200">
                          {selectedLog.userQuestion}
                        </div>
                      </div>

                      <div>
                        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                          <span className="material-symbols-outlined text-[16px]">smart_toy</span> Jawaban Sistem
                        </h3>
                        <div className="p-4 rounded-lg bg-slate-800/30 border border-slate-800 text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">
                          {selectedLog.answerGenerated || 'Tidak ada jawaban yang dihasilkan.'}
                        </div>
                      </div>
                    </div>

                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                          <span className="material-symbols-outlined text-[16px]">description</span> Sumber Terambil
                        </h3>
                        <span className="text-xs text-slate-500 bg-slate-950 border border-slate-800 px-2 py-1 rounded-md">
                          {(selectedLog.retrievedDocuments ?? []).length} dokumen
                        </span>
                      </div>

                      {(selectedLog.retrievedDocuments ?? []).length > 0 ? (
                        <div className="space-y-2">
                          {(selectedLog.retrievedDocuments ?? []).map((source) => (
                            <div key={`${source.documentName}-${source.chunkId}`} className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-lg border border-slate-800 bg-slate-950">
                              <div className="min-w-0 flex-1">
                                <p className="text-sm font-medium text-slate-200 truncate">{source.documentName}</p>
                                <p className="text-xs text-slate-500 mt-0.5">{formatSourceLocation(source)} • Chunk {source.chunkId}</p>
                                {source.excerpt && (
                                  <blockquote className="mt-2 rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-xs italic leading-relaxed text-slate-400">
                                    “{source.excerpt}”
                                  </blockquote>
                                )}
                              </div>
                              <span className="w-fit text-xs font-medium text-blue-400 bg-blue-500/10 px-2.5 py-1.5 rounded-md">
                                {formatPercent(source.relevanceScore)} relevan
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-slate-500 p-4 rounded-lg border border-slate-800 border-dashed text-center">
                          Tidak ada dokumen referensi yang ditemukan pada vektor DB.
                        </p>
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <div className="h-[400px] flex items-center justify-center text-sm text-slate-500 p-6">
                  Pilih log dari daftar di sebelah kiri untuk melihat detail.
                </div>
              )}
            </div>

          </section>
        </div>
      </main>
    </div>
  );
};

export { AdminQueryLogsDetail };
export default AdminQueryLogsDetail;