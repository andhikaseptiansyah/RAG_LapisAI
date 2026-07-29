import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AdminSidebar } from './AdminSidebar';
import { AdminHeader } from './AdminHeader';
import { useDashboard } from '../hooks/useDashboard';
import { getQueryLogsDashboard, type QueryLog } from '../services/queryLogService';

const svgToDataUri = (svg: string) => `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;

const metricImages = {
  documents: svgToDataUri(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 160">
      <defs>
        <linearGradient id="folder" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7dd3fc"/><stop offset="1" stop-color="#a78bfa"/></linearGradient>
        <linearGradient id="sheet" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#c4b5fd"/></linearGradient>
      </defs>
      <ellipse cx="112" cy="132" rx="72" ry="15" fill="#0f172a" opacity=".22"/>
      <path d="M42 58c0-8 6-14 14-14h35l14 17h62c8 0 14 6 14 14v43c0 8-6 14-14 14H56c-8 0-14-6-14-14V58z" fill="url(#folder)"/>
      <rect x="68" y="29" width="83" height="87" rx="12" fill="url(#sheet)" opacity=".92"/>
      <rect x="84" y="51" width="50" height="7" rx="3.5" fill="#6366f1" opacity=".55"/>
      <rect x="84" y="69" width="36" height="7" rx="3.5" fill="#06b6d4" opacity=".55"/>
      <circle cx="160" cy="45" r="23" fill="#22c55e"/>
      <path d="M149 45l8 8 15-17" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  `),
  chunks: svgToDataUri(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 160">
      <defs>
        <linearGradient id="a" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fde68a"/><stop offset="1" stop-color="#fb7185"/></linearGradient>
        <linearGradient id="b" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#38bdf8"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient>
      </defs>
      <ellipse cx="110" cy="134" rx="77" ry="13" fill="#0f172a" opacity=".18"/>
      <rect x="44" y="83" width="42" height="42" rx="10" fill="url(#a)"/>
      <rect x="90" y="55" width="42" height="70" rx="10" fill="url(#b)"/>
      <rect x="136" y="30" width="42" height="95" rx="10" fill="#f59e0b"/>
      <circle cx="67" cy="65" r="16" fill="#fff" opacity=".42"/>
      <circle cx="113" cy="37" r="16" fill="#fff" opacity=".42"/>
      <circle cx="159" cy="15" r="16" fill="#fff" opacity=".42"/>
      <path d="M64 66l49-28 46-22" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" opacity=".9"/>
    </svg>
  `),
  chats: svgToDataUri(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 160">
      <defs>
        <linearGradient id="bubble" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#c084fc"/><stop offset="1" stop-color="#2563eb"/></linearGradient>
        <linearGradient id="bubble2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f472b6"/><stop offset="1" stop-color="#f59e0b"/></linearGradient>
      </defs>
      <ellipse cx="113" cy="133" rx="75" ry="14" fill="#0f172a" opacity=".22"/>
      <path d="M51 45c0-13 11-24 24-24h68c13 0 24 11 24 24v34c0 13-11 24-24 24H91l-30 25 7-27c-10-3-17-12-17-22V45z" fill="url(#bubble)"/>
      <path d="M78 64h64M78 82h38" stroke="#fff" stroke-width="8" stroke-linecap="round" opacity=".75"/>
      <circle cx="164" cy="43" r="25" fill="url(#bubble2)"/>
      <path d="M154 43h20M164 33v20" stroke="#fff" stroke-width="7" stroke-linecap="round"/>
    </svg>
  `),
};

type DashboardDocumentType = 'PDF' | 'DOCX' | 'TXT' | 'Others';

const documentTypeOrder: DashboardDocumentType[] = ['PDF', 'DOCX', 'TXT', 'Others'];

const documentTypeConfig: Record<DashboardDocumentType, { dot: string; color: string }> = {
  PDF: { dot: 'bg-[#22d3ee]', color: '#22d3ee' },
  DOCX: { dot: 'bg-[#facc15]', color: '#facc15' },
  TXT: { dot: 'bg-[#f472b6]', color: '#f472b6' },
  Others: { dot: 'bg-[#8b5cf6]', color: '#8b5cf6' },
};

const normalizeDocumentType = (document: unknown): DashboardDocumentType => {
  const doc = document as Record<string, unknown>;
  const sourceText = [
    doc.type, doc.fileType, doc.file_type, doc.extension, doc.ext,
    doc.mimeType, doc.mime_type, doc.fileName, doc.filename,
    doc.name, doc.title, doc.originalName, doc.original_name,
  ].filter((value): value is string => typeof value === 'string' && value.trim().length > 0)
   .join(' ').toLowerCase();

  if (sourceText.includes('pdf') || sourceText.includes('application/pdf')) return 'PDF';
  if (sourceText.includes('docx') || sourceText.includes('.doc') || sourceText.includes('msword') || sourceText.includes('wordprocessingml')) return 'DOCX';
  if (sourceText.includes('txt') || sourceText.includes('.text') || sourceText.includes('text/plain') || sourceText.includes('plain')) return 'TXT';
  return 'Others';
};

const calculatePercentages = (counts: Record<DashboardDocumentType, number>, total: number): Record<DashboardDocumentType, number> => {
  if (total <= 0) return { PDF: 0, DOCX: 0, TXT: 0, Others: 0 };
  const rawValues = documentTypeOrder.map((type) => ({ type, raw: (counts[type] / total) * 100 }));
  const percentages = rawValues.reduce((acc, item) => { acc[item.type] = Math.floor(item.raw); return acc; }, { PDF: 0, DOCX: 0, TXT: 0, Others: 0 } as Record<DashboardDocumentType, number>);
  let remaining = 100 - documentTypeOrder.reduce((sum, type) => sum + percentages[type], 0);

  rawValues.sort((a, b) => (b.raw % 1) - (a.raw % 1)).forEach((item) => {
    if (remaining > 0) { percentages[item.type] += 1; remaining -= 1; }
  });
  return percentages;
};

type ChatAnalyticsPoint = { label: string; totalChats: number; };
type TopQuestionPoint = { question: string; count: number; percentage: number; };
type TopQuestionRange = 'day' | 'week' | 'month' | 'year' | 'all';

const topQuestionRangeOptions: Array<{ value: TopQuestionRange; label: string; icon: string }> = [
  { value: 'day', label: 'Day', icon: 'today' },
  { value: 'week', label: 'Week', icon: 'date_range' },
  { value: 'month', label: 'Month', icon: 'calendar_month' },
  { value: 'year', label: 'Year', icon: 'event_note' },
  { value: 'all', label: 'All time', icon: 'all_inclusive' },
];

const calendarMonthOptions = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
] as const;

const isDateInSameWeek = (date: Date, reference: Date): boolean => {
  const target = new Date(date);
  const ref = new Date(reference);
  target.setHours(0, 0, 0, 0);
  ref.setHours(0, 0, 0, 0);

  const refDay = ref.getDay();
  const diffToMonday = refDay === 0 ? -6 : 1 - refDay;
  const weekStart = new Date(ref);
  weekStart.setDate(ref.getDate() + diffToMonday);
  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekStart.getDate() + 6);

  return target >= weekStart && target <= weekEnd;
};

const filterLogsByRange = (
  logs: QueryLog[],
  range: TopQuestionRange,
  anchorDate: Date,
  selectedDate?: string | null,
): QueryLog[] => {
  if (range === 'all') return logs;

  return logs.filter((log) => {
    const parsedDate = parseQueryLogTimestamp(log.timestamp);
    if (!parsedDate) return false;

    if (range === 'day') {
      if (selectedDate) {
        return getDateKeyInDashboardTimeZone(parsedDate) === selectedDate;
      }
      return getDateKeyInDashboardTimeZone(parsedDate) === getDateKeyInDashboardTimeZone(anchorDate);
    }

    if (range === 'week') {
      return isDateInSameWeek(parsedDate, anchorDate);
    }

    if (range === 'month') {
      return parsedDate.getFullYear() === anchorDate.getFullYear() && parsedDate.getMonth() === anchorDate.getMonth();
    }

    if (range === 'year') {
      return parsedDate.getFullYear() === anchorDate.getFullYear();
    }

    return true;
  });
};

const normalizeQuestionText = (value: unknown): string =>
  String(value ?? '')
    .replace(/\s+/g, ' ')
    .trim();

const getQuestionFromQueryLog = (log: QueryLog): string => {
  const record = log as unknown as Record<string, unknown>;
  const candidates = [
    record.question,
    record.query,
    record.prompt,
    record.userQuestion,
    record.user_question,
    record.message,
    record.input,
    record.content,
  ];

  for (const candidate of candidates) {
    const normalized = normalizeQuestionText(candidate);
    if (normalized) return normalized;
  }

  return '';
};

const buildTopQuestions = (logs: QueryLog[], limit = 5): TopQuestionPoint[] => {
  const questionCounts = logs.reduce<Map<string, { question: string; count: number }>>((acc, log) => {
    const question = getQuestionFromQueryLog(log);
    if (!question) return acc;

    const key = question.toLocaleLowerCase('en-US');
    const current = acc.get(key);
    acc.set(key, {
      question: current?.question ?? question,
      count: (current?.count ?? 0) + 1,
    });
    return acc;
  }, new Map());

  const ranked = Array.from(questionCounts.values())
    .sort((a, b) => b.count - a.count || a.question.localeCompare(b.question))
    .slice(0, limit);

  const maxCount = Math.max(...ranked.map((item) => item.count), 1);

  return ranked.map((item) => ({
    ...item,
    percentage: Math.max(8, Math.round((item.count / maxCount) * 100)),
  }));
};

const dashboardTimeZone = 'Asia/Jakarta';

const getDateKeyInDashboardTimeZone = (date: Date): string => {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: dashboardTimeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(date);
  const year = parts.find((part) => part.type === 'year')?.value ?? '0000';
  const month = parts.find((part) => part.type === 'month')?.value ?? '00';
  const day = parts.find((part) => part.type === 'day')?.value ?? '00';
  return `${year}-${month}-${day}`;
};

const parseQueryLogTimestamp = (timestamp: string | undefined): Date | null => {
  if (!timestamp) return null;
  const normalized = timestamp.includes('T') ? timestamp : timestamp.replace(' ', 'T');
  const parsedDate = new Date(normalized);
  return !Number.isNaN(parsedDate.getTime()) ? parsedDate : null;
};

const getQueryLogDateKey = (timestamp: string | undefined): string | null => {
  const parsedDate = parseQueryLogTimestamp(timestamp);
  if (parsedDate) return getDateKeyInDashboardTimeZone(parsedDate);
  const fallbackDate = timestamp?.match(/(\d{4})[-/](\d{1,2})[-/](\d{1,2})/);
  if (!fallbackDate) return null;
  return `${fallbackDate[1]}-${fallbackDate[2].padStart(2, '0')}-${fallbackDate[3].padStart(2, '0')}`;
};

const normalizeAnalyticsDateKey = (label: string): string | null => {
  const parsedDate = parseQueryLogTimestamp(label);
  if (parsedDate) return getDateKeyInDashboardTimeZone(parsedDate);
  const fallbackDate = label?.match(/(\d{4})[-/](\d{1,2})[-/](\d{1,2})/);
  if (!fallbackDate) return null;
  return `${fallbackDate[1]}-${fallbackDate[2].padStart(2, '0')}-${fallbackDate[3].padStart(2, '0')}`;
};

const buildDailyAnalyticsFromQueryLogs = (logs: QueryLog[]): ChatAnalyticsPoint[] => {
  const countsByDate = logs.reduce<Record<string, number>>((acc, log) => {
    const dateKey = getQueryLogDateKey(log.timestamp);
    if (!dateKey) return acc;
    acc[dateKey] = (acc[dateKey] ?? 0) + 1;
    return acc;
  }, {});
  return Object.entries(countsByDate).map(([label, totalChats]) => ({ label, totalChats })).sort((a, b) => a.label.localeCompare(b.label));
};

const parseResponseTimeSeconds = (value: unknown): number => {
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0;
  const text = String(value ?? '').trim().toLowerCase();
  if (!text) return 0;
  const numeric = Number(text.replace(',', '.').replace(/[^0-9.-]/g, ''));
  if (!Number.isFinite(numeric)) return 0;
  if (text.includes('ms')) return numeric / 1000;
  return numeric;
};

const calculateAverageResponseTimeFromLogs = (logs: QueryLog[]): number => {
  const responseTimes = logs.map((log) => parseResponseTimeSeconds(log.responseTime)).filter((value) => Number.isFinite(value) && value > 0);
  if (responseTimes.length === 0) return 0;
  const total = responseTimes.reduce((sum, value) => sum + value, 0);
  return total / responseTimes.length;
};

const getReliableAverageResponseTime = (performanceAverage: unknown, logs: QueryLog[], fallbackAverage?: unknown): number => {
  const backendAverage = Number(performanceAverage ?? 0);
  if (Number.isFinite(backendAverage) && backendAverage > 0) return backendAverage;
  const logsAverage = calculateAverageResponseTimeFromLogs(logs);
  if (logsAverage > 0) return logsAverage;
  const fallback = Number(fallbackAverage ?? 0);
  return Number.isFinite(fallback) && fallback > 0 ? fallback : 0;
};

const normalizeDashboardAnalytics = (items: Array<{ label: string; totalChats: number }>): ChatAnalyticsPoint[] => {
  const countsByDate = items.reduce<Record<string, number>>((acc, item) => {
    const dateKey = normalizeAnalyticsDateKey(item.label);
    if (!dateKey) return acc;
    acc[dateKey] = (acc[dateKey] ?? 0) + Number(item.totalChats ?? 0);
    return acc;
  }, {});
  return Object.entries(countsByDate).map(([label, totalChats]) => ({ label, totalChats })).sort((a, b) => a.label.localeCompare(b.label));
};

export const AdminDashboard: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  
  const [viewDate, setViewDate] = useState<Date | null>(null);
  const [activeHoverPoint, setActiveHoverPoint] = useState<{ x: number; y: number; value: number; label: string } | null>(null);
  const [topQuestionRange, setTopQuestionRange] = useState<TopQuestionRange>('month');
  const [activeTopQuestionIndex, setActiveTopQuestionIndex] = useState<number | null>(null);
  const [isTopQuestionRangeOpen, setIsTopQuestionRangeOpen] = useState(false);
  const topQuestionRangeRef = useRef<HTMLDivElement>(null);
  const [isCalendarPickerOpen, setIsCalendarPickerOpen] = useState(false);
  const calendarPickerRef = useRef<HTMLDivElement>(null);
  const calendarPickerButtonRef = useRef<HTMLButtonElement>(null);
  const calendarPickerPanelRef = useRef<HTMLDivElement>(null);
  const [calendarPickerLayout, setCalendarPickerLayout] = useState({
    isMobile: false,
    left: 12,
    top: 12,
    width: 280,
  });

  const { summary, chatSummary, analytics, documents, isLoading, error } = useDashboard({ initialRange: 'daily', initialDocumentLimit: 1000 });

  const [queryLogAnalytics, setQueryLogAnalytics] = useState<ChatAnalyticsPoint[]>([]);
  const [queryLogs, setQueryLogs] = useState<QueryLog[]>([]);
  const [queryLogAverageResponseTime, setQueryLogAverageResponseTime] = useState<number | null>(null);
  const [isQueryLogSyncing, setIsQueryLogSyncing] = useState(false);

  const loadQueryLogAnalytics = useCallback(async (signal?: AbortSignal) => {
    setIsQueryLogSyncing(true);
    try {
      const response = await getQueryLogsDashboard({ range: 'daily', page: 1, limit: 0 }, signal);
      const logs = Array.isArray(response.logs) ? response.logs : [];
      const averageResponseTime = getReliableAverageResponseTime(response.performance?.averageResponseTime, logs);
      setQueryLogs(logs);
      setQueryLogAnalytics(buildDailyAnalyticsFromQueryLogs(logs));
      setQueryLogAverageResponseTime(averageResponseTime > 0 ? averageResponseTime : null);
    } catch {
      if (!signal?.aborted) { setQueryLogs([]); setQueryLogAnalytics([]); setQueryLogAverageResponseTime(null); }
    } finally {
      if (!signal?.aborted) setIsQueryLogSyncing(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadQueryLogAnalytics(controller.signal);
    return () => controller.abort();
  }, [loadQueryLogAnalytics]);

  useEffect(() => {
    const handlePointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target as Node;

      if (!topQuestionRangeRef.current?.contains(target)) {
        setIsTopQuestionRangeOpen(false);
      }

      const clickedCalendarTrigger = calendarPickerRef.current?.contains(target);
      const clickedCalendarPanel = calendarPickerPanelRef.current?.contains(target);

      if (!clickedCalendarTrigger && !clickedCalendarPanel) {
        setIsCalendarPickerOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsTopQuestionRangeOpen(false);
        setIsCalendarPickerOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('touchstart', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('touchstart', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const updateCalendarPickerLayout = useCallback(() => {
    const button = calendarPickerButtonRef.current;
    if (!button || typeof window === 'undefined') return;

    const rect = button.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const isMobile = viewportWidth < 640;
    const width = Math.min(280, viewportWidth - 32);
    const estimatedHeight = 318;

    let left = Math.min(
      Math.max(12, rect.left),
      Math.max(12, viewportWidth - width - 12),
    );

    let top = rect.bottom + 8;
    if (top + estimatedHeight > viewportHeight - 12) {
      top = Math.max(12, rect.top - estimatedHeight - 8);
    }

    setCalendarPickerLayout({ isMobile, left, top, width });
  }, []);

  useEffect(() => {
    if (!isCalendarPickerOpen) return;

    updateCalendarPickerLayout();
    const handleViewportChange = () => updateCalendarPickerLayout();

    window.addEventListener('resize', handleViewportChange);
    window.addEventListener('scroll', handleViewportChange, true);

    return () => {
      window.removeEventListener('resize', handleViewportChange);
      window.removeEventListener('scroll', handleViewportChange, true);
    };
  }, [isCalendarPickerOpen, updateCalendarPickerLayout]);

  const normalizedHookAnalytics = useMemo(() => normalizeDashboardAnalytics(analytics), [analytics]);
  const dashboardAnalytics = queryLogAnalytics.length > 0 ? queryLogAnalytics : normalizedHookAnalytics;
  const dashboardTotalChats = dashboardAnalytics.reduce((total, item) => total + item.totalChats, 0);

  const summaryCards = [
    { label: 'Total Documents', value: summary?.totalDocuments ?? 0, helper: 'Documents stored in the database', icon: 'folder_open', image: metricImages.documents, gradient: 'from-cyan-300 via-teal-300 to-cyan-500' },
    { label: 'Total Chunks', value: summary?.totalChunks ?? 0, helper: 'Indexed document chunks', icon: 'database', image: metricImages.chunks, gradient: 'from-amber-200 via-yellow-300 to-orange-400' },
    { label: 'Total Chats', value: summary?.totalChats ?? 0, helper: 'Conversations recorded in query logs', icon: 'forum', image: metricImages.chats, gradient: 'from-fuchsia-300 via-pink-300 to-violet-400' },
  ];

  const effectiveViewDate = useMemo(() => {
    if (viewDate) return viewDate;
    const latestDateKey = dashboardAnalytics[dashboardAnalytics.length - 1]?.label;
    if (latestDateKey) {
      const parsedDate = new Date(`${latestDateKey}T12:00:00`);
      if (!Number.isNaN(parsedDate.getTime())) return parsedDate;
    }
    return new Date();
  }, [viewDate, dashboardAnalytics]);

  const { currentMonthName, calendarGrid } = useMemo(() => {
    const year = effectiveViewDate.getFullYear();
    const month = effectiveViewDate.getMonth();
    const monthName = effectiveViewDate.toLocaleString('en-US', { month: 'long', year: 'numeric' });
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const firstDay = new Date(year, month, 1).getDay();
    const prevMonthDays = new Date(year, month, 0).getDate();
    const activeDates = new Set(dashboardAnalytics.map((item) => item.label).filter(Boolean));

    const grid = [];
    for (let i = 0; i < firstDay; i++) {
      grid.push({ value: (prevMonthDays - firstDay + i + 1).toString(), muted: true, fullDate: null, hasData: false });
    }
    for (let i = 1; i <= daysInMonth; i++) {
      const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}`;
      grid.push({ value: i.toString(), muted: false, fullDate: dateStr, hasData: activeDates.has(dateStr) });
    }
    return { currentMonthName: monthName, calendarGrid: grid };
  }, [effectiveViewDate, dashboardAnalytics]);

  const calendarPickerYear = effectiveViewDate.getFullYear();
  const calendarPickerMonth = effectiveViewDate.getMonth();

  const selectCalendarMonth = (monthIndex: number) => {
    setViewDate(new Date(calendarPickerYear, monthIndex, 1));
    setSelectedDate(null);
    setIsCalendarPickerOpen(false);
  };

  const changeCalendarYear = (yearOffset: number) => {
    setViewDate(new Date(calendarPickerYear + yearOffset, calendarPickerMonth, 1));
    setSelectedDate(null);
  };

  const filteredAnalytics = useMemo(() => {
    if (!selectedDate) return dashboardAnalytics;
    return dashboardAnalytics.filter(item => item.label === selectedDate);
  }, [dashboardAnalytics, selectedDate]);

  const chatChart = useMemo(() => {
    const values = filteredAnalytics.map((item) => item.totalChats);
    const allValues = dashboardAnalytics.map(a => a.totalChats);
    const maxValue = Math.max(...allValues, 5); 
    const width = 640, height = 260, paddingX = 40, paddingTop = 20, paddingBottom = 40; 
    const innerWidth = width - paddingX * 2, innerHeight = height - paddingTop - paddingBottom;
    const chartBaseY = paddingTop + innerHeight;

    const buildSmoothPath = (pts: Array<{x: number, y: number}>) => {
      if (pts.length === 0) return '';
      let d = `M ${pts[0].x.toFixed(1)},${pts[0].y.toFixed(1)}`;
      for (let i = 0; i < pts.length - 1; i++) {
        const p1 = pts[i], p2 = pts[i + 1];
        const cp1x = p1.x + (p2.x - p1.x) / 2;
        d += ` C ${cp1x.toFixed(1)},${p1.y.toFixed(1)} ${cp1x.toFixed(1)},${p2.y.toFixed(1)} ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`;
      }
      return d;
    };

    const points = values.map((value, index) => ({
      x: values.length <= 1 ? width / 2 : paddingX + (index * innerWidth) / (values.length - 1),
      y: paddingTop + innerHeight - (value / maxValue) * innerHeight,
      value, label: filteredAnalytics[index]?.label ?? ''
    }));

    const averagePoints = values.map((_, index) => {
      const start = Math.max(index - 2, 0);
      const slice = values.slice(start, index + 1);
      const avgValue = slice.reduce((total, val) => total + val, 0) / Math.max(slice.length, 1);
      return {
        x: values.length <= 1 ? width / 2 : paddingX + (index * innerWidth) / (values.length - 1),
        y: paddingTop + innerHeight - (avgValue / maxValue) * innerHeight
      };
    });

    let path = '', areaPath = '', averagePath = '', averageAreaPath = '';

    if (points.length === 1) {
      const p = points[0], span = 200; 
      path = `M ${p.x - span},${chartBaseY} C ${p.x - span/2},${chartBaseY} ${p.x - span/4},${p.y} ${p.x},${p.y} C ${p.x + span/4},${p.y} ${p.x + span/2},${chartBaseY} ${p.x + span},${chartBaseY}`;
      areaPath = `${path} Z`;
      const a = averagePoints[0];
      averagePath = `M ${a.x - span},${chartBaseY} C ${a.x - span/2},${chartBaseY} ${a.x - span/4},${a.y} ${a.x},${a.y} C ${a.x + span/4},${a.y} ${a.x + span/2},${chartBaseY} ${a.x + span},${chartBaseY}`;
      averageAreaPath = `${averagePath} Z`;
    } else if (points.length > 1) {
      path = buildSmoothPath(points);
      averagePath = buildSmoothPath(averagePoints);
      areaPath = `${path} L ${points[points.length - 1].x.toFixed(1)},${chartBaseY} L ${points[0].x.toFixed(1)},${chartBaseY} Z`;
      averageAreaPath = `${averagePath} L ${averagePoints[averagePoints.length - 1].x.toFixed(1)},${chartBaseY} L ${averagePoints[0].x.toFixed(1)},${chartBaseY} Z`;
    }

    return { points, path, areaPath, averagePath, averageAreaPath, maxValue, chartBaseY };
  }, [filteredAnalytics, dashboardAnalytics]);

  const documentTypeStats = useMemo(() => {
    const docs = documents || [];
    const counts = docs.reduce((acc, document) => {
      acc[normalizeDocumentType(document)] += 1;
      return acc;
    }, { PDF: 0, DOCX: 0, TXT: 0, Others: 0 } as Record<DashboardDocumentType, number>);

    const totalLoadedDocuments = docs.length;
    const percentages = calculatePercentages(counts, totalLoadedDocuments);
    const pdfStop = percentages.PDF, docxStop = pdfStop + percentages.DOCX, txtStop = docxStop + percentages.TXT;

    return {
      total: summary?.totalDocuments ?? totalLoadedDocuments,
      loadedTotal: totalLoadedDocuments,
      items: documentTypeOrder.map((type) => ({ label: type, count: counts[type], value: percentages[type], dot: documentTypeConfig[type].dot })),
      donutStyle: { background: totalLoadedDocuments === 0 ? '#1e293b' : `conic-gradient(${documentTypeConfig.PDF.color} 0 ${pdfStop}%, ${documentTypeConfig.DOCX.color} ${pdfStop}% ${docxStop}%, ${documentTypeConfig.TXT.color} ${docxStop}% ${txtStop}%, ${documentTypeConfig.Others.color} ${txtStop}% 100%)` } as React.CSSProperties,
    };
  }, [documents, summary?.totalDocuments]); 

  const performanceStats = useMemo<Array<{ label: string; value: string | number; badge: string; badgeTone: 'emerald' | 'rose' | 'cyan' | 'violet' | 'slate'; }>>(() => {
    const totalDocuments = summary?.totalDocuments ?? documents.length ?? 0;
    const totalChunks = summary?.totalChunks ?? 0;
    const totalChats = summary?.totalChats ?? chatSummary?.totalChatCount ?? 0;
    const averageResponseTime = getReliableAverageResponseTime(queryLogAverageResponseTime, [], summary?.averageResponseTime);
    const chunksPerDocument = totalDocuments > 0 ? totalChunks / totalDocuments : 0;
    const loadedDocumentPercent = totalDocuments > 0 ? Math.min(100, Math.round((documentTypeStats.loadedTotal / totalDocuments) * 100)) : 0;

    const latestChatPoint = dashboardAnalytics.length > 0 ? dashboardAnalytics[dashboardAnalytics.length - 1] : null;
    const previousChatPoint = dashboardAnalytics.length > 1 ? dashboardAnalytics[dashboardAnalytics.length - 2] : null;
    const chatChangePercent = previousChatPoint && previousChatPoint.totalChats > 0 ? ((latestChatPoint?.totalChats ?? 0) - previousChatPoint.totalChats) / previousChatPoint.totalChats * 100 : null;
    const chatBadge = chatChangePercent === null ? `${latestChatPoint?.totalChats ?? 0} latest` : `${chatChangePercent >= 0 ? '▲' : '▼'} ${Math.abs(chatChangePercent).toFixed(1)}%`;

    return [
      { label: 'Total Documents', value: totalDocuments, badge: `${loadedDocumentPercent}% loaded`, badgeTone: 'cyan' },
      { label: 'Total Chunks', value: totalChunks, badge: `${chunksPerDocument.toFixed(1)}/doc`, badgeTone: 'violet' },
      { label: 'Total Chats', value: totalChats, badge: chatBadge, badgeTone: chatChangePercent !== null && chatChangePercent < 0 ? 'rose' : 'emerald' },
      { label: 'Avg Response', value: `${averageResponseTime.toFixed(2).replace(/\.00$/, '')}s`, badge: averageResponseTime > 0 ? 'DB avg' : 'No data', badgeTone: averageResponseTime > 0 ? 'slate' : 'rose' },
    ];
  }, [dashboardAnalytics, chatSummary?.totalChatCount, documentTypeStats.loadedTotal, documents.length, queryLogAverageResponseTime, summary?.averageResponseTime, summary?.totalChats, summary?.totalChunks, summary?.totalDocuments]);

  const topQuestionAccent = [
    'from-[#ffb347] via-[#ff9f1a] to-[#ff7a18]',
    'from-[#ff8ac2] via-[#ff6fb2] to-[#ff4fa0]',
    'from-[#ffe76a] via-[#ffd33d] to-[#ffb703]',
    'from-[#a7f432] via-[#7ddc1f] to-[#58c700]',
    'from-[#ff8a3d] via-[#ff5e3a] to-[#ff3b1f]',
  ];

  const topQuestionLogs = useMemo(
    () => filterLogsByRange(queryLogs, topQuestionRange, effectiveViewDate, selectedDate),
    [effectiveViewDate, queryLogs, selectedDate, topQuestionRange],
  );

  const topQuestions = useMemo(() => buildTopQuestions(topQuestionLogs, 5), [topQuestionLogs]);
  const totalTopQuestionMentions = topQuestions.reduce((total, item) => total + item.count, 0);
  const topQuestionMaxCount = Math.max(...topQuestions.map((item) => item.count), 1);

  const topQuestionRangeLabel = {
    day: selectedDate ? `Day ${selectedDate}` : 'Current day',
    week: 'This week',
    month: currentMonthName,
    year: `${effectiveViewDate.getFullYear()}`,
    all: 'All time',
  } as const;

  const selectedTopQuestionRangeOption =
    topQuestionRangeOptions.find((option) => option.value === topQuestionRange) ??
    topQuestionRangeOptions[2];

  const performanceBadgeClass = {
    emerald: 'text-emerald-400 bg-emerald-400/10', rose: 'text-rose-400 bg-rose-400/10',
    cyan: 'text-cyan-300 bg-cyan-400/10', violet: 'text-violet-300 bg-violet-400/10',
    slate: 'text-slate-300 bg-white/10',
  } as const;

  return (
    <div className="bg-[#05070d] text-white font-body overflow-hidden flex h-[100dvh] min-h-[100dvh] w-full relative">
      <style>{`
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(30px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes drawLine { from { stroke-dashoffset: 2000; } to { stroke-dashoffset: 0; } }
        @keyframes fadeInArea { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes popUp { 0% { opacity: 0; transform: translate(-50%, -100%) scale(0.9) translateY(10px); } 100% { opacity: 1; transform: translate(-50%, -100%) scale(1) translateY(0); } }
        .animate-fade-in-up { animation: fadeInUp 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards; opacity: 0; }
        .animate-draw-line { stroke-dasharray: 2000; animation: drawLine 1.8s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
        .animate-fade-area { animation: fadeInArea 1s cubic-bezier(0.16, 1, 0.3, 1) 0.6s forwards; opacity: 0; }
        /* Scrollbar responsif elegan */
        .mobile-scroll::-webkit-scrollbar { width: 6px; height: 6px; }
        .mobile-scroll::-webkit-scrollbar-track { background: transparent; }
        .mobile-scroll::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }

        @media (max-width: 1023px) {
          .animate-fade-in-up { animation-duration: 0.45s; }
          .dashboard-document-panel,
          .dashboard-performance-panel { width: 100%; }
          .dashboard-chart-tooltip {
            max-width: min(160px, calc(100vw - 48px));
          }
        }

        @media (max-width: 639px) {
          .mobile-scroll::-webkit-scrollbar { width: 3px; height: 3px; }
          .top-question-bars { min-height: 205px; }
          .dashboard-chart-tooltip {
            transform-origin: center bottom;
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .animate-fade-in-up,
          .animate-draw-line,
          .animate-fade-area { animation: none !important; opacity: 1 !important; }
        }

        @media (max-height: 820px) and (min-width: 1024px) {
          .dashboard-document-panel h2,
          .dashboard-performance-panel h2 { font-size: 0.95rem; }
          .dashboard-document-panel > div:first-child,
          .dashboard-performance-panel > div:first-child { margin-bottom: 0.5rem; }
          .dashboard-document-panel .relative.w-\[120px\] { width: 92px; height: 92px; }
          .dashboard-document-panel .md\:w-28 { width: 92px; height: 92px; }
        }

        @media (max-height: 720px) and (min-width: 1024px) {
          .dashboard-document-panel .relative.w-\[120px\],
          .dashboard-document-panel .md\:w-28 { width: 72px; height: 72px; }
          .dashboard-document-panel .absolute.w-\[5rem\] { width: 52px; height: 52px; }
          .dashboard-performance-list { gap: 0.35rem; }
          .dashboard-performance-list > div { padding-top: 0.15rem; padding-bottom: 0.15rem; }
          .top-question-card { min-height: 184px; }
          .top-question-bars { gap: 0.25rem; }
        }
      `}</style>
      
      <AdminSidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <main className="flex-1 flex flex-col h-full relative min-w-0 bg-[#05070d] overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-full bg-[radial-gradient(ellipse_at_top_left,rgba(34,211,238,0.06),transparent_40%),radial-gradient(ellipse_at_bottom_right,rgba(168,85,247,0.06),transparent_40%)] pointer-events-none" />
        <AdminHeader onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

        {/* CONTAINER UTAMA: di HP bisa scroll y, di PC dikunci overflow-nya */}
        <div className="flex-1 min-h-0 p-3 sm:p-4 md:p-5 overflow-y-auto overscroll-contain lg:overflow-hidden mobile-scroll flex flex-col lg:flex-row gap-5 lg:gap-4 max-w-[1720px] mx-auto w-full relative z-10 pb-[calc(1rem+env(safe-area-inset-bottom))]">
          
          {/* SISI KIRI (Main Panel) */}
          <div className="flex-none lg:flex-1 flex flex-col gap-4 lg:gap-3 min-w-0 overflow-visible lg:overflow-hidden">
            
            <div className="shrink-0 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-1 animate-fade-in-up">
              <div>
                <p className="font-mono text-[10px] md:text-xs uppercase tracking-[0.28em] text-slate-500 mb-1">Database Connected</p>
                <h1 className="font-headline text-2xl md:text-3xl font-bold tracking-tight">
                  Hello, <span className="bg-gradient-to-r from-violet-300 to-cyan-300 bg-clip-text text-transparent">Admin</span>
                </h1>
              </div>
              <div className="flex items-center gap-2">
                {(isLoading || isQueryLogSyncing) && <span className="text-xs text-cyan-300 font-mono animate-pulse mr-2">Syncing...</span>}
              </div>
            </div>

            {error && (
              <div className="shrink-0 p-3 rounded-2xl border border-rose-400/30 bg-rose-500/10 text-rose-200 text-xs shadow-[0_0_30px_rgba(244,63,94,0.12)]">
                {error}
              </div>
            )}

            {/* CARD GRID: stacking di HP, berjajar 3 kolom di desktop */}
            <section className="grid grid-cols-1 sm:grid-cols-3 gap-3 md:gap-4 shrink-0">
              {summaryCards.map((card, index) => (
                <div
                  key={card.label}
                  className={`animate-fade-in-up relative overflow-hidden rounded-[1.2rem] bg-gradient-to-br ${card.gradient} p-3.5 md:p-4 min-h-[98px] text-slate-950 shadow-[0_15px_40px_rgba(0,0,0,0.2)] md:hover:-translate-y-1 active:scale-[0.99] transition-transform`}
                  style={{ animationDelay: `${0.1 + (index * 0.1)}s` }}
                >
                  <div className="absolute inset-0 bg-[radial-gradient(circle_at_15%_0%,rgba(255,255,255,0.55),transparent_35%)]" />
                  <div className="absolute -right-2 bottom-0 w-24 md:w-28 opacity-95 pointer-events-none">
                    <img src={card.image} alt="" className="w-full h-auto" />
                  </div>
                  <div className="relative z-10 pr-14">
                    <div className="flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-[14px] md:text-[16px]">{card.icon}</span>
                      <p className="text-xs md:text-sm font-semibold">{card.label}</p>
                    </div>
                    <p className="text-2xl md:text-3xl font-headline font-black mt-2 tracking-tight">{card.value}</p>
                  </div>
                </div>
              ))}
            </section>

            <section className="flex-none lg:flex-1 flex flex-col xl:flex-row gap-4 lg:gap-3 min-h-0 overflow-visible lg:overflow-hidden mt-0">
              
              {/* CHART PANEL: Ditambah min-h agar tidak gepeng di HP */}
              <div className="animate-fade-in-up flex-1 flex flex-col rounded-[1.2rem] border border-white/5 bg-transparent p-3.5 md:p-4 min-w-0 overflow-hidden relative min-h-[360px] sm:min-h-[400px] lg:min-h-0" style={{ animationDelay: '0.4s' }}>
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4 shrink-0">
                  <div>
                    <h2 className="font-headline text-base md:text-lg font-bold">Chat Analytics</h2>
                    <p className="text-[11px] md:text-xs text-slate-400 mt-0.5">
                      {selectedDate ? `Data date ${selectedDate}` : `${dashboardTotalChats || chatSummary?.totalChatCount || 0} total chats`}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {selectedDate && (
                      <button onClick={() => setSelectedDate(null)} className="min-h-10 px-3 py-2 rounded-xl border border-rose-500/30 bg-rose-500/10 text-[11px] text-rose-300 hover:bg-rose-500/20 touch-manipulation">
                        Clear Date
                      </button>
                    )}
                  </div>
                </div>

                <div className="flex-1 relative mt-4 min-h-[240px] sm:min-h-[280px] lg:min-h-0">
                  {filteredAnalytics.length > 0 ? (
                    <div className="relative z-10 w-full h-full">
                      {activeHoverPoint && (
                        <div 
                          className="dashboard-chart-tooltip absolute z-20 pointer-events-none pb-4 drop-shadow-2xl transition-all duration-100 ease-out"
                          style={{ left: `clamp(64px, ${(activeHoverPoint.x / 640) * 100}%, calc(100% - 64px))`, top: `clamp(58px, ${(activeHoverPoint.y / 260) * 100}%, calc(100% - 24px))`, animation: 'popUp 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards' }}
                        >
                          <div className="bg-[#15192b] border border-cyan-400/30 rounded-2xl p-2.5 px-3 flex flex-col items-center min-w-[100px]">
                            <span className="text-[9px] uppercase tracking-wider text-slate-400 mb-0.5 font-mono">{activeHoverPoint.label}</span>
                            <span className="font-headline text-lg font-black text-transparent bg-clip-text bg-gradient-to-r from-violet-300 to-cyan-300">{activeHoverPoint.value}</span>
                            <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-[#15192b] border-b border-r border-cyan-400/30 rotate-45" />
                          </div>
                        </div>
                      )}

                      <svg viewBox="0 0 640 260" preserveAspectRatio="none" className="w-full h-full">
                        <defs>
                          <linearGradient id="mainLineGradient" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor="#7dd3fc" /><stop offset="100%" stopColor="#22d3ee" /></linearGradient>
                          <linearGradient id="avgLineGradient" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor="#d8b4fe" /><stop offset="100%" stopColor="#c084fc" /></linearGradient>
                          <linearGradient id="mainAreaFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#38bdf8" stopOpacity="0.4" /><stop offset="100%" stopColor="#38bdf8" stopOpacity="0.01" /></linearGradient>
                          <linearGradient id="avgAreaFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#c084fc" stopOpacity="0.3" /><stop offset="100%" stopColor="#c084fc" stopOpacity="0.01" /></linearGradient>
                          <filter id="glowEffect" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="5" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
                        </defs>

                        {chatChart.averageAreaPath && <path d={chatChart.averageAreaPath} fill="url(#avgAreaFill)" className="animate-fade-area" />}
                        {chatChart.areaPath && <path d={chatChart.areaPath} fill="url(#mainAreaFill)" className="animate-fade-area" />}
                        {chatChart.averagePath && <path d={chatChart.averagePath} fill="none" stroke="url(#avgLineGradient)" strokeWidth="2.5" className="animate-draw-line" />}
                        {chatChart.path && <path d={chatChart.path} fill="none" stroke="url(#mainLineGradient)" strokeWidth="3.5" strokeLinecap="round" filter="url(#glowEffect)" className="animate-draw-line" />}

                        {chatChart.points.map((point, i, arr) => {
                          const step = Math.ceil(arr.length / 5); 
                          const showLabel = arr.length === 1 || i === 0 || i === arr.length - 1 || i % step === 0;
                          const tAnchor = arr.length > 1 ? (i === 0 ? "start" : i === arr.length - 1 ? "end" : "middle") : "middle";

                          return (
                            <g key={`${point.label}-${point.x}`}>
                              {/* Menambah onTouchStart agar interaksi berjalan di HP */}
                              <g onMouseEnter={() => setActiveHoverPoint(point)} onMouseLeave={() => setActiveHoverPoint(null)} onTouchStart={() => setActiveHoverPoint(point)} className="cursor-crosshair" style={{ transformOrigin: `${point.x}px ${point.y}px` }}>
                                <circle cx={point.x} cy={point.y} r={activeHoverPoint?.label === point.label ? "7" : "4"} fill="#22d3ee" stroke="#0f172a" strokeWidth="2" className="transition-all duration-200" />
                                <circle cx={point.x} cy={point.y} r="35" fill="transparent" />
                              </g>
                              {showLabel && <text x={point.x} y={chatChart.chartBaseY + 25} fill="#64748b" fontSize="10" fontFamily="monospace" textAnchor={tAnchor} className="animate-fade-area">{point.label}</text>}
                            </g>
                          );
                        })}
                      </svg>
                    </div>
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-xs text-slate-500 bg-white/[0.02] rounded-xl border border-white/5">No query log data yet.</div>
                  )}
                </div>
                
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mt-2 pt-3 border-t border-white/5 text-[10px] md:text-xs text-slate-400 shrink-0">
                  <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-gradient-to-r from-[#7dd3fc] to-[#22d3ee]" /> Total</span>
                  <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full bg-gradient-to-r from-[#d8b4fe] to-[#c084fc]" /> Average</span>
                  <span className="ml-auto font-mono text-slate-500 font-semibold tracking-wider">MAX: {chatChart.maxValue}</span>
                </div>
              </div>

              {/* CALENDAR PANEL */}
              <div className="animate-fade-in-up w-full xl:w-[280px] min-h-[390px] sm:min-h-[360px] xl:min-h-0 flex flex-col rounded-[1.2rem] border border-white/5 bg-transparent p-3.5 md:p-4 shrink-0 overflow-hidden" style={{ animationDelay: '0.5s' }}>
                <div className="flex items-center justify-between mb-4 shrink-0">
                  <h2 className="font-headline text-base md:text-lg font-bold">Calendar</h2>
                  <div className="flex items-center gap-1.5">
                    <button onClick={() => setViewDate(new Date(effectiveViewDate.getFullYear(), effectiveViewDate.getMonth() - 1, 1))} className="w-10 h-10 xl:w-7 xl:h-7 flex items-center justify-center rounded-xl bg-white/5 border border-white/10 hover:bg-white/15 text-slate-400 hover:text-white transition-all touch-manipulation">
                      <span className="material-symbols-outlined text-[16px] md:text-[14px]">chevron_left</span>
                    </button>
                    <button onClick={() => setViewDate(new Date(effectiveViewDate.getFullYear(), effectiveViewDate.getMonth() + 1, 1))} className="w-10 h-10 xl:w-7 xl:h-7 flex items-center justify-center rounded-xl bg-white/5 border border-white/10 hover:bg-white/15 text-slate-400 hover:text-white transition-all touch-manipulation">
                      <span className="material-symbols-outlined text-[16px] md:text-[14px]">chevron_right</span>
                    </button>
                  </div>
                </div>
                
                <div ref={calendarPickerRef} className="relative self-start mb-4 shrink-0 z-30">
                  <button
                    ref={calendarPickerButtonRef}
                    type="button"
                    onClick={() => {
                      updateCalendarPickerLayout();
                      setIsCalendarPickerOpen((current) => !current);
                    }}
                    aria-haspopup="dialog"
                    aria-expanded={isCalendarPickerOpen}
                    className={`min-h-10 inline-flex items-center gap-2.5 rounded-xl border px-3.5 py-2 text-[11px] md:text-xs font-semibold outline-none transition-all touch-manipulation ${
                      isCalendarPickerOpen
                        ? 'border-cyan-400 bg-[#0c1720] text-white shadow-[0_0_0_3px_rgba(34,211,238,0.10)]'
                        : 'border-white/10 bg-[#090d15] text-slate-300 hover:border-cyan-400/50 hover:text-white'
                    }`}
                  >
                    <span className={`material-symbols-outlined text-[17px] ${isCalendarPickerOpen ? 'text-cyan-300' : 'text-slate-500'}`}>
                      calendar_month
                    </span>
                    <span>{currentMonthName}</span>
                    <span className={`material-symbols-outlined ml-1 text-[17px] text-slate-500 transition-transform duration-200 ${isCalendarPickerOpen ? 'rotate-180 text-cyan-300' : ''}`}>
                      expand_more
                    </span>
                  </button>

                  {isCalendarPickerOpen && typeof document !== 'undefined' && createPortal(
                    <>
                      <button
                        type="button"
                        aria-label="Close month picker"
                        onClick={() => setIsCalendarPickerOpen(false)}
                        className={`fixed inset-0 z-[9998] cursor-default ${calendarPickerLayout.isMobile ? 'bg-black/65 backdrop-blur-[2px]' : 'bg-transparent'}`}
                      />

                      <div
                        ref={calendarPickerPanelRef}
                        role="dialog"
                        aria-modal={calendarPickerLayout.isMobile}
                        aria-label="Choose calendar month and year"
                        className={`fixed z-[9999] overflow-hidden rounded-[18px] border border-white/10 bg-[#0b1019] shadow-[0_24px_80px_rgba(0,0,0,0.72)] ${
                          calendarPickerLayout.isMobile
                            ? 'left-1/2 bottom-4 w-[min(288px,calc(100vw-32px))] max-h-[calc(100vh-32px)] -translate-x-1/2'
                            : ''
                        }`}
                        style={calendarPickerLayout.isMobile ? undefined : {
                          left: calendarPickerLayout.left,
                          top: calendarPickerLayout.top,
                          width: calendarPickerLayout.width,
                        }}
                      >
                        <div className="flex items-center justify-between border-b border-white/[0.07] px-3.5 py-2.5">
                          <div>
                            <p className="text-[8px] font-mono uppercase tracking-[0.18em] text-slate-500">Calendar</p>
                            <h3 className="mt-0.5 text-xs font-bold text-white">Select month and year</h3>
                          </div>
                          <button
                            type="button"
                            onClick={() => setIsCalendarPickerOpen(false)}
                            className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#151b27] text-slate-400 transition hover:bg-pink-400 hover:text-slate-950"
                            aria-label="Close month picker"
                          >
                            <span className="material-symbols-outlined text-[17px]">close</span>
                          </button>
                        </div>

                        <div className="max-h-[calc(100vh-92px)] overflow-y-auto p-3 mobile-scroll">
                          <div className="flex items-center justify-between rounded-xl bg-[#111722] p-1.5">
                            <button
                              type="button"
                              onClick={() => changeCalendarYear(-1)}
                              className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-400 text-slate-950 transition hover:bg-cyan-300 active:scale-95"
                              aria-label="Previous year"
                            >
                              <span className="material-symbols-outlined text-[18px]">chevron_left</span>
                            </button>

                            <div className="min-w-0 text-center">
                              <p className="text-[8px] font-mono uppercase tracking-[0.18em] text-slate-500">Selected year</p>
                              <p className="mt-0.5 text-xl font-black tracking-tight text-white">{calendarPickerYear}</p>
                            </div>

                            <button
                              type="button"
                              onClick={() => changeCalendarYear(1)}
                              className="flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-400 text-slate-950 transition hover:bg-cyan-300 active:scale-95"
                              aria-label="Next year"
                            >
                              <span className="material-symbols-outlined text-[18px]">chevron_right</span>
                            </button>
                          </div>

                          <div className="mt-2.5 grid grid-cols-3 gap-1.5">
                            {calendarMonthOptions.map((month, monthIndex) => {
                              const isCurrentMonth = monthIndex === calendarPickerMonth;

                              return (
                                <button
                                  key={month}
                                  type="button"
                                  onClick={() => selectCalendarMonth(monthIndex)}
                                  className={`min-h-9 rounded-lg px-2 py-1.5 text-[10px] font-bold transition touch-manipulation active:scale-[0.97] ${
                                    isCurrentMonth
                                      ? 'bg-cyan-400 text-slate-950 shadow-[0_8px_22px_rgba(34,211,238,0.20)]'
                                      : 'bg-[#151b27] text-slate-300 hover:bg-yellow-400 hover:text-slate-950'
                                  }`}
                                >
                                  {month.slice(0, 3)}
                                </button>
                              );
                            })}
                          </div>

                          <button
                            type="button"
                            onClick={() => {
                              const today = new Date();
                              setViewDate(new Date(today.getFullYear(), today.getMonth(), 1));
                              setSelectedDate(null);
                              setIsCalendarPickerOpen(false);
                            }}
                            className="mt-2.5 w-full min-h-9 rounded-lg bg-pink-400 px-3 text-[10px] font-bold text-slate-950 transition hover:bg-pink-300 active:scale-[0.99]"
                          >
                            Go to current month
                          </button>
                        </div>
                      </div>
                    </>,
                    document.body,
                  )}
                </div>
                
                <div className="flex-1 grid grid-cols-7 gap-1 md:gap-1.5 text-center text-[12px] md:text-[11px] content-start overflow-visible pr-1">
                  {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((day, index) => (
                    <span key={`day-${day}-${index}`} className="text-slate-500 font-semibold py-1 md:py-1.5">{day}</span>
                  ))}
                  {calendarGrid.map((day, index) => {
                    const isActive = selectedDate === day.fullDate && !day.muted;
                    return (
                      <button
                        key={`${day.value}-${index}`}
                        onClick={() => { if (!day.muted && day.fullDate) setSelectedDate(day.fullDate === selectedDate ? null : day.fullDate); }}
                        disabled={day.muted}
                        className={`h-10 sm:h-9 xl:h-7 rounded-lg flex flex-col items-center justify-center transition-all relative ${
                          isActive
                            ? 'bg-gradient-to-tr from-violet-600 to-cyan-500 text-white font-bold shadow-[0_0_10px_rgba(34,211,238,0.4)] scale-110'
                            : day.muted
                              ? 'text-slate-600/30 cursor-not-allowed'
                              : day.hasData
                                ? 'text-cyan-300 hover:bg-white/10 cursor-pointer font-bold bg-cyan-500/10'
                                : 'text-slate-300 hover:bg-white/10 cursor-pointer'
                        }`}
                      >
                        <span>{day.value}</span>
                        {day.hasData && !isActive && <span className="absolute bottom-1 w-1 h-1 rounded-full bg-cyan-400" />}
                      </button>
                    );
                  })}
                </div>
              </div>

            </section>
          </div>

          {/* SISI KANAN (Document Types & Performance) */}
          <div 
            className="animate-fade-in-up w-full lg:w-[320px] xl:w-[340px] shrink-0 min-h-0 flex flex-col gap-4 lg:gap-3 bg-transparent pt-1 overflow-visible lg:overflow-hidden pb-1"
            style={{ animationDelay: '0.6s' }}
          >
            <div className="shrink-0 dashboard-document-panel rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4 lg:rounded-none lg:border-0 lg:bg-transparent lg:p-0">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-headline text-base md:text-lg font-bold text-slate-200">Document Types</h2>
              </div>

              <div className="flex flex-col sm:flex-row items-center justify-center sm:justify-start gap-5 sm:gap-6 lg:gap-5">
                <div className="relative w-[120px] h-[120px] md:w-28 md:h-28 shrink-0 rounded-full flex items-center justify-center shadow-[0_0_30px_rgba(34,211,238,0.1)]" style={documentTypeStats.donutStyle}>
                  <div className="absolute w-[5rem] h-[5rem] md:w-[4.5rem] md:h-[4.5rem] bg-[#05070d] rounded-full flex flex-col items-center justify-center">
                    <span className="font-headline text-xl md:text-lg font-black text-white leading-none">{documentTypeStats.total}</span>
                    <span className="text-[9px] md:text-[8px] text-slate-500 uppercase tracking-wider mt-1">Docs</span>
                  </div>
                </div>

                <div className="flex flex-col gap-3 md:gap-2.5 flex-1">
                  {documentTypeStats.items.map((item) => (
                    <div key={item.label} className="flex items-center justify-between text-xs md:text-[11px]">
                      <span className="flex items-center gap-2 text-slate-300 font-medium">
                        <span className={`w-2.5 h-2.5 md:w-2 md:h-2 rounded-full ${item.dot}`} />
                        {item.label}
                      </span>
                      <span className="text-slate-400 font-mono">{item.count} · {item.value}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="w-full border-t border-dashed border-white/10 shrink-0" />

            <div className="shrink-0 dashboard-performance-panel rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4 lg:rounded-none lg:border-0 lg:bg-transparent lg:p-0">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-headline text-base md:text-lg font-bold text-slate-200">Performance Summary</h2>
              </div>

              <div className="dashboard-performance-list flex flex-col gap-2.5 md:gap-2.5">
                {performanceStats.map((stat) => (
                  <div key={stat.label} className="flex items-center justify-between text-sm group bg-white/[0.01] p-2.5 md:p-0 rounded-lg md:bg-transparent">
                    <span className="text-slate-400 group-hover:text-slate-300 transition-colors text-sm md:text-[13px]">{stat.label}</span>
                    <div className="flex items-center gap-3">
                      <span className="font-semibold text-white tracking-wide">{stat.value}</span>
                      <span className={`text-xs md:text-[11px] font-medium flex items-center gap-0.5 px-2 md:px-1.5 py-1 md:py-0.5 rounded-md ${performanceBadgeClass[stat.badgeTone]}`}>
                        {stat.badge}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="w-full border-t border-dashed border-white/10 shrink-0" />

            <section className="flex-none lg:flex-1 min-h-0 pb-1 flex flex-col rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4 lg:rounded-none lg:border-0 lg:bg-transparent lg:p-0" aria-labelledby="top-questions-title">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-3 shrink-0">
                <div>
                  <h2 id="top-questions-title" className="font-headline text-base md:text-lg font-bold text-slate-200">Top Questions</h2>
                  <p className="text-[10px] md:text-[11px] text-slate-500 mt-1">{topQuestionRangeLabel[topQuestionRange]} · {totalTopQuestionMentions} mentions</p>
                </div>

                <div ref={topQuestionRangeRef} className="relative w-full sm:w-auto shrink-0 z-50">
                  <button
                    type="button"
                    onClick={() => setIsTopQuestionRangeOpen((current) => !current)}
                    aria-haspopup="listbox"
                    aria-expanded={isTopQuestionRangeOpen}
                    className={`group w-full sm:w-auto min-w-[112px] sm:min-w-[122px] min-h-11 rounded-xl border px-3 flex items-center justify-between gap-2.5 text-left outline-none transition-all duration-200 ${
                      isTopQuestionRangeOpen
                        ? 'border-cyan-400/45 bg-[#101522] shadow-[0_0_0_3px_rgba(34,211,238,0.08),0_10px_28px_rgba(0,0,0,0.35)]'
                        : 'border-white/10 bg-white/[0.045] hover:border-white/20 hover:bg-white/[0.07]'
                    }`}
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      <span className={`material-symbols-outlined text-[17px] transition-colors ${isTopQuestionRangeOpen ? 'text-cyan-300' : 'text-slate-500 group-hover:text-slate-300'}`}>
                        {selectedTopQuestionRangeOption.icon}
                      </span>
                      <span className="truncate text-[11px] sm:text-xs font-semibold text-slate-200">
                        {selectedTopQuestionRangeOption.label}
                      </span>
                    </span>
                    <span className={`material-symbols-outlined text-[17px] text-slate-500 transition-transform duration-200 ${isTopQuestionRangeOpen ? 'rotate-180 text-cyan-300' : ''}`}>
                      expand_more
                    </span>
                  </button>

                  <div
                    role="listbox"
                    aria-label="Top questions range"
                    className={`absolute left-0 sm:left-auto sm:right-0 top-[calc(100%+8px)] w-full sm:w-[180px] origin-top rounded-2xl border border-white/10 bg-[#0d111c] p-1.5 shadow-[0_18px_50px_rgba(0,0,0,0.65)] transition-all duration-200 ${
                      isTopQuestionRangeOpen
                        ? 'visible translate-y-0 scale-100 opacity-100'
                        : 'invisible -translate-y-1 scale-[0.98] opacity-0 pointer-events-none'
                    }`}
                  >
                    <div className="px-2.5 py-2 text-[9px] font-mono uppercase tracking-[0.18em] text-slate-600">
                      Time range
                    </div>

                    {topQuestionRangeOptions.map((option) => {
                      const isSelected = option.value === topQuestionRange;

                      return (
                        <button
                          key={option.value}
                          type="button"
                          role="option"
                          aria-selected={isSelected}
                          onClick={() => {
                            setTopQuestionRange(option.value);
                            setIsTopQuestionRangeOpen(false);
                          }}
                          className={`group/option w-full rounded-xl px-2.5 py-2.5 flex items-center justify-between gap-3 text-left transition-all duration-150 ${
                            isSelected
                              ? 'bg-gradient-to-r from-cyan-400/15 to-violet-400/10 text-white'
                              : 'text-slate-400 hover:bg-white/[0.06] hover:text-slate-100'
                          }`}
                        >
                          <span className="flex min-w-0 items-center gap-2.5">
                            <span className={`material-symbols-outlined text-[17px] ${isSelected ? 'text-cyan-300' : 'text-slate-600 group-hover/option:text-slate-300'}`}>
                              {option.icon}
                            </span>
                            <span className="text-[11px] sm:text-xs font-medium">{option.label}</span>
                          </span>

                          {isSelected && (
                            <span className="material-symbols-outlined text-[16px] text-cyan-300">
                              check
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              {topQuestions.length > 0 ? (
                <div className="top-question-card flex-none lg:flex-1 min-h-[340px] sm:min-h-[320px] lg:min-h-[210px] max-h-none lg:max-h-[300px] rounded-[1.35rem] border border-white/[0.06] bg-[linear-gradient(180deg,rgba(255,255,255,0.045),rgba(255,255,255,0.015))] px-3 py-3 sm:px-3.5 sm:py-3.5 shadow-[0_10px_30px_rgba(0,0,0,0.22)] overflow-hidden flex flex-col">
                  <div className="mb-3 min-h-[60px] sm:min-h-[56px] max-h-[100px] shrink-0 rounded-xl border border-white/[0.06] bg-black/25 px-3 py-2.5 flex items-center justify-center overflow-y-auto mobile-scroll">
                    {activeTopQuestionIndex !== null && topQuestions[activeTopQuestionIndex] ? (
                      <p className="w-full text-center text-[11px] sm:text-xs font-semibold leading-[1.4] text-white break-words whitespace-normal">
                        {topQuestions[activeTopQuestionIndex].question}
                      </p>
                    ) : (
                      <p className="text-center text-[10px] sm:text-[11px] leading-relaxed text-slate-500">
                        Hover or tap a bar to view the question
                      </p>
                    )}
                  </div>

                  <div className="top-question-bars flex-1 min-h-[210px] lg:min-h-0 flex items-end justify-between gap-1.5 sm:gap-2.5 overflow-visible">
                    {topQuestions.map((item, index) => {
                      const barHeightPercent = Math.max(18, Math.round((item.count / topQuestionMaxCount) * 100));
                      const isActive = activeTopQuestionIndex === index;
                      const barGradient = topQuestionAccent[index] ?? topQuestionAccent[topQuestionAccent.length - 1];

                      return (
                        <button
                          type="button"
                          key={`${item.question}-${index}`}
                          className="group flex-1 min-w-0 h-full min-h-0 flex flex-col items-center justify-end gap-1 sm:gap-1.5 outline-none touch-manipulation"
                          onMouseEnter={() => setActiveTopQuestionIndex(index)}
                          onMouseLeave={() => setActiveTopQuestionIndex(null)}
                          onFocus={() => setActiveTopQuestionIndex(index)}
                          onBlur={() => setActiveTopQuestionIndex(null)}
                          onTouchStart={() => setActiveTopQuestionIndex(index)}
                          onClick={() => setActiveTopQuestionIndex(index)}
                          aria-label={`Question ${index + 1}: ${item.question}`}
                        >
                          <span className={`text-[9px] sm:text-[10px] font-mono transition-colors ${isActive ? 'text-white' : 'text-slate-500'}`}>
                            {item.count}
                          </span>

                          <div className={`relative w-full max-w-[28px] xs:max-w-[32px] sm:max-w-[40px] h-[clamp(74px,14vh,126px)] rounded-full bg-white/[0.08] border overflow-hidden flex items-end transition-all duration-200 ${
                            isActive
                              ? 'border-white/20 scale-[1.04] shadow-[0_0_22px_rgba(255,255,255,0.08)]'
                              : 'border-white/[0.04]'
                          }`}>
                            <div
                              className={`w-full rounded-full bg-gradient-to-b ${barGradient} shadow-[0_0_18px_rgba(255,153,0,0.18)] transition-all duration-500`}
                              style={{ height: `${barHeightPercent}%`, minHeight: '16px' }}
                            />
                            <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(255,255,255,0.22),transparent_38%,transparent_62%,rgba(255,255,255,0.08))] pointer-events-none" />
                          </div>

                          <div className="w-full min-w-0 text-center">
                            <p className={`text-[10px] sm:text-[11px] font-semibold tracking-wide transition-colors ${isActive ? 'text-white' : 'text-slate-300'}`}>
                              Q{index + 1}
                            </p>
                            <div className="hidden md:block mt-0.5 h-[22px] overflow-hidden">
                              <p
                                title={item.question}
                                className="text-[9px] leading-[1.25] text-slate-500 break-words"
                                style={{
                                  display: '-webkit-box',
                                  WebkitLineClamp: 2,
                                  WebkitBoxOrient: 'vertical',
                                }}
                              >
                                {item.question}
                              </p>
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-white/[0.08] bg-white/[0.015] px-4 py-7 text-center">
                  <span className="material-symbols-outlined text-[25px] text-slate-600 mb-2">query_stats</span>
                  <p className="text-xs text-slate-500">No question data available yet.</p>
                </div>
              )}
            </section>
          </div>

        </div>
      </main>
    </div>
  );
};

export default AdminDashboard;