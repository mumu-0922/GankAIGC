const CHINA_TIME_ZONE = 'Asia/Shanghai';

const normalizeBackendDate = (value) => {
  if (!value) {
    return '';
  }

  const normalized = String(value).trim().replace(' ', 'T');
  if (!normalized) {
    return '';
  }

  const hasExplicitTimezone = normalized.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(normalized);
  if (hasExplicitTimezone) {
    return normalized;
  }

  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(normalized)) {
    return `${normalized}Z`;
  }

  return normalized;
};

const parseBackendDate = (value) => {
  const normalized = normalizeBackendDate(value);
  if (!normalized) {
    return null;
  }

  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
};

export const formatChinaDateTime = (value) => {
  const date = parseBackendDate(value);
  if (!date) {
    return '-';
  }

  return date.toLocaleString('zh-CN', {
    timeZone: CHINA_TIME_ZONE,
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

export const formatChinaDate = (value) => {
  const date = parseBackendDate(value);
  if (!date) {
    return '-';
  }

  return date.toLocaleDateString('zh-CN', {
    timeZone: CHINA_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
};
