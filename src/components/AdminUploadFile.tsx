import React, { useRef, useState } from 'react';
import { AdminSidebar } from './AdminSidebar';
import { AdminHeader } from './AdminHeader';
import { useDocuments } from '../hooks/useDocuments';
import type {
  DocumentType,
  TrainedDocument,
  UploadItem,
  UploadStatus,
  VectorStatus,
} from '../services/documentService';

const maxFileSize = 25 * 1024 * 1024;
const acceptedExtensions = ['pdf', 'docx', 'txt'];

const getFileExtension = (filename: string) => {
  return filename.split('.').pop()?.toLowerCase() ?? '';
};

const formatDateTime = (value: string) => {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString([], {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
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

const getUploadStatusStyle = (status: UploadStatus) => {
  switch (status) {
    case 'Ready':
      return 'bg-surface-variant text-on-surface-variant border-outline-variant';
    case 'Parsing':
      return 'bg-primary/10 text-primary border-primary/20';
    case 'Chunking':
      return 'bg-secondary/10 text-secondary border-secondary/20';
    case 'Embedding':
      return 'bg-tertiary/10 text-tertiary border-tertiary/20';
    case 'Indexed':
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    case 'Rejected':
    case 'Failed':
      return 'bg-error-container/20 text-error border-error/30';
    default:
      return 'bg-surface-variant text-on-surface-variant border-outline-variant';
  }
};

const getVectorStatusStyle = (status: VectorStatus) => {
  switch (status) {
    case 'Active':
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    case 'Removed':
      return 'bg-error-container/20 text-error border-error/30';
    case 'Pending':
    default:
      return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
  }
};

const isProcessable = (item: UploadItem) => {
  return item.status === 'Ready' || item.status === 'Failed';
};

export const AdminUploadFile: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [warningMessage, setWarningMessage] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    uploadItems,
    trainedDocuments,
    isLoading,
    isUploading,
    isIndexing,
    error,
    clearError,
    uploadFiles,
    startIndexing,
    reindex,
    removeDocument,
    refreshAll,
  } = useDocuments({ initialLimit: 8 });

  const totalFiles = uploadItems.length;
  const indexedFiles = uploadItems.filter((item) => item.status === 'Indexed').length;
  const processingFiles = uploadItems.filter((item) =>
    ['Parsing', 'Chunking', 'Embedding'].includes(item.status)
  ).length;
  const failedFiles = uploadItems.filter((item) => ['Failed', 'Rejected'].includes(item.status)).length;
  const activeTrainedDocuments = trainedDocuments.filter((document) => document.vectorStatus === 'Active');

  const validateFiles = (files: File[]) => {
    const accepted: File[] = [];
    const rejected: string[] = [];

    for (const file of files) {
      const extension = getFileExtension(file.name);

      if (!acceptedExtensions.includes(extension)) {
        rejected.push(`${file.name}: hanya PDF, DOCX, dan TXT yang didukung.`);
        continue;
      }

      if (file.size > maxFileSize) {
        rejected.push(`${file.name}: ukuran maksimal 25 MB.`);
        continue;
      }

      accepted.push(file);
    }

    return { accepted, rejected };
  };

  const handleFiles = async (files: File[]) => {
    if (files.length === 0) return;

    const { accepted, rejected } = validateFiles(files);

    if (rejected.length > 0) {
      setWarningMessage(rejected.join(' '));
      window.setTimeout(() => setWarningMessage(''), 6000);
    }

    if (accepted.length === 0) return;

    const success = await uploadFiles(accepted);

    if (success) {
      await refreshAll();
    }
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    await handleFiles(Array.from(event.target.files ?? []));
    event.target.value = '';
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = async (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragOver(false);
    await handleFiles(Array.from(event.dataTransfer.files));
  };

  const handleStartAllIndexing = async () => {
    const documentIds = uploadItems
      .filter(isProcessable)
      .map((item) => item.id);

    const success = await startIndexing(documentIds.length > 0 ? documentIds : undefined);

    if (success) {
      await refreshAll();
    }
  };

  const handleStartOneIndexing = async (id: string) => {
    const success = await startIndexing([id]);

    if (success) {
      await refreshAll();
    }
  };

  const handleReindex = async (id: string) => {
    const success = await reindex(id);

    if (success) {
      await refreshAll();
    }
  };

  const handleRemove = async (id: string) => {
    if (!window.confirm('Hapus dokumen ini dari database dan admin panel?')) return;

    const success = await removeDocument(id);

    if (success) {
      await refreshAll();
    }
  };

  const renderUploadRow = (item: UploadItem) => (
    <tr key={item.id} className="border-b border-outline-variant/40 last:border-b-0">
      <td className="py-4 pr-4 min-w-[260px]">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${getDocumentIconStyle(item.type)}`}>
            <span className="material-symbols-outlined text-[22px]">{getDocumentIcon(item.type)}</span>
          </div>
          <div>
            <p className="text-sm font-semibold text-on-surface line-clamp-1">{item.filename}</p>
            <p className="text-xs text-outline font-mono">{item.type} · {item.size} · {formatDateTime(item.uploadedAt)}</p>
          </div>
        </div>
      </td>
      <td className="py-4 px-4">
        <span className={`inline-flex items-center px-2.5 py-1 rounded-full border font-mono text-[10px] ${getUploadStatusStyle(item.status)}`}>
          {item.status}
        </span>
      </td>
      <td className="py-4 px-4 min-w-[180px]">
        <div className="w-full h-2 rounded-full bg-surface-variant overflow-hidden">
          <div className="h-full bg-primary transition-all" style={{ width: `${item.progress}%` }} />
        </div>
        <p className="text-[10px] text-outline font-mono mt-1">{item.progress}% · {item.chunks} chunks</p>
      </td>
      <td className="py-4 px-4 text-xs text-on-surface-variant min-w-[260px]">{item.note}</td>
      <td className="py-4 pl-4">
        <div className="flex items-center justify-end gap-2">
          {item.status === 'Indexed' ? (
            <button
              type="button"
              onClick={() => void handleReindex(item.id)}
              disabled={isIndexing}
              className="px-3 py-1.5 rounded-lg border border-outline-variant text-xs text-on-surface-variant hover:text-primary hover:border-primary/50 disabled:opacity-50 transition-colors"
            >
              Re-index
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void handleStartOneIndexing(item.id)}
              disabled={isIndexing || item.status === 'Rejected'}
              className="px-3 py-1.5 rounded-lg bg-primary text-on-primary text-xs font-semibold disabled:opacity-50 transition-colors"
            >
              Index
            </button>
          )}
          <button
            type="button"
            onClick={() => void handleRemove(item.id)}
            className="w-8 h-8 rounded-lg border border-outline-variant text-outline hover:text-error hover:border-error/50 transition-colors flex items-center justify-center"
            aria-label={`Hapus ${item.filename}`}
          >
            <span className="material-symbols-outlined text-[18px]">delete</span>
          </button>
        </div>
      </td>
    </tr>
  );

  const renderTrainedDocument = (document: TrainedDocument) => (
    <div key={document.id} className="p-4 rounded-xl border border-outline-variant/60 bg-[#0b0d13] flex items-start justify-between gap-4">
      <div className="flex items-start gap-3 min-w-0">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${getDocumentIconStyle(document.type)}`}>
          <span className="material-symbols-outlined text-[22px]">{getDocumentIcon(document.type)}</span>
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-on-surface truncate">{document.filename}</p>
          <p className="text-xs text-outline font-mono mt-1">{document.size} · {document.chunks} chunks · {formatDateTime(document.indexedAt)}</p>
        </div>
      </div>
      <span className={`shrink-0 inline-flex items-center px-2.5 py-1 rounded-full border font-mono text-[10px] ${getVectorStatusStyle(document.vectorStatus)}`}>
        {document.vectorStatus}
      </span>
    </div>
  );

  return (
    <div className="bg-background text-on-surface font-body overflow-hidden flex h-screen w-full relative">
      <AdminSidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <main className="flex-1 flex flex-col h-full relative min-w-0">
        <AdminHeader onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

        <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-4 md:p-8 pb-12">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
            <div>
              <p className="font-mono text-[10px] md:text-xs uppercase tracking-wider text-outline mb-2">
                Python RAG Pipeline
              </p>
              <h1 className="font-headline text-2xl md:text-3xl font-bold text-on-surface">
                Upload & Index Knowledge Base
              </h1>
              <p className="text-on-surface-variant text-sm md:text-base mt-2 max-w-3xl">
                Upload dokumen ke database admin, lalu jalankan pipeline Python untuk parsing, chunking, embedding, dan simpan vector ke ChromaDB.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void refreshAll()}
                disabled={isLoading}
                className="px-4 py-2.5 rounded-xl border border-outline-variant text-sm text-on-surface-variant hover:text-primary hover:border-primary/50 disabled:opacity-50 transition-colors"
              >
                Refresh
              </button>
              <button
                type="button"
                onClick={handleStartAllIndexing}
                disabled={isIndexing || uploadItems.length === 0}
                className="px-4 py-2.5 rounded-xl bg-primary text-on-primary text-sm font-semibold disabled:opacity-50 transition-colors"
              >
                {isIndexing ? 'Indexing...' : 'Start Python Indexing'}
              </button>
            </div>
          </div>

          {(warningMessage || error) && (
            <div className="mb-6 p-4 rounded-xl border border-error/30 bg-error-container/20 text-error text-sm flex items-start justify-between gap-4">
              <span>{warningMessage || error}</span>
              {error && (
                <button type="button" onClick={clearError} className="text-xs underline">
                  Tutup
                </button>
              )}
            </div>
          )}

          <section className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {[
              { label: 'Total Upload', value: totalFiles, icon: 'folder_open' },
              { label: 'Indexed', value: indexedFiles, icon: 'check_circle' },
              { label: 'Processing', value: processingFiles, icon: 'sync' },
              { label: 'Failed', value: failedFiles, icon: 'error' },
            ].map((card) => (
              <div key={card.label} className="bg-surface-container-low border border-outline-variant rounded-2xl p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-outline font-mono uppercase tracking-wider">{card.label}</p>
                  <span className="material-symbols-outlined text-primary text-[22px]">{card.icon}</span>
                </div>
                <p className="text-2xl font-headline font-bold mt-3">{card.value}</p>
              </div>
            ))}
          </section>

          <section className="grid grid-cols-1 xl:grid-cols-[1.3fr_0.7fr] gap-6">
            <div className="space-y-6">
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={(event) => void handleDrop(event)}
                className={`border-2 border-dashed rounded-3xl p-8 md:p-10 bg-surface-container-low transition-all ${
                  isDragOver ? 'border-primary bg-primary/5' : 'border-outline-variant'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.docx,.txt"
                  onChange={(event) => void handleFileChange(event)}
                  className="hidden"
                />

                <div className="flex flex-col items-center text-center">
                  <div className="w-16 h-16 rounded-2xl bg-primary/10 text-primary flex items-center justify-center mb-4">
                    <span className="material-symbols-outlined text-[34px]">cloud_upload</span>
                  </div>
                  <h2 className="font-headline text-xl font-bold text-on-surface mb-2">
                    Drop PDF, DOCX, atau TXT di sini
                  </h2>
                  <p className="text-sm text-on-surface-variant max-w-xl mb-5">
                    File disimpan dulu ke database lewat backend. Setelah itu klik tombol indexing supaya Python service menjalankan pipeline RAG.
                  </p>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploading}
                    className="px-5 py-2.5 rounded-xl bg-primary text-on-primary text-sm font-semibold disabled:opacity-50 transition-colors"
                  >
                    {isUploading ? 'Uploading...' : 'Choose Files'}
                  </button>
                </div>
              </div>

              <div className="bg-surface-container-low border border-outline-variant rounded-2xl overflow-hidden">
                <div className="p-4 md:p-5 border-b border-outline-variant flex items-center justify-between gap-3">
                  <div>
                    <h2 className="font-headline text-lg font-bold">Upload Queue dari Database</h2>
                    <p className="text-xs text-outline mt-1">Data ini diambil dari tabel documents, bukan dummy state.</p>
                  </div>
                  {isLoading && <span className="text-xs text-outline font-mono">Loading...</span>}
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead className="bg-[#0b0d13] text-outline text-[10px] uppercase tracking-wider font-mono">
                      <tr>
                        <th className="py-3 px-4">Document</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4">Progress</th>
                        <th className="py-3 px-4">Pipeline Note</th>
                        <th className="py-3 px-4 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {uploadItems.length > 0 ? (
                        uploadItems.map(renderUploadRow)
                      ) : (
                        <tr>
                          <td colSpan={5} className="py-10 text-center text-sm text-outline">
                            Belum ada dokumen. Upload dulu, baru jalankan Python indexing.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <aside className="bg-surface-container-low border border-outline-variant rounded-2xl p-4 md:p-5 h-fit">
              <div className="flex items-center justify-between gap-3 mb-4">
                <div>
                  <h2 className="font-headline text-lg font-bold">Trained Repository</h2>
                  <p className="text-xs text-outline mt-1">{activeTrainedDocuments.length} dokumen aktif di vector store.</p>
                </div>
                <span className="material-symbols-outlined text-primary">database</span>
              </div>

              <div className="space-y-3 max-h-[620px] overflow-y-auto custom-scrollbar pr-1">
                {trainedDocuments.length > 0 ? (
                  trainedDocuments.map(renderTrainedDocument)
                ) : (
                  <div className="p-6 rounded-xl border border-outline-variant/60 text-center text-sm text-outline">
                    Belum ada dokumen yang selesai di-index.
                  </div>
                )}
              </div>
            </aside>
          </section>
        </div>
      </main>
    </div>
  );
};
