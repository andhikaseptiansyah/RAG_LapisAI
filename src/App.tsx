import React, { useState, useRef, useEffect } from 'react';
import { marked } from 'marked';
import { Message, AttachedFile } from './types';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { WelcomeScreen } from './components/WelcomeScreen';
import { ChatFooter } from './components/ChatFooter';
import { IntroAnimation } from './components/IntroAnimation';

type DetectedLanguage = 'ID' | 'EN';
type UploadMode = 'photo' | 'file';

const TypewriterMarkdown: React.FC<{ content: string; onTick?: () => void }> = ({ content, onTick }) => {
  const [visibleText, setVisibleText] = useState('');
  const [isDone, setIsDone] = useState(false);

  useEffect(() => {
    let index = 0;
    setVisibleText('');
    setIsDone(false);

    const typingInterval = window.setInterval(() => {
      index += 1;
      setVisibleText(content.slice(0, index));
      onTick?.();

      if (index >= content.length) {
        window.clearInterval(typingInterval);
        setIsDone(true);
      }
    }, 6);

    return () => window.clearInterval(typingInterval);
  }, [content]);

  return (
    <>
      <div
        className="prose prose-sm prose-invert prose-custom max-w-none text-on-surface leading-relaxed text-[13px] md:text-sm"
        dangerouslySetInnerHTML={{ __html: marked(visibleText) as string }}
      />
      {!isDone && <span className="inline-block w-1.5 h-4 ml-1 bg-primary/80 animate-pulse align-middle"></span>}
    </>
  );
};

export const App: React.FC = () => {
  const [showIntro, setShowIntro] = useState(true);
  const [isFirstMessage, setIsFirstMessage] = useState(true);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const [detectedLanguage, setDetectedLanguage] = useState<DetectedLanguage>('ID');
  
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const generateTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scrollButtonHideTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const recognitionRef = useRef<any>(null);

  // Fix real mobile browser height so the footer is not hidden behind the browser/navigation bar
  useEffect(() => {
    const setAppHeight = () => {
      document.documentElement.style.setProperty('--app-height', `${window.innerHeight}px`);
    };

    setAppHeight();
    window.addEventListener('resize', setAppHeight);
    window.addEventListener('orientationchange', setAppHeight);

    return () => {
      window.removeEventListener('resize', setAppHeight);
      window.removeEventListener('orientationchange', setAppHeight);
    };
  }, []);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    if (scrollButtonHideTimeoutRef.current) {
      clearTimeout(scrollButtonHideTimeoutRef.current);
    }

    setShowScrollBottom(false);

    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({ top: chatContainerRef.current.scrollHeight, behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isGenerating]);

  const handleScroll = () => {
    if (chatContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
      const shouldShowButton = scrollHeight - scrollTop - clientHeight > 100;

      setShowScrollBottom(shouldShowButton);

      if (scrollButtonHideTimeoutRef.current) {
        clearTimeout(scrollButtonHideTimeoutRef.current);
      }

      if (shouldShowButton) {
        scrollButtonHideTimeoutRef.current = setTimeout(() => {
          setShowScrollBottom(false);
        }, 2500);
      }
    }
  };

  useEffect(() => {
    return () => {
      if (scrollButtonHideTimeoutRef.current) {
        clearTimeout(scrollButtonHideTimeoutRef.current);
      }
    };
  }, []);

  const handleAttachFileClick = (mode: UploadMode = 'file') => {
    if (!fileInputRef.current) return;

    fileInputRef.current.accept =
      mode === 'photo'
        ? 'image/png,image/jpeg,image/jpg,image/webp'
        : '.pdf,.doc,.docx,.txt,.csv';

    fileInputRef.current.dataset.uploadMode = mode;
    fileInputRef.current.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files ?? []);
    const uploadMode = (e.currentTarget.dataset.uploadMode as UploadMode) || 'file';

    if (selectedFiles.length > 0) {
      const allowedDocumentExtensions = ['pdf', 'doc', 'docx', 'txt', 'csv'];
      const allowedPhotoTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp'];

      const validFiles = selectedFiles.filter((file) => {
        const extension = file.name.split('.').pop()?.toLowerCase() ?? '';

        if (uploadMode === 'photo') {
          return allowedPhotoTypes.includes(file.type);
        }

        return allowedDocumentExtensions.includes(extension);
      });

      if (validFiles.length !== selectedFiles.length) {
        alert(
          uploadMode === 'photo'
            ? 'Upload Foto hanya menerima PNG, JPG, JPEG, atau WEBP.'
            : 'Upload File hanya menerima PDF, DOC, DOCX, TXT, atau CSV.'
        );
      }

      if (validFiles.length > 0) {
        const newFiles = validFiles.map((file) => ({ name: file.name }));
        setAttachedFiles((prev) => [...prev, ...newFiles]);
        if (isFirstMessage) setIsFirstMessage(false);
      }
    }

    e.target.value = '';
  };

  const handleMicClick = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
      alert("Maaf, browser Anda tidak mendukung fitur mikrofon. Harap gunakan Google Chrome atau Edge.");
      return;
    }

    if (isRecording) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsRecording(false);
    } else {
      setIsRecording(true);
      if (isFirstMessage) setIsFirstMessage(false);
      
      const recognition = new SpeechRecognition();
      recognition.lang = detectedLanguage === 'EN' ? 'en-US' : 'id-ID';
      recognition.continuous = true;
      recognition.interimResults = true;

      const baseText = inputValue;

      recognition.onresult = (event: any) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          transcript += event.results[i][0].transcript;
        }
        setInputValue(baseText + (baseText ? " " : "") + transcript);
      };

      recognition.onerror = (event: any) => {
        console.error("Error mikrofon:", event.error);
        setIsRecording(false);
      };

      recognition.onend = () => {
        setIsRecording(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    }
  };

  const detectLanguage = (text: string): DetectedLanguage => {
    const normalizedText = text.toLowerCase().trim();

    if (!normalizedText) {
      return detectedLanguage;
    }

    const englishMatches = normalizedText.match(/\b(hello|hi|what|how|why|help|please|can|could|would|make|create|summarize|summary|report|file|document|template|system|finance|financial|explain|give|write)\b/g)?.length ?? 0;
    const indonesianMatches = normalizedText.match(/\b(hai|halo|apa|bagaimana|kenapa|tolong|bantu|buat|buatkan|rangkum|ringkas|laporan|berkas|dokumen|template|sistem|keuangan|jelaskan|berikan|tulis|saya|anda)\b/g)?.length ?? 0;

    return englishMatches > indonesianMatches ? 'EN' : 'ID';
  };

  const startGenerating = (text: string, files: AttachedFile[], language: DetectedLanguage) => {
    const confidence = Math.floor(Math.random() * (99 - 90 + 1) + 90);
    const lowerText = text.toLowerCase();
    const wantsReport = /laporan|report|template|financial|finance|keuangan/.test(lowerText);
    const wantsSummary = /rangkum|ringkas|summarize|summary|sop/.test(lowerText) || files.length > 0;
    let markdownRaw = "";

    if (language === 'EN') {
      if (wantsReport) {
        markdownRaw = `Here is your requested **Monthly Financial Report** draft based on the company system data:

### 📊 Financial Report - Q2 2026
This report includes a summary of cash flow and departmental operating expenses.

| Expense Category | Budget (IDR) | Actual (IDR) | Status |
|------------------|--------------|--------------|--------|
| Marketing & Ads  | 50,000,000   | 45,000,000   | ✅ Safe |
| Operations & IT  | 30,000,000   | 32,500,000   | ⚠️ *Overbudget* |
| Salary & Benefits | 150,000,000 | 150,000,000  | ✅ Safe |

**Recommended Actions:**
* Reduce Operations & IT costs in the next quarter.
* Allocate the remaining marketing budget to client retention programs.`;
      } else if (wantsSummary) {
        markdownRaw = `Based on the attached or requested document, here is the **Executive Summary**:

### 📋 SLA 2026 Policy Summary
The current procedure must follow the latest update standard.
* Make sure **Form 1A** (Submission) and **Form 2B** (Claim) are completed properly.
* All supporting documents must be scanned and converted into PDF format.

| Operational Category | Old SLA | New SLA (2026) | Change |
|----------------------|---------|----------------|--------|
| Leave Request        | 3 Days  | **1 Day**      | Faster |
| Medical Claim        | 5 Days  | **3 Days**     | Faster |

> **Note:** This update is estimated to reduce administrative processing time by up to **40%**.`;
      } else {
        markdownRaw = `Hello! I am ready to help. You can ask me to **summarize an attached document** or create a specific **report format**.`;
      }
    } else {
      if (wantsReport) {
        markdownRaw = `Berikut adalah draf **Laporan Keuangan Bulanan** berdasarkan data sistem perusahaan:

### 📊 Laporan Finansial - Q2 2026
Laporan ini mencakup ringkasan arus kas dan pengeluaran operasional departemen.

| Kategori Pengeluaran | Anggaran (IDR) | Realisasi (IDR) | Status |
|----------------------|----------------|-----------------|--------|
| Pemasaran & Iklan    | 50.000.000     | 45.000.000      | ✅ Aman |
| Operasional & IT     | 30.000.000     | 32.500.000      | ⚠️ *Overbudget* |
| Gaji & Tunjangan     | 150.000.000    | 150.000.000     | ✅ Aman |

**Rekomendasi Tindakan:**
* Segera lakukan efisiensi pada biaya Operasional & IT di kuartal berikutnya.
* Distribusi sisa anggaran Pemasaran dapat dialokasikan ke program retensi klien.`;
      } else if (wantsSummary) {
        markdownRaw = `Berdasarkan dokumen yang dilampirkan/diminta, berikut adalah **Rangkuman Eksekutif**:

### 📋 Ringkasan Ketentuan SLA 2026
Pelaksanaan prosedur saat ini harus mematuhi standar pembaruan terbaru.
* Pastikan **Formulir 1A** (Pengajuan) dan **Formulir 2B** (Klaim) diisi lengkap.
* Seluruh bukti pendukung wajib dipindai dan dikonversi ke format PDF.

| Kategori Operasional | SLA Lama | SLA Baru (2026) | Perubahan |
|----------------------|----------|-----------------|-----------|
| Pengajuan Cuti       | 3 Hari   | **1 Hari** | Lebih Cepat |
| Klaim Medis          | 5 Hari   | **3 Hari** | Lebih Cepat |

> **Catatan:** Pembaruan ini diestimasi akan memangkas waktu birokrasi administratif hingga **40%**.`;
      } else {
        markdownRaw = `Halo! Saya siap membantu. Anda bisa meminta saya untuk **merangkum dokumen** yang Anda lampirkan atau membuatkan **format laporan** tertentu.`;
      }
    }

    generateTimeoutRef.current = setTimeout(() => {
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'ai',
        content: markdownRaw,
        confidence,
        source: 'SOP_HRD_2026.pdf'
      }]);
      setIsGenerating(false);
    }, 2500);
  };

  const handleSendMessage = (text = inputValue, files = attachedFiles) => {
    if (isGenerating) {
      if (generateTimeoutRef.current) clearTimeout(generateTimeoutRef.current);
      setMessages(prev => [...prev, { id: Date.now().toString(), role: 'system', content: '[ Generation Stopped by User ]' }]);
      setIsGenerating(false);
      return;
    }

    if (!text.trim() && files.length === 0) return;

    if (isFirstMessage) setIsFirstMessage(false);
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      time,
      attachments: files
    }]);

    setInputValue('');
    setAttachedFiles([]);
    
    if (isRecording) {
      if (recognitionRef.current) recognitionRef.current.stop();
      setIsRecording(false);
    }
    
    const language = detectLanguage(text);
    setDetectedLanguage(language);

    setIsGenerating(true);
    startGenerating(text, files, language);
  };

  const handleClearChat = () => {
    if (window.confirm('Hapus seluruh riwayat obrolan di layar?')) {
      setMessages([]);
      setIsFirstMessage(true);
      setShowScrollBottom(false);
      if (isGenerating) {
        if (generateTimeoutRef.current) clearTimeout(generateTimeoutRef.current);
        setIsGenerating(false);
      }
      if (isRecording && recognitionRef.current) {
        recognitionRef.current.stop();
        setIsRecording(false);
      }
    }
  };

  return (
    <div className="flex relative overflow-hidden bg-[#000000]" style={{ height: 'var(--app-height)' }}>
      {showIntro && <IntroAnimation onFinish={() => setShowIntro(false)} />}

      <input type="file" ref={fileInputRef} className="hidden" multiple accept=".pdf,.doc,.docx,.txt,.csv" data-upload-mode="file" onChange={handleFileChange} />
      
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} onNewChat={handleClearChat} />

      <main className="flex-1 flex flex-col h-full w-full relative min-w-0 overflow-hidden bg-transparent">
        <div
          className={`absolute inset-0 pointer-events-none bg-body-gradient-subtle z-0 transition-opacity duration-[3500ms] ease-in-out ${
            isFirstMessage ? 'opacity-100' : 'opacity-0'
          }`}
        ></div>

        <Header 
          isOpen={sidebarOpen} 
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          detectedLanguage={detectedLanguage}
        />

        {!isFirstMessage && messages.length > 0 && (
          <button 
            onClick={scrollToBottom}
            className={`absolute bottom-[calc(5rem+env(safe-area-inset-bottom))] md:bottom-24 right-4 md:right-8 bg-surface-container-high border border-outline-variant rounded-full p-2 text-on-surface-variant hover:text-primary hover:bg-surface-variant shadow-lg z-30 transition-all duration-300 ${showScrollBottom ? 'opacity-100 translate-y-0 scale-100' : 'opacity-0 translate-y-3 scale-95 pointer-events-none'}`}
            aria-label="Scroll to latest message"
            title="Scroll to latest message"
          >
            <span className="material-symbols-outlined text-xl">arrow_downward</span>
          </button>
        )}

        <div ref={chatContainerRef} onScroll={handleScroll} className={`flex-1 overflow-y-auto custom-scrollbar p-4 md:p-6 transition-all duration-300 relative z-10 flex flex-col ${isFirstMessage ? 'pb-4 md:pb-6' : 'pb-[calc(10rem+env(safe-area-inset-bottom))] md:pb-32'}`}>
          
          {isFirstMessage ? (
            <WelcomeScreen onSendMessage={handleSendMessage} onAttachFileClick={handleAttachFileClick} onMicClick={handleMicClick} />
          ) : (
            <div className="w-full max-w-4xl mx-auto flex flex-col gap-4 md:gap-6 relative z-10 pb-6 animate-fadeIn">
              {messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fadeIn`}>
                  {msg.role === 'system' ? (
                    <div className="flex justify-center my-2 text-[9px] md:text-[10px] font-mono text-error/80 border border-error/20 bg-error/5 px-3 py-1 rounded-full mx-auto w-fit">
                      {msg.content}
                    </div>
                  ) : msg.role === 'user' ? (
                    <div className="max-w-[90%] md:max-w-[80%] bg-surface-variant text-on-surface p-3 md:p-4 rounded-2xl rounded-tr-sm shadow-sm border border-outline-variant">
                      {msg.attachments && msg.attachments.length > 0 && (
                        <div className="flex flex-wrap gap-1 mb-2">
                          {msg.attachments.map((f, i) => (
                            <span key={i} className="bg-surface-container-high text-primary px-2 py-1 rounded text-[9px] md:text-[10px] font-mono border border-outline-variant flex items-center gap-1">
                              <span className="material-symbols-outlined text-[10px] md:text-[12px]">description</span> {f.name}
                            </span>
                          ))}
                        </div>
                      )}
                      <p className="text-[13px] md:text-sm whitespace-pre-wrap">{msg.content}</p>
                      <div className="mt-1.5 md:mt-2 text-[9px] md:text-[10px] text-on-surface-variant text-right font-mono">{msg.time}</div>
                    </div>
                  ) : (
                    <div className="max-w-[95%] sm:max-w-[82%] bg-transparent p-0 md:p-0 rounded-none border-none shadow-none">
                      <div className="flex items-center gap-1.5 md:gap-2 mb-2 md:mb-3">
                        <img
                          src="/assistant-logo.png"
                          alt="Assistant Logo"
                          className="h-20 md:h-24 w-auto object-contain"
                        />
                      </div>
                      <TypewriterMarkdown content={msg.content} onTick={scrollToBottom} />
                      
                      <div className="mt-5 md:mt-6 pt-3 md:pt-4 border-t border-white/15 flex flex-col sm:flex-row sm:items-center justify-between gap-3 md:gap-4 text-white/70">
                        <div className="flex items-center gap-2 self-start sm:self-auto min-w-0">
                          <span className="material-symbols-outlined text-[14px] md:text-[16px] text-white/70">description</span>
                          <span className="text-[10px] md:text-[11px] font-mono truncate max-w-[180px] md:max-w-full">
                            {msg.source} <span className="text-white/45 ml-1">• p. 12</span>
                          </span>
                        </div>

                        <div className="flex items-center justify-between sm:justify-end gap-4 md:gap-5 w-full sm:w-auto">
                          <span className="text-[10px] md:text-[11px] font-mono text-white/65">
                            Similarity: <span className="text-white font-semibold">{msg.confidence}%</span>
                          </span>

                          <button
                            onClick={() => alert('Teks jawaban berhasil disalin!')}
                            className="material-symbols-outlined text-[15px] md:text-[17px] text-white/55 hover:text-white transition-colors"
                            title="Salin Teks"
                          >
                            content_copy
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
              
              {isGenerating && (
                <div className="flex justify-start animate-fadeIn">
                  <p className="font-mono text-[11px] md:text-xs text-primary/80 tracking-wider animate-pulse">
                    Berpikir...
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {!isFirstMessage && (
          <ChatFooter 
            inputValue={inputValue} setInputValue={setInputValue} attachedFiles={attachedFiles}
            onRemoveAttachment={(i) => setAttachedFiles(prev => prev.filter((_, idx) => idx !== i))}
            onAttachFileClick={handleAttachFileClick} onMicClick={handleMicClick}
            isRecording={isRecording} isGenerating={isGenerating}
            onSendMessage={() => handleSendMessage(inputValue, attachedFiles)}
            onClearChat={handleClearChat}
          />
        )}
      </main>
    </div>
  );
};
