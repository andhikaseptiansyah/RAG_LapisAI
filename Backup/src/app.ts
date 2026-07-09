import express from 'express';
import cors from 'cors';

import { env } from './config/env.js';

import authRoutes from './routes/authRoutes.js';
import chatRoutes from './routes/chatRoutes.js';
import conversationRoutes from './routes/conversationRoutes.js';
import documentRoutes from './routes/documentRoutes.js';
import dashboardRoutes from './routes/dashboardRoutes.js';
import queryLogRoutes from './routes/queryLogRoutes.js';

import {
  adminMiddleware,
} from './middleware/adminMiddleware.js';

import {
  authMiddleware,
} from './middleware/authMiddleware.js';

import {
  chatRateLimitMiddleware,
  uploadRateLimitMiddleware,
} from './middleware/rateLimitMiddleware.js';

import {
  errorMiddleware,
} from './middleware/errorMiddleware.js';

import {
  notFoundMiddleware,
} from './middleware/notFoundMiddleware.js';

const app = express();

app.use(
  cors({
    origin: env.FRONTEND_URL,
    credentials: true,
  })
);

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.get('/api/health', (_req, res) => {
  res.json({
    status: 'ok',
    service: 'LapisAI Backend',
  });
});

app.use('/api/auth', authRoutes);

app.use(
  '/api/conversations',
  authMiddleware,
  conversationRoutes
);

app.use(
  '/api/chat',
  authMiddleware,
  chatRateLimitMiddleware,
  chatRoutes
);

app.use(
  '/api/admin/documents',
  authMiddleware,
  adminMiddleware,
  uploadRateLimitMiddleware,
  documentRoutes
);

app.use(
  '/api/admin/dashboard',
  authMiddleware,
  adminMiddleware,
  dashboardRoutes
);

app.use(
  '/api/admin/query-logs',
  authMiddleware,
  adminMiddleware,
  queryLogRoutes
);

app.use(notFoundMiddleware);
app.use(errorMiddleware);

export default app;
