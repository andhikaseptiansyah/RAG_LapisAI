import {
  apiRequest,
  buildQueryString,
} from './api';

export type QueryLogStatus =
  | 'ANSWERED'
  | 'NO_REFERENCE'
  | 'NOT_FOUND';

export type QueryRange =
  | 'daily'
  | 'weekly'
  | 'monthly'
  | 'yearly';

export interface RetrievedSource {
  documentName: string;
  page: string;
  chunkId: string;
  relevanceScore: number;
  excerpt?: string;
  section?: string;
  paragraphStart?: number;
  paragraphEnd?: number;
  lineStart?: number;
  lineEnd?: number;
}

export interface QueryLog {
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

export interface QueryLogListParams {
  range?: QueryRange;
  page?: number;
  limit?: number;
  status?: QueryLogStatus;
  search?: string;
}

export interface QueryLogListResponse {
  logs: QueryLog[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export interface QueryLogPerformance {
  totalQueries: number;
  answered: number;
  noReference: number;
  notFound: number;
  averageConfidence: number;
  averageResponseTime: number;
}

export interface QueryLogDashboardResponse {
  logs: QueryLog[];
  performance: QueryLogPerformance;
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export const getQueryLogs = async (
  params: QueryLogListParams = {},
  signal?: AbortSignal
): Promise<QueryLogListResponse> => {
  const query = buildQueryString({
    range: params.range ?? 'daily',
    page: params.page ?? 1,
    limit: params.limit ?? 25,
    status: params.status,
    search: params.search,
  });

  return apiRequest<QueryLogListResponse>(
    `/api/admin/query-logs${query}`,
    {
      method: 'GET',
      signal,
    }
  );
};

export const getQueryLogsDashboard = async (
  params: QueryLogListParams = {},
  signal?: AbortSignal
): Promise<QueryLogDashboardResponse> => {
  const query = buildQueryString({
    range: params.range ?? 'daily',
    page: params.page ?? 1,
    limit: params.limit ?? 25,
    status: params.status,
    search: params.search,
  });

  return apiRequest<QueryLogDashboardResponse>(
    `/api/admin/query-logs/dashboard${query}`,
    {
      method: 'GET',
      signal,
    }
  );
};

export const getQueryLogById = async (
  queryId: string,
  signal?: AbortSignal
): Promise<QueryLog> => {
  return apiRequest<QueryLog>(
    `/api/admin/query-logs/${encodeURIComponent(
      queryId
    )}`,
    {
      method: 'GET',
      signal,
    }
  );
};

export const deleteQueryLog = async (
  queryId: string
): Promise<void> => {
  await apiRequest<null>(
    `/api/admin/query-logs/${encodeURIComponent(
      queryId
    )}`,
    {
      method: 'DELETE',
    }
  );
};
