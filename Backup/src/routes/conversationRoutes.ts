import { Router } from 'express';

import {
  getConversations,
  getConversationDetail,
  updateConversation,
  deleteConversation,
} from '../controllers/conversationController.js';

const router = Router();

router.get('/', getConversations);
router.get('/:id', getConversationDetail);
router.patch('/:id', updateConversation);
router.delete('/:id', deleteConversation);

export default router;
