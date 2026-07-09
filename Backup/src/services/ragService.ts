import { generateAnswer, type AiMessage } from './aiService.js';
import { AppError } from '../utils/appError.js';
import { retrieveChunksWithPython, type PythonRetrievedChunk } from './pythonRagService.js';

export type ChatLanguage = 'ID' | 'EN';

export interface RetrievedChunk {
  chunkId: string;
  documentId: string;
  documentName: string;
  page: string;
  content: string;
  score: number;
}

export interface RagAnswerInput {
  question: string;
  language: ChatLanguage;
  conversationHistory?: AiMessage[];
  topK?: number;
}

export interface RagAnswerResult {
  answer: string;
  confidence: number;
  sources: RetrievedChunk[];
  model: string;
  provider: string;
}

const DEFAULT_TOP_K = Number(process.env.RAG_TOP_K ?? 5);
const MIN_RELEVANCE_SCORE = Number(process.env.RAG_MIN_SCORE ?? 0.2);
const MAX_CONTEXT_CHARS = Number(process.env.RAG_MAX_CONTEXT_CHARS ?? 6000);

const truncateText = (text: string, maxChars: number): string => {
  if (text.length <= maxChars) {
    return text;
  }

  return `${text.slice(0, maxChars).trim()}...`;
};

const serializeSourcesForPrompt = (chunks: RetrievedChunk[]): string => {
  if (chunks.length === 0) {
    return 'Tidak ada konteks dokumen yang relevan ditemukan.';
  }

  let usedChars = 0;
  const serializedChunks: string[] = [];

  for (const [index, chunk] of chunks.entries()) {
    const remainingChars = MAX_CONTEXT_CHARS - usedChars;

    if (remainingChars <= 0) {
      break;
    }

    const safeContent = truncateText(chunk.content, remainingChars);

    const block = [
      `[Sumber ${index + 1}]`,
      `Dokumen: ${chunk.documentName}`,
      `Halaman: ${chunk.page}`,
      `Relevansi: ${chunk.score.toFixed(3)}`,
      `Isi: ${safeContent}`,
    ].join('\n');

    serializedChunks.push(block);
    usedChars += block.length;
  }

  return serializedChunks.join('\n\n');
};

const buildSystemPrompt = (language: ChatLanguage): string => {
  if (language === 'EN') {
    return [
      'You are LapisAI, a document-grounded assistant.',
      'Answer using the retrieved context when it is relevant.',
      'If the retrieved context is empty or insufficient, say that the uploaded documents do not provide enough evidence.',
      'Do not invent citations, page numbers, policies, or facts.',
      'Use clear and concise English.',
    ].join(' ');
  }

  return [
    'Anda adalah LapisAI, asisten yang menjawab berdasarkan dokumen.',
    'Gunakan konteks dokumen jika relevan.',
    'Jika konteks kosong atau tidak cukup, katakan bahwa dokumen yang tersedia belum menyediakan bukti yang cukup.',
    'Jangan mengarang sitasi, nomor halaman, kebijakan, atau fakta.',
    'Gunakan bahasa Indonesia yang jelas dan ringkas.',
  ].join(' ');
};

const buildUserPrompt = (
  question: string,
  chunks: RetrievedChunk[],
  language: ChatLanguage
): string => {
  const context = serializeSourcesForPrompt(chunks);

  if (language === 'EN') {
    return [
      'Retrieved context:',
      context,
      '',
      'User question:',
      question,
      '',
      'Answer based on the context above. If the context is insufficient, say so clearly.',
    ].join('\n');
  }

  return [
    'Konteks yang ditemukan:',
    context,
    '',
    'Pertanyaan pengguna:',
    question,
    '',
    'Jawab berdasarkan konteks di atas. Jika konteks tidak cukup, sampaikan dengan jelas.',
  ].join('\n');
};

const mapRetrievedChunk = (row: PythonRetrievedChunk): RetrievedChunk => ({
  chunkId: row.chunkId,
  documentId: row.documentId,
  documentName: row.documentName,
  page: row.page || '-',
  content: row.content,
  score: Number(row.score ?? 0),
});

export const retrieveRelevantChunks = async (
  question: string,
  topK = DEFAULT_TOP_K
): Promise<RetrievedChunk[]> => {
  const cleanQuestion = question.trim();

  if (!cleanQuestion) {
    return [];
  }

  try {
    const rows = await retrieveChunksWithPython(
      cleanQuestion,
      topK,
      MIN_RELEVANCE_SCORE
    );

    return rows.map(mapRetrievedChunk);
  } catch (error) {
    console.error('[RAG_SERVICE] Python retrieval failed:', error);

    return [];
  }
};

const calculateConfidence = (chunks: RetrievedChunk[]): number => {
  if (chunks.length === 0) {
    return 45;
  }

  const averageScore =
    chunks.reduce((sum, chunk) => sum + chunk.score, 0) / chunks.length;

  return Math.max(
    55,
    Math.min(95, Math.round(averageScore * 100))
  );
};

export const answerWithRag = async (
  input: RagAnswerInput
): Promise<RagAnswerResult> => {
  const question = input.question.trim();

  if (!question) {
    throw new Error('Pertanyaan RAG tidak boleh kosong.');
  }

  const chunks = await retrieveRelevantChunks(
    question,
    input.topK ?? DEFAULT_TOP_K
  );

  if (chunks.length === 0) {
    throw new AppError({
      code: 'RAG_NO_CONTEXT',
      statusCode: 404,
      message:
        input.language === 'EN'
          ? 'The uploaded documents do not contain relevant information for this question.'
          : 'Dokumen yang tersedia belum memuat informasi yang relevan untuk pertanyaan ini.',
    });
  }

  const messages: AiMessage[] = [
    {
      role: 'system',
      content: buildSystemPrompt(input.language),
    },
    ...(input.conversationHistory ?? []).slice(-6),
    {
      role: 'user',
      content: buildUserPrompt(question, chunks, input.language),
    },
  ];

  const aiResult = await generateAnswer({
    messages,
    temperature: 0.2,
    maxTokens: 900,
  });

  return {
    answer: aiResult.answer,
    confidence: calculateConfidence(chunks),
    sources: chunks,
    model: aiResult.model,
    provider: aiResult.provider,
  };
};