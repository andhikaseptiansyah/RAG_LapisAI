import {
  clearStoredAuth,
  getStoredAuthToken,
} from './authStorage';

const API_BASE_URL = (
  import.meta.env.VITE_API_URL ||
  'http://127.0.0.1:8000'
).replace(/\/+$/, '');

export type ApiErrorCode =
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
  | 'INTERNAL_SERVER_ERROR'
  | 'NETWORK_ERROR'
  | 'UNKNOWN_ERROR';

export interface ApiErrorPayload {
  code?: ApiErrorCode | string;
  message?: string;
  statusCode?: number;
  retryAfterSeconds?: number;
  path?: string;
  method?: string;
  timestamp?: string;
  detail?: unknown;
}

export class ApiError extends Error {
  status: number;
  code: ApiErrorCode;
  data: unknown;
  retryAfterSeconds?: number;

  constructor(
    message: string,
    status: number,
    data: unknown = null,
    code: ApiErrorCode = 'UNKNOWN_ERROR',
    retryAfterSeconds?: number
  ) {
    super(message);

    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.data = data;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

export interface ApiRequestOptions<TBody = unknown>
  extends Omit<RequestInit, 'body' | 'headers'> {
  body?: TBody;
  token?: string;
  headers?: HeadersInit;

  /**
   * Default: true.
   * Kalau false, API tidak akan auto redirect ke /login saat 401.
   */
  redirectOnUnauthorized?: boolean;

  /**
   * Default: false.
   * Pakai true hanya untuk endpoint validasi sesi, misalnya /api/auth/me.
   */
  forceLogoutOnUnauthorized?: boolean;
}

const isApiErrorPayload = (
  value: unknown
): value is ApiErrorPayload => {
  return (
    typeof value === 'object' &&
    value !== null
  );
};

const parseResponse = async (
  response: Response
): Promise<unknown> => {
  if (response.status === 204) {
    return null;
  }

  const contentType =
    response.headers.get('content-type') ?? '';

  if (contentType.includes('application/json')) {
    return response.json();
  }

  const text = await response.text();
  return text || null;
};

const redirectToLogin = (): void => {
  const currentPath =
    window.location.pathname +
    window.location.search;

  if (window.location.pathname === '/login') {
    return;
  }

  window.location.href = `/login?redirect=${encodeURIComponent(
    currentPath
  )}`;
};

const shouldClearAuthOnUnauthorized = (
  endpoint: string,
  forceLogoutOnUnauthorized: boolean
): boolean => {
  if (forceLogoutOnUnauthorized) {
    return true;
  }

  return endpoint !== '/api/auth/login';
};

const normalizeErrorCode = (
  value: unknown,
  status: number
): ApiErrorCode => {
  if (typeof value === 'string') {
    const allowedCodes: ApiErrorCode[] = [
      'AUTH_EXPIRED',
      'AUTH_REQUIRED',
      'INVALID_CREDENTIALS',
      'VALIDATION_ERROR',
      'ENDPOINT_NOT_FOUND',
      'CONVERSATION_NOT_FOUND',
      'RAG_NO_CONTEXT',
      'AI_PROVIDER_ERROR',
      'EMBEDDING_FAILED',
      'DOCUMENT_EMPTY',
      'DOCUMENT_PARSE_FAILED',
      'DOCUMENT_TOO_LARGE',
      'RATE_LIMITED',
      'INTERNAL_SERVER_ERROR',
      'NETWORK_ERROR',
      'UNKNOWN_ERROR',
    ];

    if (
      allowedCodes.includes(
        value as ApiErrorCode
      )
    ) {
      return value as ApiErrorCode;
    }
  }

  if (status === 401) return 'AUTH_EXPIRED';
  if (status === 404) return 'ENDPOINT_NOT_FOUND';
  if (status === 429) return 'RATE_LIMITED';
  if (status >= 500) return 'INTERNAL_SERVER_ERROR';

  return 'UNKNOWN_ERROR';
};

export const getFriendlyApiErrorMessage = (
  error: unknown
): string => {
  if (!(error instanceof ApiError)) {
    return error instanceof Error
      ? error.message
      : 'Terjadi kesalahan tidak dikenal.';
  }

  switch (error.code) {
    case 'AUTH_EXPIRED':
    case 'AUTH_REQUIRED':
      return 'Sesi kamu sudah habis. Silakan login ulang.';

    case 'INVALID_CREDENTIALS':
      return error.message || 'Username atau password salah.';

    case 'ENDPOINT_NOT_FOUND':
      return 'Endpoint tidak ditemukan. Periksa URL API dan route backend.';

    case 'CONVERSATION_NOT_FOUND':
      return 'Percakapan tidak ditemukan atau sudah dihapus.';

    case 'RAG_NO_CONTEXT':
      return 'Dokumen yang tersedia belum memuat informasi yang relevan untuk pertanyaan ini.';

    case 'AI_PROVIDER_ERROR':
      return 'Layanan AI sedang gagal merespons. Periksa konfigurasi provider atau coba lagi nanti.';

    case 'EMBEDDING_FAILED':
      return 'Embedding dokumen atau pertanyaan gagal dibuat.';

    case 'DOCUMENT_EMPTY':
      return 'Dokumen kosong atau tidak memiliki teks yang bisa dibaca.';

    case 'DOCUMENT_PARSE_FAILED':
      return 'Dokumen gagal dibaca. Periksa format atau isi file.';

    case 'DOCUMENT_TOO_LARGE':
      return 'Dokumen terlalu besar untuk diproses.';

    case 'RATE_LIMITED': {
      const suffix = error.retryAfterSeconds
        ? ` Coba lagi dalam ${error.retryAfterSeconds} detik.`
        : ' Coba lagi beberapa saat.';

      return `Terlalu banyak request.${suffix}`;
    }

    case 'INTERNAL_SERVER_ERROR':
      return 'Server mengalami gangguan. Coba lagi nanti.';

    case 'NETWORK_ERROR':
      return 'Frontend tidak bisa terhubung ke backend. Pastikan server backend menyala.';

    default:
      return error.message || 'Request gagal diproses.';
  }
};

export const apiRequest = async <
  TResponse,
  TBody = unknown
>(
  endpoint: string,
  options: ApiRequestOptions<TBody> = {}
): Promise<TResponse> => {
  const {
    body,
    token,
    headers: customHeaders,
    redirectOnUnauthorized = true,
    forceLogoutOnUnauthorized = false,
    ...requestOptions
  } = options;

  const headers = new Headers(customHeaders);

  headers.set('Accept', 'application/json');

  const authToken = token ?? getStoredAuthToken();

  if (authToken) {
    headers.set('Authorization', `Bearer ${authToken}`);
  }

  let requestBody: BodyInit | undefined;

  if (body instanceof FormData) {
    requestBody = body;
  } else if (body !== undefined && body !== null) {
    headers.set('Content-Type', 'application/json');
    requestBody = JSON.stringify(body);
  }

  let response: Response;

  try {
    response = await fetch(
      `${API_BASE_URL}${endpoint}`,
      {
        ...requestOptions,
        headers,
        body: requestBody,
        credentials: 'include',
      }
    );
  } catch (error) {
    if (
      error instanceof DOMException &&
      error.name === 'AbortError'
    ) {
      throw error;
    }

    const message =
      error instanceof Error
        ? error.message
        : 'Tidak dapat terhubung ke server.';

    throw new ApiError(
      message,
      0,
      null,
      'NETWORK_ERROR'
    );
  }

  const responseData = await parseResponse(response);

  if (!response.ok) {
    const payload = isApiErrorPayload(responseData)
      ? responseData
      : null;

    const code = normalizeErrorCode(
      payload?.code,
      response.status
    );

    const retryAfterFromHeader = Number(
      response.headers.get('Retry-After') ?? ''
    );

    const retryAfterSeconds =
      typeof payload?.retryAfterSeconds === 'number'
        ? payload.retryAfterSeconds
        : Number.isFinite(retryAfterFromHeader)
          ? retryAfterFromHeader
          : undefined;

    let errorMessage =
      `Request gagal dengan status ${response.status}`;

    if (
      payload?.message &&
      typeof payload.message === 'string'
    ) {
      errorMessage = payload.message;
    } else if (typeof responseData === 'string') {
      errorMessage = responseData;
    }

    const apiError = new ApiError(
      errorMessage,
      response.status,
      responseData,
      code,
      retryAfterSeconds
    );

    if (
      response.status === 401 &&
      redirectOnUnauthorized
    ) {
      console.warn(
        'Unauthorized API request:',
        endpoint,
        responseData
      );

      if (
        shouldClearAuthOnUnauthorized(
          endpoint,
          forceLogoutOnUnauthorized
        )
      ) {
        clearStoredAuth();
        redirectToLogin();
      }
    }

    throw apiError;
  }

  return responseData as TResponse;
};

export type QueryValue =
  | string
  | number
  | boolean
  | null
  | undefined;

export const buildQueryString = (
  params: Record<string, QueryValue>
): string => {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (
      value === undefined ||
      value === null ||
      value === ''
    ) {
      return;
    }

    searchParams.set(key, String(value));
  });

  const queryString = searchParams.toString();

  return queryString ? `?${queryString}` : '';
};
