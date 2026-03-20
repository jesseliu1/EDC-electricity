function parseShowtimeValue(value: unknown): boolean {
  if (Array.isArray(value)) {
    return value.some(parseShowtimeValue)
  }
  if (value === null || value === undefined) {
    return false
  }
  return ['1', 'true', 'yes', 'on'].includes(String(value).trim().toLowerCase())
}

export function isShowtimeMode(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  const params = new URLSearchParams(window.location.search)
  return parseShowtimeValue(params.get('showtime'))
}

export function getShowtimeQueryValue(): 'true' | undefined {
  return isShowtimeMode() ? 'true' : undefined
}

export function mergeShowtimeQuery(query: Record<string, unknown>): Record<string, unknown> {
  const nextQuery = { ...query }
  const showtime = getShowtimeQueryValue()
  if (showtime) {
    nextQuery.showtime = showtime
  } else {
    delete nextQuery.showtime
  }
  return nextQuery
}
