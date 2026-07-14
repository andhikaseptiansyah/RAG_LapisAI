import {
  useCallback,
  useEffect,
  useState,
} from 'react';

import {
  getDashboardData,
} from '../services/dashboardService';

import type {
  ChatMetricPoint,
  ChatRange,
  DashboardChatSummary,
  DashboardResponse,
  DashboardSummary,
  RagSystemConfig,
} from '../services/dashboardService';

import type {
  RepositoryDocument,
} from '../services/documentService';

interface UseDashboardOptions {
  initialRange?: ChatRange;
  initialDocumentLimit?: number;
  autoLoad?: boolean;
}

export const useDashboard = (
  options: UseDashboardOptions = {}
) => {
  const {
    initialRange = 'daily',
    initialDocumentLimit = 5,
    autoLoad = true,
  } = options;

  const [range, setRangeState] =
    useState<ChatRange>(initialRange);

  const [
    documentSearch,
    setDocumentSearchState,
  ] = useState('');

  const [
    documentPage,
    setDocumentPageState,
  ] = useState(1);

  const [
    documentLimit,
    setDocumentLimitState,
  ] = useState(initialDocumentLimit);

  const [summary, setSummary] =
    useState<DashboardSummary | null>(
      null
    );

  const [
    chatSummary,
    setChatSummary,
  ] =
    useState<DashboardChatSummary | null>(
      null
    );

  const [analytics, setAnalytics] =
    useState<ChatMetricPoint[]>([]);

  const [documents, setDocuments] =
    useState<RepositoryDocument[]>([]);

  const [ragConfig, setRagConfig] =
    useState<RagSystemConfig | null>(null);

  const [isLoading, setIsLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const applyDashboardResult =
    useCallback(
      (result: DashboardResponse) => {
        setSummary(result.summary);
        setChatSummary(
          result.chatSummary
        );
        setAnalytics(result.analytics);
        setDocuments(result.documents);
        setRagConfig(result.ragConfig);
      },
      []
    );

  const loadDashboard =
    useCallback(async (): Promise<void> => {
      setIsLoading(true);
      setError(null);

      try {
        const result =
          await getDashboardData({
            range,
            documentSearch,
            documentPage,
            documentLimit,
          });

        applyDashboardResult(result);
      } catch (caughtError) {
        const message =
          caughtError instanceof Error
            ? caughtError.message
            : 'Gagal mengambil data dashboard';

        setError(message);
      } finally {
        setIsLoading(false);
      }
    }, [
      applyDashboardResult,
      documentLimit,
      documentPage,
      documentSearch,
      range,
    ]);

  const setRange = useCallback(
    (value: ChatRange) => {
      setRangeState(value);
    },
    []
  );

  const setDocumentSearch =
    useCallback((value: string) => {
      setDocumentSearchState(value);
      setDocumentPageState(1);
    }, []);

  const setDocumentPage =
    useCallback((value: number) => {
      setDocumentPageState(
        Math.max(value, 1)
      );
    }, []);

  const setDocumentLimit =
    useCallback((value: number) => {
      setDocumentLimitState(
        Math.max(value, 1)
      );

      setDocumentPageState(1);
    }, []);

  useEffect(() => {
    if (!autoLoad) {
      return;
    }

    const timeoutId =
      window.setTimeout(() => {
        void loadDashboard();
      }, 300);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [
    autoLoad,
    loadDashboard,
  ]);

  return {
    summary,
    chatSummary,
    analytics,
    documents,
    ragConfig,

    range,
    documentSearch,
    documentPage,
    documentLimit,

    isLoading,
    error,

    clearError,
    loadDashboard,

    setRange,
    setDocumentSearch,
    setDocumentPage,
    setDocumentLimit,
  };
};