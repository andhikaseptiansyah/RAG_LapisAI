import { Router } from 'express';

import {
  getChatAnalytics,
  getDashboardOverview,
  getDashboardSummary,
} from '../controllers/dashboardController.js';

const router = Router();

router.get(
  '/',
  getDashboardOverview
);

router.get(
  '/summary',
  getDashboardSummary
);

router.get(
  '/chat-analytics',
  getChatAnalytics
);

export default router;