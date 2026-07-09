import { Router } from 'express';

import {
  deleteConversation,
  getConversationById,
  getConversations,
  sendChatMessage,
  updateConversationTitle,
} from '../controllers/chatController.js';

import {
  uploadChatFiles,
} from '../middleware/uploadMiddleware.js';

const router = Router();

router.post(
  '/',
  uploadChatFiles,
  sendChatMessage
);

// Legacy route. Bisa dihapus kalau frontend lama sudah tidak dipakai.
router.post(
  '/chat',
  uploadChatFiles,
  sendChatMessage
);

router.get(
  '/conversations',
  getConversations
);

router.get(
  '/conversations/:id',
  getConversationById
);

router.patch(
  '/conversations/:id',
  updateConversationTitle
);

router.delete(
  '/conversations/:id',
  deleteConversation
);

export default router;
