import React from 'react';
import { useTTS } from '../hooks/useTTS';
import { useUiLanguage } from '../i18n/LanguageContext';

interface TTSButtonProps {
  text: string;
  language: 'ID' | 'EN';
}

const isSpeechSupported = (): boolean =>
  typeof window !== 'undefined' &&
  'speechSynthesis' in window;

export const TTSButton: React.FC<TTSButtonProps> = ({
  text,
  language,
}) => {
  const { speak, stop, isPlaying } = useTTS();
  const { language: uiLanguage } = useUiLanguage();

  if (!isSpeechSupported()) return null;

  const handleClick = () => {
    if (isPlaying) {
      stop();
    } else {
      speak(text, language);
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className={`p-0 text-[19px] transition-colors ${
        isPlaying
          ? 'text-[#AFC7FF] animate-pulse'
          : 'text-white/60 hover:text-white'
      }`}
      title={
        isPlaying
          ? uiLanguage === 'EN' ? 'Stop' : 'Hentikan'
          : uiLanguage === 'EN' ? 'Listen' : 'Dengarkan'
      }
      aria-label={
        isPlaying
          ? uiLanguage === 'EN' ? 'Stop text playback' : 'Hentikan pembacaan teks'
          : uiLanguage === 'EN' ? 'Play text aloud' : 'Putar pembacaan teks'
      }
    >
      <span className="material-symbols-outlined">
        {isPlaying ? 'stop_circle' : 'volume_up'}
      </span>
    </button>
  );
};
