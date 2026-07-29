const fileSizeUnits = [
  'B',
  'KB',
  'MB',
  'GB',
  'TB',
] as const;

export const formatFileSize = (
  bytes: number,
  decimals = 1
): string => {
  if (
    !Number.isFinite(bytes) ||
    bytes < 0
  ) {
    return '0 B';
  }

  if (bytes === 0) {
    return '0 B';
  }

  const unitIndex = Math.min(
    Math.floor(
      Math.log(bytes) /
        Math.log(1024)
    ),
    fileSizeUnits.length - 1
  );

  const size =
    bytes /
    Math.pow(1024, unitIndex);

  const safeDecimals =
    Math.max(decimals, 0);

  const formattedSize =
    unitIndex === 0
      ? Math.round(size).toString()
      : size.toFixed(safeDecimals);

  return `${formattedSize} ${fileSizeUnits[unitIndex]}`;
};

export const getFileExtension = (
  filename: string
): string => {
  const lastDotIndex =
    filename.lastIndexOf('.');

  if (
    lastDotIndex === -1 ||
    lastDotIndex ===
      filename.length - 1
  ) {
    return '';
  }

  return filename
    .slice(lastDotIndex + 1)
    .toLowerCase();
};

export const isFileSizeAllowed = (
  file: File,
  maximumSizeBytes: number
): boolean => {
  return file.size <= maximumSizeBytes;
};

export const megabytesToBytes = (
  megabytes: number
): number => {
  return megabytes * 1024 * 1024;
};