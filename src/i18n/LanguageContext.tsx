import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

export type UiLanguage = 'ID' | 'EN';

const LANGUAGE_STORAGE_KEY = 'lapisai-ui-language';

const translations = {
  ID: {
    openMainMenu: 'Buka menu utama',
    closeMainMenu: 'Tutup menu utama',
    openConversationContents: 'Buka isi percakapan',
    closeConversationContents: 'Tutup isi percakapan',
    answerLanguage: 'Bahasa aplikasi dan jawaban',
    answerLanguageHelp: 'Pilih bahasa untuk seluruh halaman dan jawaban.',
    indonesian: 'Bahasa Indonesia',
    english: 'Bahasa Inggris',
    questionsInConversation: 'Pertanyaan dalam percakapan ini',
    questionsHelp: 'Pilih pertanyaan untuk membuka posisinya.',
    searchConversation: 'Cari dalam percakapan ini',
    clearSearch: 'Bersihkan pencarian',
    noQuestions: 'Belum ada pertanyaan',
    noQuestionsHelp:
      'Pertanyaan dari percakapan ini akan muncul setelah Anda mengirimkannya.',
    noMatchingQuestions: 'Pertanyaan yang sesuai tidak ditemukan.',
    attachmentMessage: 'Pesan dengan lampiran',
    latest: 'Terbaru',
    today: 'Hari ini',
    yesterday: 'Kemarin',
    newConversation: 'Percakapan Baru',
    welcome: 'Selamat datang 👋',
    staff: 'Staf',
    newChat: 'Chat baru',
    searchChats: 'Cari percakapan',
    recentChats: 'Percakapan terbaru',
    noChatHistory: 'Belum ada riwayat percakapan.',
    loadingHistory: 'Memuat riwayat...',
    failedHistory: 'Gagal memuat riwayat percakapan.',
    share: 'Bagikan',
    pin: 'Sematkan',
    unpin: 'Lepas sematan',
    rename: 'Ubah nama',
    delete: 'Hapus',
    adminDashboard: 'Dashboard admin',
    logout: 'Keluar',
    copiedConversationLink: 'Tautan percakapan berhasil disalin.',
    shareConversation: 'Bagikan percakapan',
    failedPin: 'Gagal memperbarui status sematan.',
    renameConversation: 'Ubah nama percakapan',
    failedRename: 'Gagal menyimpan nama percakapan.',
    confirmDeleteConversation: 'Hapus percakapan "{title}"?',
    failedDeleteConversation: 'Gagal menghapus percakapan.',
    closeConversationSearch: 'Tutup pencarian percakapan',
    searchYourQuestions: 'Cari pertanyaan Anda',
    conversationHistory: 'Riwayat percakapan',
    yourConversationQuestions: 'Pertanyaan percakapan Anda',
    questionCount: '{questions} pertanyaan dalam {conversations} percakapan',
    selectConversations: 'Pilih percakapan',
    deselectAll: 'Batalkan semua pilihan',
    selectAll: 'Pilih semua',
    cancel: 'Batal',
    deleteSelected: 'Hapus terpilih',
    conversationsNotFound: 'Percakapan tidak ditemukan',
    tryAnotherKeyword: 'Coba pertanyaan atau kata kunci lain.',
    deleteConversations: 'Hapus percakapan',
    deleteConversationCount:
      'Hapus {count} percakapan terpilih? Tindakan ini tidak dapat dibatalkan.',
    deleting: 'Menghapus...',
    confirmDelete: 'Ya, hapus',
    failedDeleteSelected: 'Gagal menghapus percakapan terpilih.',
    listening: 'Mendengarkan suara Anda...',
    assistantPlaceholder: 'Tulis pesan untuk Lapis AI...',
    addAttachment: 'Tambah lampiran',
    uploadPhoto: 'Unggah foto',
    uploadFile: 'Unggah file',
    speechToText: 'Suara ke teks',
    stopResponse: 'Hentikan jawaban',
    sendMessage: 'Kirim pesan',
    photoFormatError:
      'Unggah Foto hanya menerima PNG, JPG, JPEG, atau WEBP.',
    fileFormatError:
      'Unggah File hanya menerima PDF, DOC, DOCX, TXT, atau CSV.',
    microphoneUnsupported:
      'Maaf, browser Anda tidak mendukung fitur mikrofon. Gunakan Google Chrome atau Edge.',
    requestStopped: 'Permintaan dihentikan oleh pengguna. Jawaban tidak dibuat.',
    clearChatConfirm: 'Hapus seluruh riwayat obrolan di layar?',
    invalidConversation: 'ID percakapan tidak valid. Riwayat tidak bisa dibuka.',
    answerCopied: 'Teks jawaban berhasil disalin!',
    answerCopyFailed: 'Teks jawaban gagal disalin.',
    scrollLatest: 'Gulir ke pesan terbaru',
    sources: 'Sumber',
    source: 'Sumber',
    sourceExcerpt: 'Kutipan sumber',
    answerProgress: 'Progres penyusunan jawaban',
    preparingAnswer: 'Menyiapkan jawaban',
    live: 'Langsung',
    welcomeQuestion: 'Ada yang bisa saya bantu?',
    voice: 'Suara',
    askAnything: 'Tanyakan apa saja...',
    loginTitle: 'Asisten',
    enterpriseAi: 'Sistem AI Perusahaan',
    username: 'Nama pengguna',
    enterId: 'Masukkan ID Anda',
    password: 'Kata sandi',
    verifying: 'Memverifikasi...',
    signIn: 'Masuk',
    encryptedSession: 'Sesi terenkripsi end-to-end terverifikasi',
    loadingAdmin: 'Memuat halaman admin...',
  },
  EN: {
    openMainMenu: 'Open main menu',
    closeMainMenu: 'Close main menu',
    openConversationContents: 'Open conversation contents',
    closeConversationContents: 'Close conversation contents',
    answerLanguage: 'App and answer language',
    answerLanguageHelp: 'Choose the language for the entire page and answers.',
    indonesian: 'Indonesian',
    english: 'English',
    questionsInConversation: 'Questions in this conversation',
    questionsHelp: 'Select a question to jump to its position.',
    searchConversation: 'Search this conversation',
    clearSearch: 'Clear search',
    noQuestions: 'No questions yet',
    noQuestionsHelp:
      'Questions from this conversation will appear after you send them.',
    noMatchingQuestions: 'No matching questions found.',
    attachmentMessage: 'Message with attachment',
    latest: 'Latest',
    today: 'Today',
    yesterday: 'Yesterday',
    newConversation: 'New Conversation',
    welcome: 'Welcome 👋',
    staff: 'Staff',
    newChat: 'New chat',
    searchChats: 'Search conversations',
    recentChats: 'Recent conversations',
    noChatHistory: 'No conversation history yet.',
    loadingHistory: 'Loading history...',
    failedHistory: 'Failed to load conversation history.',
    share: 'Share',
    pin: 'Pin',
    unpin: 'Unpin',
    rename: 'Rename',
    delete: 'Delete',
    adminDashboard: 'Admin dashboard',
    logout: 'Sign out',
    copiedConversationLink: 'Conversation link copied.',
    shareConversation: 'Share conversation',
    failedPin: 'Failed to update pin status.',
    renameConversation: 'Rename conversation',
    failedRename: 'Failed to save the conversation name.',
    confirmDeleteConversation: 'Delete conversation "{title}"?',
    failedDeleteConversation: 'Failed to delete the conversation.',
    closeConversationSearch: 'Close conversation search',
    searchYourQuestions: 'Search your questions',
    conversationHistory: 'Conversation history',
    yourConversationQuestions: 'Your conversation questions',
    questionCount: '{questions} questions in {conversations} conversations',
    selectConversations: 'Select conversations',
    deselectAll: 'Deselect all',
    selectAll: 'Select all',
    cancel: 'Cancel',
    deleteSelected: 'Delete selected',
    conversationsNotFound: 'No conversations found',
    tryAnotherKeyword: 'Try another question or keyword.',
    deleteConversations: 'Delete conversations',
    deleteConversationCount:
      'Delete {count} selected conversations? This action cannot be undone.',
    deleting: 'Deleting...',
    confirmDelete: 'Yes, delete',
    failedDeleteSelected: 'Failed to delete selected conversations.',
    listening: 'Listening...',
    assistantPlaceholder: 'Message Lapis AI...',
    addAttachment: 'Add attachment',
    uploadPhoto: 'Upload photo',
    uploadFile: 'Upload file',
    speechToText: 'Speech to text',
    stopResponse: 'Stop response',
    sendMessage: 'Send message',
    photoFormatError:
      'Photo upload only accepts PNG, JPG, JPEG, or WEBP.',
    fileFormatError:
      'File upload only accepts PDF, DOC, DOCX, TXT, or CSV.',
    microphoneUnsupported:
      'Your browser does not support the microphone feature. Use Google Chrome or Edge.',
    requestStopped: 'The request was stopped. No answer was generated.',
    clearChatConfirm: 'Clear the entire chat shown on screen?',
    invalidConversation: 'Invalid conversation ID. The history cannot be opened.',
    answerCopied: 'Answer copied!',
    answerCopyFailed: 'Failed to copy the answer.',
    scrollLatest: 'Scroll to latest message',
    sources: 'Sources',
    source: 'Source',
    sourceExcerpt: 'Source excerpt',
    answerProgress: 'Answer generation progress',
    preparingAnswer: 'Preparing answer',
    live: 'Live',
    welcomeQuestion: 'How can I help you?',
    voice: 'Voice',
    askAnything: 'Ask anything...',
    loginTitle: 'Assistant',
    enterpriseAi: 'Enterprise AI System',
    username: 'Username',
    enterId: 'Enter your ID',
    password: 'Password',
    verifying: 'Verifying...',
    signIn: 'Sign in',
    encryptedSession: 'Verified end-to-end encrypted session',
    loadingAdmin: 'Loading admin page...',
  },
} as const;

export type TranslationKey = keyof typeof translations.ID;
type TranslationValues = Record<string, string | number>;

interface LanguageContextValue {
  language: UiLanguage;
  setLanguage: (language: UiLanguage) => void;
  t: (key: TranslationKey, values?: TranslationValues) => string;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

const getInitialLanguage = (): UiLanguage => {
  if (typeof window === 'undefined') {
    return 'ID';
  }
  return window.localStorage.getItem(LANGUAGE_STORAGE_KEY) === 'EN'
    ? 'EN'
    : 'ID';
};

export const UiLanguageProvider: React.FC<React.PropsWithChildren> = ({
  children,
}) => {
  const [language, setLanguageState] =
    useState<UiLanguage>(getInitialLanguage);

  const setLanguage = useCallback((nextLanguage: UiLanguage) => {
    setLanguageState(nextLanguage);
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage);
  }, []);

  useEffect(() => {
    document.documentElement.lang = language === 'EN' ? 'en' : 'id';
  }, [language]);

  const t = useCallback(
    (key: TranslationKey, values: TranslationValues = {}) => {
      let text: string = translations[language][key];
      Object.entries(values).forEach(([name, value]) => {
        text = text.split(`{${name}}`).join(String(value));
      });
      return text;
    },
    [language]
  );

  const value = useMemo(
    () => ({ language, setLanguage, t }),
    [language, setLanguage, t]
  );

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useUiLanguage = (): LanguageContextValue => {
  const value = useContext(LanguageContext);
  if (!value) {
    throw new Error('useUiLanguage must be used inside UiLanguageProvider.');
  }
  return value;
};
