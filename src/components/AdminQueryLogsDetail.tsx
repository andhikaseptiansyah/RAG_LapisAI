import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminSidebar } from './AdminSidebar';
import { AdminHeader } from './AdminHeader';

type QueryLogStatus = 'ANSWERED' | 'NEED_REVIEW' | 'NOT_FOUND' | 'ERROR';
type UserFeedback = 'Helpful' | 'Not Helpful' | 'No Feedback';

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
  userFeedback: UserFeedback;
  status: QueryLogStatus;
  reviewNote: string;
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
    userFeedback: 'Helpful',
    status: 'ANSWERED',
    reviewNote: 'Jawaban sudah memiliki sumber yang cukup dan halaman referensi jelas.',
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
    userFeedback: 'No Feedback',
    status: 'ANSWERED',
    reviewNote: 'Sistem mengambil satu dokumen dengan skor relevansi tinggi.',
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
    userFeedback: 'Not Helpful',
    status: 'NOT_FOUND',
    reviewNote: 'Tidak ada konteks relevan di vector database. Dokumen profil perusahaan perlu ditambahkan.',
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
    userFeedback: 'No Feedback',
    status: 'NEED_REVIEW',
    reviewNote: 'Jawaban menggunakan dua dokumen berbeda. Admin perlu memastikan aturan probation dan WFH tidak bertentangan.',
  },
];


const getPriorityStyle = (priority: 'High' | 'Medium' | 'Low') => {
  switch (priority) {
    case 'High':
      return 'bg-error-container/20 text-error border-error/30';
    case 'Medium':
      return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    case 'Low':
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    default:
      return 'bg-surface-variant text-on-surface-variant border-outline-variant';
  }
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

const getFeedbackStyle = (feedback: UserFeedback) => {
  switch (feedback) {
    case 'Helpful':
      return 'text-emerald-400';
    case 'Not Helpful':
      return 'text-error';
    default:
      return 'text-outline';
  }
};

export const AdminQueryLogsDetail: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedQueryId, setSelectedQueryId] = useState(queryLogs[0].queryId);

  const selectedLog = useMemo(
    () => queryLogs.find((log) => log.queryId === selectedQueryId) ?? queryLogs[0],
    [selectedQueryId]
  );

  const performanceSummary = useMemo(() => {
    const totalQueries = queryLogs.length;
    const answered = queryLogs.filter((log) => log.status === 'ANSWERED').length;
    const needReview = queryLogs.filter((log) => log.status === 'NEED_REVIEW').length;
    const notFound = queryLogs.filter((log) => log.status === 'NOT_FOUND').length;
    const avgConfidence = Math.round(
      (queryLogs.reduce((sum, log) => sum + log.confidenceScore, 0) / totalQueries) * 100
    );
    const avgResponseTime = (
      queryLogs.reduce((sum, log) => sum + Number(log.responseTime.replace('s', '')), 0) / totalQueries
    ).toFixed(1);

    return [
      { label: 'Total Queries', value: totalQueries.toString(), helper: 'Pertanyaan yang masuk ke sistem', icon: 'manage_search', tone: 'text-primary' },
      { label: 'Answered', value: answered.toString(), helper: 'Query berhasil dijawab dengan sumber', icon: 'check_circle', tone: 'text-emerald-400' },
      { label: 'Need Review', value: needReview.toString(), helper: 'Jawaban perlu dicek admin', icon: 'rate_review', tone: 'text-amber-400' },
      { label: 'Not Found', value: notFound.toString(), helper: 'Tidak ada konteks relevan', icon: 'error', tone: 'text-error' },
      { label: 'Avg Confidence', value: `${avgConfidence}%`, helper: 'Rata-rata keyakinan jawaban', icon: 'verified', tone: 'text-primary' },
      { label: 'Avg Response', value: `${avgResponseTime}s`, helper: 'Rata-rata waktu respons sistem', icon: 'speed', tone: 'text-tertiary' },
    ];
  }, []);

  const knowledgeGaps = useMemo(() => {
    return [
      {
        topic: 'Company leadership data',
        triggeredBy: 'Siapa nama CEO perusahaan?',
        rootCause: 'Dokumen profil perusahaan belum tersedia di vector database.',
        suggestedDocument: 'Company_Profile.pdf atau Organization_Structure.pdf',
        priority: 'High' as const,
      },
      {
        topic: 'WFH policy for new employees',
        triggeredBy: 'Apa kebijakan work from home untuk karyawan baru?',
        rootCause: 'Sistem mengambil dua dokumen dengan konteks berbeda sehingga jawaban perlu validasi.',
        suggestedDocument: 'HR_WFH_Probation_Guide.pdf',
        priority: 'Medium' as const,
      },
      {
        topic: 'Finance reporting template coverage',
        triggeredBy: 'Template laporan keuangan bulan ini',
        rootCause: 'Sistem hanya menemukan satu sumber. Perlu dipastikan template terbaru sudah diunggah.',
        suggestedDocument: 'Finance_Template_Index_2026.xlsx atau Monthly_Report_Guide.pdf',
        priority: 'Low' as const,
      },
    ];
  }, []);

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
                Halaman ini menampilkan riwayat pertanyaan, dokumen yang diambil sistem, skor keyakinan, status jawaban, dan catatan review admin.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Link
                to="/admin"
                className="inline-flex items-center gap-2 px-3 py-2 bg-surface-container-low border border-outline-variant rounded-full text-on-surface-variant hover:text-primary hover:border-primary/50 hover:bg-primary/5 transition-all font-mono text-[10px] md:text-xs"
                title="Kembali ke Admin Dashboard"
              >
                <span className="material-symbols-outlined text-[16px] md:text-[18px]">arrow_back</span>
                Back to Dashboard
              </Link>

              <div className="flex items-center gap-2 px-3 py-2 bg-primary/10 text-primary border border-primary/20 rounded-full font-mono text-[10px] md:text-xs w-fit">
                <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                Live Query Trace
              </div>
            </div>
          </div>

          <section className="h-auto lg:h-[50vh] min-h-[520px] bg-surface-container-low border border-outline-variant rounded-2xl p-4 md:p-6 shadow-sm mb-6 flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="font-headline text-lg md:text-xl font-bold">Query Logs</h2>
                <p className="text-outline text-xs md:text-sm mt-1">
                  Klik salah satu log untuk melihat detail lengkapnya.
                </p>
              </div>

              <span className="flex items-center gap-1.5 px-2 py-1 bg-emerald-500/10 text-emerald-400 text-[10px] md:text-xs rounded-md border border-emerald-500/20 font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                Live
              </span>
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
                      {queryLogs.map((log) => (
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
                      ))}
                    </tbody>
                  </table>
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

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
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

                    <div className="bg-[#0b0d13] border border-outline-variant/50 rounded-lg p-3">
                      <p className="text-outline font-mono text-[10px] uppercase mb-1">Feedback</p>
                      <p className={`text-sm font-semibold ${getFeedbackStyle(selectedLog.userFeedback)}`}>
                        {selectedLog.userFeedback}
                      </p>
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

                    <div className="bg-[#0b0d13] border border-outline-variant/50 rounded-lg p-3">
                      <p className="text-outline font-mono text-[10px] uppercase mb-2">Admin Review Note</p>
                      <p className="text-sm text-on-surface-variant leading-relaxed">{selectedLog.reviewNote}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <div className="grid grid-cols-1 2xl:grid-cols-12 gap-6">
            <section className="2xl:col-span-5 bg-surface-container-low border border-outline-variant rounded-2xl p-4 md:p-6 shadow-sm">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-5">
                <div>
                  <h2 className="font-headline text-lg md:text-xl font-bold">Query Performance Summary</h2>
                  <p className="text-outline text-sm mt-1">
                    Ringkasan performa sistem berdasarkan status log, confidence score, dan response time.
                  </p>
                </div>

                <span className="font-mono text-[10px] md:text-xs px-2 md:px-3 py-1 bg-primary/10 text-primary border border-primary/20 rounded-full w-fit">
                  System Health
                </span>
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
                  <h2 className="font-headline text-lg md:text-xl font-bold">Knowledge Gap Detection</h2>
                  <p className="text-outline text-sm mt-1">
                    Daftar celah pengetahuan yang perlu diperbaiki dengan upload dokumen baru atau validasi sumber.
                  </p>
                </div>

                <span className="font-mono text-[10px] md:text-xs px-2 md:px-3 py-1 bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded-full w-fit">
                  Action Required
                </span>
              </div>

              <div className="overflow-x-auto custom-scrollbar bg-[#0b0d13] border border-outline-variant/50 rounded-xl">
                <table className="w-full text-left border-collapse min-w-[780px]">
                  <thead className="text-outline font-mono text-[10px] md:text-xs uppercase tracking-wider border-b border-outline-variant/40">
                    <tr>
                      <th className="px-4 py-3 font-medium">Missing Topic</th>
                      <th className="px-4 py-3 font-medium">Triggered By</th>
                      <th className="px-4 py-3 font-medium">Root Cause</th>
                      <th className="px-4 py-3 font-medium">Suggested Document</th>
                      <th className="px-4 py-3 font-medium">Priority</th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-outline-variant/30 text-[12px] md:text-sm">
                    {knowledgeGaps.map((gap) => (
                      <tr key={gap.topic} className="hover:bg-surface-container-high/30 transition-colors">
                        <td className="px-4 py-4 text-on-surface font-medium max-w-[180px]">
                          {gap.topic}
                        </td>
                        <td className="px-4 py-4 text-on-surface-variant max-w-[220px]">
                          "{gap.triggeredBy}"
                        </td>
                        <td className="px-4 py-4 text-on-surface-variant max-w-[260px]">
                          {gap.rootCause}
                        </td>
                        <td className="px-4 py-4 text-primary font-mono text-[11px] max-w-[220px]">
                          {gap.suggestedDocument}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <span className={`px-2 py-1 rounded-md border text-[10px] font-mono ${getPriorityStyle(gap.priority)}`}>
                            {gap.priority}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
};
