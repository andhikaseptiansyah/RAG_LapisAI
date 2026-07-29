export interface AttachedFile {
  name: string;
  size?: number;
  type?: string;
  file?: File;
}

export interface MessageSource {
  documentName: string;
  documentType?: 'pdf' | 'docx' | 'txt' | string;
  page?: string | number;
  pageIsReliable?: boolean;
  relevanceScore?: number;
  excerpt?: string;
  chapter?: string;
  section?: string;
  paragraphStart?: number;
  paragraphEnd?: number;
  lineStart?: number;
  lineEnd?: number;
}

export interface Message {
  id: string;
  role: 'user' | 'ai' | 'assistant' | 'system';
  content: string;
  time?: string;
  attachments?: AttachedFile[];
  confidence?: number;
  source?: string;
  page?: string | number;
  sources?: MessageSource[];
  responseTimeMs?: number;
  followUpQuestion?: string;
  shouldAnimate?: boolean;
}

export type ModelType = 'ollama' | 'gemini' | 'groq';
