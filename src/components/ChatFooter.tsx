import React, { useRef } from 'react';
import { AttachedFile } from '../types';
import { useUiLanguage } from '../i18n/LanguageContext';

interface ChatFooterProps {
  inputValue: string;
  setInputValue: (val: string) => void;
  attachedFiles: AttachedFile[];
  onRemoveAttachment: (index: number) => void;
  onMicClick: () => void;
  isRecording: boolean;
  isGenerating: boolean;
  onSendMessage: () => void;
  onClearChat: () => void;
}

export const ChatFooter: React.FC<ChatFooterProps> = ({
  inputValue, setInputValue, attachedFiles, onRemoveAttachment, onMicClick, isRecording, isGenerating, onSendMessage
}) => {
  const { t } = useUiLanguage();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isGenerating) onSendMessage();
    }
  };

  return (
    <footer className="p-3 md:p-5 bg-transparent absolute bottom-0 left-0 right-0 z-20">
      <div className="max-w-3xl mx-auto flex flex-col gap-2 md:gap-3">
        <div className="relative group bg-[#20232d]/95 border border-white/10 rounded-[28px] md:rounded-[30px] transition-all flex flex-col overflow-visible shadow-[0_10px_30px_rgba(0,0,0,0.18)]">
          {attachedFiles.length > 0 && (
            <div className="w-full px-3 pt-2 pb-1 flex gap-2 items-center overflow-x-auto custom-scrollbar">
              {attachedFiles.map((file, index) => (
                <div key={index} className="flex items-center gap-1.5 md:gap-2 border border-white/15 px-2 py-1 rounded-md shrink-0 animate-fadeIn text-white/70">
                  <span className="material-symbols-outlined text-[12px] md:text-[14px]">draft</span>
                  <span className="text-[10px] md:text-[11px] font-mono truncate max-w-[80px] md:max-w-[120px]">{file.name}</span>
                  <button
                    onClick={() => onRemoveAttachment(index)}
                    className="text-white/45 hover:text-white flex items-center justify-center p-0.5"
                    aria-label={`${t('delete')} ${file.name}`}
                  >
                    <span className="material-symbols-outlined text-[12px] md:text-[14px]">close</span>
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="relative w-full flex items-end">
            <textarea
              ref={textareaRef}
              rows={1}
              className="w-full bg-transparent border-none focus:ring-0 py-2.5 md:py-3 pl-4 md:pl-5 pr-[78px] md:pr-[86px] text-[13px] md:text-sm text-white placeholder:text-white/45 resize-none max-h-20 md:max-h-28 overflow-y-auto custom-scrollbar leading-relaxed outline-none"
              placeholder={
                isRecording
                  ? t('listening')
                  : t('assistantPlaceholder')
              }
              value={inputValue}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
            />

            <div className="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center gap-1">
              <button
                onClick={onMicClick}
                className={`p-1.5 transition-colors rounded-full flex items-center justify-center ${isRecording ? 'text-error recording' : 'text-white/55 hover:text-white'}`}
                title={t('speechToText')}
                aria-label={t('speechToText')}
              >
                <span className="flex items-center justify-center gap-[2px] w-5 h-5" aria-hidden="true">
                  <span className="w-[2px] h-2.5 bg-current rounded-full"></span>
                  <span className="w-[2px] h-4 bg-current rounded-full"></span>
                  <span className="w-[2px] h-5 bg-current rounded-full"></span>
                  <span className="w-[2px] h-4 bg-current rounded-full"></span>
                  <span className="w-[2px] h-2.5 bg-current rounded-full"></span>
                </span>
              </button>

              <button
                onClick={onSendMessage}
                className="w-8 h-8 md:w-9 md:h-9 rounded-full transition-all active:scale-95 flex items-center justify-center bg-primary text-on-primary-container hover:bg-primary-container"
                title={isGenerating ? t('stopResponse') : t('sendMessage')}
                aria-label={isGenerating ? t('stopResponse') : t('sendMessage')}
              >
                <span className={`material-symbols-outlined icon-filled text-[20px] md:text-[22px] ${isGenerating ? 'text-error' : ''}`}>
                  {isGenerating ? 'stop_circle' : 'send'}
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};
