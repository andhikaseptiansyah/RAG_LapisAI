import { useCallback, useEffect, useRef, useState } from 'react';

const stripMarkdown = (text: string): string => {
  return text
    .replace(/```[\s\S]*?```/g, '')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/__(.+?)__/g, '$1')
    .replace(/_(.+?)_/g, '$1')
    .replace(/~~(.+?)~~/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/^>\s+/gm, '')
    .replace(/^[-*+]\s+/gm, '')
    .replace(/^\d+\.\s+/gm, '')
    .replace(/---+/g, '')
    .replace(/\n{2,}/g, '\n')
    .trim();
};

const langToSpeechLang = (lang: 'ID' | 'EN'): string =>
  lang === 'ID' ? 'id-ID' : 'en-US';

export interface UseTTSReturn {
  speak: (text: string, lang: 'ID' | 'EN') => void;
  stop: () => void;
  isPlaying: boolean;
}

export const useTTS = (): UseTTSReturn => {
  const [isPlaying, setIsPlaying] = useState(false);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  const stop = useCallback(() => {
    window.speechSynthesis.cancel();
    utteranceRef.current = null;
    setIsPlaying(false);
  }, []);

  useEffect(() => {
    return () => {
      window.speechSynthesis.cancel();
    };
  }, []);

  const speak = useCallback(
    (text: string, lang: 'ID' | 'EN') => {
      if (!window.speechSynthesis) return;

      if (isPlaying) {
        stop();
        return;
      }

      const clean = stripMarkdown(text);
      if (!clean) return;

      const utterance = new SpeechSynthesisUtterance(clean);
      utterance.lang = langToSpeechLang(lang);

      const voices = window.speechSynthesis.getVoices();
      const match = voices.find((v) =>
        v.lang.startsWith(lang === 'ID' ? 'id' : 'en')
      );
      if (match) utterance.voice = match;

      utterance.onend = () => {
        setIsPlaying(false);
        utteranceRef.current = null;
      };

      utterance.onerror = () => {
        setIsPlaying(false);
        utteranceRef.current = null;
      };

      utteranceRef.current = utterance;
      setIsPlaying(true);
      window.speechSynthesis.speak(utterance);
    },
    [isPlaying, stop]
  );

  return { speak, stop, isPlaying };
};
