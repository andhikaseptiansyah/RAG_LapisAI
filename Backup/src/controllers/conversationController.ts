import type {
  NextFunction,
  Request,
  Response,
} from 'express';

import type {
  AuthenticatedRequest,
} from '../middleware/authMiddleware.js';

import {
  listUserConversations,
  getUserConversationWithMessages,
  removeUserConversation,
  updateUserConversation,
} from '../services/conversationService.js';

const getParamId = (
  value: string | string[] | undefined
): string | null => {
  if (Array.isArray(value)) {
    return value[0]?.trim() || null;
  }

  if (typeof value === 'string') {
    return value.trim() || null;
  }

  return null;
};

const getAuthenticatedUserId = (
  req: Request
): string | null => {
  const authReq = req as AuthenticatedRequest;
  return authReq.user?.id ?? null;
};

export const getConversations = async (
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> => {
  try {
    const userId = getAuthenticatedUserId(req);

    if (!userId) {
      res.status(401).json({
        message: 'User belum login.',
      });
      return;
    }

    const conversations =
      await listUserConversations(userId);

    res.json({
      data: conversations,
    });
  } catch (error) {
    next(error);
  }
};

export const getConversationDetail = async (
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> => {
  try {
    const userId = getAuthenticatedUserId(req);

    if (!userId) {
      res.status(401).json({
        message: 'User belum login.',
      });
      return;
    }

    const conversationId =
      getParamId(req.params.id);

    if (!conversationId) {
      res.status(400).json({
        message: 'ID percakapan tidak valid.',
      });
      return;
    }

    const detail =
      await getUserConversationWithMessages(
        userId,
        conversationId
      );

    if (!detail) {
      res.status(404).json({
        message:
          'Percakapan tidak ditemukan atau bukan milik user ini.',
      });
      return;
    }

    res.json({
      data: detail,
    });
  } catch (error) {
    next(error);
  }
};

export const updateConversation = async (
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> => {
  try {
    const userId = getAuthenticatedUserId(req);

    if (!userId) {
      res.status(401).json({
        message: 'User belum login.',
      });
      return;
    }

    const conversationId =
      getParamId(req.params.id);

    if (!conversationId) {
      res.status(400).json({
        message: 'ID percakapan tidak valid.',
      });
      return;
    }

    const title =
      typeof req.body.title === 'string'
        ? req.body.title.trim()
        : undefined;

    const isPinned =
      typeof req.body.is_pinned === 'boolean'
        ? req.body.is_pinned
        : typeof req.body.pinned === 'boolean'
          ? req.body.pinned
          : undefined;

    const language =
      req.body.language === 'ID' ||
      req.body.language === 'EN'
        ? req.body.language
        : undefined;

    if (title !== undefined && !title) {
      res.status(400).json({
        message: 'Judul percakapan wajib diisi.',
      });
      return;
    }

    if (
      title === undefined &&
      isPinned === undefined &&
      language === undefined
    ) {
      res.status(400).json({
        message:
          'Kirim title, is_pinned, atau language untuk memperbarui percakapan.',
      });
      return;
    }

    const updated =
      await updateUserConversation(
        userId,
        conversationId,
        {
          title,
          is_pinned: isPinned,
          language,
        }
      );

    if (!updated) {
      res.status(404).json({
        message:
          'Percakapan tidak ditemukan atau bukan milik user ini.',
      });
      return;
    }

    res.json({
      data: updated,
    });
  } catch (error) {
    next(error);
  }
};

export const deleteConversation = async (
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> => {
  try {
    const userId = getAuthenticatedUserId(req);

    if (!userId) {
      res.status(401).json({
        message: 'User belum login.',
      });
      return;
    }

    const conversationId =
      getParamId(req.params.id);

    if (!conversationId) {
      res.status(400).json({
        message: 'ID percakapan tidak valid.',
      });
      return;
    }

    await removeUserConversation(
      userId,
      conversationId
    );

    res.json({
      message: 'Percakapan berhasil dihapus.',
    });
  } catch (error) {
    next(error);
  }
};
