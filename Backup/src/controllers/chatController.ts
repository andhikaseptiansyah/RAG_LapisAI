import type {
  NextFunction,
  Request,
  RequestHandler,
  Response,
} from 'express';

import {
  findConversationById,
  listConversations,
  processChat,
  removeConversation,
  updateConversationTitle as updateConversationTitleService,
  type ChatLanguage,
  type UploadedFileLike,
} from '../services/chatService.js';

import type {
  AuthenticatedRequest,
} from '../middleware/authMiddleware.js';

type RequestWithFiles = Request & {
  file?: UploadedFileLike;
  files?: UploadedFileLike[] | Record<string, UploadedFileLike[]>;
};


const getAuthenticatedUserId = (
  req: Request
): string => {
  const request = req as AuthenticatedRequest;

  if (!request.user?.id) {
    throw new Error('User belum terautentikasi.');
  }

  return request.user.id;
};

const isChatLanguage = (
  value: unknown
): value is ChatLanguage => {
  return value === 'ID' || value === 'EN';
};

const normalizeLanguage = (
  value: unknown
): ChatLanguage => {
  return isChatLanguage(value) ? value : 'ID';
};

const getRouteParam = (
  value: unknown
): string | undefined => {
  if (typeof value === 'string') {
    return value.trim() || undefined;
  }

  if (Array.isArray(value)) {
    const firstValue = value[0];

    if (typeof firstValue === 'string') {
      return firstValue.trim() || undefined;
    }
  }

  return undefined;
};

const normalizeFiles = (
  req: RequestWithFiles
): UploadedFileLike[] => {
  if (Array.isArray(req.files)) {
    return req.files;
  }

  if (
    req.files &&
    typeof req.files === 'object'
  ) {
    return Object.values(req.files).flat();
  }

  if (req.file) {
    return [req.file];
  }

  return [];
};

export const sendChatMessage: RequestHandler =
  async (
    req: Request,
    res: Response,
    next: NextFunction
  ): Promise<void> => {
    try {
      const request = req as RequestWithFiles & AuthenticatedRequest;
      const userId = getAuthenticatedUserId(req);

      const message =
        typeof req.body.message === 'string'
          ? req.body.message
          : '';

      const conversationId =
        typeof req.body.conversationId === 'string' &&
        req.body.conversationId.trim()
          ? req.body.conversationId.trim()
          : undefined;

      const language = normalizeLanguage(
        req.body.language
      );

      const files = normalizeFiles(request);

      const result = await processChat({
        message,
        conversationId,
        language,
        files,
        userId,
      });

      res.status(200).json(result);
    } catch (error) {
      next(error);
    }
  };

export const getConversations: RequestHandler =
  async (
    req: Request,
    res: Response,
    next: NextFunction
  ): Promise<void> => {
    try {
      const userId = getAuthenticatedUserId(req);

      const conversations =
        await listConversations(userId);

      res.status(200).json(conversations);
    } catch (error) {
      next(error);
    }
  };

export const getConversationById: RequestHandler =
  async (
    req: Request,
    res: Response,
    next: NextFunction
  ): Promise<void> => {
    try {
      const id = getRouteParam(
        req.params.id
      );

      if (!id) {
        res.status(400).json({
          message: 'ID percakapan wajib diisi.',
        });
        return;
      }

      const userId = getAuthenticatedUserId(req);

      const conversation =
        await findConversationById(id, userId);

      if (!conversation) {
        res.status(404).json({
          message: 'Percakapan tidak ditemukan.',
        });
        return;
      }

      res.status(200).json(conversation);
    } catch (error) {
      next(error);
    }
  };

export const updateConversationTitle: RequestHandler =
  async (
    req: Request,
    res: Response,
    next: NextFunction
  ): Promise<void> => {
    try {
      const id = getRouteParam(
        req.params.id
      );

      const title =
        typeof req.body.title === 'string'
          ? req.body.title.trim()
          : '';

      if (!id) {
        res.status(400).json({
          message: 'ID percakapan wajib diisi.',
        });
        return;
      }

      if (!title) {
        res.status(400).json({
          message: 'Judul percakapan wajib diisi.',
        });
        return;
      }

      const userId = getAuthenticatedUserId(req);

      const updated =
        await updateConversationTitleService(
          id,
          userId,
          title
        );

      if (!updated) {
        res.status(404).json({
          message: 'Percakapan tidak ditemukan.',
        });
        return;
      }

      res.status(200).json(updated);
    } catch (error) {
      next(error);
    }
  };

export const deleteConversation: RequestHandler =
  async (
    req: Request,
    res: Response,
    next: NextFunction
  ): Promise<void> => {
    try {
      const id = getRouteParam(
        req.params.id
      );

      if (!id) {
        res.status(400).json({
          message: 'ID percakapan wajib diisi.',
        });
        return;
      }

      const userId = getAuthenticatedUserId(req);

      const deleted =
        await removeConversation(id, userId);

      if (!deleted) {
        res.status(404).json({
          message: 'Percakapan tidak ditemukan.',
        });
        return;
      }

      res.status(204).send();
    } catch (error) {
      next(error);
    }
  };