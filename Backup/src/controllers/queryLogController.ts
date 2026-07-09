import type {
  NextFunction,
  Request,
  RequestHandler,
  Response,
} from 'express';

import {
  findQueryLogById,
  listQueryLogs,
  loadQueryLogsDashboard,
  removeQueryLog,
  type QueryLogStatus,
  type QueryRange,
} from '../services/queryLogService.js';

const getQueryString = (
  value: unknown
): string | undefined => {
  return typeof value === 'string'
    ? value
    : undefined;
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

const isQueryRange = (
  value: unknown
): value is QueryRange => {
  return (
    value === 'daily' ||
    value === 'weekly' ||
    value === 'monthly' ||
    value === 'yearly'
  );
};

const isQueryLogStatus = (
  value: unknown
): value is QueryLogStatus => {
  return (
    value === 'ANSWERED' ||
    value === 'NEED_REVIEW' ||
    value === 'NOT_FOUND' ||
    value === 'ERROR'
  );
};

const normalizeRange = (
  value: unknown
): QueryRange => {
  return isQueryRange(value)
    ? value
    : 'daily';
};

const normalizeStatus = (
  value: unknown
): QueryLogStatus | undefined => {
  return isQueryLogStatus(value)
    ? value
    : undefined;
};

export const getQueryLogs: RequestHandler =
  async (
    req: Request,
    res: Response,
    next: NextFunction
  ): Promise<void> => {
    try {
      const result =
        await listQueryLogs({
          range: normalizeRange(
            req.query.range
          ),
          page: parsePositiveInteger(
            req.query.page,
            1
          ),
          limit: parsePositiveInteger(
            req.query.limit,
            25
          ),
          status: normalizeStatus(
            req.query.status
          ),
          search: getQueryString(
            req.query.search
          ),
        });

      res.status(200).json(result);
    } catch (error) {
      next(error);
    }
  };

export const getQueryLogDashboard: RequestHandler =
  async (
    req: Request,
    res: Response,
    next: NextFunction
  ): Promise<void> => {
    try {
      const result =
        await loadQueryLogsDashboard({
          range: normalizeRange(
            req.query.range
          ),
          page: parsePositiveInteger(
            req.query.page,
            1
          ),
          limit: parsePositiveInteger(
            req.query.limit,
            25
          ),
          status: normalizeStatus(
            req.query.status
          ),
          search: getQueryString(
            req.query.search
          ),
        });

      res.status(200).json(result);
    } catch (error) {
      next(error);
    }
  };

export const getQueryLogById: RequestHandler =
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
          message: 'ID query log wajib diisi.',
        });
        return;
      }

      const result =
        await findQueryLogById(id);

      if (!result) {
        res.status(404).json({
          message: 'Query log tidak ditemukan.',
        });
        return;
      }

      res.status(200).json(result);
    } catch (error) {
      next(error);
    }
  };

export const deleteQueryLog: RequestHandler =
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
          message: 'ID query log wajib diisi.',
        });
        return;
      }

      const deleted =
        await removeQueryLog(id);

      if (!deleted) {
        res.status(404).json({
          message: 'Query log tidak ditemukan.',
        });
        return;
      }

      res.status(204).send();
    } catch (error) {
      next(error);
    }
  };