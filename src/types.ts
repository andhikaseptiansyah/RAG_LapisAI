export interface AttachedFile {
  name: string;
  size?: number;
  type?: string;
  file?: File;
}

export interface MessageSource {
  documentName: string;
  page?: string | number;
  chunkId?: string;
  relevanceScore?: number;
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
  shouldAnimate?: boolean;
}

