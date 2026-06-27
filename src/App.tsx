import React, { useState, useRef, useEffect } from 'react';
import { marked } from 'marked';
import { Message, AttachedFile } from './types';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { WelcomeScreen } from './components/WelcomeScreen';
import { ChatFooter } from './components/ChatFooter';

type DetectedLanguage = 'ID' | 'EN';

export const App: React.FC = () => {
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
      setShowScrollBottom(scrollHeight - scrollTop - clientHeight > 100);
    }
  };

  const handleAttachFileClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const newFiles = Array.from(e.target.files).map(f => ({ name: f.name }));
      setAttachedFiles(prev => [...prev, ...newFiles]);
      if (isFirstMessage) setIsFirstMessage(false);
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
    <div className="flex relative overflow-hidden bg-[#0b0d13]" style={{ height: 'var(--app-height)' }}>
      <input type="file" ref={fileInputRef} className="hidden" multiple accept=".pdf,.doc,.docx,.txt,.csv" onChange={handleFileChange} />
      
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} onNewChat={handleClearChat} />

      <main className="flex-1 flex flex-col h-full w-full relative min-w-0 overflow-hidden">
        <div className="absolute inset-0 pointer-events-none bg-body-gradient-subtle z-0"></div>
        
        <Header 
          isOpen={sidebarOpen} 
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          detectedLanguage={detectedLanguage}
        />

        {!isFirstMessage && messages.length > 0 && (
          <button 
            onClick={scrollToBottom}
            className={`absolute bottom-[calc(12rem+env(safe-area-inset-bottom))] md:bottom-40 right-4 md:right-8 bg-surface-container-high border border-outline-variant rounded-full p-2 text-on-surface-variant hover:text-primary hover:bg-surface-variant shadow-lg z-30 transition-all ${showScrollBottom ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4 pointer-events-none'}`}
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
            <div className="max-w-4xl mx-auto w-full flex flex-col gap-4 md:gap-6 relative z-10 pb-6 animate-fadeIn">
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
                    <div className="max-w-[95%] sm:max-w-[85%] bg-gradient-to-br from-surface-container to-surface-container-low p-4 md:p-5 rounded-2xl rounded-tl-sm border border-primary/20 shadow-lg shadow-primary/5">
                      <div className="flex items-center gap-1.5 md:gap-2 mb-2 md:mb-3">
                        <span className="material-symbols-outlined text-primary text-[14px] md:text-sm icon-filled">smart_toy</span>
                        <span className="font-mono text-primary tracking-widest text-[9px] md:text-[10px] uppercase">Verified System Response</span>
                      </div>
                      <div className="prose prose-sm prose-invert prose-custom max-w-none text-on-surface leading-relaxed text-[13px] md:text-sm" dangerouslySetInnerHTML={{ __html: marked(msg.content) as string }} />
                      
                      <div className="mt-4 md:mt-5 pt-3 md:pt-4 border-t border-outline-variant flex flex-col sm:flex-row sm:items-center justify-between gap-3 md:gap-4">
                        <div className="flex items-center gap-2 bg-surface-container-high px-2 md:px-3 py-1.5 md:py-2 rounded-lg border border-outline-variant self-start sm:self-auto">
                          <span className="material-symbols-outlined text-[14px] md:text-[16px] text-primary">description</span>
                          <span className="text-[10px] md:text-[11px] font-mono text-primary truncate max-w-[150px] md:max-w-full">{msg.source} <span className="text-on-surface-variant ml-1">• p. 12</span></span>
                        </div>
                        
                        <div className="flex items-center justify-between sm:justify-end gap-3 md:gap-4 w-full sm:w-auto">
                          <div className="flex items-center gap-1.5 md:gap-2 px-1">
                            <span className={`w-1.5 h-1.5 md:w-2 md:h-2 rounded-full ${(msg.confidence || 0) > 95 ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)]'}`}></span>
                            <span className="text-[10px] md:text-[11px] font-mono text-on-surface-variant">Similarity: <span className={`${(msg.confidence || 0) > 95 ? 'text-emerald-400' : 'text-amber-400'} font-bold`}>{msg.confidence}%</span></span>
                          </div>
                          <div className="flex items-center bg-surface-container-high rounded-lg p-1 border border-outline-variant">
                            <button onClick={() => alert('Teks jawaban berhasil disalin!')} className="p-1 material-symbols-outlined text-[14px] md:text-[16px] text-outline hover:text-primary transition-colors rounded" title="Salin Teks">content_copy</button>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
              
              {isGenerating && (
                <div className="flex justify-start animate-fadeIn">
                  <div className="bg-surface-container p-3 md:p-4 rounded-2xl rounded-tl-sm border border-outline-variant flex gap-1 items-center h-10 md:h-12">
                    <div className="w-1.5 h-1.5 md:w-2 md:h-2 bg-primary rounded-full animate-typing" style={{ animationDelay: '-0.32s' }}></div>
                    <div className="w-1.5 h-1.5 md:w-2 md:h-2 bg-primary rounded-full animate-typing" style={{ animationDelay: '-0.16s' }}></div>
                    <div className="w-1.5 h-1.5 md:w-2 md:h-2 bg-primary rounded-full animate-typing"></div>
                  </div>
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