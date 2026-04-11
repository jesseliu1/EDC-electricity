export function ceilAbnormalDurationMinutes(value: number | null | undefined): number | null {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return null
  }
  return Math.max(0, Math.ceil(value))
}

export function formatAbnormalDurationMinutes(
  value: number | null | undefined,
  options?: {
    fallback?: string
    withUnit?: boolean
  }
): string {
  const rounded = ceilAbnormalDurationMinutes(value)
  if (rounded === null) {
    return options?.fallback ?? '--'
  }
  return options?.withUnit === false ? String(rounded) : `${rounded}m`
}
