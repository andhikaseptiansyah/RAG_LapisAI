export interface ChunkingOptions {
  maxChars?: number;
  overlapChars?: number;
  minChars?: number;
}

export interface TextChunk {
  index: number;
  content: string;
  charStart: number;
  charEnd: number;
  pageNumber?: number;
  metadata: Record<string, unknown>;
}

export interface PageText {
  pageNumber: number;
  text: string;
}

const DEFAULT_MAX_CHARS = 1_200;
const DEFAULT_OVERLAP_CHARS = 200;
const DEFAULT_MIN_CHARS = 80;

export const normalizeDocumentText = (text: string): string => {
  return text
    .replace(/\r\n/g, '\n')
    .replace(/\t/g, ' ')
    .replace(/[ \u00A0]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
};

const splitIntoParagraphs = (text: string): string[] => {
  return normalizeDocumentText(text)
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);
};

const splitLongText = (text: string, maxChars: number): string[] => {
  if (text.length <= maxChars) return [text];

  const sentences = text
    .split(/(?<=[.!?。！？])\s+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean);

  if (sentences.length <= 1) {
    const chunks: string[] = [];

    for (let start = 0; start < text.length; start += maxChars) {
      chunks.push(text.slice(start, start + maxChars).trim());
    }

    return chunks.filter(Boolean);
  }

  const chunks: string[] = [];
  let current = '';

  for (const sentence of sentences) {
    const candidate = current ? `${current} ${sentence}` : sentence;

    if (candidate.length > maxChars && current) {
      chunks.push(current.trim());
      current = sentence;
    } else {
      current = candidate;
    }
  }

  if (current.trim()) chunks.push(current.trim());

  return chunks;
};

const createOverlap = (text: string, overlapChars: number): string => {
  if (overlapChars <= 0 || text.length <= overlapChars) {
    return '';
  }

  return text.slice(-overlapChars).trim();
};

export const chunkText = (
  text: string,
  options: ChunkingOptions = {}
): TextChunk[] => {
  const maxChars = options.maxChars ?? DEFAULT_MAX_CHARS;
  const overlapChars = options.overlapChars ?? DEFAULT_OVERLAP_CHARS;
  const minChars = options.minChars ?? DEFAULT_MIN_CHARS;

  if (maxChars <= overlapChars) {
    throw new Error('maxChars harus lebih besar dari overlapChars.');
  }

  const normalizedText = normalizeDocumentText(text);

  if (!normalizedText) return [];

  const paragraphs = splitIntoParagraphs(normalizedText)
    .flatMap((paragraph) => splitLongText(paragraph, maxChars));

  const chunks: TextChunk[] = [];
  let current = '';
  let cursor = 0;

  for (const paragraph of paragraphs) {
    const candidate = current ? `${current}\n\n${paragraph}` : paragraph;

    if (candidate.length > maxChars && current.length >= minChars) {
      const charStart = Math.max(cursor - current.length, 0);
      const charEnd = cursor;

      chunks.push({
        index: chunks.length,
        content: current.trim(),
        charStart,
        charEnd,
        metadata: {
          strategy: 'paragraph-window',
          maxChars,
          overlapChars,
        },
      });

      const overlap = createOverlap(current, overlapChars);
      current = overlap ? `${overlap}\n\n${paragraph}` : paragraph;
    } else {
      current = candidate;
    }

    cursor += paragraph.length + 2;
  }

  if (current.trim().length >= minChars || chunks.length === 0) {
    chunks.push({
      index: chunks.length,
      content: current.trim(),
      charStart: Math.max(cursor - current.length, 0),
      charEnd: cursor,
      metadata: {
        strategy: 'paragraph-window',
        maxChars,
        overlapChars,
      },
    });
  }

  return chunks;
};

export const chunkPages = (
  pages: PageText[],
  options: ChunkingOptions = {}
): TextChunk[] => {
  const chunks: TextChunk[] = [];

  for (const page of pages) {
    const pageChunks = chunkText(page.text, options).map((chunk) => ({
      ...chunk,
      index: chunks.length + chunk.index,
      pageNumber: page.pageNumber,
      metadata: {
        ...chunk.metadata,
        pageNumber: page.pageNumber,
      },
    }));

    chunks.push(...pageChunks);
  }

  return chunks.map((chunk, index) => ({
    ...chunk,
    index,
  }));
};