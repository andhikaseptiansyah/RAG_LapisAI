import type {
  ErrorRequestHandler,
  NextFunction,
  Request,
  Response,
} from 'express';

import {
  AppError,
  isAppError,
  type AppErrorCode,
} from '../utils/appError.js';

interface ErrorLike {
  message?: string;
  status?: number;
  statusCode?: number;
  code?: string;
  detail?: unknown;
  stack?: string;
}

const isErrorLike = (
  error: unknown
): error is ErrorLike => {
  return (
    typeof error === 'object' &&
    error !== null
  );
};

const normalizeStatusCode = (
  statusCode: number
): number => {
  if (statusCode < 400 || statusCode > 599) {
    return 500;
  }

  return statusCode;
};

const getStatusCode = (
  error: unknown
): number => {
  if (isAppError(error)) {
    return normalizeStatusCode(error.statusCode);
  }

  if (!isErrorLike(error)) {
    return 500;
  }

  const statusCode =
    typeof error.statusCode === 'number'
      ? error.statusCode
      : typeof error.status === 'number'
        ? error.status
        : 500;

  return normalizeStatusCode(statusCode);
};

const getErrorCode = (
  error: unknown,
  statusCode: number
): AppErrorCode => {
  if (isAppError(error)) {
    return error.code;
  }

  if (statusCode === 401) {
    return 'AUTH_EXPIRED';
  }

  if (statusCode === 404) {
    return 'ENDPOINT_NOT_FOUND';
  }

  return 'INTERNAL_SERVER_ERROR';
};

const getSafeMessage = (
  error: unknown,
  statusCode: number
): string => {
  if (isAppError(error)) {
    return error.message;
  }

  if (statusCode === 401) {
    return 'Sesi tidak valid atau sudah kedaluwarsa. Silakan login ulang.';
  }

  if (statusCode === 404) {
    return 'Endpoint atau data tidak ditemukan.';
  }

  if (statusCode >= 500) {
    return 'Server mengalami gangguan. Coba lagi nanti.';
  }

  if (
    isErrorLike(error) &&
    typeof error.message === 'string' &&
    error.message.trim()
  ) {
    return error.message;
  }

  return 'Request tidak dapat diproses.';
};

export const errorMiddleware: ErrorRequestHandler =
  (
    error: unknown,
    req: Request,
    res: Response,
    _next: NextFunction
  ): void => {
    const statusCode = getStatusCode(error);
    const code = getErrorCode(error, statusCode);
    const message = getSafeMessage(error, statusCode);

    const payload: Record<string, unknown> = {
      code,
      message,
      statusCode,
      path: req.originalUrl,
      method: req.method,
      timestamp: new Date().toISOString(),
    };

    if (
      isAppError(error) &&
      typeof error.retryAfterSeconds === 'number'
    ) {
      payload.retryAfterSeconds = error.retryAfterSeconds;
    }

    if (
      process.env.NODE_ENV !== 'production' &&
      isErrorLike(error)
    ) {
      payload.detail = error.detail;
      payload.stack = error.stack;
    }

    console.error('[ERROR_MIDDLEWARE]', {
      method: req.method,
      path: req.originalUrl,
      statusCode,
      code,
      message,
      error,
    });

    res.status(statusCode).json(payload);
  };
