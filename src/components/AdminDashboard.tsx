import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { AdminSidebar } from './AdminSidebar';
import { AdminHeader } from './AdminHeader';

type DocumentType = 'PDF' | 'DOCX' | 'TXT';

interface RepositoryDocument {
  id: string;
  filename: string;
  type: DocumentType;
  size: string;
  uploadDate: string;
  chunks: number;
  indexedStatus: 'Indexed' | 'Re-indexed' | 'Pending';
}

type ChatRange = 'daily' | 'weekly' | 'monthly' | 'yearly';

interface ChatMetricPoint {
  label: string;
  totalChats: number;
  uniqueUsers: number;
}

const chatAnalyticsData: Record<ChatRange, ChatMetricPoint[]> = {
  daily: [
    { label: '08:00', totalChats: 18, uniqueUsers: 7 },
    { label: '10:00', totalChats: 34, uniqueUsers: 13 },
    { label: '12:00', totalChats: 27, uniqueUsers: 11 },
    { label: '14:00', totalChats: 46, uniqueUsers: 18 },
    { label: '16:00', totalChats: 39, uniqueUsers: 16 },
    { label: '18:00', totalChats: 24, uniqueUsers: 9 },
  ],
  weekly: [
    { label: 'Mon', totalChats: 92, uniqueUsers: 31 },
    { label: 'Tue', totalChats: 128, uniqueUsers: 42 },
    { label: 'Wed', totalChats: 104, uniqueUsers: 38 },
    { label: 'Thu', totalChats: 156, uniqueUsers: 51 },
    { label: 'Fri', totalChats: 141, uniqueUsers: 47 },
    { label: 'Sat', totalChats: 76, uniqueUsers: 26 },
    { label: 'Sun', totalChats: 61, uniqueUsers: 19 },
  ],
  monthly: [
    { label: 'Week 1', totalChats: 426, uniqueUsers: 132 },
    { label: 'Week 2', totalChats: 518, uniqueUsers: 157 },
    { label: 'Week 3', totalChats: 472, uniqueUsers: 146 },
    { label: 'Week 4', totalChats: 603, uniqueUsers: 181 },
  ],
  yearly: [
    { label: 'Jan', totalChats: 1680, uniqueUsers: 412 },
    { label: 'Feb', totalChats: 1845, uniqueUsers: 438 },
    { label: 'Mar', totalChats: 2130, uniqueUsers: 501 },
    { label: 'Apr', totalChats: 2388, uniqueUsers: 544 },
    { label: 'May', totalChats: 2514, uniqueUsers: 587 },
    { label: 'Jun', totalChats: 2760, uniqueUsers: 621 },
  ],
};

const rangeLabels: Record<ChatRange, string> = {
  daily: 'Harian',
  weekly: 'Mingguan',
  monthly: 'Bulanan',
  yearly: 'Tahunan',
};

const repositoryDocuments: RepositoryDocument[] = [
  {
    id: 'DOC-001',
    filename: 'Employee_Handbook_2024.pdf',
    type: 'PDF',
    size: '2.4 MB',
    uploadDate: 'Oct 12, 2023',
    chunks: 124,
    indexedStatus: 'Indexed',
  },
  {
    id: 'DOC-002',
    filename: 'SOP_Claim_Medical.pdf',
    type: 'PDF',
    size: '1.8 MB',
    uploadDate: 'Jan 18, 2026',
    chunks: 88,
    indexedStatus: 'Indexed',
  },
  {
    id: 'DOC-003',
    filename: 'Policy_WFH.pdf',
    type: 'PDF',
    size: '920 KB',
    uploadDate: 'Feb 04, 2026',
    chunks: 36,
    indexedStatus: 'Re-indexed',
  },
  {
    id: 'DOC-004',
    filename: 'Finance_Report_Template_2026.docx',
    type: 'DOCX',
    size: '640 KB',
    uploadDate: 'Mar 11, 2026',
    chunks: 21,
    indexedStatus: 'Indexed',
  },
  {
    id: 'DOC-005',
    filename: 'FAQ_IT_Support.txt',
    type: 'TXT',
    size: '180 KB',
    uploadDate: 'Apr 02, 2026',
    chunks: 14,
    indexedStatus: 'Pending',
  },
  {
    id: 'DOC-006',
    filename: 'SOP_Onboarding.pdf',
    type: 'PDF',
    size: '1.1 MB',
    uploadDate: 'Apr 11, 2026',
    chunks: 42,
    indexedStatus: 'Indexed',
  },
  {
    id: 'DOC-007',
    filename: 'Policy_Employee_Benefit.pdf',
    type: 'PDF',
    size: '1.5 MB',
    uploadDate: 'Apr 19, 2026',
    chunks: 64,
    indexedStatus: 'Indexed',
  },
  {
    id: 'DOC-008',
    filename: 'IT_Helpdesk_Guide.docx',
    type: 'DOCX',
    size: '720 KB',
    uploadDate: 'May 03, 2026',
    chunks: 29,
    indexedStatus: 'Re-indexed',
  },
  {
    id: 'DOC-009',
    filename: 'Security_Access_FAQ.txt',
    type: 'TXT',
    size: '210 KB',
    uploadDate: 'May 12, 2026',
    chunks: 18,
    indexedStatus: 'Indexed',
  },
  {
    id: 'DOC-010',
    filename: 'Operational_Report_Q2.pdf',
    type: 'PDF',
    size: '3.2 MB',
    uploadDate: 'Jun 01, 2026',
    chunks: 156,
    indexedStatus: 'Indexed',
  },
  {
    id: 'DOC-011',
    filename: 'HR_Leave_Policy.docx',
    type: 'DOCX',
    size: '590 KB',
    uploadDate: 'Jun 10, 2026',
    chunks: 24,
    indexedStatus: 'Pending',
  },
  {
    id: 'DOC-012',
    filename: 'Company_Profile.pdf',
    type: 'PDF',
    size: '840 KB',
    uploadDate: 'Jun 18, 2026',
    chunks: 33,
    indexedStatus: 'Indexed',
  },
];

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


export const AdminDashboard: React.FC = () => {
  // State untuk Navigasi Mobile
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [documentSearch, setDocumentSearch] = useState('');
  const [chatRange, setChatRange] = useState<ChatRange>('daily');
  const [documentPage, setDocumentPage] = useState(1);

  const currentChatData = chatAnalyticsData[chatRange];

  const chatChartMax = Math.max(...currentChatData.map((item) => item.totalChats), 1);

  const totalChatCount = currentChatData.reduce((sum, item) => sum + item.totalChats, 0);

  const totalUniqueUsers = currentChatData.reduce((sum, item) => sum + item.uniqueUsers, 0);

  const averageChatCount = Math.round(totalChatCount / currentChatData.length);

  const peakChatPoint = currentChatData.reduce((maxItem, item) =>
    item.totalChats > maxItem.totalChats ? item : maxItem
  );

  const filteredDocuments = useMemo(() => {
    const keyword = documentSearch.trim().toLowerCase();

    if (!keyword) return repositoryDocuments;

    return repositoryDocuments.filter((doc) =>
      [doc.filename, doc.type, doc.uploadDate, doc.indexedStatus]
        .join(' ')
        .toLowerCase()
        .includes(keyword)
    );
  }, [documentSearch]);

  const documentsPerPage = 5;
  const totalDocumentPages = Math.max(Math.ceil(filteredDocuments.length / documentsPerPage), 1);
  const safeDocumentPage = Math.min(documentPage, totalDocumentPages);
  const paginatedDocuments = filteredDocuments.slice(
    (safeDocumentPage - 1) * documentsPerPage,
    safeDocumentPage * documentsPerPage
  );

  return (
    <div className="bg-background text-on-surface font-body overflow-hidden flex h-screen w-full relative">
      <AdminSidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      
      <main className="flex-1 flex flex-col h-full relative min-w-0">
        <AdminHeader onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

        <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-4 md:p-8 pb-12">
          {/* Bagian Statistik */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 md:gap-6 mb-6 md:mb-8">
            <div className="bg-surface-container-low border border-outline-variant p-4 md:p-6 rounded-2xl flex items-center justify-between group hover:border-primary transition-all shadow-sm">
              <div>
                <p className="text-outline font-mono text-[10px] md:text-xs uppercase tracking-wider mb-1 md:mb-2">Total Documents</p>
                <h3 className="font-headline text-2xl md:text-4xl font-bold text-on-surface">50</h3>
              </div>
              <div className="w-10 h-10 md:w-14 md:h-14 bg-primary/10 rounded-full flex items-center justify-center text-primary group-hover:scale-110 transition-transform">
                <span className="material-symbols-outlined text-2xl md:text-3xl">description</span>
              </div>
            </div>
            <div className="bg-surface-container-low border border-outline-variant p-4 md:p-6 rounded-2xl flex items-center justify-between group hover:border-secondary transition-all shadow-sm">
              <div>
                <p className="text-outline font-mono text-[10px] md:text-xs uppercase tracking-wider mb-1 md:mb-2">Total Chunks</p>
                <h3 className="font-headline text-2xl md:text-4xl font-bold text-on-surface">1,200</h3>
              </div>
              <div className="w-10 h-10 md:w-14 md:h-14 bg-secondary/10 rounded-full flex items-center justify-center text-secondary group-hover:scale-110 transition-transform">
                <span className="material-symbols-outlined text-2xl md:text-3xl">segment</span>
              </div>
            </div>
            <div className="bg-surface-container-low border border-outline-variant p-4 md:p-6 rounded-2xl flex items-center justify-between group hover:border-tertiary transition-all shadow-sm sm:col-span-2 md:col-span-1">
              <div>
                <p className="text-outline font-mono text-[10px] md:text-xs uppercase tracking-wider mb-1 md:mb-2">Avg Response</p>
                <h3 className="font-headline text-2xl md:text-4xl font-bold text-on-surface">2.1s</h3>
              </div>
              <div className="w-10 h-10 md:w-14 md:h-14 bg-tertiary/10 rounded-full flex items-center justify-center text-tertiary group-hover:scale-110 transition-transform">
                <span className="material-symbols-outlined text-2xl md:text-3xl">speed</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* User Chat Analytics */}
            <div className="lg:col-span-7 space-y-6">
              <section className="bg-surface-container-low border border-outline-variant rounded-2xl p-4 md:p-6 h-[340px] flex flex-col">
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-4">
                  <div>
                    <h2 className="font-headline text-lg md:text-xl font-bold">User Chat Analytics</h2>
                    <p className="text-outline text-xs md:text-sm mt-1">
                      Diagram jumlah chat user berdasarkan periode harian, mingguan, bulanan, dan tahunan.
                    </p>
                  </div>

                  <div className="w-full sm:w-[190px]">
                    <label className="block font-mono text-[10px] text-outline uppercase tracking-wider mb-1.5">
                      Periode
                    </label>

                    <div className="relative">
                      <select
                        value={chatRange}
                        onChange={(e) => setChatRange(e.target.value as ChatRange)}
                        className="w-full appearance-none bg-[#0b0d13] border border-outline-variant/50 rounded-xl py-2.5 pl-3 pr-10 font-mono text-xs md:text-sm text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/60 transition-all cursor-pointer"
                      >
                        {(Object.keys(rangeLabels) as ChatRange[]).map((range) => (
                          <option key={range} value={range} className="bg-[#0b0d13] text-on-surface">
                            {rangeLabels[range]}
                          </option>
                        ))}
                      </select>

                      <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-outline">
                        <span className="material-symbols-outlined text-[18px]">expand_more</span>
                      </span>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div className="bg-[#0b0d13] border border-outline-variant/50 rounded-xl p-3">
                    <p className="font-mono text-[9px] md:text-[10px] text-outline uppercase tracking-wider mb-1">Total Chat</p>
                    <p className="font-headline text-xl md:text-2xl font-bold text-on-surface">{totalChatCount.toLocaleString()}</p>
                  </div>

                  <div className="bg-[#0b0d13] border border-outline-variant/50 rounded-xl p-3">
                    <p className="font-mono text-[9px] md:text-[10px] text-outline uppercase tracking-wider mb-1">Unique Users</p>
                    <p className="font-headline text-xl md:text-2xl font-bold text-on-surface">{totalUniqueUsers.toLocaleString()}</p>
                  </div>

                  <div className="bg-[#0b0d13] border border-outline-variant/50 rounded-xl p-3">
                    <p className="font-mono text-[9px] md:text-[10px] text-outline uppercase tracking-wider mb-1">Avg Chat</p>
                    <p className="font-headline text-xl md:text-2xl font-bold text-on-surface">{averageChatCount.toLocaleString()}</p>
                  </div>
                </div>

                <div className="flex-1 min-h-0 bg-[#0b0d13] border border-outline-variant/50 rounded-xl p-4">
                  <div className="h-full flex items-end gap-2 md:gap-3">
                    {currentChatData.map((item) => {
                      const barHeight = Math.max((item.totalChats / chatChartMax) * 100, 8);

                      return (
                        <div key={item.label} className="flex-1 h-full flex flex-col items-center justify-end gap-2 group">
                          <div className="relative w-full flex-1 flex items-end justify-center">
                            <div
                              className="w-full max-w-[42px] rounded-t-xl bg-primary/80 hover:bg-primary transition-all shadow-[0_0_16px_rgba(77,142,255,0.18)]"
                              style={{ height: `${barHeight}%` }}
                              title={`${item.label}: ${item.totalChats} chats, ${item.uniqueUsers} users`}
                            />

                            <div className="absolute -top-2 translate-y-[-100%] hidden group-hover:block bg-surface-container-high border border-outline-variant rounded-lg px-2 py-1 shadow-lg whitespace-nowrap z-10">
                              <p className="font-mono text-[10px] text-on-surface">{item.totalChats} chats</p>
                              <p className="font-mono text-[10px] text-outline">{item.uniqueUsers} users</p>
                            </div>
                          </div>

                          <div className="text-center">
                            <p className="font-mono text-[10px] md:text-xs text-on-surface-variant">{item.label}</p>
                            <p className="font-mono text-[9px] text-primary">{item.totalChats}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-between gap-3 text-[10px] md:text-xs font-mono text-outline">
                  <span>Peak: <span className="text-primary">{peakChatPoint.label}</span> dengan {peakChatPoint.totalChats.toLocaleString()} chat</span>
                  <span className="hidden sm:inline">Metric: total user messages</span>
                </div>
              </section>
            </div>

            {/* Live Query Logs */}
            <div className="lg:col-span-5">
              <section className="bg-surface-container-low border border-outline-variant rounded-2xl p-4 md:p-6 flex flex-col h-[340px]">
                
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2 md:gap-3">
                    <h2 className="font-headline text-base md:text-lg font-bold">Live Query Logs</h2>
                    
                    {/* Ikon Redirect ke Detail Page */}
                    <Link
                      to="/admin/logs"
                      className="p-1 md:p-1.5 text-outline hover:text-primary transition-colors flex items-center justify-center rounded-md hover:bg-surface-variant border border-transparent hover:border-outline-variant/50 group"
                      title="Buka Detail Logs"
                    >
                      <span className="material-symbols-outlined text-[16px] md:text-[18px] group-hover:scale-110 transition-transform">open_in_new</span>
                    </Link>
                  </div>

                  <span className="flex items-center gap-1.5 px-2 py-1 bg-emerald-500/10 text-emerald-400 text-[10px] md:text-xs rounded-md border border-emerald-500/20 font-mono">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    Live
                  </span>
                </div>
                
                <div className="flex-1 overflow-y-auto custom-scrollbar bg-[#0b0d13] border border-outline-variant/50 rounded-xl p-3 md:p-4 font-mono text-[11px] md:text-[13px] space-y-4">
                  <div className="flex flex-col gap-1.5 border-b border-outline-variant/30 pb-3">
                    <div className="flex justify-between items-start">
                      <span className="text-on-surface-variant">10:45:22 AM - <span className="text-primary font-semibold">Staff User</span></span>
                      <span className="text-emerald-400">200 OK</span>
                    </div>
                    <span className="text-on-surface break-words">"Bagaimana prosedur klaim medis rawat inap?"</span>
                    <span className="text-outline text-[10px] md:text-[11px] mt-1">↳ Fetched 3 chunks (1.2s)</span>
                  </div>
                  
                  <div className="flex flex-col gap-1.5 border-b border-outline-variant/30 pb-3">
                    <div className="flex justify-between items-start">
                      <span className="text-on-surface-variant">10:42:15 AM - <span className="text-primary font-semibold">Staff User</span></span>
                      <span className="text-emerald-400">200 OK</span>
                    </div>
                    <span className="text-on-surface break-words">"Template laporan keuangan bulan ini"</span>
                    <span className="text-outline text-[10px] md:text-[11px] mt-1">↳ Fetched 1 chunk (0.8s)</span>
                  </div>
                  
                  <div className="flex flex-col gap-1.5">
                    <div className="flex justify-between items-start">
                      <span className="text-on-surface-variant">10:35:01 AM - <span className="text-error font-semibold">System Admin</span></span>
                      <span className="text-error">404 NOT_FOUND</span>
                    </div>
                    <span className="text-on-surface break-words">"Siapa nama CEO perusahaan?"</span>
                    <span className="text-error/80 text-[10px] md:text-[11px] mt-1">↳ No relevant context found in vector DB.</span>
                  </div>
                </div>
              </section>
            </div>

            {/* Table Repository */}
            <div className="lg:col-span-12">
              <section className="bg-surface-container-low border border-outline-variant rounded-2xl overflow-hidden shadow-sm">
                <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-outline-variant bg-surface-container-high/30 px-4 md:px-6 py-4">
                  <div className="flex items-center gap-3">
                    <button className="px-4 py-2.5 font-mono text-xs md:text-sm text-primary border border-primary/20 bg-primary/10 rounded-full whitespace-nowrap flex items-center gap-2">
                      <span className="material-symbols-outlined text-[17px]">folder_managed</span>
                      Document Repository
                    </button>

                    <span className="hidden sm:inline-flex px-2.5 py-1 bg-surface-container-low border border-outline-variant rounded-full font-mono text-[10px] text-on-surface-variant">
                      {filteredDocuments.length} of {repositoryDocuments.length} files
                    </span>
                  </div>

                  <div className="w-full lg:w-[420px]">
                    <div className="relative group">
                      <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-outline group-focus-within:text-primary transition-colors">
                        <span className="material-symbols-outlined text-[19px]">search</span>
                      </span>

                      <input
                        type="text"
                        value={documentSearch}
                        onChange={(e) => { setDocumentSearch(e.target.value); setDocumentPage(1); }}
                        className="w-full bg-[#0b0d13] border border-outline-variant rounded-xl py-2.5 pl-10 pr-10 text-sm text-on-surface placeholder:text-outline focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/60 transition-all shadow-inner"
                        placeholder="Search by filename, type, date, or status..."
                      />

                      {documentSearch && (
                        <button
                          type="button"
                          onClick={() => { setDocumentSearch(''); setDocumentPage(1); }}
                          className="absolute inset-y-0 right-0 pr-3 flex items-center text-outline hover:text-error transition-colors"
                          title="Clear search"
                        >
                          <span className="material-symbols-outlined text-[18px]">close</span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                <div className="overflow-x-auto custom-scrollbar">
                  <table className="w-full text-left border-collapse min-w-[680px]">
                    <thead className="bg-surface-container-high/50 text-outline font-mono text-[10px] md:text-xs uppercase tracking-wider">
                      <tr>
                        <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Filename</th>
                        <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Type</th>
                        <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Chunks</th>
                        <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Size</th>
                        <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Upload Date</th>
                        <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Status</th>
                      </tr>
                    </thead>

                    <tbody className="divide-y divide-outline-variant/30 text-[13px] md:text-sm">
                      {filteredDocuments.length > 0 ? (
                        paginatedDocuments.map((doc) => (
                          <tr key={doc.id} className="hover:bg-surface-container-high/50 transition-colors group">
                            <td className="px-4 md:px-6 py-3 md:py-4">
                              <div className="flex items-center gap-2 md:gap-3">
                                <span className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${getDocumentIconStyle(doc.type)}`}>
                                  <span className="material-symbols-outlined text-[19px] md:text-[22px]">{getDocumentIcon(doc.type)}</span>
                                </span>

                                <div className="min-w-0">
                                  <span className="font-medium text-on-surface truncate block max-w-[180px] md:max-w-[320px]">
                                    {doc.filename}
                                  </span>
                                  <span className="font-mono text-[10px] text-outline">{doc.id}</span>
                                </div>
                              </div>
                            </td>

                            <td className="px-4 md:px-6 py-3 md:py-4 text-on-surface-variant whitespace-nowrap font-mono">
                              {doc.type}
                            </td>

                            <td className="px-4 md:px-6 py-3 md:py-4 text-on-surface-variant whitespace-nowrap">
                              {doc.chunks}
                            </td>

                            <td className="px-4 md:px-6 py-3 md:py-4 text-on-surface-variant whitespace-nowrap">
                              {doc.size}
                            </td>

                            <td className="px-4 md:px-6 py-3 md:py-4 text-on-surface-variant whitespace-nowrap">
                              {doc.uploadDate}
                            </td>

                            <td className="px-4 md:px-6 py-3 md:py-4 whitespace-nowrap">
                              <span className={`px-2 py-1 rounded-md border font-mono text-[10px] ${getIndexedStatusStyle(doc.indexedStatus)}`}>
                                {doc.indexedStatus}
                              </span>
                            </td>

                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={6} className="px-4 md:px-6 py-10 text-center">
                            <div className="flex flex-col items-center justify-center gap-2 text-on-surface-variant">
                              <span className="material-symbols-outlined text-4xl text-outline">search_off</span>
                              <p className="font-semibold text-on-surface">No document found</p>
                              <p className="text-sm text-outline">
                                Try another filename, document type, date, or indexed status.
                              </p>
                            </div>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 md:px-6 py-4 border-t border-outline-variant bg-surface-container-high/20">
                  <p className="font-mono text-[10px] md:text-xs text-outline">
                    Showing {filteredDocuments.length === 0 ? 0 : (safeDocumentPage - 1) * documentsPerPage + 1}
                    -{Math.min(safeDocumentPage * documentsPerPage, filteredDocuments.length)} of {filteredDocuments.length} files
                  </p>

                  {totalDocumentPages > 1 && (
                    <div className="flex items-center gap-2">
                      {Array.from({ length: totalDocumentPages }, (_, index) => index + 1).map((page) => (
                        <button
                          key={page}
                          type="button"
                          onClick={() => setDocumentPage(page)}
                          className={`w-8 h-8 rounded-lg border font-mono text-xs transition-all ${
                            safeDocumentPage === page
                              ? 'bg-primary text-on-primary-container border-primary'
                              : 'bg-[#0b0d13] text-on-surface-variant border-outline-variant/50 hover:text-primary hover:border-primary/50'
                          }`}
                        >
                          {page}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};