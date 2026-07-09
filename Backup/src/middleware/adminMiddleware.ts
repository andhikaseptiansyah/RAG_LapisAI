import type {
  NextFunction,
  Request,
  RequestHandler,
  Response,
} from 'express';

import type {
  AuthenticatedRequest,
} from './authMiddleware.js';

const adminRoles = new Set([
  'admin',
  'superadmin',
  'owner',
]);

export const adminMiddleware: RequestHandler =
  (
    req: Request,
    res: Response,
    next: NextFunction
  ): void => {
    const request =
      req as AuthenticatedRequest;

    if (!request.user) {
      res.status(401).json({
        message:
          'Akses ditolak. User belum terautentikasi.',
      });
      return;
    }

    if (
      !adminRoles.has(request.user.role)
    ) {
      res.status(403).json({
        message:
          'Akses ditolak. Role admin diperlukan.',
      });
      return;
    }

    next();
  };