import path from 'node:path';
import { fileURLToPath } from 'node:url';
import dotenv from 'dotenv';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Paksa backend selalu membaca file:
 * backend/.env
 *
 * Jadi meskipun server dijalankan dari folder root atau folder backend,
 * env tetap konsisten.
 */
dotenv.config({
  path: path.resolve(__dirname, '../../.env'),
});

type NodeEnvironment =
  | 'development'
  | 'test'
  | 'production';

const getRequiredEnv = (key: string): string => {
  const value = process.env[key]?.trim();

  if (!value) {
    throw new Error(
      `Environment variable ${key} belum diatur.`
    );
  }

  return value;
};

const getOptionalEnv = (
  key: string,
  defaultValue = ''
): string => {
  const value = process.env[key]?.trim();

  return value || defaultValue;
};

const getNumberEnv = (
  key: string,
  defaultValue: number
): number => {
  const rawValue = process.env[key];

  if (
    rawValue === undefined ||
    rawValue.trim() === ''
  ) {
    return defaultValue;
  }

  const parsedValue = Number(rawValue);

  if (!Number.isFinite(parsedValue)) {
    throw new Error(
      `Environment variable ${key} harus berupa angka.`
    );
  }

  return parsedValue;
};

const getBooleanEnv = (
  key: string,
  defaultValue: boolean
): boolean => {
  const rawValue =
    process.env[key]?.trim().toLowerCase();

  if (!rawValue) {
    return defaultValue;
  }

  if (
    ['true', '1', 'yes', 'on'].includes(
      rawValue
    )
  ) {
    return true;
  }

  if (
    ['false', '0', 'no', 'off'].includes(
      rawValue
    )
  ) {
    return false;
  }

  throw new Error(
    `Environment variable ${key} harus bernilai true atau false.`
  );
};

const parseNodeEnvironment =
  (): NodeEnvironment => {
    const value = getOptionalEnv(
      'NODE_ENV',
      'development'
    );

    const allowedValues: NodeEnvironment[] = [
      'development',
      'test',
      'production',
    ];

    if (
      !allowedValues.includes(
        value as NodeEnvironment
      )
    ) {
      throw new Error(
        'NODE_ENV harus bernilai development, test, atau production.'
      );
    }

    return value as NodeEnvironment;
  };

const getJwtSecret = (): string => {
  const value = getRequiredEnv('JWT_SECRET');

  if (value.length < 32) {
    throw new Error(
      'JWT_SECRET minimal harus 32 karakter.'
    );
  }

  return value;
};

export const env = Object.freeze({
  NODE_ENV: parseNodeEnvironment(),

  PORT: getNumberEnv('PORT', 5000),

  FRONTEND_URL: getOptionalEnv(
    'FRONTEND_URL',
    'http://localhost:5173'
  ),

  DATABASE_URL: getRequiredEnv(
    'DATABASE_URL'
  ),

  DATABASE_SSL: getBooleanEnv(
    'DATABASE_SSL',
    false
  ),

  DATABASE_SSL_REJECT_UNAUTHORIZED:
    getBooleanEnv(
      'DATABASE_SSL_REJECT_UNAUTHORIZED',
      true
    ),

  DATABASE_POOL_MAX: getNumberEnv(
    'DATABASE_POOL_MAX',
    10
  ),

  DATABASE_IDLE_TIMEOUT_MS:
    getNumberEnv(
      'DATABASE_IDLE_TIMEOUT_MS',
      30_000
    ),

  DATABASE_CONNECTION_TIMEOUT_MS:
    getNumberEnv(
      'DATABASE_CONNECTION_TIMEOUT_MS',
      10_000
    ),

  AI_PROVIDER: getOptionalEnv(
    'AI_PROVIDER',
    'groq'
  ),

  AI_BASE_URL: getOptionalEnv(
    'AI_BASE_URL',
    'https://api.groq.com/openai/v1'
  ),

  AI_API_KEY: getOptionalEnv(
    'AI_API_KEY'
  ),

  AI_MODEL: getOptionalEnv(
    'AI_MODEL',
    'llama-3.3-70b-versatile'
  ),

  AI_TIMEOUT_MS: getNumberEnv(
    'AI_TIMEOUT_MS',
    60_000
  ),

  EMBEDDING_PROVIDER: getOptionalEnv(
    'EMBEDDING_PROVIDER',
    'fallback'
  ),

  EMBEDDING_MODEL: getOptionalEnv(
    'EMBEDDING_MODEL',
    'fallback-hash-embedding'
  ),

  FALLBACK_EMBEDDING_DIMENSION:
    getNumberEnv(
      'FALLBACK_EMBEDDING_DIMENSION',
      384
    ),

  RAG_TOP_K: getNumberEnv(
    'RAG_TOP_K',
    5
  ),

  RAG_MIN_SCORE: Number(
    getOptionalEnv('RAG_MIN_SCORE', '0.2')
  ),

  RAG_MAX_CONTEXT_CHARS:
    getNumberEnv(
      'RAG_MAX_CONTEXT_CHARS',
      6000
    ),

  RAG_PYTHON_URL: getOptionalEnv(
    'RAG_PYTHON_URL',
    'http://localhost:8001'
  ),

  RAG_PYTHON_TIMEOUT_MS:
    getNumberEnv(
      'RAG_PYTHON_TIMEOUT_MS',
      120_000
    ),

  JWT_SECRET: getJwtSecret(),

  JWT_EXPIRES_IN: getOptionalEnv(
    'JWT_EXPIRES_IN',
    '30d'
  ),

  STAFF_USERNAME: getOptionalEnv(
    'STAFF_USERNAME'
  ),

  STAFF_PASSWORD: getOptionalEnv(
    'STAFF_PASSWORD'
  ),

  STAFF_NAME: getOptionalEnv(
    'STAFF_NAME',
    'Staff User'
  ),

  ADMIN_USERNAME: getOptionalEnv(
    'ADMIN_USERNAME'
  ),

  ADMIN_PASSWORD: getOptionalEnv(
    'ADMIN_PASSWORD'
  ),

  ADMIN_NAME: getOptionalEnv(
    'ADMIN_NAME',
    'System Admin'
  ),

  UPLOAD_DIR: getOptionalEnv(
    'UPLOAD_DIR',
    'uploads'
  ),

  MAX_FILE_SIZE_MB: getNumberEnv(
    'MAX_FILE_SIZE_MB',
    20
  ),

  ALLOWED_FILE_TYPES: getOptionalEnv(
    'ALLOWED_FILE_TYPES',
    'pdf,docx,txt'
  ),
});

export type AppEnvironment = typeof env;