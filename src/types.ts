export interface AttachedFile {
  name: string;
}

export interface Message {
  id: string;
  role: 'user' | 'ai' | 'system';
  content: string;
  time?: string;
  attachments?: AttachedFile[];
  confidence?: number;
  source?: string;
}