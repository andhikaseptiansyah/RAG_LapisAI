import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AdminSidebar } from './AdminSidebar';
import { AdminHeader } from './AdminHeader';
import { useDocuments } from '../hooks/useDocuments';
import type {
  DocumentType,
  UploadItem,
  UploadStatus,
} from '../services/documentService';

const maxFileSize = 25 * 1024 * 1024;
const acceptedExtensions = ['pdf', 'docx', 'txt'];
const itemsPerPage = 5;

// Only use these three single-color tones for every button state.
const buttonTone = {
  cyan: 'border-cyan-400 bg-cyan-400 text-slate-950 hover:border-cyan-300 hover:bg-cyan-300 hover:text-slate-950 focus-visible:ring-cyan-400',
  yellow: 'border-yellow-400 bg-yellow-400 text-slate-950 hover:border-yellow-300 hover:bg-yellow-300 hover:text-slate-950 focus-visible:ring-yellow-400',
  pink: 'border-pink-400 bg-pink-400 text-slate-950 hover:border-pink-300 hover:bg-pink-300 hover:text-slate-950 focus-visible:ring-pink-400',
} as const;

const baseButtonClass =
  'border font-semibold shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[#05070d] disabled:opacity-100 disabled:brightness-50 disabled:hover:translate-y-0 disabled:cursor-not-allowed';

// --- SVG ILLUSTRATIONS ---
const svgToDataUri = (svg: string) => `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
const metricImages = {
  documents: svgToDataUri(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 160">
      <defs>
        <linearGradient id="folder" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7dd3fc"/><stop offset="1" stop-color="#a78bfa"/></linearGradient>
        <linearGradient id="sheet" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#c4b5fd"/></linearGradient>
      </defs>
      <ellipse cx="112" cy="132" rx="72" ry="15" fill="#0f172a" opacity=".22"/>
      <path d="M42 58c0-8 6-14 14-14h35l14 17h62c8 0 14 6 14 14v43c0 8-6 14-14 14H56c-8 0-14-6-14-14V58z" fill="url(#folder)"/>
      <rect x="68" y="29" width="83" height="87" rx="12" fill="url(#sheet)" opacity=".92"/>
      <rect x="84" y="51" width="50" height="7" rx="3.5" fill="#6366f1" opacity=".55"/>
      <rect x="84" y="69" width="36" height="7" rx="3.5" fill="#06b6d4" opacity=".55"/>
    </svg>
  `),
  chunks: svgToDataUri(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 160">
      <defs>
        <linearGradient id="a" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fde68a"/><stop offset="1" stop-color="#fb7185"/></linearGradient>
        <linearGradient id="b" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#38bdf8"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient>
      </defs>
      <ellipse cx="110" cy="134" rx="77" ry="13" fill="#0f172a" opacity=".18"/>
      <rect x="44" y="83" width="42" height="42" rx="10" fill="url(#a)"/>
      <rect x="90" y="55" width="42" height="70" rx="10" fill="url(#b)"/>
      <rect x="136" y="30" width="42" height="95" rx="10" fill="#f59e0b"/>
      <circle cx="67" cy="65" r="16" fill="#fff" opacity=".42"/>
      <circle cx="113" cy="37" r="16" fill="#fff" opacity=".42"/>
      <circle cx="159" cy="15" r="16" fill="#fff" opacity=".42"/>
      <path d="M64 66l49-28 46-22" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" opacity=".9"/>
    </svg>
  `),
  indexed: svgToDataUri(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 160">
      <defs>
        <linearGradient id="folder2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#86efac"/><stop offset="1" stop-color="#3b82f6"/></linearGradient>
        <linearGradient id="sheet2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#bfdbfe"/></linearGradient>
      </defs>
      <ellipse cx="112" cy="132" rx="72" ry="15" fill="#0f172a" opacity=".22"/>
      <path d="M42 58c0-8 6-14 14-14h35l14 17h62c8 0 14 6 14 14v43c0 8-6 14-14 14H56c-8 0-14-6-14-14V58z" fill="url(#folder2)"/>
      <rect x="68" y="29" width="83" height="87" rx="12" fill="url(#sheet2)" opacity=".92"/>
      <rect x="84" y="51" width="50" height="7" rx="3.5" fill="#10b981" opacity=".55"/>
      <rect x="84" y="69" width="36" height="7" rx="3.5" fill="#3b82f6" opacity=".55"/>
      <circle cx="160" cy="45" r="23" fill="#22c55e"/>
      <path d="M149 45l8 8 15-17" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  `),
  failed: svgToDataUri(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 160">
      <defs>
        <linearGradient id="folderRed" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fca5a5"/><stop offset="1" stop-color="#e11d48"/></linearGradient>
        <linearGradient id="sheetRed" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#fecdd3"/></linearGradient>
      </defs>
      <ellipse cx="112" cy="132" rx="72" ry="15" fill="#0f172a" opacity=".22"/>
      <path d="M42 58c0-8 6-14 14-14h35l14 17h62c8 0 14 6 14 14v43c0 8-6 14-14 14H56c-8 0-14-6-14-14V58z" fill="url(#folderRed)"/>
      <rect x="68" y="29" width="83" height="87" rx="12" fill="url(#sheetRed)" opacity=".92"/>
      <rect x="84" y="51" width="50" height="7" rx="3.5" fill="#e11d48" opacity=".45"/>
      <rect x="84" y="69" width="36" height="7" rx="3.5" fill="#fb7185" opacity=".45"/>
      <circle cx="160" cy="45" r="23" fill="#ef4444"/>
      <path d="M152 37l16 16M168 37l-16 16" stroke="#fff" stroke-width="6" stroke-linecap="round"/>
    </svg>
  `),
};

// --- HELPERS ---
const getFileExtension = (filename: string) => {
  return filename.split('.').pop()?.toLowerCase() ?? '';
};

const normalizeFilename = (filename: string) => filename.trim().toLowerCase();

const getDocTypeFromFile = (file: File): DocumentType => {
  const ext = getFileExtension(file.name);
  if (ext === 'pdf') return 'PDF';
  if (ext === 'docx') return 'DOCX';
  if (ext === 'txt') return 'TXT';
  return 'Others' as DocumentType;
};

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const formatDateTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' });
};

const getDocumentIcon = (type: DocumentType) => {
  switch (type) {
    case 'PDF': return 'picture_as_pdf';
    case 'DOCX': return 'article';
    case 'TXT': return 'text_snippet';
    default: return 'description';
  }
};

const getDocumentIconStyle = (type: DocumentType) => {
  switch (type) {
    case 'PDF': return 'text-slate-950 bg-pink-400 border-pink-400';
    case 'DOCX': return 'text-slate-950 bg-cyan-400 border-cyan-400';
    case 'TXT': return 'text-slate-950 bg-yellow-400 border-yellow-400';
    default: return 'text-slate-950 bg-cyan-400 border-cyan-400';
  }
};

const getUploadStatusStyle = (status: UploadStatus | 'Waiting' | 'Indexing') => {
  switch (status) {
    case 'Ready':
    case 'Waiting': return 'bg-yellow-400 text-slate-950 border-yellow-400';
    case 'Parsing':
    case 'Chunking':
    case 'Embedding':
    case 'Indexing': return 'bg-cyan-400 text-slate-950 border-cyan-400';
    case 'Indexed': return 'bg-cyan-400 text-slate-950 border-cyan-400';
    case 'Rejected':
    case 'Failed': return 'bg-pink-400 text-slate-950 border-pink-400';
    default: return 'bg-cyan-400 text-slate-950 border-cyan-400';
  }
};

const getPaginationNumbers = (totalPages: number, currentPage: number) => {
  if (totalPages <= 5) return Array.from({ length: totalPages }, (_, index) => index + 1);
  if (currentPage <= 3) return [1, 2, 3, 4, 5];
  if (currentPage >= totalPages - 2) return [totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
  return [currentPage - 2, currentPage - 1, currentPage, currentPage + 1, currentPage + 2];
};

const paginateItems = <T,>(items: T[], page: number) => {
  const start = (page - 1) * itemsPerPage;
  return items.slice(start, start + itemsPerPage);
};

const getStagedItemId = (file: File) =>
  `staged-${normalizeFilename(file.name)}-${file.size}-${file.lastModified}`;

export const AdminUploadFile: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isDragOver, setIsDragOver] = useState(false);
  const [warningMessage, setWarningMessage] = useState('');
  
  // STATE: Penampung lokal untuk file sebelum dikirim
  const [stagedFiles, setStagedFiles] = useState<File[]>([]);
  const [duplicateFiles, setDuplicateFiles] = useState<File[]>([]);
  const [replacementFilenames, setReplacementFilenames] = useState<Set<string>>(new Set());
  const [deleteTargets, setDeleteTargets] = useState<Array<{ id: string; filename: string }>>([]);
  const [selectedRepositoryIds, setSelectedRepositoryIds] = useState<Set<string>>(new Set());
  const [selectedQueueIds, setSelectedQueueIds] = useState<Set<string>>(new Set());
  const [isDeletingDocument, setIsDeletingDocument] = useState(false);
  
  const [repositoryPage, setRepositoryPage] = useState(1);
  const [queuePage, setQueuePage] = useState(1);
  
  const [locallyMovedIds, setLocallyMovedIds] = useState<Set<string>>(new Set());
  const [forcedWaitingIds, setForcedWaitingIds] = useState<Set<string>>(new Set());
  
  const pendingUploadNamesRef = useRef<string[]>([]);
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
    removeDocument,
    refreshAll,
  } = useDocuments({ initialLimit: 1000 });

  const existingDocumentNames = useMemo(() => {
    return new Set(
      [...uploadItems, ...trainedDocuments].map((item) =>
        normalizeFilename(item.filename)
      )
    );
  }, [trainedDocuments, uploadItems]);

  // Filter 1: File dari database yang statusnya Ready/Waiting
  const dbWaitingItems = useMemo(() => {
    return uploadItems.filter((item) => {
      if (locallyMovedIds.has(item.id)) return false;
      return item.status === 'Ready' || forcedWaitingIds.has(item.id);
    });
  }, [forcedWaitingIds, locallyMovedIds, uploadItems]);

  // Filter 2: Gabungan file lokal (staged) + file dari database (Dengan perbaikan TS)
  const waitingRepositoryItems = useMemo(() => {
    const stagedAsItems = stagedFiles.map((file) => ({
      id: getStagedItemId(file),
      filename: file.name,
      type: getDocTypeFromFile(file),
      size: formatBytes(file.size),
      uploadedAt: new Date().toISOString(),
      status: 'Waiting' as any, // Perbaikan TS agar tipe status diterima
      progress: 0,
      chunks: 0,
      note: 'Waiting in local repository.',
    } as UploadItem));

    return [...stagedAsItems, ...dbWaitingItems];
  }, [stagedFiles, dbWaitingItems]);

  // Antrean pipeline dari database
  const uploadQueueItems = useMemo(() => {
    return uploadItems.filter((item) => {
      if (locallyMovedIds.has(item.id)) return true;
      if (forcedWaitingIds.has(item.id)) return false;
      return item.status !== 'Ready';
    });
  }, [forcedWaitingIds, locallyMovedIds, uploadItems]);

  const totalRepositoryPages = Math.max(1, Math.ceil(waitingRepositoryItems.length / itemsPerPage));
  const totalQueuePages = Math.max(1, Math.ceil(uploadQueueItems.length / itemsPerPage));

  const repositoryPageItems = useMemo(() => paginateItems(waitingRepositoryItems, repositoryPage), [repositoryPage, waitingRepositoryItems]);
  const queuePageItems = useMemo(() => paginateItems(uploadQueueItems, queuePage), [queuePage, uploadQueueItems]);

  const allRepositorySelected =
    waitingRepositoryItems.length > 0 &&
    waitingRepositoryItems.every((item) => selectedRepositoryIds.has(item.id));
  const allQueueSelected =
    uploadQueueItems.length > 0 &&
    uploadQueueItems.every((item) => selectedQueueIds.has(item.id));

  const selectedRepositoryItems = useMemo(
    () => waitingRepositoryItems.filter((item) => selectedRepositoryIds.has(item.id)),
    [selectedRepositoryIds, waitingRepositoryItems]
  );
  const selectedQueueItems = useMemo(
    () => uploadQueueItems.filter((item) => selectedQueueIds.has(item.id)),
    [selectedQueueIds, uploadQueueItems]
  );

  const totalFiles = waitingRepositoryItems.length + uploadQueueItems.length;
  const waitingFiles = waitingRepositoryItems.length;
  const pipelineFiles = uploadQueueItems.length;
  const indexedFiles = uploadQueueItems.filter((item) => item.status === 'Indexed').length;
  const failedFiles = uploadQueueItems.filter((item) => ['Failed', 'Rejected'].includes(item.status)).length;

  useEffect(() => { setRepositoryPage((current) => Math.min(current, totalRepositoryPages)); }, [totalRepositoryPages]);
  useEffect(() => { setQueuePage((current) => Math.min(current, totalQueuePages)); }, [totalQueuePages]);

  useEffect(() => {
    const validIds = new Set(waitingRepositoryItems.map((item) => item.id));
    setSelectedRepositoryIds((current) => {
      const next = new Set([...current].filter((id) => validIds.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [waitingRepositoryItems]);

  useEffect(() => {
    const validIds = new Set(uploadQueueItems.map((item) => item.id));
    setSelectedQueueIds((current) => {
      const next = new Set([...current].filter((id) => validIds.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [uploadQueueItems]);

  useEffect(() => {
    setLocallyMovedIds((current) => {
      if (current.size === 0) return current;
      const next = new Set(current);
      uploadItems.forEach((item) => { if (item.status !== 'Ready') next.delete(item.id); });
      return next.size === current.size ? current : next;
    });
  }, [uploadItems]);

  useEffect(() => {
    const pendingNames = pendingUploadNamesRef.current;
    if (pendingNames.length === 0 || uploadItems.length === 0) return;

    const remainingNames = [...pendingNames];
    const matchedIds: string[] = [];

    const newestFirst = [...uploadItems].sort((a, b) => {
      const timeA = new Date(a.uploadedAt).getTime();
      const timeB = new Date(b.uploadedAt).getTime();
      return (Number.isNaN(timeB) ? 0 : timeB) - (Number.isNaN(timeA) ? 0 : timeA);
    });

    newestFirst.forEach((item) => {
      const index = remainingNames.findIndex((name) => name === item.filename);
      if (index >= 0) {
        matchedIds.push(item.id);
        remainingNames.splice(index, 1);
      }
    });

    if (matchedIds.length === 0) return;

    setForcedWaitingIds((current) => {
      const next = new Set(current);
      matchedIds.forEach((id) => next.add(id));
      return next;
    });

    pendingUploadNamesRef.current = remainingNames;
    setRepositoryPage(1);
  }, [uploadItems]);

  const validateFiles = (files: File[]) => {
    const accepted: File[] = [];
    const rejected: string[] = [];
    for (const file of files) {
      const extension = getFileExtension(file.name);
      if (!acceptedExtensions.includes(extension)) { rejected.push(`${file.name}: only PDF, DOCX, TXT supported.`); continue; }
      if (file.size > maxFileSize) { rejected.push(`${file.name}: max file size 25 MB.`); continue; }
      accepted.push(file);
    }
    return { accepted, rejected };
  };

  const handleFiles = (files: File[]) => {
    if (files.length === 0) return;
    const { accepted, rejected } = validateFiles(files);

    const stagedNames = new Set(
      stagedFiles.map((file) => normalizeFilename(file.name))
    );
    const newFiles: File[] = [];
    const duplicates: File[] = [];

    accepted.forEach((file) => {
      const normalizedName = normalizeFilename(file.name);

      // A duplicate can already be staged locally or already exist in the
      // trained/upload repository. Both cases must use the confirmation modal.
      if (
        stagedNames.has(normalizedName) ||
        existingDocumentNames.has(normalizedName)
      ) {
        duplicates.push(file);
        return;
      }

      stagedNames.add(normalizedName);
      newFiles.push(file);
    });

    if (rejected.length > 0) {
      setWarningMessage(rejected.join(' '));
      window.setTimeout(() => setWarningMessage(''), 6000);
    }

    if (newFiles.length > 0) {
      setStagedFiles((prev) => [...prev, ...newFiles]);
      setRepositoryPage(1);
    }

    if (duplicates.length > 0) {
      setDuplicateFiles(duplicates);
    }
  };

  const handleCancelDuplicateUpload = () => {
    // Keep the existing file and discard only the newly selected duplicate.
    setDuplicateFiles([]);
  };

  const handleConfirmDuplicateUpload = () => {
    if (duplicateFiles.length === 0) return;

    const confirmedFiles = [...duplicateFiles];

    setStagedFiles((currentFiles) => {
      const nextFiles = [...currentFiles];

      confirmedFiles.forEach((newFile) => {
        const normalizedName = normalizeFilename(newFile.name);
        const stagedIndex = nextFiles.findIndex(
          (currentFile) =>
            normalizeFilename(currentFile.name) === normalizedName
        );

        if (stagedIndex >= 0) {
          // Replace the old local selection instead of creating two queue rows.
          nextFiles[stagedIndex] = newFile;
        } else {
          nextFiles.push(newFile);
        }
      });

      return nextFiles;
    });

    setReplacementFilenames((currentNames) => {
      const nextNames = new Set(currentNames);

      confirmedFiles.forEach((file) => {
        const normalizedName = normalizeFilename(file.name);

        // Only tell the backend to replace when the filename already exists
        // in its upload/trained repository. A local staged replacement does
        // not need the backend overwrite flag unless such a record also exists.
        if (existingDocumentNames.has(normalizedName)) {
          nextNames.add(normalizedName);
        }
      });

      return nextNames;
    });

    setDuplicateFiles([]);
    setRepositoryPage(1);
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(Array.from(event.target.files ?? []));
    event.target.value = '';
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => { event.preventDefault(); setIsDragOver(true); };
  const handleDragLeave = () => { setIsDragOver(false); };
  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragOver(false);
    handleFiles(Array.from(event.dataTransfer.files));
  };

  const handleStartAllIndexing = async () => {
    const documentIds = dbWaitingItems.map((item) => item.id);
    if (stagedFiles.length === 0 && documentIds.length === 0) return;

    let shouldRefresh = false;

    if (stagedFiles.length > 0) {
      const uploadedNames = stagedFiles.map(f => f.name);
      const replaceFilenames = stagedFiles
        .filter((file) => replacementFilenames.has(normalizeFilename(file.name)))
        .map((file) => file.name);
      const success = await uploadFiles(stagedFiles, replaceFilenames);
      if (success) {
        pendingUploadNamesRef.current = [...pendingUploadNamesRef.current, ...uploadedNames];
        setStagedFiles([]);
        setReplacementFilenames(new Set());
        shouldRefresh = true;
      }
    }

    if (documentIds.length > 0) {
      setForcedWaitingIds((current) => { const next = new Set(current); documentIds.forEach((id) => next.delete(id)); return next; });
      setLocallyMovedIds((current) => { const next = new Set(current); documentIds.forEach((id) => next.add(id)); return next; });
      setQueuePage(1);

      const success = await startIndexing(documentIds);
      if (success) {
        shouldRefresh = true;
      } else {
        setLocallyMovedIds((current) => { const next = new Set(current); documentIds.forEach((id) => next.delete(id)); return next; });
        setForcedWaitingIds((current) => { const next = new Set(current); documentIds.forEach((id) => next.add(id)); return next; });
      }
    }

    if (shouldRefresh) {
      await refreshAll();
    }
  };

  const handleRetryIndexing = async (id: string) => {
    setLocallyMovedIds((current) => { const next = new Set(current); next.add(id); return next; });
    const success = await startIndexing([id]);
    if (success) { await refreshAll(); } else { setLocallyMovedIds((current) => { const next = new Set(current); next.delete(id); return next; }); }
  };

  const toggleSelection = (
    id: string,
    setter: React.Dispatch<React.SetStateAction<Set<string>>>
  ) => {
    setter((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleToggleAllRepository = () => {
    setSelectedRepositoryIds(
      allRepositorySelected
        ? new Set<string>()
        : new Set(waitingRepositoryItems.map((item) => item.id))
    );
  };

  const handleToggleAllQueue = () => {
    setSelectedQueueIds(
      allQueueSelected
        ? new Set<string>()
        : new Set(uploadQueueItems.map((item) => item.id))
    );
  };

  const openDeleteConfirmation = (
    targets: Array<{ id: string; filename: string }>
  ) => {
    const uniqueTargets = Array.from(
      new Map(targets.map((target) => [target.id, target])).values()
    );
    setDeleteTargets(uniqueTargets);
  };

  const handleRemove = (id: string, filename: string) => {
    openDeleteConfirmation([{ id, filename }]);
  };

  const handleDeleteSelectedRepository = () => {
    if (selectedRepositoryItems.length === 0) return;
    openDeleteConfirmation(
      selectedRepositoryItems.map((item) => ({
        id: item.id,
        filename: item.filename,
      }))
    );
  };

  const handleDeleteSelectedQueue = () => {
    if (selectedQueueItems.length === 0) return;
    openDeleteConfirmation(
      selectedQueueItems.map((item) => ({
        id: item.id,
        filename: item.filename,
      }))
    );
  };

  const handleCancelDelete = () => {
    if (isDeletingDocument) return;
    setDeleteTargets([]);
  };

  const handleConfirmDelete = async () => {
    if (deleteTargets.length === 0 || isDeletingDocument) return;

    setIsDeletingDocument(true);
    const targetIds = new Set(deleteTargets.map((target) => target.id));
    const removedStagedFiles = stagedFiles.filter((file) =>
      targetIds.has(getStagedItemId(file))
    );
    const remoteTargets = deleteTargets.filter(
      (target) => !target.id.startsWith('staged-')
    );
    const deletedIds = new Set(
      deleteTargets
        .filter((target) => target.id.startsWith('staged-'))
        .map((target) => target.id)
    );
    const failedTargets: Array<{ id: string; filename: string }> = [];

    try {
      if (removedStagedFiles.length > 0) {
        setStagedFiles((currentFiles) =>
          currentFiles.filter(
            (file) => !targetIds.has(getStagedItemId(file))
          )
        );

        const removedNames = new Set(
          removedStagedFiles.map((file) => normalizeFilename(file.name))
        );
        setReplacementFilenames((currentNames) => {
          const nextNames = new Set(currentNames);
          removedNames.forEach((name) => nextNames.delete(name));
          return nextNames;
        });
      }

      for (const target of remoteTargets) {
        const success = await removeDocument(target.id);
        if (success) deletedIds.add(target.id);
        else failedTargets.push(target);
      }

      if (deletedIds.size > 0) {
        setLocallyMovedIds((current) => {
          const next = new Set(current);
          deletedIds.forEach((id) => next.delete(id));
          return next;
        });
        setForcedWaitingIds((current) => {
          const next = new Set(current);
          deletedIds.forEach((id) => next.delete(id));
          return next;
        });
        setSelectedRepositoryIds((current) => {
          const next = new Set(current);
          deletedIds.forEach((id) => next.delete(id));
          return next;
        });
        setSelectedQueueIds((current) => {
          const next = new Set(current);
          deletedIds.forEach((id) => next.delete(id));
          return next;
        });
      }

      if (remoteTargets.length > 0) {
        await refreshAll();
      }

      if (failedTargets.length > 0) {
        setDeleteTargets(failedTargets);
        setWarningMessage(
          `${failedTargets.length} file${failedTargets.length === 1 ? '' : 's'} could not be deleted. Please try again.`
        );
        window.setTimeout(() => setWarningMessage(''), 6000);
      } else {
        setDeleteTargets([]);
      }
    } finally {
      setIsDeletingDocument(false);
    }
  };

  const renderPagination = (totalItems: number, totalPages: number, page: number, setPage: React.Dispatch<React.SetStateAction<number>>) => {
    if (totalItems <= itemsPerPage) return null;
    const pageNumbers = getPaginationNumbers(totalPages, page);

    return (
      <div className="flex flex-wrap items-center justify-end gap-1.5 pt-4 text-xs">
        <button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page === 1} className={`h-8 px-3 rounded-lg ${baseButtonClass} ${buttonTone.cyan}`}>Prev</button>
        {pageNumbers[0] > 1 && (<><button type="button" onClick={() => setPage(1)} className={`h-8 min-w-8 rounded-lg ${baseButtonClass} ${buttonTone.cyan}`}>1</button><span className="px-1 text-slate-600">...</span></>)}
        {pageNumbers.map((pageNumber) => (
          <button key={pageNumber} type="button" onClick={() => setPage(pageNumber)} className={`h-8 min-w-8 rounded-lg ${baseButtonClass} ${page === pageNumber ? buttonTone.yellow : buttonTone.cyan}`}>{pageNumber}</button>
        ))}
        {pageNumbers[pageNumbers.length - 1] < totalPages && (<><span className="px-1 text-slate-600">...</span><button type="button" onClick={() => setPage(totalPages)} className={`h-8 min-w-8 rounded-lg ${baseButtonClass} ${buttonTone.cyan}`}>{totalPages}</button></>)}
        <button type="button" onClick={() => setPage((current) => Math.min(totalPages, current + 1))} disabled={page === totalPages} className={`h-8 px-3 rounded-lg ${baseButtonClass} ${buttonTone.cyan}`}>Next</button>
      </div>
    );
  };

  const renderRepositoryItem = (item: UploadItem) => (
    <div key={item.id} className="grid grid-cols-[32px_minmax(0,1fr)] md:grid-cols-[32px_minmax(0,1.7fr)_110px_minmax(0,1fr)_78px] gap-3 md:gap-4 items-center py-4 border-b border-white/5 last:border-b-0">
      <label className="flex h-8 w-8 cursor-pointer items-center justify-center" title={`Select ${item.filename}`}>
        <input
          type="checkbox"
          checked={selectedRepositoryIds.has(item.id)}
          onChange={() => toggleSelection(item.id, setSelectedRepositoryIds)}
          className="h-4 w-4 cursor-pointer rounded border-white/20 bg-slate-950 accent-cyan-400"
          aria-label={`Select ${item.filename}`}
        />
      </label>
      <div className="flex items-center gap-3 min-w-0">
        <div className={`w-10 h-10 rounded-xl border flex items-center justify-center shrink-0 ${getDocumentIconStyle(item.type)}`}><span className="material-symbols-outlined text-[22px]">{getDocumentIcon(item.type)}</span></div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-100 truncate">{item.filename}</p>
          <p className="text-[11px] text-slate-500 font-mono truncate">{item.type} · {item.size} · {formatDateTime(item.uploadedAt)}</p>
        </div>
      </div>
      <div className="col-start-2 md:col-start-auto md:text-left"><span className={`inline-flex items-center px-2.5 py-1 rounded-full border font-mono text-[10px] ${getUploadStatusStyle('Waiting')}`}>Waiting</span></div>
      <p className="col-start-2 text-xs text-slate-500 line-clamp-2 md:col-start-auto">{item.note || 'Waiting for batch indexing.'}</p>
      <div className="col-start-2 flex md:col-start-auto md:justify-end">
        <button type="button" onClick={() => handleRemove(item.id, item.filename)} className={`w-8 h-8 rounded-lg flex items-center justify-center ${baseButtonClass} ${buttonTone.pink}`} aria-label={`Remove ${item.filename}`} title="Remove"><span className="material-symbols-outlined text-[18px]">delete</span></button>
      </div>
    </div>
  );

  const renderQueueItem = (item: UploadItem) => {
    const wasMovedLocally = locallyMovedIds.has(item.id) && item.status === 'Ready';
    const visibleStatus = wasMovedLocally ? 'Indexing' : item.status;
    const progress = wasMovedLocally ? Math.max(item.progress, 5) : item.progress;

    return (
      <div key={item.id} className="grid grid-cols-[32px_minmax(0,1fr)] lg:grid-cols-[32px_minmax(0,1.6fr)_110px_minmax(0,1fr)_minmax(0,1.25fr)_86px] gap-3 lg:gap-4 items-center py-4 border-b border-white/5 last:border-b-0">
        <label className="flex h-8 w-8 cursor-pointer items-center justify-center" title={`Select ${item.filename}`}>
          <input
            type="checkbox"
            checked={selectedQueueIds.has(item.id)}
            onChange={() => toggleSelection(item.id, setSelectedQueueIds)}
            className="h-4 w-4 cursor-pointer rounded border-white/20 bg-slate-950 accent-cyan-400"
            aria-label={`Select ${item.filename}`}
          />
        </label>
        <div className="flex items-center gap-3 min-w-0">
          <div className={`w-10 h-10 rounded-xl border flex items-center justify-center shrink-0 ${getDocumentIconStyle(item.type)}`}><span className="material-symbols-outlined text-[22px]">{getDocumentIcon(item.type)}</span></div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-100 truncate">{item.filename}</p>
            <p className="text-[11px] text-slate-500 font-mono truncate">{item.type} · {item.size} · {formatDateTime(item.uploadedAt)}</p>
          </div>
        </div>
        <div className="col-start-2 lg:col-start-auto"><span className={`inline-flex items-center px-2.5 py-1 rounded-full border font-mono text-[10px] ${getUploadStatusStyle(visibleStatus)}`}>{visibleStatus}</span></div>
        <div className="col-start-2 min-w-0 lg:col-start-auto">
          <div className="w-full h-2 rounded-full bg-white/5 overflow-hidden"><div className="h-full bg-cyan-400 transition-all" style={{ width: `${progress}%` }} /></div>
          <p className="text-[10px] text-slate-500 font-mono mt-1 truncate">{progress}% · {item.chunks} chunks</p>
        </div>
        <p className="col-start-2 text-xs text-slate-500 line-clamp-2 lg:col-start-auto">{wasMovedLocally ? 'Moved to indexing queue.' : item.note}</p>
        <div className="col-start-2 flex gap-2 lg:col-start-auto lg:justify-end">
          {item.status === 'Failed' && (<button type="button" onClick={() => void handleRetryIndexing(item.id)} disabled={isIndexing} className={`h-8 px-3 rounded-lg text-[11px] ${baseButtonClass} ${buttonTone.yellow}`}>Retry</button>)}
          <button type="button" onClick={() => handleRemove(item.id, item.filename)} className={`w-8 h-8 rounded-lg flex items-center justify-center ${baseButtonClass} ${buttonTone.pink}`} aria-label={`Remove ${item.filename}`} title="Remove"><span className="material-symbols-outlined text-[18px]">delete</span></button>
        </div>
      </div>
    );
  };

  const summaryCards = [
    {
      label: 'Total Files',
      value: totalFiles,
      icon: 'folder_open',
      image: metricImages.documents,
      gradient: 'from-cyan-300 via-teal-300 to-cyan-500',
    },
    {
      label: 'Waiting',
      value: waitingFiles,
      icon: 'hourglass_top',
      image: metricImages.chunks,
      gradient: 'from-amber-200 via-yellow-300 to-orange-400',
    },
    {
      label: 'Indexed',
      value: indexedFiles,
      icon: 'task_alt',
      image: metricImages.indexed,
      gradient: 'from-emerald-300 via-green-300 to-emerald-500',
    },
    {
      label: 'Failed',
      value: failedFiles,
      icon: 'report',
      image: metricImages.failed,
      gradient: 'from-rose-300 via-pink-300 to-rose-500',
    },
  ];

  return (
    <div className="bg-[#05070d] text-white font-body overflow-hidden flex h-screen w-full relative">
      <style>{`
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }
        .animate-fade-in-up { animation: fadeInUp 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards; opacity: 0; }
      `}</style>
      <AdminSidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <main className="flex-1 flex flex-col h-full relative min-w-0 bg-[#05070d] overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(34,211,238,0.06),transparent_40%),radial-gradient(ellipse_at_bottom_right,rgba(168,85,247,0.06),transparent_40%)] pointer-events-none" />
        <AdminHeader onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

        <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar p-4 md:p-6 pb-12 relative z-10">
          <div className="max-w-[1720px] mx-auto w-full">
            
            <div className="shrink-0 flex flex-col md:flex-row md:items-center justify-between mb-4 animate-fade-in-up gap-4">
              <div>
                <p className="font-mono text-[10px] md:text-xs uppercase tracking-[0.28em] text-slate-500 mb-1">
                  Python RAG Pipeline
                </p>
                <h1 className="font-headline text-2xl md:text-3xl font-bold tracking-tight text-white">
                  Upload & Index <span className="bg-gradient-to-r from-violet-300 to-cyan-300 bg-clip-text text-transparent">Knowledge Base</span>
                </h1>
                <p className="text-slate-400 text-xs md:text-sm mt-1.5 max-w-2xl">
                  Upload files first. They will wait in the Trained Repository until you run batch indexing.
                </p>
              </div>
              <div className="flex items-center gap-2">
                {isUploading && <span className="text-xs text-cyan-300 font-mono animate-pulse mr-2">Uploading...</span>}
                {isIndexing && <span className="text-xs text-violet-300 font-mono animate-pulse mr-2">Indexing...</span>}
              </div>
            </div>

            {(warningMessage || error) && (
              <div className="mb-6 p-4 rounded-xl border border-rose-400/30 bg-rose-500/10 text-rose-200 text-sm flex items-start justify-between gap-4">
                <span>{warningMessage || error}</span>
                {error && (
                  <button type="button" onClick={clearError} className={`h-8 px-3 rounded-lg text-xs ${baseButtonClass} ${buttonTone.pink}`}>
                    Close
                  </button>
                )}
              </div>
            )}

            <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 shrink-0 mb-6">
              {summaryCards.map((card, index) => (
                <div
                  key={card.label}
                  className={`animate-fade-in-up relative overflow-hidden rounded-[1.2rem] bg-gradient-to-br ${card.gradient} p-4 min-h-[110px] text-slate-950 shadow-[0_15px_40px_rgba(0,0,0,0.2)] hover:-translate-y-1 transition-transform`}
                  style={{ animationDelay: `${0.1 + (index * 0.1)}s` }}
                >
                  <div className="absolute inset-0 bg-[radial-gradient(circle_at_15%_0%,rgba(255,255,255,0.55),transparent_35%)]" />
                  <div className="absolute -right-2 bottom-0 w-24 opacity-95 pointer-events-none">
                    <img src={card.image} alt="" className="w-full h-auto" />
                  </div>
                  <div className="relative z-10 pr-16">
                    <div className="flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-[14px]">{card.icon}</span>
                      <p className="text-xs font-semibold">{card.label}</p>
                    </div>
                    <p className="text-2xl font-headline font-black mt-2 tracking-tight">{card.value}</p>
                  </div>
                </div>
              ))}
            </section>

            <section className="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-8 items-stretch">
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`min-h-[360px] flex flex-col justify-center border border-dashed rounded-[1.2rem] p-6 md:p-8 bg-transparent transition-all animate-fade-in-up ${
                  isDragOver
                    ? 'border-cyan-400/60 bg-cyan-500/5 shadow-[0_0_35px_rgba(34,211,238,0.12)]'
                    : 'border-white/10 hover:border-cyan-400/25'
                }`}
                style={{ animationDelay: '0.4s' }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.docx,.txt"
                  onChange={handleFileChange}
                  className="hidden"
                />

                <div className="flex flex-col items-center text-center">
                  <div className="w-16 h-16 rounded-2xl bg-cyan-400 text-slate-950 border border-cyan-300 flex items-center justify-center mb-4 shadow-[0_10px_30px_rgba(34,211,238,0.22)]">
                    <span className="material-symbols-outlined text-[34px]">cloud_upload</span>
                  </div>
                  <h2 className="font-headline text-xl font-bold text-white mb-2">
                    Upload Files
                  </h2>
                  <p className="text-sm text-slate-400 max-w-xl mb-5">
                    Add PDF, DOCX, or TXT files. Uploaded files will stay in the waiting repository and will not be indexed automatically.
                  </p>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploading}
                    className={`px-5 py-2.5 rounded-xl text-sm ${baseButtonClass} ${buttonTone.cyan}`}
                  >
                    {isUploading ? 'Uploading...' : 'Choose Files'}
                  </button>
                </div>
              </div>

              <div className="min-h-[360px] flex flex-col bg-transparent border border-white/10 rounded-[1.2rem] p-5 md:p-6 animate-fade-in-up" style={{ animationDelay: '0.5s' }}>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/5">
                  <div>
                    <h2 className="font-headline text-lg font-bold text-slate-100">Trained Repository</h2>
                    <p className="text-xs text-slate-500 mt-1">
                      Waiting files before batch indexing.
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="inline-flex items-center rounded-full border border-yellow-400 bg-yellow-400 px-3 py-1 text-[11px] font-semibold text-slate-950 font-mono">
                      {waitingRepositoryItems.length} waiting files
                    </span>
                    <button
                      type="button"
                      onClick={handleToggleAllRepository}
                      disabled={waitingRepositoryItems.length === 0 || isDeletingDocument}
                      className={`px-3 py-2 rounded-xl text-xs ${baseButtonClass} ${buttonTone.cyan}`}
                    >
                      {allRepositorySelected ? 'Deselect All' : 'Select All'}
                    </button>
                    <button
                      type="button"
                      onClick={handleDeleteSelectedRepository}
                      disabled={selectedRepositoryItems.length === 0 || isDeletingDocument}
                      className={`px-3 py-2 rounded-xl text-xs ${baseButtonClass} ${buttonTone.pink}`}
                    >
                      Delete Selected{selectedRepositoryItems.length > 0 ? ` (${selectedRepositoryItems.length})` : ''}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleStartAllIndexing()}
                      disabled={isIndexing || waitingRepositoryItems.length === 0}
                      className={`px-4 py-2 rounded-xl text-sm ${baseButtonClass} ${buttonTone.yellow}`}
                    >
                      {isIndexing ? 'Indexing...' : 'Index All'}
                    </button>
                  </div>
                </div>

                <div className="hidden md:grid grid-cols-[32px_minmax(0,1.7fr)_110px_minmax(0,1fr)_78px] gap-4 pt-4 pb-2 text-[10px] uppercase tracking-wider text-slate-600 font-mono">
                  <span className="text-center">Select</span>
                  <span>Document</span>
                  <span>Status</span>
                  <span>Repository Note</span>
                  <span className="text-right">Action</span>
                </div>

                <div className="flex-1 min-h-0">
                  {repositoryPageItems.length > 0 ? (
                    repositoryPageItems.map(renderRepositoryItem)
                  ) : (
                    <div className="h-full min-h-[190px] flex items-center justify-center text-center text-sm text-slate-500 px-6">
                      No waiting files yet. Upload files first, then they will appear here before indexing.
                    </div>
                  )}
                </div>

                {renderPagination(waitingRepositoryItems.length, totalRepositoryPages, repositoryPage, setRepositoryPage)}
              </div>
            </section>

            <section className="bg-transparent border border-white/10 rounded-[1.2rem] p-5 md:p-6 animate-fade-in-up" style={{ animationDelay: '0.6s' }}>
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-4 border-b border-white/5">
                <div>
                  <h2 className="font-headline text-lg font-bold text-slate-100">Upload Queue from Database</h2>
                  <p className="text-xs text-slate-500 mt-1">
                    Files move here only after you click Index All. Indexed means the pipeline has finished.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center rounded-full border border-cyan-400 bg-cyan-400 px-3 py-1 text-[11px] font-semibold text-slate-950 font-mono">
                    {pipelineFiles} pipeline files
                  </span>
                  <button
                    type="button"
                    onClick={handleToggleAllQueue}
                    disabled={uploadQueueItems.length === 0 || isDeletingDocument}
                    className={`px-3 py-2 rounded-xl text-xs ${baseButtonClass} ${buttonTone.cyan}`}
                  >
                    {allQueueSelected ? 'Deselect All' : 'Select All'}
                  </button>
                  <button
                    type="button"
                    onClick={handleDeleteSelectedQueue}
                    disabled={selectedQueueItems.length === 0 || isDeletingDocument}
                    className={`px-3 py-2 rounded-xl text-xs ${baseButtonClass} ${buttonTone.pink}`}
                  >
                    Delete Selected{selectedQueueItems.length > 0 ? ` (${selectedQueueItems.length})` : ''}
                  </button>
                  {isLoading && <span className="text-xs text-cyan-300 font-mono animate-pulse">Loading...</span>}
                </div>
              </div>

              <div className="hidden lg:grid grid-cols-[32px_minmax(0,1.6fr)_110px_minmax(0,1fr)_minmax(0,1.25fr)_86px] gap-4 pt-4 pb-2 text-[10px] uppercase tracking-wider text-slate-600 font-mono">
                <span className="text-center">Select</span>
                <span>Document</span>
                <span>Status</span>
                <span>Progress</span>
                <span>Pipeline Note</span>
                <span className="text-right">Action</span>
              </div>

              <div>
                {queuePageItems.length > 0 ? (
                  queuePageItems.map(renderQueueItem)
                ) : (
                  <div className="min-h-[170px] flex items-center justify-center text-center text-sm text-slate-500 px-6">
                    No pipeline files yet. Start batch indexing from the Trained Repository.
                  </div>
                )}
              </div>

              {renderPagination(uploadQueueItems.length, totalQueuePages, queuePage, setQueuePage)}
            </section>
          </div>
        </div>
      </main>

      {deleteTargets.length > 0 && (
        <div
          className="fixed inset-0 z-[110] flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-file-title"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) handleCancelDelete();
          }}
        >
          <div className="w-full max-w-md overflow-hidden rounded-2xl border border-pink-400/40 bg-[#101827] shadow-[0_24px_80px_rgba(0,0,0,0.55)]">
            <div className="flex items-start gap-4 border-b border-white/10 p-5">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-pink-300 bg-pink-400 text-slate-950">
                <span className="material-symbols-outlined">delete</span>
              </div>
              <div className="min-w-0">
                <h2 id="delete-file-title" className="font-headline text-lg font-bold text-white">
                  {deleteTargets.length === 1 ? 'Delete this file?' : `Delete ${deleteTargets.length} files?`}
                </h2>
                <p className="mt-1 text-sm leading-6 text-slate-400">
                  {deleteTargets.length === 1
                    ? 'Are you sure you want to delete this file? This action will remove it from the repository and cannot be undone.'
                    : 'Are you sure you want to delete all selected files? They will be removed from the repository and this action cannot be undone.'}
                </p>
              </div>
            </div>

            <div className="max-h-60 space-y-2 overflow-y-auto p-5 custom-scrollbar">
              {deleteTargets.slice(0, 8).map((target) => (
                <div key={target.id} className="flex items-center gap-3 rounded-xl border border-white/10 bg-slate-950/40 px-4 py-3">
                  <span className="material-symbols-outlined text-pink-300">description</span>
                  <p className="min-w-0 truncate text-sm font-semibold text-slate-100">
                    {target.filename}
                  </p>
                </div>
              ))}
              {deleteTargets.length > 8 && (
                <p className="px-1 text-xs font-mono text-slate-500">
                  +{deleteTargets.length - 8} more files selected
                </p>
              )}
            </div>

            <div className="flex flex-col-reverse gap-3 border-t border-white/10 p-5 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={handleCancelDelete}
                disabled={isDeletingDocument}
                className={`h-10 rounded-xl px-5 text-sm ${baseButtonClass} ${buttonTone.cyan}`}
              >
                No, Cancel
              </button>
              <button
                type="button"
                onClick={() => void handleConfirmDelete()}
                disabled={isDeletingDocument}
                className={`h-10 rounded-xl px-5 text-sm ${baseButtonClass} ${buttonTone.pink}`}
              >
                {isDeletingDocument
                  ? 'Deleting...'
                  : deleteTargets.length === 1
                    ? 'Yes, Delete'
                    : `Yes, Delete ${deleteTargets.length} Files`}
              </button>
            </div>
          </div>
        </div>
      )}

      {duplicateFiles.length > 0 && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="duplicate-upload-title"
        >
          <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-yellow-400/40 bg-[#101827] shadow-[0_24px_80px_rgba(0,0,0,0.55)]">
            <div className="flex items-start gap-4 border-b border-white/10 p-5">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-yellow-300 bg-yellow-400 text-slate-950">
                <span className="material-symbols-outlined">warning</span>
              </div>
              <div>
                <h2 id="duplicate-upload-title" className="font-headline text-lg font-bold text-white">
                  {duplicateFiles.length === 1
                    ? 'File already exists'
                    : 'Files already exist'}
                </h2>
                <p className="mt-1 text-sm leading-6 text-slate-400">
                  {duplicateFiles.length === 1
                    ? 'This file was uploaded previously. Are you sure you want to replace it with the newly selected file?'
                    : 'These files were uploaded previously. Are you sure you want to replace them with the newly selected files?'}
                </p>
              </div>
            </div>

            <div className="max-h-56 space-y-2 overflow-y-auto p-5 custom-scrollbar">
              {duplicateFiles.map((file) => (
                <div key={`${file.name}-${file.size}-${file.lastModified}`} className="flex items-center gap-3 rounded-xl border border-white/10 bg-slate-950/40 px-4 py-3">
                  <span className="material-symbols-outlined text-yellow-300">description</span>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-100">{file.name}</p>
                    <p className="text-xs font-mono text-slate-500">New file · {formatBytes(file.size)}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex flex-col-reverse gap-3 border-t border-white/10 p-5 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={handleCancelDuplicateUpload}
                className={`h-10 rounded-xl px-5 text-sm ${baseButtonClass} ${buttonTone.pink}`}
              >
                No, Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDuplicateUpload}
                className={`h-10 rounded-xl px-5 text-sm ${baseButtonClass} ${buttonTone.yellow}`}
              >
                Yes, Replace
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};