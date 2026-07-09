import { Router } from 'express';

import {
  deleteDocument,
  getDocumentById,
  getDocuments,
  getTrainedDocuments,
  getUploadQueue,
  reindexDocument,
  startIndexing,
  uploadDocument,
} from '../controllers/documentController.js';

import {
  uploadDocumentFile,
} from '../middleware/uploadMiddleware.js';

const router = Router();

router.get(
  '/',
  getDocuments
);

router.post(
  '/',
  uploadDocumentFile,
  uploadDocument
);

router.get(
  '/uploads',
  getUploadQueue
);

router.get(
  '/trained',
  getTrainedDocuments
);

router.post(
  '/index',
  startIndexing
);

router.get(
  '/:id/status',
  getDocumentById
);

router.get(
  '/:id',
  getDocumentById
);

router.post(
  '/:id/reindex',
  reindexDocument
);

router.delete(
  '/:id',
  deleteDocument
);

export default router;