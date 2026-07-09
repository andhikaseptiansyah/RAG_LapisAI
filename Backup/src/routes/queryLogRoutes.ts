import { Router } from 'express';

import {
  deleteQueryLog,
  getQueryLogById,
  getQueryLogDashboard,
  getQueryLogs,
} from '../controllers/queryLogController.js';

const router = Router();

router.get(
  '/',
  getQueryLogs
);

router.get(
  '/dashboard',
  getQueryLogDashboard
);

router.get(
  '/:id',
  getQueryLogById
);

router.delete(
  '/:id',
  deleteQueryLog
);

export default router;