import React, { useRef } from 'react';
import { AttachedFile } from '../types';

interface ChatFooterProps {
  inputValue: string;
  setInputValue: (val: string) => void;
  attachedFiles: AttachedFile[];
  onRemoveAttachment: (index: number) => void;
  onAttachFileClick: () => void;
  onMicClick: () => void;
  isRecording: boolean;
  isGenerating: boolean;
  onSendMessage: () => void;
  onClearChat: () => void;
}

export const ChatFooter: React.FC<ChatFooterProps> = ({
  inputValue, setInputValue, attachedFiles, onRemoveAttachment, onAttachFileClick, onMicClick, isRecording, isGenerating, onSendMessage, onClearChat
}) => {
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
    <footer className="p-3 md:p-6 bg-surface/90 backdrop-blur-md border-t border-outline-variant absolute bottom-0 left-0 right-0 z-20">
      <div className="max-w-4xl mx-auto flex flex-col gap-2 md:gap-3">
        <div className="relative group bg-surface-container border border-outline-variant rounded-xl md:rounded-2xl focus-within:ring-1 focus-within:ring-primary focus-within:border-primary transition-all shadow-sm flex flex-col overflow-hidden">
          
          {attachedFiles.length > 0 && (
            <div className="w-full bg-surface-container-high border-b border-outline-variant px-3 py-2 flex gap-2 items-center overflow-x-auto custom-scrollbar">
              {attachedFiles.map((file, index) => (
                <div key={index} className="flex items-center gap-1.5 md:gap-2 bg-surface-variant border border-outline-variant px-2 py-1 rounded-md shrink-0 animate-fadeIn">
                  <span className="material-symbols-outlined text-[12px] md:text-[14px] text-primary">draft</span>
                  <span className="text-[10px] md:text-[11px] font-mono text-on-surface truncate max-w-[80px] md:max-w-[120px]">{file.name}</span>
                  <button onClick={() => onRemoveAttachment(index)} className="text-outline hover:text-error flex items-center justify-center p-0.5">
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
              className="w-full bg-transparent border-none focus:ring-0 py-3 md:py-3.5 px-3 md:px-4 pr-[110px] md:pr-[120px] text-[13px] md:text-sm text-on-surface placeholder:text-outline/50 resize-none max-h-24 md:max-h-32 overflow-y-auto custom-scrollbar leading-relaxed outline-none" 
              placeholder={isRecording ? "Mendengarkan suara Anda..." : "Ketik pertanyaan..."}
              value={inputValue}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
            />
            
            <div className="absolute right-1.5 bottom-[5px] md:bottom-[7px] flex items-center gap-1">
              <button onClick={onMicClick} className={`p-1.5 transition-colors rounded-lg flex items-center justify-center ${isRecording ? 'text-error recording' : 'text-outline hover:text-primary hover:bg-surface-variant'}`} title="Voice to Text">
                <span className="material-symbols-outlined text-[20px] md:text-[22px]">mic</span>
              </button>
              
              <button onClick={onAttachFileClick} className="p-1.5 text-outline hover:text-primary hover:bg-surface-variant transition-colors rounded-lg flex items-center justify-center">
                <span className="material-symbols-outlined text-[20px] md:text-[22px]">attach_file</span>
              </button>
              
              <button 
                onClick={onSendMessage} 
                className={`p-1.5 rounded-lg transition-all active:scale-95 flex items-center justify-center ${isGenerating ? 'bg-surface-variant hover:bg-outline-variant' : 'bg-primary hover:bg-primary-container'}`}
              >
                <span className={`material-symbols-outlined icon-filled text-[20px] md:text-[22px] ${isGenerating ? 'text-error' : 'text-on-primary-container'}`}>
                  {isGenerating ? 'stop_circle' : 'send'}
                </span>
              </button>
            </div>
          </div>
        </div>
        
        <div className="flex justify-between items-center px-1 md:px-2 mt-1">
          <button onClick={onClearChat} className="flex items-center gap-1 text-outline hover:text-error transition-colors font-mono text-[9px] md:text-[10px]">
            <span className="material-symbols-outlined text-[12px] md:text-[14px]">delete</span> Hapus Obrolan
          </button>
          <div className="flex gap-3 md:gap-4 text-[9px] md:text-[10px] font-mono text-outline">
            <span className="hidden sm:flex items-center gap-1"><span className="material-symbols-outlined text-[12px] md:text-[14px]">fact_check</span> Metadata & Markdown</span>
            <span className="flex items-center gap-1"><span className="material-symbols-outlined text-[12px] md:text-[14px]">verified_user</span> Secure</span>
          </div>
        </div>
      </div>
    </footer>
  );
};