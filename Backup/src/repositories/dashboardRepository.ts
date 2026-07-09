import type {
  QueryResultRow,
} from 'pg';

import { query } from '../config/database.js';

export type ChatAnalyticsRange =
  | 'daily'
  | 'weekly'
  | 'monthly'
  | 'yearly';

export interface SummaryRow extends QueryResultRow {
  total_documents: string | number;
  indexed_documents: string | number;
  processing_documents: string | number;
  failed_documents: string | number;
  total_chunks: string | number;
  total_conversations: string | number;
  total_user_messages: string | number;
  total_assistant_messages: string | number;
  total_queries: string | number;
  answered_queries: string | number;
  need_review_queries: string | number;
  failed_queries: string | number;
  average_confidence: string | number;
  average_response_time_ms: string | number;
  queries_last_24h: string | number;
  queries_last_7d: string | number;
  queries_last_30d: string | number;

  // Alias lama agar dashboardService lama tidak langsung rusak.
  average_response_time_seconds: string | number;
  total_chats: string | number;
  total_unique_users: string | number;
}

export interface AnalyticsRow extends QueryResultRow {
  label: string;
  total_chats: string | number;
  unique_users: string | number;
}

const analyticsConfig = (
  range: ChatAnalyticsRange
): {
  bucketSql: string;
  labelSql: string;
  intervalSql: string;
} => {
  switch (range) {
    case 'daily':
      return {
        bucketSql: `date_trunc('hour', created_at)`,
        labelSql: `to_char(date_trunc('hour', created_at), 'HH24:00')`,
        intervalSql: '1 day',
      };

    case 'weekly':
      return {
        bucketSql: `date_trunc('day', created_at)`,
        labelSql: `to_char(date_trunc('day', created_at), 'YYYY-MM-DD')`,
        intervalSql: '7 days',
      };

    case 'monthly':
      return {
        bucketSql: `date_trunc('day', created_at)`,
        labelSql: `to_char(date_trunc('day', created_at), 'YYYY-MM-DD')`,
        intervalSql: '1 month',
      };

    case 'yearly':
      return {
        bucketSql: `date_trunc('month', created_at)`,
        labelSql: `to_char(date_trunc('month', created_at), 'YYYY-MM')`,
        intervalSql: '1 year',
      };

    default:
      return {
        bucketSql: `date_trunc('day', created_at)`,
        labelSql: `to_char(date_trunc('day', created_at), 'YYYY-MM-DD')`,
        intervalSql: '7 days',
      };
  }
};

export const findDashboardSummaryRow = async (): Promise<SummaryRow | null> => {
  const result = await query<SummaryRow>(
    `
      select
        total_documents,
        indexed_documents,
        processing_documents,
        failed_documents,
        total_chunks,
        total_conversations,
        total_user_messages,
        total_assistant_messages,
        total_queries,
        answered_queries,
        need_review_queries,
        failed_queries,
        average_confidence,
        average_response_time_ms,
        queries_last_24h,
        queries_last_7d,
        queries_last_30d,

        -- Alias lama
        (average_response_time_ms / 1000.0) as average_response_time_seconds,
        total_queries as total_chats,
        total_conversations as total_unique_users
      from public.dashboard_summary_view
    `
  );

  return result.rows[0] ?? null;
};

export const listChatAnalyticsRows = async (
  range: ChatAnalyticsRange
): Promise<AnalyticsRow[]> => {
  const config = analyticsConfig(range);

  const result = await query<AnalyticsRow>(
    `
      select
        ${config.labelSql} as label,
        count(*)::text as total_chats,
        count(distinct user_id)::text as unique_users
      from public.query_logs
      where created_at >= now() - $1::interval
      group by ${config.bucketSql}, ${config.labelSql}
      order by ${config.bucketSql} asc
    `,
    [config.intervalSql]
  );

  return result.rows;
};
