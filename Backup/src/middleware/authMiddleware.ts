import type {
  NextFunction,
  Request,
  RequestHandler,
  Response,
} from 'express';

import jwt from 'jsonwebtoken';
import type { JwtPayload } from 'jsonwebtoken';

import { env } from '../config/env.js';
import {
  createUnauthorizedError,
} from '../utils/appError.js';

export interface AuthenticatedUser {
  id: string;
  email?: string;
  username?: string;
  name?: string;
  role: string;
}

export type AuthenticatedRequest = Request & {
  user?: AuthenticatedUser;
};

const getJwtSecret = (): string => {
  const secret = env.JWT_SECRET?.trim();

  if (!secret) {
    throw new Error('JWT_SECRET belum diisi di backend/.env.');
  }

  return secret;
};

const extractBearerToken = (
  authorizationHeader: unknown
): string | undefined => {
  if (typeof authorizationHeader !== 'string') {
    return undefined;
  }

  const [scheme, token] = authorizationHeader.split(' ');

  if (scheme !== 'Bearer' || !token?.trim()) {
    return undefined;
  }

  return token.trim();
};

const isJwtPayload = (
  value: string | JwtPayload
): value is JwtPayload => {
  return typeof value !== 'string';
};

const mapJwtPayloadToUser = (
  payload: JwtPayload
): AuthenticatedUser => {
  const id =
    typeof payload.sub === 'string'
      ? payload.sub
      : typeof payload.id === 'string'
        ? payload.id
        : '';

  if (!id) {
    throw createUnauthorizedError(
      'Token tidak memiliki user id. Silakan login ulang.'
    );
  }

  return {
    id,
    email:
      typeof payload.email === 'string'
        ? payload.email
        : undefined,
    username:
      typeof payload.username === 'string'
        ? payload.username
        : undefined,
    name:
      typeof payload.name === 'string'
        ? payload.name
        : undefined,
    role:
      typeof payload.role === 'string'
        ? payload.role
        : 'user',
  };
};

export const authMiddleware: RequestHandler = (
  req: Request,
  _res: Response,
  next: NextFunction
): void => {
  try {
    const token = extractBearerToken(req.headers.authorization);

    if (!token) {
      next(
        createUnauthorizedError(
          'Sesi tidak ditemukan. Silakan login ulang.'
        )
      );
      return;
    }

    const decoded = jwt.verify(token, getJwtSecret());

    if (!isJwtPayload(decoded)) {
      next(
        createUnauthorizedError(
          'Token tidak valid. Silakan login ulang.'
        )
      );
      return;
    }

    const request = req as AuthenticatedRequest;
    request.user = mapJwtPayloadToUser(decoded);

    next();
  } catch (error) {
    if (error instanceof Error && error.message.includes('JWT_SECRET')) {
      next(error);
      return;
    }

    next(
      createUnauthorizedError(
        'Sesi tidak valid atau sudah kedaluwarsa. Silakan login ulang.'
      )
    );
  }
};

export const optionalAuthMiddleware: RequestHandler = (
  req: Request,
  _res: Response,
  next: NextFunction
): void => {
  try {
    const token = extractBearerToken(req.headers.authorization);

    if (!token) {
      next();
      return;
    }

    const decoded = jwt.verify(token, getJwtSecret());

    if (isJwtPayload(decoded)) {
      const request = req as AuthenticatedRequest;
      request.user = mapJwtPayloadToUser(decoded);
    }

    next();
  } catch {
    next();
  }
};
