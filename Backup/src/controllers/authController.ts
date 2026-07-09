import type {
  NextFunction,
  Request,
  RequestHandler,
  Response,
} from 'express';

import {
  loginUser,
} from '../services/authService.js';

import type {
  AuthenticatedRequest,
} from '../middleware/authMiddleware.js';

export const login: RequestHandler = async (
  req: Request,
  res: Response,
  _next: NextFunction
): Promise<void> => {
  try {
    const username =
      typeof req.body.username === 'string'
        ? req.body.username
        : '';

    const password =
      typeof req.body.password === 'string'
        ? req.body.password
        : '';

    const result = await loginUser({ username, password });

    res.status(200).json(result);
  } catch (error) {
    const message = error instanceof Error
      ? error.message
      : 'Login gagal.';

    res.status(401).json({
      code: 'INVALID_CREDENTIALS',
      message,
      statusCode: 401,
    });
  }
};

export const getMe: RequestHandler = (
  req: Request,
  res: Response,
  _next: NextFunction
): void => {
  const request = req as AuthenticatedRequest;

  if (!request.user) {
    res.status(401).json({
      code: 'AUTH_EXPIRED',
      message: 'Sesi tidak valid. Silakan login ulang.',
      statusCode: 401,
    });
    return;
  }

  res.status(200).json({
    user: request.user,
  });
};
