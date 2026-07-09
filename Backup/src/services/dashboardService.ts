import {
  findDashboardSummaryRow,
  listChatAnalyticsRows,
} from '../repositories/dashboardRepository.js';

import {
  listDocuments,
} from './documentService.js';

export type ChatRange =
  | 'daily'
  | 'weekly'
  | 'monthly'
  | 'yearly';

export interface DashboardInput {
  range: ChatRange;
  documentSearch?: string;
  documentPage: number;
  documentLimit: number;
}

export interface DashboardSummary {
  totalDocuments: number;
  totalChunks: number;
  averageResponseTime: number;
  totalChats: number;
  totalUniqueUsers: number;
}

export interface ChatMetricPoint {
  label: string;
  totalChats: number;
  uniqueUsers: number;
}

export interface DashboardChatSummary {
  totalChatCount: number;
  totalUniqueUsers: number;
  averageChatCount: number;
  peakLabel: string;
  peakTotalChats: number;
}

export const loadDashboardSummary = async (
): Promise<DashboardSummary> => {
  const row = await findDashboardSummaryRow();

  return {
    totalDocuments: Number(
      row?.total_documents ?? 0
    ),
    totalChunks: Number(
      row?.total_chunks ?? 0
    ),
    averageResponseTime: Number(
      row?.average_response_time_seconds ?? 0
    ),
    totalChats: Number(
      row?.total_chats ?? 0
    ),
    totalUniqueUsers: Number(
      row?.total_unique_users ?? 0
    ),
  };
};

export const loadChatAnalytics = async (
  range: ChatRange
): Promise<ChatMetricPoint[]> => {
  const rows = await listChatAnalyticsRows(
    range
  );

  return rows.map(
    (row): ChatMetricPoint => ({
      label: row.label,
      totalChats: Number(row.total_chats),
      uniqueUsers: Number(row.unique_users),
    })
  );
};

export const loadDashboard = async (
  input: DashboardInput
) => {
  const [summary, analytics, documentResult] =
    await Promise.all([
      loadDashboardSummary(),
      loadChatAnalytics(input.range),
      listDocuments({
        search: input.documentSearch,
        page: input.documentPage,
        limit: input.documentLimit,
      }),
    ]);

  const totalChatCount = analytics.reduce(
    (
      total: number,
      item: ChatMetricPoint
    ) => total + item.totalChats,
    0
  );

  const peak = analytics.reduce<ChatMetricPoint>(
    (currentPeak, item) =>
      item.totalChats > currentPeak.totalChats
        ? item
        : currentPeak,
    {
      label: '-',
      totalChats: 0,
      uniqueUsers: 0,
    }
  );

  const chatSummary: DashboardChatSummary = {
    totalChatCount,
    totalUniqueUsers: summary.totalUniqueUsers,
    averageChatCount:
      analytics.length > 0
        ? Number(
            (
              totalChatCount / analytics.length
            ).toFixed(2)
          )
        : 0,
    peakLabel: peak.label,
    peakTotalChats: peak.totalChats,
  };

  return {
    summary,
    chatSummary,
    analytics,
    documents: documentResult.documents,
  };
};
