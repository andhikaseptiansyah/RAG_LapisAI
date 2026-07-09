import type {
  RepositoryDocument,
} from './documentService';

import {
  apiRequest,
  buildQueryString,
} from './api';

export type ChatRange =
  | 'daily'
  | 'weekly'
  | 'monthly'
  | 'yearly';

export interface ChatMetricPoint {
  label: string;
  totalChats: number;
  uniqueUsers: number;
}

export interface DashboardSummary {
  totalDocuments: number;
  totalChunks: number;
  averageResponseTime: number;
  totalChats: number;
  totalUniqueUsers: number;
}

export interface DashboardChatSummary {
  totalChatCount: number;
  totalUniqueUsers: number;
  averageChatCount: number;
  peakLabel: string;
  peakTotalChats: number;
}

export interface DashboardResponse {
  summary: DashboardSummary;
  chatSummary: DashboardChatSummary;
  analytics: ChatMetricPoint[];
  documents: RepositoryDocument[];
}

export interface DashboardParams {
  range?: ChatRange;
  documentSearch?: string;
  documentPage?: number;
  documentLimit?: number;
}

export const getDashboardData = async (
  params: DashboardParams = {},
  signal?: AbortSignal
): Promise<DashboardResponse> => {
  const query = buildQueryString({
    range: params.range ?? 'daily',
    documentSearch: params.documentSearch,
    documentPage: params.documentPage ?? 1,
    documentLimit: params.documentLimit ?? 5,
  });

  return apiRequest<DashboardResponse>(
    `/api/admin/dashboard${query}`,
    {
      method: 'GET',
      signal,
    }
  );
};

export const getChatAnalytics = async (
  range: ChatRange,
  signal?: AbortSignal
): Promise<ChatMetricPoint[]> => {
  const query = buildQueryString({ range });

  return apiRequest<ChatMetricPoint[]>(
    `/api/admin/dashboard/chat-analytics${query}`,
    {
      method: 'GET',
      signal,
    }
  );
};

export const getDashboardSummary = async (
  signal?: AbortSignal
): Promise<DashboardSummary> => {
  return apiRequest<DashboardSummary>(
    '/api/admin/dashboard/summary',
    {
      method: 'GET',
      signal,
    }
  );
};
