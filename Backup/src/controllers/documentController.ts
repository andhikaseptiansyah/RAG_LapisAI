import type {
  NextFunction,
  Request,
  RequestHandler,
  Response,
} from 'express';

import {
  getDocumentIndexingStatus,
  listDocuments,
  listTrainedDocuments,
  listUploadQueue,
  removeDocument,
  reindexDocument as reindexDocumentService,
  startDocumentIndexing,
  uploadDocuments,
  type DocumentType,
  type IndexedStatus,
  type UploadedDocumentLike,
} from '../services/documentService.js';

type RequestWithFiles = Request & {
  file?: UploadedDocumentLike;
  files?: UploadedDocumentLike[] | Record<string, UploadedDocumentLike[]>;
};

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

const isDocumentType = (
  value: unknown
): value is DocumentType => {
  return (
    value === 'PDF' ||
    value === 'DOCX' ||
    value === 'TXT'
  );
};

const isIndexedStatus = (
  value: unknown
): value is IndexedStatus => {
  return (
    value === 'Indexed' ||
    value === 'Re-indexed' ||
    value === 'Pending'
  );
};

const normalizeFiles = (
  req: RequestWithFiles
): UploadedDocumentLike[] => {
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

export const getDocuments: RequestHandler =
  async (
    req: Request,
    res: Response,
    next: NextFunction
  ): Promise<void> => {
    try {
      const search = getQueryString(
        req.query.search
      );

      const type = isDocumentType(
        req.query.type
      )
        ? req.query.type
        : undefined;

      const status = isIndexedStatus(
        req.query.status
      )
        ? req.query.status
        : undefined;

      const page = parsePositiveInteger(
        req.query.page,
        1
      );

      const limit = parsePositiveInteger(
        req.query.limit,
        10
      );

      const result = await listDocuments({
        search,
        page,
        limit,
        status,
        type,
      });

      res.status(200).json(result);
    } catch (error) {
      next(error);
    }
  };

export const uploadDocument: RequestHandler =
  async (
    req: Request,
    res: Response,
    next: NextFunction
  ): Promise<void> => {
    try {
      const files = normalizeFiles(
        req as RequestWithFiles
      );

      if (files.length === 0) {
        res.status(400).json({
          message: 'Tidak ada file yang diunggah.',
        });
        return;
      }

      const result =
        await uploadDocuments(files);

      res.status(201).json(result);
    } catch (error) {
      next(error);
    }
  };

export const getUploadQueue: RequestHandler =
  async (
    _req: Request,
    res: Response,
    next: NextFunction
  ): Promise<void> => {
    try {
      const result =
        await listUploadQueue();

      res.status(200).json(result);
    } catch (error) {
      next(error);
    }
  };

export const getTrainedDocuments: RequestHandler =
  async (
    _req: Request,
    res: Response,
    next: NextFunction
  ): Promise<void> => {
    try {
      const result =
        await listTrainedDocuments();

      res.status(200).json(result);
    } catch (error) {
      next(error);
    }
  };

export const startIndexing: RequestHandler =
  async (
    req: Request,
    res: Response,
    next: NextFunction
  ): Promise<void> => {
    try {
      const documentIds =
        Array.isArray(req.body.documentIds)
          ? req.body.documentIds.filter(
              (id: unknown) =>
                typeof id === 'string' &&
                id.trim().length > 0
            )
          : undefined;

      const result =
        await startDocumentIndexing(
          documentIds
        );

      res.status(200).json(result);
    } catch (error) {
      next(error);
    }
  };

export const getDocumentById: RequestHandler =
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
          message: 'ID dokumen wajib diisi.',
        });
        return;
      }

      const result =
        await getDocumentIndexingStatus(id);

      if (!result) {
        res.status(404).json({
          message: 'Dokumen tidak ditemukan.',
        });
        return;
      }

      res.status(200).json(result);
    } catch (error) {
      next(error);
    }
  };

export const reindexDocument: RequestHandler =
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
          message: 'ID dokumen wajib diisi.',
        });
        return;
      }

      const result =
        await reindexDocumentService(id);

      if (!result) {
        res.status(404).json({
          message: 'Dokumen tidak ditemukan.',
        });
        return;
      }

      res.status(200).json(result);
    } catch (error) {
      next(error);
    }
  };

export const deleteDocument: RequestHandler =
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
          message: 'ID dokumen wajib diisi.',
        });
        return;
      }

      const deleted =
        await removeDocument(id);

      if (!deleted) {
        res.status(404).json({
          message: 'Dokumen tidak ditemukan.',
        });
        return;
      }

      res.status(204).send();
    } catch (error) {
      next(error);
    }
  };