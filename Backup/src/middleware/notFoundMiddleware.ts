import type {
  NextFunction,
  Request,
  RequestHandler,
  Response,
} from 'express';

export const notFoundMiddleware: RequestHandler =
  (
    req: Request,
    res: Response,
    _next: NextFunction
  ): void => {
    res.status(404).json({
      code: 'ENDPOINT_NOT_FOUND',
      message: 'Endpoint tidak ditemukan. Periksa method dan URL request.',
      statusCode: 404,
      method: req.method,
      path: req.originalUrl,
      timestamp: new Date().toISOString(),
    });
  };
