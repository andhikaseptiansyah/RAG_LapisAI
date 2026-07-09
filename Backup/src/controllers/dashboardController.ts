import type {
  NextFunction,
  Request,
  RequestHandler,
  Response,
} from 'express';

import {
  loadChatAnalytics,
  loadDashboard,
  loadDashboardSummary,
  type ChatRange,
} from '../services/dashboardService.js';

const getQueryString = (
  value: unknown
): string | undefined => {
  return typeof value === 'string'
    ? value
    : undefined;
};

const parsePositiveInteger = (
  value: unknown,
  defaultValue: number
): number => {
  const rawValue = getQueryString(value);

  if (!rawValue) {
    return defaultValue;
  }

  const parsed = Number(rawValue);

  if (
    !Number.isInteger(parsed) ||
    parsed <= 0
  ) {
    return defaultValue;
  }

  return parsed;
};

const isChatRange = (
  value: unknown
): value is ChatRange => {
  return (
    value === 'daily' ||
    value === 'weekly' ||
    value === 'monthly' ||
    value === 'yearly'
  );
};

const normalizeRange = (
  value: unknown
): ChatRange => {
  return isChatRange(value)
    ? value
    : 'daily';
};

export const getDashboardOverview: RequestHandler =
  async (
    req: Request,
    res: Response,
    next: NextFunction
  ): Promise<void> => {
    try {
      const range = normalizeRange(
        req.query.range
      );

      const documentSearch =
        getQueryString(
          req.query.documentSearch
        );

      const documentPage =
        parsePositiveInteger(
          req.query.documentPage,
          1
        );

      const documentLimit =
        parsePositiveInteger(
          req.query.documentLimit,
          5
        );

      const result = await loadDashboard({
        range,
        documentSearch,
        documentPage,
        documentLimit,
      });

      res.status(200).json(result);
    } catch (error) {
      next(error);
    }
  };

export const getDashboardSummary: RequestHandler =
  async (
    _req: Request,
    res: Response,
    next: NextFunction
  ): Promise<void> => {
    try {
      const result =
        await loadDashboardSummary();

      res.status(200).json(result);
    } catch (error) {
      next(error);
    }
  };

export const getChatAnalytics: RequestHandler =
  async (
    req: Request,
    res: Response,
    next: NextFunction
  ): Promise<void> => {
    try {
      const range = normalizeRange(
        req.query.range
      );

      const result =
        await loadChatAnalytics(range);

      res.status(200).json(result);
    } catch (error) {
      next(error);
    }
  };