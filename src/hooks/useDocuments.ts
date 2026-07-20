import {
  useCallback,
  useEffect,
  useState,
} from 'react';

import {
  deleteDocument,
  getDocuments,
  getTrainedDocuments,
  getUploadQueue,
  reindexDocument,
  startDocumentIndexing,
  uploadDocuments,
} from '../services/documentService';

import type {
  DocumentListParams,
  RepositoryDocument,
  TrainedDocument,
  UploadItem,
} from '../services/documentService';

interface UseDocumentsOptions {
  initialPage?: number;
  initialLimit?: number;
  autoLoad?: boolean;
}

export const useDocuments = (
  options: UseDocumentsOptions = {}
) => {
  const {
    initialPage = 1,
    initialLimit = 10,
    autoLoad = true,
  } = options;

  const [documents, setDocuments] =
    useState<RepositoryDocument[]>([]);

  const [uploadItems, setUploadItems] =
    useState<UploadItem[]>([]);

  const [
    trainedDocuments,
    setTrainedDocuments,
  ] = useState<TrainedDocument[]>([]);

  const [search, setSearchState] =
    useState('');

  const [page, setPageState] =
    useState(initialPage);

  const [limit, setLimitState] =
    useState(initialLimit);

  const [total, setTotal] =
    useState(0);

  const [totalPages, setTotalPages] =
    useState(1);

  const [isLoading, setIsLoading] =
    useState(false);

  const [isUploading, setIsUploading] =
    useState(false);

  const [isIndexing, setIsIndexing] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const loadDocuments = useCallback(
    async (
      overrides: Partial<DocumentListParams> = {}
    ): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        const result = await getDocuments({
          search,
          page,
          limit,
          ...overrides,
        });

        setDocuments(result.documents);
        setTotal(result.total);
        setTotalPages(
          Math.max(result.totalPages, 1)
        );
      } catch (caughtError) {
        const message =
          caughtError instanceof Error
            ? caughtError.message
            : 'Gagal mengambil daftar dokumen';

        setError(message);
      } finally {
        setIsLoading(false);
      }
    },
    [limit, page, search]
  );

  const loadUploadItems =
    useCallback(async (): Promise<void> => {
      try {
        const result =
          await getUploadQueue();

        setUploadItems(result);
      } catch (caughtError) {
        const message =
          caughtError instanceof Error
            ? caughtError.message
            : 'Gagal mengambil antrean upload';

        setError(message);
      }
    }, []);

  const loadTrainedDocuments =
    useCallback(async (): Promise<void> => {
      try {
        const result =
          await getTrainedDocuments();

        setTrainedDocuments(
          result.documents
        );
      } catch (caughtError) {
        const message =
          caughtError instanceof Error
            ? caughtError.message
            : 'Gagal mengambil dokumen terindeks';

        setError(message);
      }
    }, []);

  const refreshAll =
    useCallback(async (): Promise<void> => {
      await Promise.all([
        loadDocuments(),
        loadUploadItems(),
        loadTrainedDocuments(),
      ]);
    }, [
      loadDocuments,
      loadTrainedDocuments,
      loadUploadItems,
    ]);

  const uploadFiles = useCallback(
    async (
      files: File[],
      replaceFilenames: string[] = []
    ): Promise<boolean> => {
      if (files.length === 0) {
        setError(
          'Pilih minimal satu file untuk diunggah'
        );

        return false;
      }

      setIsUploading(true);
      setError(null);

      try {
        const result =
          await uploadDocuments(
            files,
            replaceFilenames
          );

        setUploadItems(
          result.uploadItems
        );

        await Promise.all([
          loadDocuments(),
          loadUploadItems(),
          loadTrainedDocuments(),
        ]);

        return true;
      } catch (caughtError) {
        const message =
          caughtError instanceof Error
            ? caughtError.message
            : 'Gagal mengunggah dokumen';

        setError(message);

        return false;
      } finally {
        setIsUploading(false);
      }
    },
    [
      loadDocuments,
      loadTrainedDocuments,
      loadUploadItems,
    ]
  );

  const startIndexing = useCallback(
    async (
      documentIds?: string[]
    ): Promise<boolean> => {
      setIsIndexing(true);
      setError(null);

      try {
        const result =
          await startDocumentIndexing(
            documentIds
          );

        setUploadItems(
          result.uploadItems
        );

        await Promise.all([
          loadDocuments(),
          loadUploadItems(),
          loadTrainedDocuments(),
        ]);

        return true;
      } catch (caughtError) {
        const message =
          caughtError instanceof Error
            ? caughtError.message
            : 'Gagal memulai indexing';

        setError(message);

        return false;
      } finally {
        setIsIndexing(false);
      }
    },
    [
      loadDocuments,
      loadTrainedDocuments,
      loadUploadItems,
    ]
  );

  const reindex = useCallback(
    async (
      documentId: string
    ): Promise<boolean> => {
      setError(null);

      try {
        const updatedDocument =
          await reindexDocument(documentId);

        setUploadItems(
          (currentItems) => {
            const documentExists =
              currentItems.some(
                (item) =>
                  item.id === documentId
              );

            if (!documentExists) {
              return [
                updatedDocument,
                ...currentItems,
              ];
            }

            return currentItems.map(
              (item) =>
                item.id === documentId
                  ? updatedDocument
                  : item
            );
          }
        );

        await Promise.all([
          loadDocuments(),
          loadUploadItems(),
          loadTrainedDocuments(),
        ]);

        return true;
      } catch (caughtError) {
        const message =
          caughtError instanceof Error
            ? caughtError.message
            : 'Gagal melakukan re-index dokumen';

        setError(message);

        return false;
      }
    },
    [
      loadDocuments,
      loadTrainedDocuments,
      loadUploadItems,
    ]
  );

  const removeDocument = useCallback(
    async (
      documentId: string
    ): Promise<boolean> => {
      setError(null);

      try {
        await deleteDocument(documentId);

        setDocuments(
          (currentDocuments) =>
            currentDocuments.filter(
              (document) =>
                document.id !== documentId
            )
        );

        setUploadItems(
          (currentItems) =>
            currentItems.filter(
              (item) =>
                item.id !== documentId
            )
        );

        setTrainedDocuments(
          (currentDocuments) =>
            currentDocuments.filter(
              (document) =>
                document.id !== documentId
            )
        );

        setTotal((currentTotal) =>
          Math.max(currentTotal - 1, 0)
        );

        return true;
      } catch (caughtError) {
        const message =
          caughtError instanceof Error
            ? caughtError.message
            : 'Gagal menghapus dokumen';

        setError(message);

        return false;
      }
    },
    []
  );

  const setSearch = useCallback(
    (value: string) => {
      setSearchState(value);
      setPageState(1);
    },
    []
  );

  const setPage = useCallback(
    (value: number) => {
      setPageState(
        Math.max(
          1,
          Math.min(value, totalPages)
        )
      );
    },
    [totalPages]
  );

  const setLimit = useCallback(
    (value: number) => {
      setLimitState(Math.max(value, 1));
      setPageState(1);
    },
    []
  );

  useEffect(() => {
    if (!autoLoad) {
      return;
    }

    const timeoutId =
      window.setTimeout(() => {
        void loadDocuments();
      }, 300);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [
    autoLoad,
    loadDocuments,
  ]);

  useEffect(() => {
    if (!autoLoad) {
      return;
    }

    void loadUploadItems();
    void loadTrainedDocuments();
  }, [
    autoLoad,
    loadTrainedDocuments,
    loadUploadItems,
  ]);

  useEffect(() => {
    const hasActiveIndexing =
      uploadItems.some((item) =>
        [
          'Parsing',
          'Chunking',
          'Embedding',
        ].includes(item.status)
      );

    if (!hasActiveIndexing) {
      return;
    }

    const intervalId =
      window.setInterval(() => {
        void loadUploadItems();
        void loadDocuments();
        void loadTrainedDocuments();
      }, 1500);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [
    loadDocuments,
    loadTrainedDocuments,
    loadUploadItems,
    uploadItems,
  ]);

  return {
    documents,
    uploadItems,
    trainedDocuments,

    search,
    page,
    limit,
    total,
    totalPages,

    isLoading,
    isUploading,
    isIndexing,

    error,
    clearError,

    setSearch,
    setPage,
    setLimit,

    loadDocuments,
    loadUploadItems,
    loadTrainedDocuments,
    refreshAll,

    uploadFiles,
    startIndexing,
    reindex,
    removeDocument,
  };
};