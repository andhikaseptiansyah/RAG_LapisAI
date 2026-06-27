import React, { useMemo, useState, useRef } from 'react';
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

  // State Dropzone
  const [isDragOver, setIsDragOver] = useState(false);
  const [showWarning, setShowWarning] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragOver(true); };
  const handleDragLeave = () => setIsDragOver(false);
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    setShowWarning(true);
    setTimeout(() => setShowWarning(false), 4000);
  };

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
            {/* Dropzone Upload */}
            <div className="lg:col-span-7 space-y-6">
              <section className="bg-surface-container-low border border-outline-variant rounded-2xl p-4 md:p-6 h-full flex flex-col">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 md:mb-6 gap-3">
                  <h2 className="font-headline text-lg md:text-xl font-bold">Ingest Knowledge</h2>
                  <span className="font-mono text-[10px] md:text-xs px-2 md:px-3 py-1 bg-primary/10 text-primary border border-primary/20 rounded-full flex items-center gap-2 w-fit">
                    <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span> Vector Sync Active
                  </span>
                </div>
                
                <input type="file" ref={fileInputRef} className="hidden" multiple accept=".pdf,.txt,.docx" />
                <div 
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  className={`flex-1 flex flex-col items-center justify-center border-2 border-dashed border-outline-variant hover:border-primary hover:bg-primary/5 transition-all rounded-xl p-6 md:p-10 text-center cursor-pointer group ${isDragOver ? 'border-primary bg-primary/5' : ''}`}
                >
                  <span className="material-symbols-outlined text-4xl md:text-5xl text-outline mb-3 md:mb-4 group-hover:text-primary transition-colors">cloud_upload</span>
                  <p className="text-sm md:text-base text-on-surface mb-2">Drag & drop files here or <span className="text-primary font-semibold">Browse</span></p>
                  <p className="text-outline text-xs md:text-sm">PDF, TXT, DOCX (Max 25MB)</p>
                </div>

                {showWarning && (
                  <div className="mt-4 p-4 bg-error-container/20 border border-error/30 rounded-lg flex items-center gap-3 animate-fadeIn">
                    <span className="material-symbols-outlined text-error">warning</span>
                    <p className="text-error text-sm">Warning: Duplicate file detected. System will re-index existing chunks.</p>
                  </div>
                )}
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
                        onChange={(e) => setDocumentSearch(e.target.value)}
                        className="w-full bg-[#0b0d13] border border-outline-variant rounded-xl py-2.5 pl-10 pr-10 text-sm text-on-surface placeholder:text-outline focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/60 transition-all shadow-inner"
                        placeholder="Search by filename, type, date, or status..."
                      />

                      {documentSearch && (
                        <button
                          type="button"
                          onClick={() => setDocumentSearch('')}
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
                  <table className="w-full text-left border-collapse min-w-[760px]">
                    <thead className="bg-surface-container-high/50 text-outline font-mono text-[10px] md:text-xs uppercase tracking-wider">
                      <tr>
                        <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Filename</th>
                        <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Type</th>
                        <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Chunks</th>
                        <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Size</th>
                        <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Upload Date</th>
                        <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Status</th>
                        <th className="px-4 md:px-6 py-3 md:py-4 font-medium text-right">Action</th>
                      </tr>
                    </thead>

                    <tbody className="divide-y divide-outline-variant/30 text-[13px] md:text-sm">
                      {filteredDocuments.length > 0 ? (
                        filteredDocuments.map((doc) => (
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

                            <td className="px-4 md:px-6 py-3 md:py-4 text-right">
                              <div className="flex items-center justify-end gap-1 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
                                <button className="text-outline hover:text-primary transition-colors p-1.5 md:p-2 rounded-lg hover:bg-primary/10" title="View document detail">
                                  <span className="material-symbols-outlined text-[18px] md:text-[20px]">visibility</span>
                                </button>

                                <button className="text-outline hover:text-error transition-colors p-1.5 md:p-2 rounded-lg hover:bg-error/10" title="Delete document">
                                  <span className="material-symbols-outlined text-[18px] md:text-[20px]">delete</span>
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={7} className="px-4 md:px-6 py-10 text-center">
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
              </section>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};