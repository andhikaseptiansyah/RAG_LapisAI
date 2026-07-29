export type DateInput =
  | string
  | number
  | Date
  | null
  | undefined;

const normalizeDateString = (
  value: string
): string => {
  const trimmedValue = value.trim();

  const databaseDatePattern =
    /^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}(:\d{2})?$/;

  if (
    databaseDatePattern.test(trimmedValue)
  ) {
    return trimmedValue.replace(' ', 'T');
  }

  return trimmedValue;
};

export const parseDate = (
  input: DateInput
): Date | null => {
  if (
    input === null ||
    input === undefined ||
    input === ''
  ) {
    return null;
  }

  const date =
    input instanceof Date
      ? new Date(input.getTime())
      : new Date(
          typeof input === 'string'
            ? normalizeDateString(input)
            : input
        );

  if (
    Number.isNaN(date.getTime())
  ) {
    return null;
  }

  return date;
};

export const formatDate = (
  input: DateInput
): string => {
  const date = parseDate(input);

  if (!date) {
    return '-';
  }

  return new Intl.DateTimeFormat(
    'id-ID',
    {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    }
  ).format(date);
};

export const formatDateLong = (
  input: DateInput
): string => {
  const date = parseDate(input);

  if (!date) {
    return '-';
  }

  return new Intl.DateTimeFormat(
    'id-ID',
    {
      weekday: 'long',
      day: '2-digit',
      month: 'long',
      year: 'numeric',
    }
  ).format(date);
};

export const formatTime = (
  input: DateInput
): string => {
  const date = parseDate(input);

  if (!date) {
    return '-';
  }

  return new Intl.DateTimeFormat(
    'id-ID',
    {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }
  ).format(date);
};

export const formatDateTime = (
  input: DateInput
): string => {
  const date = parseDate(input);

  if (!date) {
    return '-';
  }

  return new Intl.DateTimeFormat(
    'id-ID',
    {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }
  ).format(date);
};

export const formatRelativeDate = (
  input: DateInput
): string => {
  const date = parseDate(input);

  if (!date) {
    return '-';
  }

  const now = new Date();

  const differenceMilliseconds =
    date.getTime() - now.getTime();

  const differenceSeconds =
    Math.round(
      differenceMilliseconds / 1000
    );

  const formatter =
    new Intl.RelativeTimeFormat(
      'id-ID',
      {
        numeric: 'auto',
      }
    );

  const absoluteSeconds =
    Math.abs(differenceSeconds);

  if (absoluteSeconds < 60) {
    return formatter.format(
      differenceSeconds,
      'second'
    );
  }

  const differenceMinutes =
    Math.round(
      differenceSeconds / 60
    );

  if (
    Math.abs(differenceMinutes) < 60
  ) {
    return formatter.format(
      differenceMinutes,
      'minute'
    );
  }

  const differenceHours =
    Math.round(
      differenceMinutes / 60
    );

  if (
    Math.abs(differenceHours) < 24
  ) {
    return formatter.format(
      differenceHours,
      'hour'
    );
  }

  const differenceDays =
    Math.round(
      differenceHours / 24
    );

  if (
    Math.abs(differenceDays) < 30
  ) {
    return formatter.format(
      differenceDays,
      'day'
    );
  }

  return formatDate(date);
};