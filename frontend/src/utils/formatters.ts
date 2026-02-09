// Date, size, duration formatters

export function formatDate(date: string): string {
  // TODO: Format date to locale string
  return new Date(date).toLocaleDateString()
}

export function formatDateTime(date: string): string {
  // TODO: Format date and time
  return new Date(date).toLocaleString()
}

export function formatFileSize(bytes: number): string {
  // TODO: Format bytes to human readable size
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }

  return `${size.toFixed(1)} ${units[unitIndex]}`
}

export function formatDuration(ms: number): string {
  // TODO: Format milliseconds to human readable duration
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}
