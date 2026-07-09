import fs from 'node:fs';
import path from 'node:path';

import type {
  NextFunction,
  Request,
  RequestHandler,
  Response,
} from 'express';

import multer from 'multer';
import type {
  FileFilterCallback,
} from 'multer';

const uploadRootDir = path.resolve(
  process.cwd(),
  process.env.UPLOAD_DIR ?? 'uploads'
);

const rawUploadDir = path.join(
  uploadRootDir,
  'raw'
);

const tempUploadDir = path.join(
  uploadRootDir,
  'temp'
);

const ensureDirectory = (
  directory: string
): void => {
  if (!fs.existsSync(directory)) {
    fs.mkdirSync(directory, {
      recursive: true,
    });
  }
};

ensureDirectory(rawUploadDir);
ensureDirectory(tempUploadDir);

const maxFileSizeMb = Number(
  process.env.MAX_FILE_SIZE_MB ?? 20
);

const maxFileSizeBytes =
  maxFileSizeMb * 1024 * 1024;

const documentMimeTypes = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
]);

const documentExtensions = new Set([
  '.pdf',
  '.docx',
  '.txt',
]);

const chatMimeTypes = new Set([
  ...documentMimeTypes,
  'image/png',
  'image/jpeg',
  'image/webp',
  'text/csv',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
]);

const chatExtensions = new Set([
  ...documentExtensions,
  '.png',
  '.jpg',
  '.jpeg',
  '.webp',
  '.csv',
  '.xls',
  '.xlsx',
]);

const sanitizeFileName = (
  fileName: string
): string => {
  return fileName
    .replace(/[^\w.\-() ]+/g, '_')
    .replace(/\s+/g, '_')
    .slice(0, 180);
};

const createStorage = (
  destination: string
): multer.StorageEngine => {
  return multer.diskStorage({
    destination: (
      _req,
      _file,
      callback
    ) => {
      callback(null, destination);
    },
    filename: (
      _req,
      file,
      callback
    ) => {
      const safeName = sanitizeFileName(
        file.originalname
      );

      const uniquePrefix =
        `${Date.now()}-${Math.round(Math.random() * 1e9)}`;

      callback(
        null,
        `${uniquePrefix}-${safeName}`
      );
    },
  });
};

const createFileFilter = (
  allowedMimeTypes: Set<string>,
  allowedExtensions: Set<string>
) => {
  return (
    _req: Request,
    file: Express.Multer.File,
    callback: FileFilterCallback
  ): void => {
    const extension = path
      .extname(file.originalname)
      .toLowerCase();

    const isMimeAllowed =
      allowedMimeTypes.has(file.mimetype);

    const isExtensionAllowed =
      allowedExtensions.has(extension);

    if (
      !isMimeAllowed &&
      !isExtensionAllowed
    ) {
      callback(
        new Error(
          `Tipe file tidak didukung: ${file.originalname}`
        )
      );
      return;
    }

    callback(null, true);
  };
};

const documentUploader = multer({
  storage: createStorage(rawUploadDir),
  limits: {
    fileSize: maxFileSizeBytes,
    files: 10,
  },
  fileFilter: createFileFilter(
    documentMimeTypes,
    documentExtensions
  ),
}).fields([
  {
    name: 'file',
    maxCount: 1,
  },
  {
    name: 'files',
    maxCount: 10,
  },
]);

const chatUploader = multer({
  storage: createStorage(tempUploadDir),
  limits: {
    fileSize: maxFileSizeBytes,
    files: 5,
  },
  fileFilter: createFileFilter(
    chatMimeTypes,
    chatExtensions
  ),
}).fields([
  {
    name: 'file',
    maxCount: 1,
  },
  {
    name: 'files',
    maxCount: 5,
  },
  {
    name: 'attachments',
    maxCount: 5,
  },
]);

const handleUploadError = (
  error: unknown,
  res: Response,
  next: NextFunction
): void => {
  if (!error) {
    next();
    return;
  }

  if (error instanceof multer.MulterError) {
    if (error.code === 'LIMIT_FILE_SIZE') {
      res.status(400).json({
        message: `Ukuran file melebihi batas ${maxFileSizeMb} MB.`,
      });
      return;
    }

    res.status(400).json({
      message: error.message,
      code: error.code,
    });
    return;
  }

  next(error);
};

export const uploadDocumentFile: RequestHandler =
  (
    req: Request,
    res: Response,
    next: NextFunction
  ): void => {
    documentUploader(
      req,
      res,
      (error: unknown) => {
        handleUploadError(
          error,
          res,
          next
        );
      }
    );
  };

export const uploadChatFiles: RequestHandler =
  (
    req: Request,
    res: Response,
    next: NextFunction
  ): void => {
    chatUploader(
      req,
      res,
      (error: unknown) => {
        handleUploadError(
          error,
          res,
          next
        );
      }
    );
  };