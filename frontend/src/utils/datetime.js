const DATE_TIME_OPTIONS = {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
}

/**
 * Render an API timestamp for metadata tables.
 *
 * Returns an empty string for missing or unparseable values so callers can
 * keep layout stable instead of printing "Invalid Date" or a raw ISO string.
 */
export function formatDateTime(value, locale = 'zh-CN') {
  if (value === null || value === undefined || value === '') return ''
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat(locale, DATE_TIME_OPTIONS).format(date)
}

export default formatDateTime
