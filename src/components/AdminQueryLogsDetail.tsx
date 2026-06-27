import React, { useMemo, useState } from 'react';
import { AdminSidebar } from './AdminSidebar';
import { AdminHeader } from './AdminHeader';

type QueryLogStatus = 'ANSWERED' | 'NEED_REVIEW' | 'NOT_FOUND' | 'ERROR';
type QueryRange = 'daily' | 'weekly' | 'monthly' | 'yearly';

const queryRangeLabels: Record<QueryRange, string> = {
  daily: 'Harian',
  weekly: 'Mingguan',
  monthly: 'Bulanan',
  yearly: 'Tahunan',
};

const parseQueryDate = (timestamp: string) => new Date(timestamp.replace(' ', 'T'));

interface RetrievedSource {
  documentName: string;
  page: string;
  chunkId: string;
  relevanceScore: number;
}

interface QueryLog {
  queryId: string;
  userName: string;
  userQuestion: string;
  timestamp: string;
  retrievedDocuments: RetrievedSource[];
  answerGenerated: string;
  confidenceScore: number;
  responseTime: string;
  status: QueryLogStatus;
}

const queryLogs: QueryLog[] = [
  {
    queryId: 'QL-20260628-001',
    userName: 'Staff User',
    userQuestion: 'Bagaimana prosedur klaim medis rawat inap?',
    timestamp: '2026-06-28 10:45:22',
    retrievedDocuments: [
      { documentName: 'SOP_Claim_Medical.pdf', page: 'p.7', chunkId: 'CHK-00071', relevanceScore: 0.94 },
      { documentName: 'Policy_Employee_Benefit.pdf', page: 'p.3', chunkId: 'CHK-00119', relevanceScore: 0.88 },
      { documentName: 'FAQ_HR_Benefit.docx', page: 'p.2', chunkId: 'CHK-00204', relevanceScore: 0.81 },
    ],
    answerGenerated:
      'Prosedur klaim medis rawat inap dilakukan dengan mengisi formulir klaim, melampirkan kuitansi asli, surat keterangan rawat inap, dan ringkasan medis. Dokumen diserahkan ke HR maksimal 14 hari kerja setelah pasien keluar dari rumah sakit.',
    confidenceScore: 0.91,
    responseTime: '1.2s',
    status: 'ANSWERED',
  },
  {
    queryId: 'QL-20260628-002',
    userName: 'Staff User',
    userQuestion: 'Template laporan keuangan bulan ini',
    timestamp: '2026-06-28 10:42:15',
    retrievedDocuments: [
      { documentName: 'Finance_Report_Template_2026.docx', page: 'p.1', chunkId: 'CHK-00321', relevanceScore: 0.86 },
    ],
    answerGenerated:
      'Template laporan keuangan bulan ini menggunakan format Finance_Report_Template_2026.docx. Bagian yang wajib diisi meliputi ringkasan pendapatan, pengeluaran operasional, arus kas, dan catatan pembayaran tertunda.',
    confidenceScore: 0.87,
    responseTime: '0.8s',
    status: 'ANSWERED',
  },
  {
    queryId: 'QL-20260628-003',
    userName: 'System Admin',
    userQuestion: 'Siapa nama CEO perusahaan?',
    timestamp: '2026-06-28 10:35:01',
    retrievedDocuments: [],
    answerGenerated:
      'Saya belum menemukan informasi yang cukup pada dokumen yang tersedia. Silakan unggah dokumen perusahaan yang memuat struktur organisasi atau profil manajemen.',
    confidenceScore: 0.22,
    responseTime: '0.6s',
    status: 'NOT_FOUND',
  },
  {
    queryId: 'QL-20260628-004',
    userName: 'Staff User',
    userQuestion: 'Apa kebijakan work from home untuk karyawan baru?',
    timestamp: '2026-06-28 10:31:47',
    retrievedDocuments: [
      { documentName: 'Policy_WFH.pdf', page: 'p.2', chunkId: 'CHK-00033', relevanceScore: 0.89 },
      { documentName: 'SOP_Onboarding.pdf', page: 'p.5', chunkId: 'CHK-00012', relevanceScore: 0.76 },
    ],
    answerGenerated:
      'Karyawan dapat melakukan work from home maksimal 2 hari per minggu setelah mendapat persetujuan manajer. Untuk karyawan baru, kebijakan ini menyesuaikan hasil evaluasi masa probation.',
    confidenceScore: 0.74,
    responseTime: '1.4s',
    status: 'NEED_REVIEW',
  },
];

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

export const AdminQueryLogsDetail: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedQueryId, setSelectedQueryId] = useState(queryLogs[0].queryId);
  const [queryPage, setQueryPage] = useState(1);
  const [queryRange, setQueryRange] = useState<QueryRange>('daily');

  const filteredQueryLogs = useMemo(() => {
    if (queryLogs.length === 0) return [];

    const latestTimestamp = Math.max(
      ...queryLogs.map((log) => parseQueryDate(log.timestamp).getTime())
    );
    const latestDate = new Date(latestTimestamp);

    return queryLogs.filter((log) => {
      const logDate = parseQueryDate(log.timestamp);
      const logTimestamp = logDate.getTime();
      const diffDays = (latestTimestamp - logTimestamp) / (1000 * 60 * 60 * 24);

      if (queryRange === 'daily') {
        return logDate.toDateString() === latestDate.toDateString();
      }

      if (queryRange === 'weekly') {
        return diffDays >= 0 && diffDays < 7;
      }

      if (queryRange === 'monthly') {
        return (
          logDate.getFullYear() === latestDate.getFullYear() &&
          logDate.getMonth() === latestDate.getMonth()
        );
      }

      return logDate.getFullYear() === latestDate.getFullYear();
    });
  }, [queryRange]);

  const selectedLog = useMemo(
    () =>
      filteredQueryLogs.find((log) => log.queryId === selectedQueryId) ??
      filteredQueryLogs[0] ??
      queryLogs[0],
    [filteredQueryLogs, selectedQueryId]
  );

  const queriesPerPage = 25;
  const totalQueryPages = Math.max(Math.ceil(filteredQueryLogs.length / queriesPerPage), 1);
  const safeQueryPage = Math.min(queryPage, totalQueryPages);
  const queryStartNumber =
    filteredQueryLogs.length === 0 ? 0 : (safeQueryPage - 1) * queriesPerPage + 1;
  const queryEndNumber = Math.min(safeQueryPage * queriesPerPage, filteredQueryLogs.length);
  const paginatedQueryLogs = filteredQueryLogs.slice(
    (safeQueryPage - 1) * queriesPerPage,
    safeQueryPage * queriesPerPage
  );

  const handleQueryRangeChange = (range: QueryRange) => {
    setQueryRange(range);
    setQueryPage(1);
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

  const performanceSummary = useMemo(() => {
    const totalQueries = filteredQueryLogs.length;
    const answered = filteredQueryLogs.filter((log) => log.status === 'ANSWERED').length;
    const notFound = filteredQueryLogs.filter((log) => log.status === 'NOT_FOUND').length;
    const avgConfidence =
      totalQueries === 0
        ? 0
        : Math.round(
            (filteredQueryLogs.reduce((sum, log) => sum + log.confidenceScore, 0) / totalQueries) *
              100
          );
    const avgResponseTime =
      totalQueries === 0
        ? '0.0'
        : (
            filteredQueryLogs.reduce(
              (sum, log) => sum + Number(log.responseTime.replace('s', '')),
              0
            ) / totalQueries
          ).toFixed(1);

    return [
      { label: 'Total Queries', value: totalQueries.toString(), helper: `Pertanyaan pada periode ${queryRangeLabels[queryRange]}`, icon: 'manage_search', tone: 'text-primary' },
      { label: 'Answered', value: answered.toString(), helper: 'Query berhasil dijawab dengan sumber', icon: 'check_circle', tone: 'text-emerald-400' },
      { label: 'Not Found', value: notFound.toString(), helper: 'Tidak ada konteks relevan', icon: 'error', tone: 'text-error' },
      { label: 'Avg Confidence', value: `${avgConfidence}%`, helper: 'Rata-rata keyakinan jawaban', icon: 'verified', tone: 'text-primary' },
      { label: 'Avg Response', value: `${avgResponseTime}s`, helper: 'Rata-rata waktu respons sistem', icon: 'speed', tone: 'text-tertiary' },
    ];
  }, [filteredQueryLogs, queryRange]);

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
                Halaman ini menampilkan riwayat pertanyaan, dokumen yang diambil sistem, skor keyakinan, status jawaban, dan jawaban yang dihasilkan sistem.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">

              <div className="flex items-center gap-2 px-3 py-2 bg-primary/10 text-primary border border-primary/20 rounded-full font-mono text-[10px] md:text-xs w-fit">
                <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                Live Query Trace
              </div>
            </div>
          </div>

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
                  Live
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
                      {paginatedQueryLogs.length > 0 ? (
                        paginatedQueryLogs.map((log) => (
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
                            {log.timestamp.split(' ')[1]}
                          </td>
                          <td className="px-4 py-4 text-on-surface max-w-[280px]">
                            <span className="block truncate">"{log.userQuestion}"</span>
                            <span className="block text-outline text-[10px] mt-1">{log.queryId}</span>
                          </td>
                          <td className="px-4 py-4 text-on-surface-variant whitespace-nowrap">
                            {log.retrievedDocuments.length > 0
                              ? `${log.retrievedDocuments.length} sources`
                              : 'No source'}
                          </td>
                          <td className="px-4 py-4 whitespace-nowrap">
                            <span className="text-primary font-semibold">
                              {Math.round(log.confidenceScore * 100)}%
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
                            No query logs found for this period.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-3 px-3 py-3 bg-[#0b0d13] border border-outline-variant/50 rounded-xl">
                  <p className="font-mono text-[10px] md:text-xs text-outline">
                    Showing {queryStartNumber}-{queryEndNumber} of {filteredQueryLogs.length} chats
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
                  <div className="flex items-start justify-between gap-3 mb-4">
                    <div>
                      <p className="font-mono text-[10px] text-outline uppercase tracking-wider mb-1">
                        Selected Log
                      </p>
                      <h3 className="font-headline text-lg font-bold text-on-surface">
                        {selectedLog.queryId}
                      </h3>
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
                            style={{ width: `${selectedLog.confidenceScore * 100}%` }}
                          />
                        </div>
                        <span className="font-mono text-xs text-primary">
                          {Math.round(selectedLog.confidenceScore * 100)}%
                        </span>
                      </div>
                    </div>

                  </div>

                  <div className="space-y-3">
                    <div className="bg-[#0b0d13] border border-outline-variant/50 rounded-lg p-3">
                      <p className="text-outline font-mono text-[10px] uppercase mb-2">User Question</p>
                      <p className="text-sm text-on-surface leading-relaxed">"{selectedLog.userQuestion}"</p>
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
                                  {source.page} • {source.chunkId}
                                </p>
                              </div>
                              <span className="font-mono text-xs text-primary whitespace-nowrap">
                                {Math.round(source.relevanceScore * 100)}%
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
                      <p className="text-sm text-on-surface-variant leading-relaxed">{selectedLog.answerGenerated}</p>
                    </div>

                  </div>
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
                    Ringkasan performa sistem berdasarkan status log, confidence score, dan response time.
                  </p>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-end gap-3">
                  {rangeDropdown}

                  <span className="font-mono text-[10px] md:text-xs px-2 md:px-3 py-1 bg-primary/10 text-primary border border-primary/20 rounded-full w-fit sm:mb-1.5">
                    System Health
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
