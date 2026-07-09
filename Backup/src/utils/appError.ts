export type AppErrorCode =
  | 'AUTH_EXPIRED'
  | 'AUTH_REQUIRED'
  | 'INVALID_CREDENTIALS'
  | 'VALIDATION_ERROR'
  | 'ENDPOINT_NOT_FOUND'
  | 'CONVERSATION_NOT_FOUND'
  | 'RAG_NO_CONTEXT'
  | 'AI_PROVIDER_ERROR'
  | 'EMBEDDING_FAILED'
  | 'DOCUMENT_EMPTY'
  | 'DOCUMENT_PARSE_FAILED'
  | 'DOCUMENT_TOO_LARGE'
  | 'RATE_LIMITED'
  | 'INTERNAL_SERVER_ERROR';

export interface AppErrorOptions {
  code: AppErrorCode;
  message: string;
  statusCode?: number;
  detail?: unknown;
  retryAfterSeconds?: number;
  expose?: boolean;
}

export class AppError extends Error {
  code: AppErrorCode;
  statusCode: number;
  detail?: unknown;
  retryAfterSeconds?: number;
  expose: boolean;

  constructor(options: AppErrorOptions) {
    super(options.message);
    this.name = 'AppError';
    this.code = options.code;
    this.statusCode = options.statusCode ?? 500;
    this.detail = options.detail;
    this.retryAfterSeconds = options.retryAfterSeconds;
    this.expose = options.expose ?? this.statusCode < 500;
  }
}

export const isAppError = (error: unknown): error is AppError => {
  return error instanceof AppError;
};

export const createValidationError = (
  message: string,
  detail?: unknown
): AppError => {
  return new AppError({
    code: 'VALIDATION_ERROR',
    statusCode: 400,
    message,
    detail,
  });
};

export const createUnauthorizedError = (
  message = 'Sesi tidak valid atau sudah kedaluwarsa.'
): AppError => {
  return new AppError({
    code: 'AUTH_EXPIRED',
    statusCode: 401,
    message,
  });
};
