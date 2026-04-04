import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'

dayjs.extend(utc)
dayjs.extend(timezone)

const DEFAULT_PLANT_TIMEZONE = 'Asia/Shanghai'
const PLANT_TIMEZONE_STORAGE_KEY = 'asns-plant-timezone'

function readStoredPlantTimezone(): string {
  if (typeof window === 'undefined') {
    return DEFAULT_PLANT_TIMEZONE
  }

  const rawValue = window.localStorage.getItem(PLANT_TIMEZONE_STORAGE_KEY)
  return normalizeTimezone(rawValue)
}

let plantTimezone = readStoredPlantTimezone()

export function normalizeTimezone(value: string | null | undefined): string {
  const candidate = String(value || '').trim() || DEFAULT_PLANT_TIMEZONE
  try {
    new Intl.DateTimeFormat('en-US', { timeZone: candidate })
    return candidate
  } catch {
    return DEFAULT_PLANT_TIMEZONE
  }
}

export function getPlantTimezone() {
  return plantTimezone
}

export function setPlantTimezone(value: string | null | undefined) {
  plantTimezone = normalizeTimezone(value)
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(PLANT_TIMEZONE_STORAGE_KEY, plantTimezone)
  }
  return plantTimezone
}

export function timestampToDate(value: number | null | undefined) {
  if (value === null || value === undefined) return null
  return new Date(Number(value))
}

export function timestampToPlantPickerDate(value: number | null | undefined) {
  if (value === null || value === undefined) return null
  const plantLocalText = dayjs.utc(Number(value)).tz(plantTimezone).format('YYYY-MM-DD HH:mm:ss.SSS')
  const parsed = dayjs(plantLocalText)
  return parsed.isValid() ? parsed.toDate() : null
}

export function toTimestampMs(value: Date | number | string | null | undefined) {
  if (value === null || value === undefined || value === '') return null
  if (typeof value === 'number') return Math.trunc(value)
  if (value instanceof Date) return value.getTime()
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.valueOf() : null
}

export function pickerDateToPlantTimestamp(value: Date | number | string | null | undefined) {
  if (value === null || value === undefined || value === '') return null
  const localValue = dayjs(value)
  if (!localValue.isValid()) return null
  return dayjs.tz(localValue.format('YYYY-MM-DD HH:mm:ss.SSS'), plantTimezone).utc().valueOf()
}

export function formatTimestamp(
  value: number | null | undefined,
  format = 'YYYY-MM-DD HH:mm'
) {
  if (value === null || value === undefined) return ''
  return dayjs.utc(Number(value)).tz(plantTimezone).format(format)
}

export function formatTimestampOrFallback(
  value: number | null | undefined,
  fallback = '--',
  format = 'YYYY-MM-DD HH:mm'
) {
  return value === null || value === undefined ? fallback : formatTimestamp(value, format)
}

function padNumber(value: number) {
  return String(value).padStart(2, '0')
}

function plantCalendarDateText(value: number) {
  return dayjs.utc(Number(value)).tz(plantTimezone).format('YYYY-MM-DD')
}

function calendarDateText(value: Date | number | string) {
  const date = value instanceof Date ? value : new Date(toTimestampMs(value) || 0)
  return `${date.getFullYear()}-${padNumber(date.getMonth() + 1)}-${padNumber(date.getDate())}`
}

export function plantDayRangeFromTimestamp(value: number) {
  const dateText = plantCalendarDateText(value)
  const start = dayjs.tz(`${dateText} 00:00:00`, plantTimezone).utc().valueOf()
  const end = dayjs.tz(`${dateText} 23:59:59.999`, plantTimezone).utc().valueOf()
  return { start, end }
}

export function plantDayRangeFromDate(value: Date | number | string) {
  const dateText = calendarDateText(value)
  const start = dayjs.tz(`${dateText} 00:00:00`, plantTimezone).utc().valueOf()
  const end = dayjs.tz(`${dateText} 23:59:59.999`, plantTimezone).utc().valueOf()
  return { start, end }
}

export function plantDateRangeFromPicker(
  value: [Date, Date] | null
): { start: number; end: number } | null {
  if (!value) return null
  const [startDate, endDate] = value
  if (!startDate || !endDate) return null
  return {
    start: plantDayRangeFromDate(startDate).start,
    end: plantDayRangeFromDate(endDate).end
  }
}
