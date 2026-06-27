import React, { useRef, useState } from 'react';
import { AdminSidebar } from './AdminSidebar';
import { AdminHeader } from './AdminHeader';

type UploadStatus = 'Ready' | 'Parsing' | 'Chunking' | 'Embedding' | 'Indexed' | 'Rejected';
type UploadFileType = 'PDF' | 'DOCX' | 'TXT';

interface UploadItem {
  id: string;
  filename: string;
  type: UploadFileType;
  size: string;
  sizeBytes: number;
  uploadedAt: string;
  status: UploadStatus;
  progress: number;
  chunks: number;
  note: string;
}

interface TrainedDocument {
  id: string;
  filename: string;
  type: UploadFileType;
  size: string;
  chunks: number;
  indexedAt: string;
  vectorStatus: 'Active' | 'Removed';
}

const maxFileSize = 25 * 1024 * 1024;
const acceptedExtensions = ['pdf', 'docx', 'txt'];

const formatFileSize = (bytes: number) => {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
};

const getFileExtension = (filename: string) => {
  return filename.split('.').pop()?.toLowerCase() ?? '';
};

const getFileType = (filename: string): UploadFileType => {
  const extension = getFileExtension(filename);

  if (extension === 'docx') return 'DOCX';
  if (extension === 'txt') return 'TXT';

  return 'PDF';
};

const getDocumentIcon = (type: UploadFileType) => {
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

const getDocumentIconStyle = (type: UploadFileType) => {
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
      return 'bg-error-container/20 text-error border-error/30';
    default:
      return 'bg-surface-variant text-on-surface-variant border-outline-variant';
  }
};

const initialUploadItems: UploadItem[] = [
  {
    id: 'UPL-001',
    filename: 'SOP_Claim_Medical.pdf',
    type: 'PDF',
    size: '1.8 MB',
    sizeBytes: 1887436,
    uploadedAt: '10:45 AM',
    status: 'Indexed',
    progress: 100,
    chunks: 88,
    note: 'Indexed into vector database.',
  },
  {
    id: 'UPL-002',
    filename: 'Policy_WFH.pdf',
    type: 'PDF',
    size: '920 KB',
    sizeBytes: 942080,
    uploadedAt: '10:38 AM',
    status: 'Embedding',
    progress: 72,
    chunks: 36,
    note: 'Embedding generation in progress.',
  },
  {
    id: 'UPL-003',
    filename: 'FAQ_IT_Support.txt',
    type: 'TXT',
    size: '180 KB',
    sizeBytes: 184320,
    uploadedAt: '10:21 AM',
    status: 'Chunking',
    progress: 44,
    chunks: 14,
    note: 'Text split into searchable chunks.',
  },
];

const initialTrainedDocuments: TrainedDocument[] = [
  {
    id: 'TRN-001',
    filename: 'SOP_Claim_Medical.pdf',
    type: 'PDF',
    size: '1.8 MB',
    chunks: 88,
    indexedAt: '10:45 AM',
    vectorStatus: 'Active',
  },
  {
    id: 'TRN-002',
    filename: 'Employee_Handbook_2024.pdf',
    type: 'PDF',
    size: '2.4 MB',
    chunks: 124,
    indexedAt: '09:30 AM',
    vectorStatus: 'Active',
  },
  {
    id: 'TRN-003',
    filename: 'Finance_Report_Template_2026.docx',
    type: 'DOCX',
    size: '640 KB',
    chunks: 21,
    indexedAt: '09:14 AM',
    vectorStatus: 'Active',
  },
];

export const AdminUploadFile: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadItems, setUploadItems] = useState<UploadItem[]>(initialUploadItems);
  const [trainedDocuments, setTrainedDocuments] = useState<TrainedDocument[]>(initialTrainedDocuments);
  const [warningMessage, setWarningMessage] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const totalFiles = uploadItems.length;
  const indexedFiles = uploadItems.filter((item) => item.status === 'Indexed').length;
  const processingFiles = uploadItems.filter((item) =>
    ['Parsing', 'Chunking', 'Embedding'].includes(item.status)
  ).length;
  const rejectedFiles = uploadItems.filter((item) => item.status === 'Rejected').length;
  const activeTrainedDocuments = trainedDocuments.filter((document) => document.vectorStatus === 'Active');

  const addFilesToQueue = (files: File[]) => {
    if (files.length === 0) return;

    const timestamp = new Date().toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });

    const newItems = files.map((file, index): UploadItem => {
      const extension = getFileExtension(file.name);
      const isAcceptedType = acceptedExtensions.includes(extension);
      const isAcceptedSize = file.size <= maxFileSize;
      const isRejected = !isAcceptedType || !isAcceptedSize;

      return {
        id: `UPL-${Date.now()}-${index}`,
        filename: file.name,
        type: isAcceptedType ? getFileType(file.name) : 'PDF',
        size: formatFileSize(file.size),
        sizeBytes: file.size,
        uploadedAt: timestamp,
        status: isRejected ? 'Rejected' : 'Ready',
        progress: isRejected ? 0 : 12,
        chunks: isRejected ? 0 : Math.max(Math.round(file.size / 22000), 1),
        note: !isAcceptedType
          ? 'Rejected: only PDF, DOCX, and TXT files are supported.'
          : !isAcceptedSize
            ? 'Rejected: file size exceeds 25MB.'
            : 'Ready to parse and index.',
      };
    });

    setUploadItems((prevItems) => [...newItems, ...prevItems]);

    const rejectedCount = newItems.filter((item) => item.status === 'Rejected').length;

    if (rejectedCount > 0) {
      setWarningMessage(`${rejectedCount} file rejected. Check file type or maximum size.`);
      window.setTimeout(() => setWarningMessage(''), 4000);
    }
  };

  const addToTrainedRepository = (item: UploadItem) => {
    const indexedAt = new Date().toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });

    setTrainedDocuments((prevDocuments) => {
      const alreadyExists = prevDocuments.some((document) => document.filename === item.filename);

      if (alreadyExists) return prevDocuments;

      return [
        {
          id: `TRN-${Date.now()}`,
          filename: item.filename,
          type: item.type,
          size: item.size,
          chunks: item.chunks,
          indexedAt,
          vectorStatus: 'Active',
        },
        ...prevDocuments,
      ];
    });
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files ?? []);
    addFilesToQueue(selectedFiles);
    event.target.value = '';
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragOver(false);
    addFilesToQueue(Array.from(event.dataTransfer.files));
  };

  const handleStartIndexing = () => {
    setUploadItems((prevItems) =>
      prevItems.map((item) => {
        if (item.status !== 'Ready') return item;

        return {
          ...item,
          status: 'Parsing',
          progress: 28,
          note: 'Parsing document content.',
        };
      })
    );
  };

  const handleSimulateNextStep = (id: string) => {
    let completedItem: UploadItem | null = null;

    setUploadItems((prevItems) =>
      prevItems.map((item) => {
        if (item.id !== id) return item;

        if (item.status === 'Ready') {
          return { ...item, status: 'Parsing', progress: 28, note: 'Parsing document content.' };
        }

        if (item.status === 'Parsing') {
          return { ...item, status: 'Chunking', progress: 52, note: 'Splitting text into chunks.' };
        }

        if (item.status === 'Chunking') {
          return { ...item, status: 'Embedding', progress: 76, note: 'Generating embeddings.' };
        }

        if (item.status === 'Embedding') {
          const indexedItem = {
            ...item,
            status: 'Indexed' as UploadStatus,
            progress: 100,
            note: 'Indexed into vector database.',
          };

          completedItem = indexedItem;
          return indexedItem;
        }

        return item;
      })
    );

    window.setTimeout(() => {
      if (completedItem) addToTrainedRepository(completedItem);
    }, 0);
  };

  const handleRemoveItem = (id: string) => {
    setUploadItems((prevItems) => prevItems.filter((item) => item.id !== id));
  };

  const handleViewTrainedDocument = (document: TrainedDocument) => {
    window.alert(
      `Document Preview\n\nFile: ${document.filename}\nChunks: ${document.chunks}\nStatus: ${document.vectorStatus}`
    );
  };

  const handleRemoveTrainedDocument = (id: string) => {
    if (!window.confirm('Remove this document from trained repository?')) return;

    setTrainedDocuments((prevDocuments) =>
      prevDocuments.map((document) =>
        document.id === id ? { ...document, vectorStatus: 'Removed' } : document
      )
    );
  };

  return (
    <div className="bg-background text-on-surface font-body overflow-hidden flex h-screen w-full relative">
      <AdminSidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <main className="flex-1 flex flex-col h-full relative min-w-0">
        <AdminHeader onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

        <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-4 md:p-8 pb-12">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-6">
            <div>
              <p className="font-mono text-[10px] md:text-xs uppercase tracking-wider text-outline mb-2">
                Admin Upload Center
              </p>
              <h1 className="font-headline text-2xl md:text-3xl font-bold text-on-surface">
                Upload File
              </h1>
              <p className="text-on-surface-variant text-sm md:text-base mt-2 max-w-3xl">
                Upload dokumen knowledge base, validasi format, lakukan parsing, chunking, embedding, lalu simpan ke vector database.
              </p>
            </div>

            <button
              type="button"
              onClick={handleStartIndexing}
              className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-on-primary-container rounded-xl font-mono text-xs md:text-sm hover:bg-primary-container transition-all shadow-sm w-full sm:w-fit"
            >
              <span className="material-symbols-outlined text-[18px]">sync</span>
              Start Indexing
            </button>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
            <div className="bg-surface-container-low border border-outline-variant rounded-2xl p-4">
              <p className="font-mono text-[10px] text-outline uppercase tracking-wider mb-2">Total Files</p>
              <p className="font-headline text-2xl md:text-3xl font-bold text-on-surface">{totalFiles}</p>
            </div>

            <div className="bg-surface-container-low border border-outline-variant rounded-2xl p-4">
              <p className="font-mono text-[10px] text-outline uppercase tracking-wider mb-2">Indexed</p>
              <p className="font-headline text-2xl md:text-3xl font-bold text-emerald-400">{indexedFiles}</p>
            </div>

            <div className="bg-surface-container-low border border-outline-variant rounded-2xl p-4">
              <p className="font-mono text-[10px] text-outline uppercase tracking-wider mb-2">Processing</p>
              <p className="font-headline text-2xl md:text-3xl font-bold text-primary">{processingFiles}</p>
            </div>

            <div className="bg-surface-container-low border border-outline-variant rounded-2xl p-4">
              <p className="font-mono text-[10px] text-outline uppercase tracking-wider mb-2">Rejected</p>
              <p className="font-headline text-2xl md:text-3xl font-bold text-error">{rejectedFiles}</p>
            </div>

            <div className="bg-surface-container-low border border-outline-variant rounded-2xl p-4 col-span-2 lg:col-span-1">
              <p className="font-mono text-[10px] text-outline uppercase tracking-wider mb-2">Trained Docs</p>
              <p className="font-headline text-2xl md:text-3xl font-bold text-secondary">{activeTrainedDocuments.length}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
            <section className="xl:col-span-5 bg-surface-container-low border border-outline-variant rounded-2xl p-4 md:p-6 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="font-headline text-lg md:text-xl font-bold">Upload Documents</h2>
                  <p className="text-outline text-xs md:text-sm mt-1">PDF, DOCX, TXT. Maximum 25MB per file.</p>
                </div>

                <span className="font-mono text-[10px] md:text-xs px-2 md:px-3 py-1 bg-primary/10 text-primary border border-primary/20 rounded-full flex items-center gap-2 w-fit">
                  <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                  Vector Ready
                </span>
              </div>

              <input
                type="file"
                ref={fileInputRef}
                className="hidden"
                multiple
                accept=".pdf,.docx,.txt"
                onChange={handleFileChange}
              />

              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`min-h-[260px] flex flex-col items-center justify-center border-2 border-dashed rounded-2xl p-6 md:p-8 text-center cursor-pointer group transition-all ${
                  isDragOver
                    ? 'border-primary bg-primary/5'
                    : 'border-outline-variant hover:border-primary hover:bg-primary/5'
                }`}
              >
                <span className="material-symbols-outlined text-5xl text-outline mb-4 group-hover:text-primary transition-colors">
                  cloud_upload
                </span>
                <p className="text-sm md:text-base text-on-surface mb-2">
                  Drag & drop files here or <span className="text-primary font-semibold">Browse</span>
                </p>
                <p className="text-outline text-xs md:text-sm">Supported: PDF, DOCX, TXT</p>
              </div>

              {warningMessage && (
                <div className="mt-4 p-4 bg-error-container/20 border border-error/30 rounded-xl flex items-center gap-3 animate-fadeIn">
                  <span className="material-symbols-outlined text-error">warning</span>
                  <p className="text-error text-sm">{warningMessage}</p>
                </div>
              )}

              <div className="mt-4 bg-[#0b0d13] border border-outline-variant/50 rounded-xl p-4">
                <h3 className="font-headline text-sm font-bold mb-3">Processing Requirement</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {[
                    { icon: 'rule', title: 'Validation', text: 'Check file type and size.' },
                    { icon: 'plagiarism', title: 'Parsing', text: 'Extract text from documents.' },
                    { icon: 'segment', title: 'Chunking', text: 'Split into searchable chunks.' },
                    { icon: 'hub', title: 'Embedding', text: 'Store vectors for retrieval.' },
                  ].map((item) => (
                    <div key={item.title} className="bg-surface-container-high/30 border border-outline-variant/50 rounded-lg p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="material-symbols-outlined text-primary text-[18px]">{item.icon}</span>
                        <p className="font-mono text-xs text-on-surface">{item.title}</p>
                      </div>
                      <p className="text-[11px] text-outline leading-relaxed">{item.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            <section className="xl:col-span-7 bg-surface-container-low border border-outline-variant rounded-2xl overflow-hidden shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 md:px-6 py-4 border-b border-outline-variant bg-surface-container-high/30">
                <div>
                  <h2 className="font-headline text-lg md:text-xl font-bold">Upload Queue</h2>
                  <p className="text-outline text-xs md:text-sm mt-1">Monitor parsing, chunking, embedding, and indexing status.</p>
                </div>

                <span className="font-mono text-[10px] md:text-xs px-2.5 py-1 bg-surface-container-low border border-outline-variant rounded-full text-on-surface-variant w-fit">
                  {uploadItems.length} files
                </span>
              </div>

              <div className="overflow-x-auto custom-scrollbar">
                <table className="w-full text-left border-collapse min-w-[820px]">
                  <thead className="bg-surface-container-high/50 text-outline font-mono text-[10px] md:text-xs uppercase tracking-wider">
                    <tr>
                      <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Filename</th>
                      <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Size</th>
                      <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Chunks</th>
                      <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Progress</th>
                      <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Status</th>
                      <th className="px-4 md:px-6 py-3 md:py-4 font-medium text-right">Action</th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-outline-variant/30 text-[13px] md:text-sm">
                    {uploadItems.map((item) => (
                      <tr key={item.id} className="hover:bg-surface-container-high/50 transition-colors group">
                        <td className="px-4 md:px-6 py-3 md:py-4">
                          <div className="flex items-center gap-3">
                            <span className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${getDocumentIconStyle(item.type)}`}>
                              <span className="material-symbols-outlined text-[19px] md:text-[22px]">{getDocumentIcon(item.type)}</span>
                            </span>

                            <div className="min-w-0">
                              <p className="font-medium text-on-surface truncate max-w-[260px]">{item.filename}</p>
                              <p className="font-mono text-[10px] text-outline">{item.id} • {item.uploadedAt}</p>
                              <p className="text-[11px] text-on-surface-variant mt-1 truncate max-w-[300px]">{item.note}</p>
                            </div>
                          </div>
                        </td>

                        <td className="px-4 md:px-6 py-3 md:py-4 text-on-surface-variant whitespace-nowrap">{item.size}</td>

                        <td className="px-4 md:px-6 py-3 md:py-4 text-on-surface-variant whitespace-nowrap">{item.chunks}</td>

                        <td className="px-4 md:px-6 py-3 md:py-4 min-w-[160px]">
                          <div className="flex items-center gap-2">
                            <div className="h-2 bg-surface-variant rounded-full overflow-hidden flex-1">
                              <div
                                className={`h-full rounded-full ${item.status === 'Rejected' ? 'bg-error' : 'bg-primary'}`}
                                style={{ width: `${item.progress}%` }}
                              />
                            </div>
                            <span className="font-mono text-[10px] text-primary w-8 text-right">{item.progress}%</span>
                          </div>
                        </td>

                        <td className="px-4 md:px-6 py-3 md:py-4 whitespace-nowrap">
                          <span className={`px-2 py-1 rounded-md border font-mono text-[10px] ${getUploadStatusStyle(item.status)}`}>
                            {item.status}
                          </span>
                        </td>

                        <td className="px-4 md:px-6 py-3 md:py-4 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              type="button"
                              onClick={() => handleSimulateNextStep(item.id)}
                              disabled={item.status === 'Indexed' || item.status === 'Rejected'}
                              className="text-outline hover:text-primary transition-colors p-1.5 md:p-2 rounded-lg hover:bg-primary/10 disabled:opacity-30 disabled:hover:text-outline disabled:hover:bg-transparent"
                              title="Move to next step"
                            >
                              <span className="material-symbols-outlined text-[18px] md:text-[20px]">play_arrow</span>
                            </button>

                            <button
                              type="button"
                              onClick={() => handleRemoveItem(item.id)}
                              className="text-outline hover:text-error transition-colors p-1.5 md:p-2 rounded-lg hover:bg-error/10"
                              title="Remove from queue"
                            >
                              <span className="material-symbols-outlined text-[18px] md:text-[20px]">delete</span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="xl:col-span-12 bg-surface-container-low border border-outline-variant rounded-2xl overflow-hidden shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 md:px-6 py-4 border-b border-outline-variant bg-surface-container-high/30">
                <div>
                  <h2 className="font-headline text-lg md:text-xl font-bold">Document Repository</h2>
                  <p className="text-outline text-xs md:text-sm mt-1">
                    Total dokumen yang sudah di-train dan aktif sebagai sumber jawaban chatbot.
                  </p>
                </div>

                <span className="font-mono text-[10px] md:text-xs px-2.5 py-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full w-fit">
                  {activeTrainedDocuments.length} trained documents
                </span>
              </div>

              <div className="overflow-x-auto custom-scrollbar">
                <table className="w-full text-left border-collapse min-w-[760px]">
                  <thead className="bg-surface-container-high/50 text-outline font-mono text-[10px] md:text-xs uppercase tracking-wider">
                    <tr>
                      <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Filename</th>
                      <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Type</th>
                      <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Chunks</th>
                      <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Size</th>
                      <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Indexed At</th>
                      <th className="px-4 md:px-6 py-3 md:py-4 font-medium">Status</th>
                      <th className="px-4 md:px-6 py-3 md:py-4 font-medium text-right">Action</th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-outline-variant/30 text-[13px] md:text-sm">
                    {activeTrainedDocuments.length > 0 ? (
                      activeTrainedDocuments.map((document) => (
                        <tr key={document.id} className="hover:bg-surface-container-high/50 transition-colors group">
                          <td className="px-4 md:px-6 py-3 md:py-4">
                            <div className="flex items-center gap-3">
                              <span className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${getDocumentIconStyle(document.type)}`}>
                                <span className="material-symbols-outlined text-[19px] md:text-[22px]">
                                  {getDocumentIcon(document.type)}
                                </span>
                              </span>

                              <div className="min-w-0">
                                <p className="font-medium text-on-surface truncate max-w-[300px]">{document.filename}</p>
                                <p className="font-mono text-[10px] text-outline">{document.id}</p>
                              </div>
                            </div>
                          </td>

                          <td className="px-4 md:px-6 py-3 md:py-4 text-on-surface-variant whitespace-nowrap font-mono">
                            {document.type}
                          </td>

                          <td className="px-4 md:px-6 py-3 md:py-4 text-on-surface-variant whitespace-nowrap">
                            {document.chunks}
                          </td>

                          <td className="px-4 md:px-6 py-3 md:py-4 text-on-surface-variant whitespace-nowrap">
                            {document.size}
                          </td>

                          <td className="px-4 md:px-6 py-3 md:py-4 text-on-surface-variant whitespace-nowrap">
                            {document.indexedAt}
                          </td>

                          <td className="px-4 md:px-6 py-3 md:py-4 whitespace-nowrap">
                            <span className="px-2 py-1 rounded-md border font-mono text-[10px] bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
                              {document.vectorStatus}
                            </span>
                          </td>

                          <td className="px-4 md:px-6 py-3 md:py-4 text-right">
                            <div className="flex items-center justify-end gap-1">
                              <button
                                type="button"
                                onClick={() => handleViewTrainedDocument(document)}
                                className="text-outline hover:text-primary transition-colors p-1.5 md:p-2 rounded-lg hover:bg-primary/10"
                                title="View trained document"
                              >
                                <span className="material-symbols-outlined text-[18px] md:text-[20px]">visibility</span>
                              </button>

                              <button
                                type="button"
                                onClick={() => handleRemoveTrainedDocument(document.id)}
                                className="text-outline hover:text-error transition-colors p-1.5 md:p-2 rounded-lg hover:bg-error/10"
                                title="Remove trained document"
                              >
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
                            <span className="material-symbols-outlined text-4xl text-outline">folder_off</span>
                            <p className="font-semibold text-on-surface">No trained document found</p>
                            <p className="text-sm text-outline">
                              Upload a document and finish indexing to activate it in the knowledge base.
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
      </main>
    </div>
  );
};
