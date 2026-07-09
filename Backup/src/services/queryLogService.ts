import {
  deleteQueryLogById,
  findQueryLogRowById,
  listQueryLogRows,
  loadQueryLogPerformanceRow,
  type QueryLogFilters,
  type QueryLogStatus,
  type QueryRange,
  type QueryLogRow,
  type SourceRecord,
} from '../repositories/queryLogRepository.js';

export type {
  QueryLogFilters,
  QueryLogStatus,
  QueryRange,
};

export interface RetrievedSource {
  documentName: string;
  page: string;
  chunkId: string;
  relevanceScore: number;
}

export interface QueryLogItem {
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

const mapQueryLog = (
  row: QueryLogRow
): QueryLogItem => ({
  queryId: row.query_id,
  userName: row.user_name ?? 'Anonymous',
  userQuestion: row.user_question,
  timestamp: row.timestamp.toISOString(),
  retrievedDocuments: (
    row.retrieved_documents ?? []
  ).map((source: SourceRecord) => ({
    documentName:
      source.documentName ??
      'Dokumen tidak tersedia',
    page:
      source.page === null ||
      source.page === undefined
        ? '-'
        : String(source.page),
    chunkId: source.chunkId ?? '-',
    relevanceScore: Number(
      source.relevanceScore ?? 0
    ),
  })),
  answerGenerated: row.answer_generated ?? '',
  confidenceScore: Number(
    row.confidence_score ?? 0
  ),
  responseTime: `${(
    Number(row.response_time_ms ?? 0) / 1000
  ).toFixed(2)} s`,
  status: row.status,
});

export const listQueryLogs = async (
  filters: QueryLogFilters
) => {
  const result = await listQueryLogRows(
    filters
  );

  return {
    logs: result.rows.map(mapQueryLog),
    total: result.total,
    page: result.page,
    limit: result.limit,
    totalPages: result.totalPages,
  };
};

export const loadQueryLogsDashboard = async (
  filters: QueryLogFilters
) => {
  const list = await listQueryLogs(filters);
  const row = await loadQueryLogPerformanceRow(
    filters
  );

  return {
    ...list,
    performance: {
      totalQueries: Number(
        row?.total_queries ?? 0
      ),
      answered: Number(row?.answered ?? 0),
      notFound: Number(row?.not_found ?? 0),
      needReview: Number(
        row?.need_review ?? 0
      ),
      errors: Number(row?.errors ?? 0),
      averageConfidence: Number(
        Number(
          row?.average_confidence ?? 0
        ).toFixed(2)
      ),
      averageResponseTime: Number(
        (
          Number(
            row?.average_response_time ?? 0
          ) / 1000
        ).toFixed(2)
      ),
    },
  };
};

export const findQueryLogById = async (
  queryId: string
): Promise<QueryLogItem | null> => {
  const row = await findQueryLogRowById(
    queryId
  );

  return row ? mapQueryLog(row) : null;
};

export const removeQueryLog = async (
  queryId: string
): Promise<boolean> => {
  return deleteQueryLogById(queryId);
};
