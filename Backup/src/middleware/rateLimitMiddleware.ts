import type {
  NextFunction,
  Request,
  RequestHandler,
  Response,
} from 'express';

import type {
  AuthenticatedRequest,
} from './authMiddleware.js';

interface RateLimitBucket {
  count: number;
  resetAt: number;
}

interface CreateRateLimitOptions {
  name: string;
  windowMs: number;
  maxRequests: number;
  message: string;
  keyGenerator: (req: Request) => string;
}

const stores = new Map<string, Map<string, RateLimitBucket>>();

const getStore = (
  name: string
): Map<string, RateLimitBucket> => {
  const existingStore = stores.get(name);

  if (existingStore) {
    return existingStore;
  }

  const nextStore = new Map<string, RateLimitBucket>();
  stores.set(name, nextStore);

  return nextStore;
};

const getClientIp = (req: Request): string => {
  const forwardedFor = req.headers['x-forwarded-for'];

  if (typeof forwardedFor === 'string') {
    const firstIp = forwardedFor
      .split(',')
      .map((value) => value.trim())
      .find(Boolean);

    if (firstIp) {
      return firstIp;
    }
  }

  if (Array.isArray(forwardedFor)) {
    const firstIp = forwardedFor
      .flatMap((value) => value.split(','))
      .map((value) => value.trim())
      .find(Boolean);

    if (firstIp) {
      return firstIp;
    }
  }

  return (
    req.ip ??
    req.socket.remoteAddress ??
    'unknown-ip'
  );
};

const getAuthenticatedUserKey = (
  req: Request
): string | null => {
  const request = req as AuthenticatedRequest;

  if (!request.user?.id) {
    return null;
  }

  return `user:${request.user.id}`;
};

const buildRateLimitKey = (
  scope: string,
  rawKey: string
): string => {
  return `${scope}:${rawKey}`;
};

const cleanupExpiredBuckets = (
  store: Map<string, RateLimitBucket>,
  now: number
): void => {
  for (const [key, bucket] of store.entries()) {
    if (bucket.resetAt <= now) {
      store.delete(key);
    }
  }
};

const setRateLimitHeaders = (
  res: Response,
  maxRequests: number,
  remainingRequests: number,
  resetAt: number
): void => {
  res.setHeader(
    'X-RateLimit-Limit',
    String(maxRequests)
  );

  res.setHeader(
    'X-RateLimit-Remaining',
    String(Math.max(remainingRequests, 0))
  );

  res.setHeader(
    'X-RateLimit-Reset',
    String(Math.ceil(resetAt / 1000))
  );
};

const createRateLimitMiddleware = ({
  name,
  windowMs,
  maxRequests,
  message,
  keyGenerator,
}: CreateRateLimitOptions): RequestHandler => {
  const store = getStore(name);

  return (
    req: Request,
    res: Response,
    next: NextFunction
  ): void => {
    const now = Date.now();
    const key = buildRateLimitKey(
      name,
      keyGenerator(req)
    );

    cleanupExpiredBuckets(store, now);

    const existingBucket = store.get(key);

    const bucket =
      existingBucket && existingBucket.resetAt > now
        ? existingBucket
        : {
            count: 0,
            resetAt: now + windowMs,
          };

    bucket.count += 1;
    store.set(key, bucket);

    const remainingRequests =
      maxRequests - bucket.count;

    setRateLimitHeaders(
      res,
      maxRequests,
      remainingRequests,
      bucket.resetAt
    );

    if (bucket.count > maxRequests) {
      const retryAfterSeconds = Math.max(
        1,
        Math.ceil((bucket.resetAt - now) / 1000)
      );

      res.setHeader(
        'Retry-After',
        String(retryAfterSeconds)
      );

      res.status(429).json({
        code: 'RATE_LIMITED',
        message,
        retryAfterSeconds,
      });
      return;
    }

    next();
  };
};

export const chatRateLimitMiddleware =
  createRateLimitMiddleware({
    name: 'chat',
    windowMs: 60 * 1000,
    maxRequests: 20,
    message:
      'Terlalu banyak pesan. Coba lagi beberapa saat.',
    keyGenerator: (req) =>
      getAuthenticatedUserKey(req) ??
      `ip:${getClientIp(req)}`,
  });

export const loginRateLimitMiddleware =
  createRateLimitMiddleware({
    name: 'login',
    windowMs: 10 * 60 * 1000,
    maxRequests: 5,
    message:
      'Terlalu banyak percobaan login. Coba lagi dalam beberapa menit.',
    keyGenerator: (req) => `ip:${getClientIp(req)}`,
  });

export const uploadRateLimitMiddleware =
  createRateLimitMiddleware({
    name: 'upload',
    windowMs: 60 * 60 * 1000,
    maxRequests: 10,
    message:
      'Terlalu banyak upload dokumen. Coba lagi nanti.',
    keyGenerator: (req) =>
      getAuthenticatedUserKey(req) ??
      `ip:${getClientIp(req)}`,
  });
