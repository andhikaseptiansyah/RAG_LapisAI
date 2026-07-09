import { env } from '../config/env.js';
import { AppError } from '../utils/appError.js';

export type AiRole = 'system' | 'user' | 'assistant';

export interface AiMessage {
  role: AiRole;
  content: string;
}

export interface GenerateAnswerInput {
  messages: AiMessage[];
  temperature?: number;
  maxTokens?: number;
  model?: string;
}

export interface GenerateAnswerResult {
  answer: string;
  model: string;
  provider: string;
}

interface GroqChatResponse {
  id?: string;
  object?: string;
  created?: number;
  model?: string;
  choices?: Array<{
    index?: number;
    message?: {
      role?: string;
      content?: string;
    };
    finish_reason?: string;
  }>;
  error?: {
    message?: string;
    type?: string;
    code?: string;
  };
}

const GROQ_BASE_URL = (
  process.env.AI_BASE_URL ?? 'https://api.groq.com/openai/v1'
).replace(/\/$/, '');

const DEFAULT_CHAT_MODEL =
  env.AI_MODEL ||
  process.env.GROQ_MODEL ||
  'llama-3.3-70b-versatile';

const DEFAULT_TIMEOUT_MS = Number(
  process.env.AI_TIMEOUT_MS ?? 60_000
);

const getProviderName = (): string => {
  return 'groq';
};

const buildHeaders = (): Record<string, string> => {
  if (!env.AI_API_KEY) {
    throw new AppError({
      code: 'AI_PROVIDER_ERROR',
      statusCode: 502,
      message: 'AI_API_KEY Groq belum diisi di file backend/.env.',
    });
  }

  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${env.AI_API_KEY}`,
  };
};

const parseGroqResponse = async (
  response: Response
): Promise<GroqChatResponse> => {
  const text = await response.text();

  if (!text) {
    throw new AppError({
      code: 'AI_PROVIDER_ERROR',
      statusCode: 502,
      message: 'Groq tidak mengembalikan response body.',
    });
  }

  try {
    return JSON.parse(text) as GroqChatResponse;
  } catch {
    throw new AppError({
      code: 'AI_PROVIDER_ERROR',
      statusCode: 502,
      message: 'Response Groq bukan JSON valid.',
      detail: text.slice(0, 500),
    });
  }
};

const normalizeProviderError = (
  error: unknown
): AppError => {
  if (error instanceof AppError) {
    return error;
  }

  if (
    error instanceof DOMException &&
    error.name === 'AbortError'
  ) {
    return new AppError({
      code: 'AI_PROVIDER_ERROR',
      statusCode: 504,
      message: 'Layanan AI timeout. Coba lagi nanti.',
    });
  }

  const message =
    error instanceof Error
      ? error.message
      : 'Layanan AI gagal merespons.';

  return new AppError({
    code: 'AI_PROVIDER_ERROR',
    statusCode: 502,
    message: `Layanan AI gagal: ${message}`,
    detail: error,
  });
};

export const generateAnswer = async (
  input: GenerateAnswerInput
): Promise<GenerateAnswerResult> => {
  const model = input.model ?? DEFAULT_CHAT_MODEL;

  const controller = new AbortController();

  const timeout = setTimeout(() => {
    controller.abort();
  }, DEFAULT_TIMEOUT_MS);

  try {
    const response = await fetch(`${GROQ_BASE_URL}/chat/completions`, {
      method: 'POST',
      headers: buildHeaders(),
      signal: controller.signal,
      body: JSON.stringify({
        model,
        messages: input.messages,
        temperature: input.temperature ?? 0.2,
        max_completion_tokens: input.maxTokens ?? 900,
      }),
    });

    const payload = await parseGroqResponse(response);

    if (!response.ok) {
      throw new AppError({
        code: 'AI_PROVIDER_ERROR',
        statusCode: response.status >= 500 ? 502 : response.status,
        message:
          payload.error?.message ??
          `Groq AI service gagal dengan status ${response.status}.`,
        detail: payload.error,
      });
    }

    const answer = payload.choices?.[0]?.message?.content?.trim();

    if (!answer) {
      throw new AppError({
        code: 'AI_PROVIDER_ERROR',
        statusCode: 502,
        message: 'Groq tidak mengembalikan jawaban.',
        detail: payload,
      });
    }

    return {
      answer,
      model: payload.model ?? model,
      provider: getProviderName(),
    };
  } catch (error) {
    const appError = normalizeProviderError(error);

    console.error('[GROQ_AI_SERVICE] generateAnswer failed:', appError);

    throw appError;
  } finally {
    clearTimeout(timeout);
  }
};
