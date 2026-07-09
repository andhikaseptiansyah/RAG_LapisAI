import { Router } from 'express';

import {
  getMe,
  login,
} from '../controllers/authController.js';

import {
  authMiddleware,
} from '../middleware/authMiddleware.js';

import {
  loginRateLimitMiddleware,
} from '../middleware/rateLimitMiddleware.js';

const router = Router();

router.post(
  '/login',
  loginRateLimitMiddleware,
  login
);

router.get('/me', authMiddleware, getMe);

export default router;
